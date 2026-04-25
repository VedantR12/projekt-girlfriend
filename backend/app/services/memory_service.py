import json
import re
from app.services.llm_service import call_llm

import time


# ──────────────────────────────────────────
# Memory relevance scoring
# ──────────────────────────────────────────

def get_relevant_memories(memories: list, user_message: str, top_n: int = 6) -> list:
    message = user_message.lower()
    message_words = set(message.split())

    scored = []

    for m in memories:
        text = m.get("text", "").lower()
        text_words = set(text.split())

        overlap = len(message_words & text_words)
        partial = sum(1 for w in message_words if any(w in tw for tw in text_words))
        norm = max(len(message_words), 1)
        importance = m.get("importance", 0.7)
        source = m.get("source", "long_term")
        recency = m.get("recency_score", 0.1)

        source_weight = 0.5 if source == "live" else 0.2

        score = (
            ((overlap * 2.5) + (partial * 1.5)) / norm
            + (importance * 0.5)
            + source_weight
            + recency
        )

        scored.append((score, m))

    scored.sort(reverse=True, key=lambda x: x[0])

    selected = []
    seen = set()

    for score, m in scored:
        text = m["text"]
        if any(t in text for t in seen):
            continue
        if score < 0.8:
            continue
        selected.append(m)
        seen.add(text)
        if len(selected) >= top_n:
            break

    # No fallback — zero memories is valid.
    # Forcing unrelated memories causes the LLM to inject them into replies.
    return selected[:top_n]


# ──────────────────────────────────────────
# HELPER: build chunks from signal messages
# ──────────────────────────────────────────

def _build_chunks(signal_messages: list, max_chunks: int = 8) -> list:
    """
    Recent-heavy chunking: 1 chunk from start, 1 from mid, 5 from recent half.
    More chunks from recent = more memories extracted from developed personality.
    """
    total = len(signal_messages)
    if total == 0:
        return []

    chunks = []
    chunk_size = 120  # smaller chunks = more focused memories

    # 1 chunk from start (context only)
    chunks.append(signal_messages[:chunk_size])

    # 1 chunk from middle
    mid = total // 2
    chunks.append(signal_messages[max(mid - chunk_size // 2, 0): mid + chunk_size // 2])

    # 5 chunks from recent 50% — split evenly
    recent_start = total // 2
    recent_msgs  = signal_messages[recent_start:]
    recent_total = len(recent_msgs)
    if recent_total > 0:
        step = max(recent_total // 5, 1)
        for i in range(0, recent_total, step):
            chunk = recent_msgs[i: i + chunk_size]
            if len(chunk) > 20:
                chunks.append(chunk)
            if len(chunks) >= max_chunks:
                break

    # Deduplicate by first-5-message fingerprint
    unique_chunks = []
    seen_keys = set()
    for chunk in chunks:
        key = tuple((msg["speaker"], msg["text"]) for msg in chunk[:5])
        if key not in seen_keys:
            seen_keys.add(key)
            unique_chunks.append(chunk)

    return unique_chunks[:max_chunks]


# ──────────────────────────────────────────
# Memory extraction from uploaded chat
# NOW accepts pre-cleaned signal_messages
# ──────────────────────────────────────────

def extract_memories_ai(
    signal_messages: list,
    persona_name: str,
    behavior_context: list = None,
    keyword_metadata: list = None,
    user_id: str = None
) -> list:
    """
    Extract long-term memories from cleaned signal messages.
    
    Args:
        signal_messages:   List of {speaker, text} — already filtered signals
        persona_name:      Target person's name
        behavior_context:  Filler word frequency data from chat_cleaner
        keyword_metadata:  Top repeated keywords from chat_cleaner
        user_id:           For LLM routing (BYOK)
    
    Returns:
        List of memory objects [{text, type, importance}]
    """

    start_time = time.time()
    all_memories = []

    if not signal_messages:
        print("⚠️ No signal messages to extract memories from.")
        return []

    chunks = _build_chunks(signal_messages, max_chunks=8)

    # Build behavior context string for the prompt
    behavior_str = ""
    if behavior_context:
        top_fillers = [f"'{b['token']}' ({b['frequency']})" for b in behavior_context[:8]]
        behavior_str = f"\nKnown filler tokens this person uses: {', '.join(top_fillers)}"

    keyword_str = ""
    if keyword_metadata:
        top_words = [kw["word"] for kw in keyword_metadata[:20]]
        keyword_str = f"\nFrequent words in their messages: {', '.join(top_words)}"

    for chunk in chunks:
        formatted_chat = "\n".join(
            [f"{msg['speaker']}: {msg['text']}" for msg in chunk]
        )

        prompt = f"""
You are a strict information extraction engine.

You ONLY extract structured memories.
You NEVER explain.
You NEVER add extra text.
Your job is to CONVERT chat into reusable memories.

If output is not valid JSON, it is a failure.

--------------------------------------

Target person: {persona_name}
{behavior_str}
{keyword_str}

--------------------------------------

A valid memory MUST:
- contain a specific real-world detail about {persona_name}
- be generalized (not an exact sentence copy)
- refer to a concrete event, habit, preference, or behaviour — NOT a momentary emotion

Reject: generic statements, one-time emotional outbursts, anything about the user not the persona.

--------------------------------------

GOOD MEMORY:
✔ "{persona_name} prefers sleeping before midnight"
✔ "{persona_name} often uses sarcasm in conversations"
✔ "{persona_name} has mentioned missing their hometown"
✔ "{persona_name} dislikes unplanned changes to schedules"

BAD MEMORY (do NOT extract these):
❌ Dramatic emotional statements said once in a heated moment
❌ "{persona_name} feels people love her conditionally" — one-time vent, not a pattern
❌ Opinions that repeat the same theme as another memory already extracted
❌ Direct sentence copies from chat

--------------------------------------

IMPORTANCE RULES (critical — wrong importance breaks the whole system):
- habits and preferences: 0.4–0.6
- recurring behaviors: 0.5–0.6
- beliefs held consistently: 0.5–0.7
- one-time events: 0.3–0.4
- emotional/dramatic statements: MAX 0.4 even if intense
- NEVER assign importance > 0.7 to opinions or feelings
- Assign diverse importance values — do not cluster everything at 0.7+

--------------------------------------

Return ONLY valid JSON array.

FORMAT:
[
  {{
    "text": "",
    "type": "event / habit / preference / behavior / belief",
    "importance": 0.0 to 0.7
  }}
]

--------------------------------------

Extract 3–6 DIVERSE memories. Prefer variety over quantity. If nothing meaningful — return [].

CHAT:
{formatted_chat}
"""

        raw = None
        for attempt in range(2):
            try:
                raw = call_llm(prompt, user_id=user_id, temperature=0.1, use_fast_model=True)
                print("✅ Memory chunk processed")
                break
            except Exception as e:
                if attempt == 1:
                    print(f"❌ LLM failed for chunk: {e}")
                    raw = None

        if not raw:
            continue

        clean = re.sub(r"```json|```", "", raw)
        start = clean.find("[")
        end = clean.rfind("]") + 1

        if start != -1 and end > start:
            clean = clean[start:end]

        try:
            parsed = json.loads(clean)
            # Basic validation
            valid = [
                m for m in parsed
                if isinstance(m, dict)
                and m.get("text")
                and len(m["text"].split()) > 4
            ]
            all_memories.extend(valid)
        except Exception:
            continue

    # Deduplicate + cap importance at 0.7 (prevents emotional memories from dominating)
    seen_texts = set()
    deduped = []
    for m in all_memories:
        key = m["text"][:60].lower().strip()
        if key not in seen_texts:
            seen_texts.add(key)
            # Hard cap — no memory gets importance > 0.7 regardless of LLM output
            m["importance"] = min(float(m.get("importance", 0.5)), 0.7)
            deduped.append(m)

    print(f"⏱ Memory extraction: {time.time() - start_time:.2f}s")
    print(f"🧠 Memories extracted: {len(deduped)} (from {len(all_memories)} raw)")

    return deduped