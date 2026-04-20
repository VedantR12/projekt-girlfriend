from app.services.db import supabase
from datetime import datetime

# ──────────────────────────────────────────
# DATABASE MEMORY OPERATIONS
# All Supabase table operations for:
#   - personas
#   - memories (from uploaded chat)
#   - live_memories (from active conversations)
#   - conversations (chat history)
# ──────────────────────────────────────────


# ─── PERSONA OPS ───

def save_persona(user_id: str, persona_name: str, persona_json: dict) -> dict:
    """Insert persona and return the created record."""
    result = supabase.table("personas").insert({
        "user_id": user_id,
        "persona_name": persona_name,
        "persona_json": persona_json
    }).execute()

    return result.data[0] if result.data else None


def get_persona(persona_id: str, user_id: str) -> dict | None:
    """Get a single persona by ID (with user_id ownership check)."""
    result = supabase.table("personas") \
        .select("*") \
        .eq("id", persona_id) \
        .eq("user_id", user_id) \
        .execute()

    return result.data[0] if result.data else None


def list_personas(user_id: str) -> list:
    """List all personas for a user."""
    result = supabase.table("personas") \
        .select("id, persona_name, created_at") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()

    return result.data or []


def delete_persona(persona_id: str, user_id: str) -> bool:
    """Delete a persona and all related data (cascades via FK)."""
    result = supabase.table("personas") \
        .delete() \
        .eq("id", persona_id) \
        .eq("user_id", user_id) \
        .execute()

    return bool(result.data)


# ─── MEMORY OPS (from uploaded chat) ───

def save_memories(user_id: str, persona_id: str, memories: list):
    """Bulk insert memories extracted from uploaded chat."""
    if not memories:
        return

    rows = []
    for m in memories:
        rows.append({
            "user_id": user_id,
            "persona_id": persona_id,
            "text": m["text"],
            "type": m.get("type", "event"),
            "importance": m.get("importance", 0.7)
        })

    supabase.table("memories").insert(rows).execute()


def get_memories(persona_id: str, user_id: str) -> list:
    """Get all memories for a persona."""
    result = supabase.table("memories") \
        .select("*") \
        .eq("persona_id", persona_id) \
        .eq("user_id", user_id) \
        .order("importance", desc=True) \
        .execute()

    return result.data or []


# ─── LIVE MEMORY OPS (from active conversations) ───

def save_live_memories(user_id: str, persona_id: str, memories: list):
    """Bulk insert live memories from chat interactions."""
    if not memories:
        return

    # Cap at 100 live memories per persona
    existing = supabase.table("live_memories") \
        .select("id", count="exact") \
        .eq("persona_id", persona_id) \
        .execute()

    current_count = existing.count or 0

    if current_count >= 100:
        # Delete oldest to make room
        overflow = current_count + len(memories) - 100
        if overflow > 0:
            oldest = supabase.table("live_memories") \
                .select("id") \
                .eq("persona_id", persona_id) \
                .order("created_at", desc=False) \
                .limit(overflow) \
                .execute()

            if oldest.data:
                ids = [r["id"] for r in oldest.data]
                for old_id in ids:
                    supabase.table("live_memories") \
                        .delete() \
                        .eq("id", old_id) \
                        .execute()

    rows = []
    for m in memories:
        rows.append({
            "user_id": user_id,
            "persona_id": persona_id,
            "text": m["text"],
            "type": m.get("type", "event"),
            "importance": m.get("importance", 0.7)
        })

    supabase.table("live_memories").insert(rows).execute()


def get_live_memories(persona_id: str, user_id: str) -> list:
    """Get all live memories for a persona."""
    result = supabase.table("live_memories") \
        .select("*") \
        .eq("persona_id", persona_id) \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()

    return result.data or []


from datetime import datetime

def get_all_memories(persona_id: str, user_id: str) -> list:
    old = get_memories(persona_id, user_id)
    live = get_live_memories(persona_id, user_id)

    now = datetime.utcnow()

    # ─── Tag + enrich old memories ───
    for m in old:
        m["source"] = "long_term"
        m["recency_score"] = 0.1  # old memories are stable but less dynamic

    # ─── Tag + enrich live memories ───
    for m in live:
        m["source"] = "live"

        created_at = m.get("created_at")

        try:
            if created_at:
                created_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                age_hours = (now - created_time).total_seconds() / 3600

                if age_hours < 6:
                    m["recency_score"] = 1.0
                elif age_hours < 24:
                    m["recency_score"] = 0.8
                elif age_hours < 72:
                    m["recency_score"] = 0.5
                else:
                    m["recency_score"] = 0.2
            else:
                m["recency_score"] = 0.3
        except:
            m["recency_score"] = 0.3

    return old + live


# ─── CONVERSATION OPS ───

def save_conversation_message(user_id: str, persona_id: str, message: str, sender: str):
    """
    Save a single message to conversation history.
    sender = 'user' or 'persona'
    """
    supabase.table("conversations").insert({
        "user_id": user_id,
        "persona_id": persona_id,
        "message": message,
        "sender": sender
    }).execute()


def get_conversation_history(persona_id: str, user_id: str, limit: int = 50, offset: int = 0) -> list:
    """
    Get conversation history for a persona, ordered by time.
    Most recent last (chronological order for display).
    """
    result = supabase.table("conversations") \
        .select("*") \
        .eq("persona_id", persona_id) \
        .eq("user_id", user_id) \
        .order("created_at", desc=False) \
        .range(offset, offset + limit - 1) \
        .execute()

    return result.data or []


def get_recent_context(persona_id: str, user_id: str, limit: int = 10) -> list:
    """
    Get last N messages for context window in chat prompt.
    Returns in chronological order.
    """
    result = supabase.table("conversations") \
        .select("message, sender") \
        .eq("persona_id", persona_id) \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .limit(limit) \
        .execute()

    # Reverse to get chronological order
    messages = result.data or []
    messages.reverse()
    return messages