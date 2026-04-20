import json
import hashlib
from enum import Enum
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException

from app.services.llm_service import generate_persona
from app.services.memory_service import extract_memories_ai
from app.utils.chat_parser import parse_chat
from app.services.chat_cleaner import build_clean_payload
from app.services.db import supabase
from app.services.db_memory import (
    save_memories, save_persona, get_persona,
    list_personas, delete_persona, get_memories
)
from app.utils.deps import get_current_user


# ──────────────────────────────────────────
# ENUMS
# ──────────────────────────────────────────

class RelationshipType(str, Enum):
    friend = "friend"
    best_friend = "best_friend"
    crush = "crush"
    girlfriend = "girlfriend"
    ex = "ex"
    colleague = "colleague"

class InteractionDynamic(str, Enum):
    balanced = "balanced"
    dominant_persona = "dominant_persona"
    dominant_user = "dominant_user"
    teasing_dynamic = "teasing_dynamic"

class MessageLength(str, Enum):
    short = "short"
    medium = "medium"
    long = "long"
    mixed = "mixed"

class TypingStyle(str, Enum):
    clean = "clean"
    lowercase = "lowercase"
    broken = "broken"
    fast_typing = "fast_typing"

class SlangLevel(str, Enum):
    none = "none"
    mild = "mild"
    heavy = "heavy"
    genz = "genz"

class EmojiUsage(str, Enum):
    none = "none"
    rare = "rare"
    frequent = "frequent"
    overuse = "overuse"

class DefaultMood(str, Enum):
    neutral = "neutral"
    happy = "happy"
    anxious = "anxious"
    moody = "moody"
    playful = "playful"

class AffectionStyle(str, Enum):
    direct = "direct"
    subtle = "subtle"
    teasing = "teasing"
    avoidant = "avoidant"
    clingy = "clingy"

class HumorType(str, Enum):
    sarcastic = "sarcastic"
    dark = "dark"
    wholesome = "wholesome"
    random = "random"
    none = "none"

class ReplyBehavior(str, Enum):
    instant = "instant"
    delayed = "delayed"
    random = "random"
    seen_zone = "seen_zone"

class ConversationStyle(str, Enum):
    question_based = "question_based"
    statement_based = "statement_based"
    mixed = "mixed"
    dry_replies = "dry_replies"

class InitiativeLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ──────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────

PERSONA_LIMIT = 5  # max personas per user


# ──────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────

def apply_overrides(persona_data: dict, user_inputs: dict) -> dict:
    core = persona_data.get("persona_core", {})
    comm = core.get("communication_style", {})
    emotion = core.get("emotional_model", {})
    behavior = core.get("behavior_patterns", {})
    relationship = persona_data.get("relationship_model", {})

    comm["message_length"]      = user_inputs.get("message_length")
    comm["slang_level"]         = user_inputs.get("slang_level")
    comm["emoji_usage"]         = user_inputs.get("emoji_usage")
    comm["typing_style"]        = user_inputs.get("typing_style")
    emotion["affection_style"]  = user_inputs.get("affection_style")
    emotion["humor_type"]       = user_inputs.get("humor_type")
    emotion["emotional_range"]  = user_inputs.get("default_mood")
    behavior["response_behavior"]  = user_inputs.get("reply_behavior")
    behavior["conversation_style"] = user_inputs.get("conversation_style")
    relationship["with_user"]       = user_inputs.get("relationship_type")
    relationship["interaction_style"] = user_inputs.get("interaction_dynamic")

    persona_data["relationship_model"] = relationship
    return persona_data


def build_user_inputs_fingerprint(persona_name: str, chat_speaker_name: str, user_inputs: dict) -> str:
    """
    Build a deterministic hash from all fields that define a unique persona.
    Same combo of persona_name + chat_speaker_name + all user_inputs = same hash.
    """
    data = {
        "persona_name": persona_name,
        "chat_speaker_name": chat_speaker_name,
        **user_inputs
    }
    canonical = json.dumps(data, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def find_duplicate_persona(user_id: str, fingerprint: str) -> dict | None:
    """
    Check if a persona with the same fingerprint already exists for this user.
    Returns the existing persona record or None.
    """
    result = supabase.table("personas") \
        .select("id, persona_name, created_at") \
        .eq("user_id", user_id) \
        .eq("fingerprint", fingerprint) \
        .execute()

    return result.data[0] if result.data else None


def count_user_personas(user_id: str) -> int:
    result = supabase.table("personas") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .execute()
    return result.count or 0


# ──────────────────────────────────────────
# ROUTER
# ──────────────────────────────────────────

router = APIRouter(prefix="/persona", tags=["Persona"])


# ──────────────────────────────────────────
# POST /persona/create
# ──────────────────────────────────────────

@router.post("/create")
async def create_persona(
    file: UploadFile = File(...),

    user_name: str = Form(...),
    chat_speaker_name: str = Form(...),
    persona_name: str = Form(...),

    relationship_type: RelationshipType = Form(...),
    interaction_dynamic: InteractionDynamic = Form(...),
    message_length: MessageLength = Form(...),
    typing_style: TypingStyle = Form(...),
    slang_level: SlangLevel = Form(...),
    emoji_usage: EmojiUsage = Form(...),
    default_mood: DefaultMood = Form(...),
    affection_style: AffectionStyle = Form(...),
    humor_type: HumorType = Form(...),
    reply_behavior: ReplyBehavior = Form(...),
    conversation_style: ConversationStyle = Form(...),
    initiative_level: InitiativeLevel = Form(...),

    # Gender context — used to generate natural persona replies
    persona_gender: str = Form(...),   # "male" | "female" | "non-binary"
    user_gender: str = Form(...),      # "male" | "female" | "non-binary"

    user_id: str = Depends(get_current_user)
):

    # ─── 1. Persona cap check ───
    current_count = count_user_personas(user_id)
    if current_count >= PERSONA_LIMIT:
        raise HTTPException(
            status_code=403,
            detail=f"Persona limit reached ({PERSONA_LIMIT} max). Delete an existing persona to create a new one."
        )

    # ─── 2. Build user_inputs ───
    user_inputs = {
        "relationship_type":   relationship_type.value,
        "interaction_dynamic": interaction_dynamic.value,
        "message_length":      message_length.value,
        "typing_style":        typing_style.value,
        "slang_level":         slang_level.value,
        "emoji_usage":         emoji_usage.value,
        "default_mood":        default_mood.value,
        "affection_style":     affection_style.value,
        "humor_type":          humor_type.value,
        "reply_behavior":      reply_behavior.value,
        "conversation_style":  conversation_style.value,
        "initiative_level":    initiative_level.value
    }

    # ─── 3. Duplicate check ───
    fingerprint = build_user_inputs_fingerprint(persona_name, chat_speaker_name, user_inputs)
    existing = find_duplicate_persona(user_id, fingerprint)

    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "persona_already_exists",
                "message": f"A persona with these exact settings already exists.",
                "existing_persona_id": existing["id"],
                "created_at": existing["created_at"]
            }
        )

    # ─── 4. Parse + clean chat file ───
    content = await file.read()
    try:
        text_data = content.decode("utf-8")
    except UnicodeDecodeError:
        text_data = content.decode("utf-8", errors="replace")

    parsed_chat = parse_chat(text_data)

    if not parsed_chat:
        raise HTTPException(
            status_code=400,
            detail="Could not parse chat file. Make sure it's a WhatsApp export (.txt format)."
        )

    clean_payload = build_clean_payload(parsed_chat, chat_speaker_name)

    print(f"📊 Chat: {clean_payload['total_messages']} total → "
          f"{clean_payload['total_signals']} signals → "
          f"{clean_payload['signal_count']} sent to LLM (after cap)")

    if clean_payload["signal_count"] < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Only {clean_payload['signal_count']} signal messages found. "
                   f"Check that the speaker name '{chat_speaker_name}' exactly matches the chat export."
        )

    # ─── 5. Generate persona (from capped clean signals) ───
    persona_raw = generate_persona(
        clean_payload=clean_payload,
        user_name=user_name,
        persona_name=chat_speaker_name,
        user_id=user_id
    )

    try:
        persona_data = json.loads(persona_raw)
        persona_data = apply_overrides(persona_data, user_inputs)
    except Exception as e:
        persona_data = {
            "error": "Invalid JSON from LLM",
            "raw_output": persona_raw,
            "details": str(e)
        }

    persona_data["identity"] = {
        "chat_speaker_name": chat_speaker_name,
        "persona_name": persona_name,
        "persona_gender": persona_gender,
        "user_gender": user_gender
    }
    persona_data["user_overrides"] = user_inputs
    persona_data["control_strength"] = "strict"

    # ─── 6. Extract memories (from capped signals) ───
    memories = extract_memories_ai(
        signal_messages=clean_payload["signal_messages"],
        persona_name=chat_speaker_name,
        behavior_context=clean_payload.get("behavior_context", []),
        keyword_metadata=clean_payload.get("keyword_metadata", []),
        user_id=user_id
    )

    # ─── 7. Save persona to DB (with fingerprint) ───
    result = supabase.table("personas").insert({
        "user_id":      user_id,
        "persona_name": persona_name,
        "persona_json": persona_data,
        "fingerprint":  fingerprint
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to save persona to database.")

    persona_id = result.data[0]["id"]

    # ─── 8. Save memories to DB ───
    if memories:
        save_memories(user_id=user_id, persona_id=persona_id, memories=memories)
        print(f"💾 Saved {len(memories)} memories for persona {persona_id}")
    else:
        print("⚠️ No memories extracted.")

    unique_speakers = list(set([msg["speaker"] for msg in parsed_chat]))

    return {
        "persona_id":           persona_id,
        "total_messages":       clean_payload["total_messages"],
        "total_signals":        clean_payload["total_signals"],
        "signal_messages_used": clean_payload["signal_count"],
        "speakers":             unique_speakers,
        "persona":              persona_data,
        "memories_saved":       len(memories),
        "memories_sample":      memories[:5] if memories else [],
        "behavior_metadata": {
            "fillers":       clean_payload.get("behavior_context", [])[:10],
            "top_keywords":  clean_payload.get("keyword_metadata", [])[:10]
        }
    }


# ──────────────────────────────────────────
# GET /persona/list
# ──────────────────────────────────────────

@router.get("/list")
async def list_user_personas(user_id: str = Depends(get_current_user)):
    personas = list_personas(user_id)
    return {
        "personas": personas,
        "count": len(personas),
        "slots_remaining": max(0, PERSONA_LIMIT - len(personas))
    }


# ──────────────────────────────────────────
# GET /persona/{persona_id}
# ──────────────────────────────────────────

@router.get("/{persona_id}")
async def get_single_persona(
    persona_id: str,
    user_id: str = Depends(get_current_user)
):
    persona = get_persona(persona_id, user_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found.")
    return persona


# ──────────────────────────────────────────
# DELETE /persona/{persona_id}
# Also cleans up memories for that persona
# ──────────────────────────────────────────

@router.delete("/{persona_id}")
async def delete_user_persona(
    persona_id: str,
    user_id: str = Depends(get_current_user)
):
    # Verify ownership before delete
    persona = get_persona(persona_id, user_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found or not yours.")

    deleted = delete_persona(persona_id, user_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Delete failed.")

    return {
        "deleted": True,
        "persona_id": persona_id,
        "message": "Persona and all associated memories deleted."
    }