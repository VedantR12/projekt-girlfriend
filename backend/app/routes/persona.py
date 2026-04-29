import json
import hashlib
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException

from app.services.llm_service import generate_persona
from app.services.memory_service import extract_memories_ai
from app.utils.chat_parser import parse_chat
from app.services.chat_cleaner import build_signal_bundle
from app.services.db import supabase
from app.services.db_memory import (
    save_memories, save_persona, get_persona,
    list_personas, delete_persona
)
from app.utils.deps import get_current_user

router = APIRouter(prefix="/persona", tags=["Persona"])

PERSONA_LIMIT = 5


# ──────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────

def build_fingerprint(persona_name: str, chat_speaker_name: str, relationship_type: str) -> str:
    """
    Fingerprint based on the 3 user-controlled fields only.
    Same speaker + same persona name + same relationship = duplicate.
    """
    data = {
        "persona_name":      persona_name,
        "chat_speaker_name": chat_speaker_name,
        "relationship_type": relationship_type,
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def find_duplicate(user_id: str, fingerprint: str) -> dict | None:
    result = supabase.table("personas") \
        .select("id, persona_name, created_at") \
        .eq("user_id", user_id) \
        .eq("fingerprint", fingerprint) \
        .execute()
    return result.data[0] if result.data else None


def count_personas(user_id: str) -> int:
    result = supabase.table("personas") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .execute()
    return result.count or 0


# ──────────────────────────────────────────
# POST /persona/create
#
# User provides only:
#   - chat.txt file
#   - chat_speaker_name (exact name as in chat export)
#   - persona_name (display name)
#   - relationship_type
#   - persona_gender
#   - user_gender
#
# Everything else extracted from the chat by LLM.
# ──────────────────────────────────────────

VALID_RELATIONSHIPS = {
    "friend", "best_friend", "crush",
    "girlfriend", "boyfriend", "ex", "colleague"
}

VALID_GENDERS = {"male", "female", "non-binary"}

@router.post("/{id}/avatar")
async def update_avatar(
    id: str,
    avatar: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    # check ownership
    persona = get_persona(id, user_id)
    if not persona:
        raise HTTPException(404, "Persona not found")

    file_bytes = await avatar.read()
    file_path = f"avatars/{uuid4()}.jpg"

    supabase.storage.from_("avatars").upload(file_path, file_bytes)
    avatar_url = supabase.storage.from_("avatars").get_public_url(file_path)

    supabase.table("personas").update({
        "avatar_url": avatar_url
    }).eq("id", id).execute()

    return {"avatar_url": avatar_url}


@router.post("/create")
async def create_persona(
    file: UploadFile = File(...),

    chat_speaker_name: str = Form(...),
    persona_name:      str = Form(...),
    relationship_type: str = Form(...),
    persona_gender:    str = Form(...),
    user_gender:       str = Form(...),
    user_name: str = Form(default="User"),
    avatar: UploadFile = File(None),
    user_id: str = Depends(get_current_user)
):
    # ── Validate ──
    if relationship_type not in VALID_RELATIONSHIPS:
        raise HTTPException(400, f"Invalid relationship_type. Valid: {VALID_RELATIONSHIPS}")
    if persona_gender not in VALID_GENDERS:
        raise HTTPException(400, f"Invalid persona_gender. Valid: {VALID_GENDERS}")
    if user_gender not in VALID_GENDERS:
        raise HTTPException(400, f"Invalid user_gender. Valid: {VALID_GENDERS}")
    avatar_url = None

    if avatar:
        file_bytes = await avatar.read()
        file_path = f"avatars/{uuid4()}.jpg"

        supabase.storage.from_("avatars").upload(file_path, file_bytes)
        avatar_url = supabase.storage.from_("avatars").get_public_url(file_path)

    # ── Persona cap ──
    if count_personas(user_id) >= PERSONA_LIMIT:
        raise HTTPException(403, f"Persona limit reached ({PERSONA_LIMIT} max). Delete one to continue.")

    # ── Duplicate check ──
    fingerprint = build_fingerprint(persona_name, chat_speaker_name, relationship_type)
    existing = find_duplicate(user_id, fingerprint)
    if existing:
        raise HTTPException(409, {
            "error": "persona_already_exists",
            "message": "A persona with this name, speaker, and relationship already exists.",
            "existing_persona_id": existing["id"],
            "created_at": existing["created_at"]
        })

    # ── Parse chat file ──
    content = await file.read()
    try:
        text_data = content.decode("utf-8")
    except UnicodeDecodeError:
        text_data = content.decode("utf-8", errors="replace")

    parsed_chat = parse_chat(text_data)
    if not parsed_chat:
        raise HTTPException(400, "Could not parse chat file. Must be a WhatsApp export (.txt).")

    # ── Build signal bundle ──
    signal_bundle = build_signal_bundle(parsed_chat, chat_speaker_name)

    if signal_bundle["target_signals"] < 10:
        raise HTTPException(400,
            f"Only {signal_bundle['target_signals']} signal messages found for '{chat_speaker_name}'. "
            "Check that the speaker name exactly matches the chat export."
        )

    # ── Generate persona ──
    persona_raw = generate_persona(
        signal_bundle=signal_bundle,
        persona_name=chat_speaker_name,
        user_name=user_name,
        relationship_type=relationship_type.replace("_", " "),
        persona_gender=persona_gender,
        user_gender=user_gender,
        user_id=user_id
    )

    try:
        persona_data = json.loads(persona_raw)
    except Exception as e:
        persona_data = {
            "error": "Invalid JSON from LLM",
            "raw_output": persona_raw,
            "details": str(e)
        }

    # ── Attach identity ──
    persona_data["identity"] = {
        "chat_speaker_name": chat_speaker_name,
        "persona_name":      persona_name,
        "persona_gender":    persona_gender,
        "user_gender":       user_gender,
        "relationship_type": relationship_type,
        "user_name":         user_name 
    }

    # ── Extract memories from signal bundle ──
    memories = extract_memories_ai(
        signal_messages=signal_bundle["trait_signals"],
        persona_name=chat_speaker_name,
        behavior_context=signal_bundle.get("filler_tokens", []),
        keyword_metadata=signal_bundle.get("top_keywords", []),
        user_id=user_id
    )

    # ── Save to DB ──
    result = supabase.table("personas").insert({
        "user_id":      user_id,
        "persona_name": persona_name,
        "persona_json": persona_data,
        "fingerprint":  fingerprint,
        "avatar_url": avatar_url
    }).execute()

    if not result.data:
        raise HTTPException(500, "Failed to save persona to database.")

    persona_id = result.data[0]["id"]

    if memories:
        save_memories(user_id=user_id, persona_id=persona_id, memories=memories)

    speakers = list(set(m["speaker"] for m in parsed_chat))

    return {
        "persona_id":       persona_id,
        "total_messages":   signal_bundle["total_messages"],
        "signals_used":     len(signal_bundle["trait_signals"]),
        "casual_samples":   len(signal_bundle["casual_samples"]),
        "memories_saved":   len(memories),
        "speakers":         speakers,
        "persona":          persona_data,
    }


# ──────────────────────────────────────────
# GET /persona/list
# ──────────────────────────────────────────

@router.get("/list")
async def list_user_personas(user_id: str = Depends(get_current_user)):
    personas = list_personas(user_id)
    return {
        "personas":        personas,
        "count":           len(personas),
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
        raise HTTPException(404, "Persona not found.")
    return persona


# ──────────────────────────────────────────
# DELETE /persona/{persona_id}
# ──────────────────────────────────────────

@router.delete("/{persona_id}")
async def delete_user_persona(
    persona_id: str,
    user_id: str = Depends(get_current_user)
):
    persona = get_persona(persona_id, user_id)
    if not persona:
        raise HTTPException(404, "Persona not found or not yours.")

    deleted = delete_persona(persona_id, user_id)
    if not deleted:
        raise HTTPException(500, "Delete failed.")

    return {
        "deleted":    True,
        "persona_id": persona_id,
        "message":    "Persona and all associated memories deleted."
    }