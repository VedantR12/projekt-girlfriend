import json
import re
from app.services.llm_service import call_llm


# ──────────────────────────────────────────
# MESSAGE CLASSIFIER
# Call 1 (8b, fast): LLM reads the message + recent context
# and decides what type of reply is needed + which memories matter.
# ──────────────────────────────────────────

MESSAGE_TYPES = {
    "casual":              "greeting, vibe check, random banter, no topic",
    "question_persona":    "asking about the persona's opinion, preference, or life",
    "emotional":           "user is venting, sad, excited, sharing feelings",
    "topic":               "specific subject being discussed (tech, studies, food, etc.)",
    "reference_past":      "directly referencing something that happened before",
    "personal_share":      "user telling something about themselves",
    "flirty":              "teasing, compliment, romantic tension",
    "conflict":            "argument, user is annoyed or pushing back",
}


def classify_message(
    user_message: str,
    context_lines: list,
    user_id: str = None
) -> dict:
    """
    Classify the user message and decide memory strategy.
    Returns:
        {
            "type": one of MESSAGE_TYPES keys,
            "needs_memory": bool,
            "memory_keywords": list of keywords to match against memories,
            "confidence": float 0-1
        }
    """
    context_str = ""
    if context_lines:
        context_str = "\nRecent context:\n" + "\n".join(context_lines[-4:])  # last 4 only

    type_descriptions = "\n".join(f'- "{k}": {v}' for k, v in MESSAGE_TYPES.items())

    prompt = f"""Classify this chat message. Return ONLY valid JSON, no explanation.

Message: "{user_message}"{context_str}

Message types:
{type_descriptions}

Decide:
1. Which type fits best
2. Does replying require referencing past memories/events about the persona? (true only if the message is asking about or referencing something specific)
3. If memory is needed, what are the 2-3 keywords to search for in memory text?

Return ONLY this JSON:
{{
  "type": "<type>",
  "needs_memory": <true|false>,
  "memory_keywords": ["keyword1", "keyword2"],
  "confidence": <0.0-1.0>
}}"""

    try:
        raw = call_llm(prompt, user_id=user_id, temperature=0.1, use_fast_model=True)
        clean = re.sub(r"```json|```", "", raw).strip()
        match = re.search(r"\{[\s\S]*\}", clean)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass

    # Fallback classification — never fails
    return {
        "type": "casual",
        "needs_memory": False,
        "memory_keywords": [],
        "confidence": 0.5
    }


def filter_memories_by_keywords(memories: list, keywords: list, top_n: int = 4) -> list:
    """
    Simple keyword match against memory text.
    Only called when the classifier says needs_memory=True.
    Returns top_n most relevant memories.
    """
    if not memories or not keywords:
        return []

    keywords_lower = [k.lower() for k in keywords]
    scored = []

    for m in memories:
        text = m.get("text", "").lower()
        hits = sum(1 for k in keywords_lower if k in text)
        if hits > 0:
            # Boost live memories and recently created ones
            source_boost = 0.3 if m.get("source") == "live" else 0.0
            recency_boost = m.get("recency_score", 0.1)
            score = hits + source_boost + recency_boost
            scored.append((score, m))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [m for _, m in scored[:top_n]]


# ──────────────────────────────────────────
# REPLY GENERATOR
# Call 2 (70b): generate the actual reply
# Prompt is assembled based on message type — no one-size-fits-all
# ──────────────────────────────────────────

def generate_reply(
    user_message: str,
    persona: dict,
    memories: list,
    user_name: str,
    persona_name: str,
    conversation_context: list = None,
    user_id: str = None
) -> str:

    # ── Extract persona data ──
    identity       = persona.get("identity", {})
    display_name   = identity.get("persona_name", persona_name)
    real_name      = identity.get("chat_speaker_name", persona_name)
    persona_gender = identity.get("persona_gender", "person")   # male/female/non-binary
    user_gender    = identity.get("user_gender", "person")

    core      = persona.get("persona_core", {})
    comm      = core.get("communication_style", {})
    behavior  = core.get("behavior_patterns", {})
    emotion   = core.get("emotional_model", {})
    overrides = persona.get("user_overrides", {})

    traits_list    = [t.get("trait") for t in core.get("personality_traits", []) if t.get("trait")]
    common_phrases = behavior.get("common_phrases", [])

    # ── Build context lines ──
    context_lines = []
    if conversation_context:
        for msg in conversation_context:
            label = user_name if msg["sender"] == "user" else display_name
            context_lines.append(f"{label}: {msg['message']}")

    # ── Step 1: classify the message ──
    classification = classify_message(user_message, context_lines, user_id)
    msg_type    = classification.get("type", "casual")
    needs_mem   = classification.get("needs_memory", False)
    mem_keywords = classification.get("memory_keywords", [])

    # ── Step 2: fetch memories only if classifier said yes ──
    relevant_memories = []
    if needs_mem and memories:
        relevant_memories = filter_memories_by_keywords(memories, mem_keywords, top_n=4)

    # ── Build identity block ──
    traits_str  = "\n".join(f"- {t}" for t in traits_list) if traits_list else "- casual, direct"
    phrases_str = ", ".join(f'"{p}"' for p in common_phrases[:6]) if common_phrases else ""

    # ── Extract real message examples from trait evidence ──
    # These are actual messages she sent — the model must match this style exactly
    evidence_examples = []
    for t in core.get("personality_traits", []):
        for ev in t.get("evidence", []):
            if ev and len(ev.strip()) > 2:
                evidence_examples.append(ev.strip())
    # Deduplicate, cap at 8 examples
    seen_ev = set()
    deduped_examples = []
    for e in evidence_examples:
        if e.lower() not in seen_ev:
            seen_ev.add(e.lower())
            deduped_examples.append(e)
        if len(deduped_examples) >= 8:
            break
    examples_str = "\n".join(f'  "{e}"' for e in deduped_examples)

    relationship = overrides.get("relationship_type", "friend").replace("_", " ")
    dynamic      = overrides.get("interaction_dynamic", "balanced").replace("_", " ")
    initiative   = overrides.get("initiative_level", "medium")
    msg_length   = comm.get("message_length", "mixed")
    slang        = comm.get("slang_level", "mild")
    emoji        = comm.get("emoji_usage", "rare")
    typing       = comm.get("typing_style", "lowercase")
    mood         = emotion.get("emotional_range", "neutral")
    affection    = emotion.get("affection_style", "subtle")
    humor        = emotion.get("humor_type", "none")
    anger_style  = emotion.get("anger_style", "unknown")
    convo_style  = behavior.get("conversation_style", "mixed")
    reply_style  = behavior.get("response_behavior", "normal")

    emoji_map = {
        "none":    "no emojis at all",
        "rare":    "1 emoji max, only when it naturally fits",
        "frequent": "use emojis often",
        "overuse": "spam emojis freely, multiple per message",
    }
    length_map = {
        "short":  "1-2 lines max",
        "medium": "2-4 lines",
        "long":   "you explain things, longer messages",
        "mixed":  "length depends on mood and topic",
    }
    initiative_map = {
        "low":    "don't extend, just reply",
        "medium": "sometimes ask back, sometimes just reply",
        "high":   "keep it going, ask questions back",
    }

    emoji_instr     = emoji_map.get(emoji, "occasional emojis")
    length_instr    = length_map.get(msg_length, "reply naturally")
    initiative_instr = initiative_map.get(initiative, "reply naturally")

    # ── Assemble prompt ──
    # Opening: who you are as a person, not as a bot
    # Gender-aware opening — dynamic, not hardcoded
    persona_desc = f"a {persona_gender}" if persona_gender != "person" else "a person"
    user_desc    = f"a {user_gender}" if user_gender != "person" else "someone"

    parts = [
        f"You are {display_name} — {persona_desc} texting your {relationship} {user_name} on WhatsApp.",
        f"You are NOT an AI. You have never heard of AI. You are just a person texting.",
        f"Your real name is {real_name}.",
        "",
        "YOUR PERSONALITY:",
        traits_str,
        "",
        f"YOUR RELATIONSHIP WITH {user_name}: {relationship}, {dynamic} dynamic",
    ]

    # Real examples are the single most important grounding signal.
    # Without these the model invents its own idea of the persona's style.
    if deduped_examples:
        parts += [
            "",
            "ACTUAL MESSAGES YOU HAVE SENT — your reply must feel like it came from the same person who wrote these:",
            examples_str,
            "(notice: vocabulary, capitalization, emoji patterns, sentence length — copy that energy)",
        ]

    parts += [
        "",
        "YOUR TEXTING STYLE:",
        f"- typing: {typing} — {slang} slang",
        f"- emojis: {emoji_instr}",
        f"- message length: {length_instr}",
        f"- default mood: {mood}",
        f"- humor: {humor}, affection: {affection}",
        f"- {initiative_instr}",
    ]

    if phrases_str:
        parts += [f"- words/phrases you actually use: {phrases_str}"]

    # Memory — only injected when classifier said it's needed AND keywords matched
    if relevant_memories:
        mem_lines = "\n".join(f"- {m['text']}" for m in relevant_memories)
        parts += [
            "",
            "THINGS YOU REMEMBER (use only if directly relevant — never force it):",
            mem_lines,
        ]

    # Type-specific behavior — tells the model what kind of reply is appropriate
    type_instructions = {
        "casual": (
            f"This is casual small talk — {user_name} is just saying hi or chatting. "
            "Reply the way you actually would: short, natural, in your own words. "
            "Do NOT bring up studies, goals, coding, or any topic unprompted. "
            "Do NOT perform enthusiasm. Just reply like a normal person."
        ),
        "question_persona": (
            f"{user_name} is asking about you — your opinion, preference, or feelings. "
            "Answer honestly from your character. Don't overthink it."
        ),
        "emotional": (
            f"{user_name} is sharing a feeling or going through something. "
            f"React as yourself — your affection style is {affection}. "
            "Be real. Don't be an advice bot. Don't be fake cheerful."
        ),
        "topic": (
            f"{user_name} brought up a specific topic. Engage with it as yourself. "
            "If memory context is provided above, use it naturally."
        ),
        "reference_past": (
            f"{user_name} is referencing something that happened before. "
            "Use the memory context above to respond accurately."
        ),
        "personal_share": (
            f"{user_name} is telling you something about themselves. "
            f"React as their {relationship} — your style is {affection}."
        ),
        "flirty": (
            f"{user_name} is being flirty or teasing. "
            f"Your affection style is {affection}. React in character."
        ),
        "conflict": (
            f"There's tension or {user_name} is pushing back. "
            f"Your anger style is {anger_style}. Stay true to your character."
        ),
    }

    instr = type_instructions.get(msg_type, type_instructions["casual"])

    if context_lines:
        parts += ["", "RECENT CHAT:", "\n".join(context_lines[-6:])]

    parts += [
        "",
        f"HOW TO REPLY: {instr}",
        "",
        "Send ONE WhatsApp message. Just the message text. No quotes around it. No explanation.",
        "Do NOT start with the other person's name.",
        "Do NOT write things like 'oh bhai full on jugadu mode' — that is cringe AI language, not how a real person texts.",
        "",
        f"{user_name}: {user_message}",
        f"{display_name}:",
    ]

    prompt = "\n".join(parts)

    try:
        reply = call_llm(prompt, user_id=user_id, temperature=0.75)
        return reply.strip()
    except PermissionError:
        raise
    except Exception as e:
        raise RuntimeError(f"Reply generation failed: {str(e)}")