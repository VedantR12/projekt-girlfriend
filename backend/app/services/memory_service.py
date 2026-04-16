import json
import re
from app.services.llm_service import client

def get_relevant_memories(memories, user_message):

    message = user_message.lower()

    scored = []

    for m in memories:
        text = m["text"].lower()

        score = 0

        # 🔥 keyword match
        for word in message.split():
            if word in text:
                score += 1

        # 🔥 semantic hints (manual)
        if any(k in message for k in ["trip", "bahar", "jaana"]):
            if "trip" in text or "go" in text:
                score += 2

        if any(k in message for k in ["family", "ghar", "parents"]):
            if any(x in text for x in ["father", "mother", "family"]):
                score += 2

        if any(k in message for k in ["future", "career", "banegi"]):
            if any(x in text for x in ["career", "become", "profession"]):
                score += 2

        # 🔥 importance weight
        score += m.get("importance", 0)

        scored.append((score, m))

    scored.sort(reverse=True, key=lambda x: x[0])

    return [m for _, m in scored[:3]]


def extract_memories_ai(chat_data, persona_name):

    # format chat
    formatted_chat = "\n".join(
        [f"{msg['speaker']}: {msg['text']}" for msg in chat_data[:300]]
    )

    prompt = f"""
You extract ONLY high-value long-term memories.

Target person: {persona_name}

--------------------------------------

STRICT RULES:

1. ONLY include:
   - specific events
   - strong opinions
   - repeated habits
   - clear preferences

2. NEVER include:
   - generic summaries
   - relationship descriptions
   - vague statements

3. Memory must be:
   - specific
   - useful for future conversation
   - tied to real situations

--------------------------------------

GOOD MEMORY:

✔ "She refused extra photos and prefers minimal selection"
✔ "Her father did not allow her to go on a trip"

BAD MEMORY:

❌ "They have a good relationship"
❌ "She talks casually"

--------------------------------------

FORMAT:

[
  {{
    "text": "",
    "type": "event / belief / opinion / habit",
    "importance": 0.0 to 1.0
  }}
]

--------------------------------------

CHAT:
{formatted_chat}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.choices[0].message.content

    # 🔥 STRONG CLEANING
    clean = re.sub(r"```json|```", "", raw)

    # extract JSON array
    start = clean.find("[")
    end = clean.rfind("]") + 1

    if start != -1 and end != -1:
        clean = clean[start:end]

    clean = clean.strip()

    try:
        memories = json.loads(clean)

        # 🔥 filter weak memories
        filtered_memories = [
            m for m in memories
            if m.get("importance", 0) >= 0.7
            and len(m.get("text", "").split()) >= 8
            and not any(word in m.get("text", "").lower() for word in [
                "someone",
                "something",
                "people",
                "relationship",
                "dynamic",
                "conversation",
                "mentioned",
                "involved"
            ])
        ]

        return filtered_memories

    except Exception as e:
        return {
            "error": "Invalid memory JSON",
            "raw": clean
        }