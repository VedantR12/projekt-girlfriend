import json
import re
from app.services.llm_service import call_llm


# ──────────────────────────────────────────
# Live Memory Extraction
# Called after EVERY chat exchange
# Learns from active conversations
# ──────────────────────────────────────────

def extract_live_memory(
    user_message: str,
    bot_reply: str,
    persona_name: str,
    user_id: str = None
) -> list:
    """
    Extract meaningful long-term memory from a single chat exchange.
    Returns filtered list of memory objects.
    """

    prompt = f"""
You detect IMPORTANT long-term memory from a single conversation exchange.

Target: {persona_name}

RULES:
- Extract ONLY if it's genuinely important
- Ignore casual chat, small talk, greetings
- Ignore temporary emotions ("I'm tired today")
- Ignore obvious facts ("the sky is blue")

Focus on:
- concrete plans or decisions
- preferences revealed for the first time
- repeated behaviors being confirmed
- relationship status changes
- beliefs or strong opinions expressed

Return ONLY JSON list (no explanation, no markdown):

[
  {{
    "text": "",
    "type": "event / belief / opinion / relationship / habit",
    "importance": 0.0 to 1.0
  }}
]

If nothing important — return empty list: []

Conversation:
User: {user_message}
{persona_name}: {bot_reply}
"""

    try:
        raw = call_llm(prompt, user_id=user_id, temperature=0.1, use_fast_model=True)
    except Exception:
        return []

    # ─── Clean and parse ───
    clean = re.sub(r"```json|```", "", raw)
    start = clean.find("[")
    end = clean.rfind("]") + 1

    if start == -1 or end <= start:
        return []

    clean = clean[start:end].strip()

    try:
        memories = json.loads(clean)

        # ─── Strict filter ───
        filtered = [
            m for m in memories
            if m.get("importance", 0) >= 0.7
            and len(m.get("text", "").split()) > 6
            and not any(w in m.get("text", "").lower() for w in [
                "seems", "probably", "maybe", "might",
                "casual", "general", "mentions"
            ])
        ]

        return filtered

    except Exception:
        return []