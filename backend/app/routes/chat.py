from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.services.chat_service import generate_reply
from app.services.live_memory_service import extract_live_memory
from app.services.db_memory import (
    get_persona,
    get_all_memories,
    get_recent_context,
    save_conversation_message,
    save_live_memories,
    get_conversation_history
)
from app.utils.deps import get_current_user
from app.services.api_key_service import get_api_key


router = APIRouter(prefix="/chat", tags=["Chat"])


# ──────────────────────────────────────────
# REQUEST / RESPONSE MODELS
# ──────────────────────────────────────────

class ChatRequest(BaseModel):
    persona_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    persona_name: str
    memory_saved: bool


# ──────────────────────────────────────────
# POST /chat/send
# Full flow:
#   1. Load persona from DB
#   2. Load all memories (long-term + live) for this persona
#   3. Load last 10 messages as context window
#   4. Generate reply via LLM
#   5. Save user message + reply to conversations table
#   6. Extract live memory from this exchange
#   7. Save live memory if important enough
# ──────────────────────────────────────────

@router.post("/send", response_model=ChatResponse)
async def send_message(
    body: ChatRequest,
    user_id: str = Depends(get_current_user)
):
    # ─── 1. Load persona ───
    persona = get_persona(body.persona_id, user_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found.")

    persona_json   = persona["persona_json"]
    persona_name   = persona_json.get("identity", {}).get("persona_name", "Persona")
    user_name      = persona_json.get("identity", {}).get("chat_speaker_name", "User")

    # ─── 2. Load memories (long-term + live combined) ───
    all_memories = get_all_memories(body.persona_id, user_id)

    # ─── 3. Load recent conversation context (last 10 messages) ───
    context = get_recent_context(body.persona_id, user_id, limit=10)

    # ─── 0. Ensure user has API key ───
    api_key = get_api_key(user_id)

    if not api_key:
        raise HTTPException(
            status_code=403,
            detail="NO_API_KEY"
        )

    # ─── 4. Generate reply ───
    try:
        reply = generate_reply(
            user_message=body.message,
            persona=persona_json,
            memories=all_memories,
            user_name=user_name,
            persona_name=persona_name,
            conversation_context=context,
            user_id=user_id,
            api_key=api_key
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reply generation failed: {str(e)}")

    # ─── 5. Save both messages to conversation history ───
    save_conversation_message(user_id, body.persona_id, body.message, "user")
    save_conversation_message(user_id, body.persona_id, reply, "persona")

    # ─── 6. Extract live memory from this exchange ───
    live_memories = extract_live_memory(
        user_message=body.message,
        bot_reply=reply,
        persona_name=persona_name,
        user_id=user_id
    )

    # ─── 7. Save live memory if anything meaningful found ───
    memory_saved = False
    if live_memories:
        save_live_memories(user_id, body.persona_id, live_memories)
        memory_saved = True

    return ChatResponse(
        reply=reply,
        persona_name=persona_name,
        memory_saved=memory_saved
    )


# ──────────────────────────────────────────
# GET /chat/history/{persona_id}
# Returns paginated conversation history
# ──────────────────────────────────────────

@router.get("/history/{persona_id}")
async def get_chat_history(
    persona_id: str,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(get_current_user)
):
    # Verify persona ownership
    persona = get_persona(persona_id, user_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found.")

    history = get_conversation_history(persona_id, user_id, limit=limit, offset=offset)

    return {
        "persona_id": persona_id,
        "messages": history,
        "count": len(history),
        "offset": offset,
        "messages": [
        {
            "role": m["sender"],   # map properly
            "content": m["message"]
        }
        for m in history
    ]
    }


# ──────────────────────────────────────────
# DELETE /chat/history/{persona_id}
# Clears conversation history (not memories)
# ──────────────────────────────────────────

@router.delete("/history/{persona_id}")
async def clear_chat_history(
    persona_id: str,
    user_id: str = Depends(get_current_user)
):
    persona = get_persona(persona_id, user_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found.")

    from app.services.db import supabase
    supabase.table("conversations") \
        .delete() \
        .eq("persona_id", persona_id) \
        .eq("user_id", user_id) \
        .execute()

    return {"cleared": True, "persona_id": persona_id}