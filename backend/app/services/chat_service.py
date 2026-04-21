import re
from app.services.llm_service import call_llm


def generate_reply(
    user_message: str,
    persona: dict,
    memories: list,
    user_name: str,
    persona_name: str,
    conversation_context: list = None,
    user_id: str = None
) -> str:
    """
    Generate a WhatsApp reply as the persona.

    Prompt design principles:
    - Examples FIRST — real messages before any instruction
    - Minimal instructions — 5 strict rules only
    - No classifier, no maps, no behavioral flags
    - 70b infers tone/intent from examples naturally
    - Anti-repetition guard using last persona reply
    """

    # ── Extract persona layers ──
    identity     = persona.get("identity", {})
    display_name = identity.get("persona_name", persona_name)
    real_name    = identity.get("chat_speaker_name", persona_name)
    persona_gender = identity.get("persona_gender", "person")
    user_gender    = identity.get("user_gender", "person")

    core    = persona.get("persona_core", {})
    rel     = persona.get("relationship_context", {})

    # ── Relationship ──
    relationship = rel.get("type", "friend").replace("_", " ")
    dynamic      = rel.get("dynamic", "")
    tone_note    = rel.get("tone_with_user", "")

    # ── Traits with evidence — this is the persona fingerprint ──
    traits = core.get("personality_traits", [])
    fingerprint = core.get("communication_fingerprint", {})
    casual_replies = core.get("casual_replies", [])

    # Build trait block: "trait (evidence: 'msg1', 'msg2')"
    trait_lines = []
    for t in traits[:5]:
        trait = t.get("trait", "")
        evidence = t.get("evidence", [])
        if trait and evidence:
            ev_str = ", ".join(f'"{e}"' for e in evidence[:3])
            trait_lines.append(f"- {trait} (e.g. {ev_str})")
        elif trait:
            trait_lines.append(f"- {trait}")
    traits_block = "\n".join(trait_lines) if trait_lines else "- casual, direct"

    # ── Communication fingerprint block ──
    fp_lines = []
    if fingerprint.get("typical_message"):
        fp_lines.append(f'Typical message: "{fingerprint["typical_message"]}"')
    if fingerprint.get("emoji_pattern"):
        fp_lines.append(f"Emojis: {fingerprint['emoji_pattern']}")
    if fingerprint.get("language_mix"):
        fp_lines.append(f"Language: {fingerprint['language_mix']}")
    if fingerprint.get("message_length"):
        fp_lines.append(f"Length: {fingerprint['message_length']}")
    if fingerprint.get("punctuation_style"):
        fp_lines.append(f"Punctuation: {fingerprint['punctuation_style']}")
    fp_block = "\n".join(fp_lines) if fp_lines else ""

    # ── Casual reply samples (for greeting/small talk) ──
    # These are actual messages she sent — model imitates directly
    if casual_replies:
        casual_block = "\n".join(f'  "{r}"' for r in casual_replies[:10])
    else:
        casual_block = ""

    # ── Build conversation context (last 6 messages max) ──
    context_lines = []
    last_persona_reply = ""
    if conversation_context:
        recent = conversation_context[-6:]
        for msg in recent:
            label = user_name if msg["sender"] == "user" else display_name
            context_lines.append(f"{label}: {msg['message']}")
        # Extract last persona reply for anti-repetition guard
        for msg in reversed(conversation_context):
            if msg["sender"] == "persona":
                last_persona_reply = msg["message"]
                break

    # ── Relevant memories — only if keywords overlap significantly ──
    # Simplified scoring: word overlap only, no fallback
    relevant_memories = []
    if memories:
        msg_words = set(user_message.lower().split())
        for m in memories:
            mem_words = set(m.get("text", "").lower().split())
            if len(msg_words & mem_words) >= 2:  # at least 2 words overlap
                relevant_memories.append(m)
        relevant_memories = relevant_memories[:3]

    # ──────────────────────────────────────────
    # PROMPT — examples first, rules last, nothing else
    # ──────────────────────────────────────────

    parts = []

    # 1. Identity — one line
    parts += [
        f"You are {display_name}, a {persona_gender}. "
        f"You are texting your {relationship} {user_name} (a {user_gender}) on WhatsApp. "
        f"You are a real person. You are NOT an AI.",
        "",
    ]

    # 2. Who you are — traits with real evidence
    parts += [
        "YOUR PERSONALITY (with real examples of how you talk):",
        traits_block,
        "",
    ]

    # 3. How you text — fingerprint
    if fp_block:
        parts += [
            "HOW YOU TEXT:",
            fp_block,
            "",
        ]

    # 4. Casual reply samples — most important for hi/hello/reaction messages
    if casual_block:
        parts += [
            "HOW YOU RESPOND TO CASUAL MESSAGES (these are your actual replies):",
            casual_block,
            "",
        ]

    # 5. Relationship context
    if dynamic or tone_note:
        rel_lines = []
        if dynamic:
            rel_lines.append(f"Dynamic: {dynamic}")
        if tone_note:
            rel_lines.append(f"Your tone with {user_name}: {tone_note}")
        parts += ["RELATIONSHIP:", "\n".join(rel_lines), ""]

    # 6. Memory — only if actually relevant, no section if empty
    if relevant_memories:
        mem_lines = "\n".join(f"- {m['text']}" for m in relevant_memories)
        parts += [
            "RELEVANT CONTEXT (use only if it fits naturally):",
            mem_lines,
            "",
        ]

    # 7. Recent conversation
    if context_lines:
        parts += [
            "RECENT CHAT:",
            "\n".join(context_lines),
            "",
        ]

    # 8. Anti-repetition guard
    if last_persona_reply:
        parts += [
            f"YOUR LAST REPLY WAS: \"{last_persona_reply}\"",
            "Do NOT repeat or closely mirror this.",
            "",
        ]

    # 9. Strict rules — 5 only
    parts += [
        "RULES:",
        "1. Reply ONLY to the last message — do not introduce new topics",
        "2. Do NOT assume or invent context that was not mentioned",
        "3. Match your texting style from the examples above exactly",
        "4. Keep it short — 1 to 2 lines unless the message needs more",
        "5. If the message is a greeting or casual, reply casually — do not ask about projects, studies, or anything unprompted",
        "",
        f"{user_name}: {user_message}",
        f"{display_name}:",
    ]

    prompt = "\n".join(parts)

    try:
        reply = call_llm(prompt, user_id=user_id, temperature=0.65)
        return reply.strip()
    except PermissionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Reply generation failed: {str(e)}")