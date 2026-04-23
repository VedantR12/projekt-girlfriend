import re
from app.services.llm_service import call_llm

EMOTIONAL_WORDS = {
    "sad", "cry", "miss", "hurt", "bura", "laga", "lonely",
    "scared", "anxious", "stressed", "tired", "upset",
    "happy", "excited", "proud", "love", "angry", "gussa",
    "😭", "😢", "🥺", "😤", "❤", "💔", "😠"
}


def _strip_prefix(text: str) -> str:
    """Strip 'SpeakerName: ' prefix if model included it in stored data."""
    if ": " in text[:50]:
        parts = text.split(": ", 1)
        if len(parts[0].strip()) < 40:
            return parts[1].strip()
    return text.strip()


def _is_emotional(message: str) -> bool:
    msg_lower = message.lower()
    return any(w in msg_lower for w in EMOTIONAL_WORDS)


def generate_reply(
    user_message: str,
    persona: dict,
    memories: list,
    user_name: str,
    persona_name: str,
    conversation_context: list = None,
    user_id: str = None
) -> str:

    # ── Extract persona ──
    identity       = persona.get("identity", {})
    display_name   = identity.get("persona_name", persona_name)
    persona_gender = identity.get("persona_gender", "person")
    user_gender    = identity.get("user_gender", "person")

    core = persona.get("persona_core", {})
    rel  = persona.get("relationship_context", {})

    traits         = core.get("personality_traits", [])
    fingerprint    = core.get("communication_fingerprint", {})
    casual_replies = core.get("casual_replies", [])
    tone_samples   = core.get("tone_samples", [])
    typing_quirks  = core.get("typing_quirks", "")

    relationship        = rel.get("type", "friend").replace("_", " ")
    relationship_detail = rel.get("relationship_detail", "") or rel.get("dynamic", "")
    tone_with_user      = rel.get("tone_with_user", "")
    unknown_topics      = rel.get("unknown_topics", [])

    # ── Traits — 5 traits × 3 evidence, strip prefixes ──
    trait_lines = []
    for t in traits[:5]:
        trait    = t.get("trait", "")
        evidence = [_strip_prefix(e) for e in t.get("evidence", [])[:3]]
        if trait and evidence:
            trait_lines.append(f"- {trait} (e.g. {', '.join(repr(e) for e in evidence)})")
        elif trait:
            trait_lines.append(f"- {trait}")
    traits_block = "\n".join(trait_lines) if trait_lines else "- casual and direct"

    # ── Full fingerprint ──
    fp_lines = []
    for key, label in [
        ("typical_message", "Typical"),
        ("emoji_pattern", "Emojis"),
        ("language_mix", "Language"),
        ("message_length", "Length"),
        ("punctuation_style", "Punctuation"),
    ]:
        val = fingerprint.get(key, "")
        if val:
            fp_lines.append(f"{label}: {_strip_prefix(val) if key == 'typical_message' else val}")
    fp_block = "\n".join(fp_lines)

    # ── Casual replies — 10 samples ──
    clean_casual = [_strip_prefix(r) for r in casual_replies if r.strip()]
    casual_block = "\n".join(f'  "{r}"' for r in clean_casual[:10])

    # ── Tone samples — real conversation flow ──
    tone_block = ""
    if tone_samples:
        lines = []
        for s in tone_samples[:3]:
            trigger  = _strip_prefix(s.get("trigger", ""))
            response = _strip_prefix(s.get("response", ""))
            followup = s.get("followup")
            if trigger and response:
                lines.append(f'  {user_name}: "{trigger}"')
                lines.append(f'  {display_name}: "{response}"')
                if followup and followup != "null":
                    lines.append(f'  {display_name}: "{_strip_prefix(followup)}"')
                lines.append("")
        tone_block = "\n".join(lines)

    # ── Context — 10 messages ──
    context_lines = []
    last_persona_reply = ""
    if conversation_context:
        for msg in conversation_context[-10:]:
            label = user_name if msg["sender"] == "user" else display_name
            clean_msg = _strip_prefix(msg["message"])
            context_lines.append(f"{label}: {clean_msg}")
        for msg in reversed(conversation_context):
            if msg["sender"] == "persona":
                last_persona_reply = _strip_prefix(msg["message"])
                break

    # Memory — requires strong match (3+ word overlap, or emotional+1 word)
    # Max 2 memories — prevents flooding the prompt with unrelated context
    relevant_memories = []
    if memories:
        msg_words = set(user_message.lower().split())
        is_emo = _is_emotional(user_message)
        scored = []
        for m in memories:
            mem_text  = m.get("text", "")
            mem_words = set(mem_text.lower().split())
            overlap   = len(msg_words & mem_words)
            emo_match = is_emo and _is_emotional(mem_text)
            if overlap >= 3 or (emo_match and overlap >= 1):
                scored.append((overlap, m))
        scored.sort(reverse=True, key=lambda x: x[0])
        relevant_memories = [m for _, m in scored[:2]]

    # ── Anti-hallucination anchor ──
    unknown_block = ""
    if unknown_topics:
        unknown_block = f"Topics NEVER discussed — do NOT bring up: {', '.join(unknown_topics[:5])}"

    # ──────────────────────────────────────
    # PROMPT — ~950 tokens, examples first
    # ──────────────────────────────────────
    parts = []

    # Identity
    parts += [
        f"You are {display_name} ({persona_gender}), texting your {relationship} "
        f"{user_name} ({user_gender}) on WhatsApp. You are a real person. Not an AI.",
        "",
    ]

    # Personality
    parts += ["YOUR PERSONALITY:", traits_block, ""]

    # Style fingerprint
    if fp_block:
        parts += ["HOW YOU TEXT:", fp_block]
    if typing_quirks and typing_quirks not in ("none detected", ""):
        parts += [f"Typing quirks: {typing_quirks}"]
    parts += [""]

    # Casual replies
    if casual_block:
        parts += [
            "YOUR ACTUAL CASUAL REPLIES (match this style for greetings and small talk):",
            casual_block, "",
        ]

    # Tone samples — response flow
    if tone_block:
        parts += ["HOW YOU RESPOND IN CONVERSATION (real exchanges):", tone_block]

    # Relationship detail
    rel_lines = []
    if relationship_detail:
        rel_lines.append(f"Dynamic: {relationship_detail}")
    if tone_with_user:
        rel_lines.append(f"Your tone with {user_name}: {tone_with_user}")
    if rel_lines:
        parts += ["RELATIONSHIP:", "\n".join(rel_lines), ""]

    # Memory
    if relevant_memories:
                parts += [
            "BACKGROUND KNOWLEDGE (you know these FACTS — never repeat these exact sentences. Always rephrase completely. Use only the MEANING, not the words.):",
            "\n".join(f"- {m['text']}" for m in relevant_memories),
            "",
        ]

    # Anti-hallucination
    if unknown_block:
        parts += [unknown_block, ""]

    # Anti-repetition
    if last_persona_reply:
        parts += [
            f'YOUR LAST REPLY: "{last_persona_reply}"',
            "Do NOT repeat or closely mirror this.",
            "",
        ]

    # Recent conversation
    if context_lines:
        parts += ["RECENT CHAT:", "\n".join(context_lines), ""]

    # 5 strict rules
    parts += [
        "RULES:",
        "1. Reply ONLY to the last message — do not introduce new topics",
        "2. Do NOT assume or invent context not in the conversation",
        "3. Match your texting style from the examples above exactly",
        "4. Keep it 1-2 lines unless the message genuinely needs more",
        "5. If message is casual/greeting, reply casually — no topics, no advice, nothing unprompted",
        "",
        f"{user_name}: {user_message}",
        f"{display_name}:",
    ]

    prompt = "\n".join(parts)

    try:
        reply = call_llm(prompt, user_id=user_id, temperature=0.65)
        reply = reply.strip()
        return _strip_prefix(reply)
    except PermissionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Reply generation failed: {str(e)}")
