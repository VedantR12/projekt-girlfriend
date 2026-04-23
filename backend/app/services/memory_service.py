import json
import re
from app.services.llm_service import call_llm
import time

def _strip_prefix(text: str) -> str:
    """Strip 'SpeakerName: ' prefix if model included it in stored data."""
    if ": " in text[:50]:
        parts = text.split(": ", 1)
        if len(parts[0].strip()) < 40:
            return parts[1].strip()
    return text.strip()


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
    Splits signal_messages into smart chunks: start, middle, end + spaced.
    Deduplicates chunks.
    """
    total = len(signal_messages)
    if total == 0:
        return []

    chunks = []

    # Start, middle, end
    chunks.append(signal_messages[:150])
    mid = total // 2
    chunks.append(signal_messages[max(mid - 75, 0): mid + 75])
    chunks.append(signal_messages[-150:])

    # Additional spaced
    step = max(total // max_chunks, 1)
    for i in range(step, total, step):
        chunk = signal_messages[i: i + 150]
        if len(chunk) > 30:
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
- be usable and meaningful in a future conversation
- refer to a concrete event, habit, preference, belief, or behaviour of {persona_name}

Reject anything generic or about the user (not the persona).

--------------------------------------

GOOD MEMORY:
✔ "{persona_name} prefers sleeping before midnight"
✔ "{persona_name} dislikes being judged by others"
✔ "{persona_name} often uses sarcasm in conversations"
✔ "{persona_name} has mentioned missing their hometown"

BAD MEMORY:
❌ "12 se pehle sona hai yaad rakhna"
❌ "Wah, 18 saal ki umar me hi ye haal"
❌ "User asked about plans"
❌ "They had a conversation"

--------------------------------------

Return ONLY valid JSON array.

FORMAT:

[
  {{
    "text": "",
    "type": "event / belief / opinion / habit / preference / relationship",
    "importance": 0.0 to 1.0
  }}
]

--------------------------------------

Extract 3–8 memories if possible. If nothing meaningful — return [].

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

    # Deduplicate by text similarity
    seen_texts = set()
    deduped = []
    for m in all_memories:
        key = m["text"][:60].lower().strip()
        if key not in seen_texts:
            seen_texts.add(key)
            deduped.append(m)
            
    # Strip any speaker prefix from memory texts
    for m in deduped:
        m["text"] = _strip_prefix(m["text"])

    print(f"⏱ Memory extraction: {time.time() - start_time:.2f}s")
    print(f"🧠 Memories extracted: {len(deduped)} (from {len(all_memories)} raw)")

    return deduped
