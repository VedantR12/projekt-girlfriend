from app.services.llm_service import client
import json
import re


def extract_live_memory(user_message, bot_reply, persona_name):

    prompt = f"""
You are an expert at detecting IMPORTANT long-term memory from conversations.

Target: {persona_name}

RULES:
- Extract ONLY if it's important
- Ignore casual chat
- Ignore small talk
- Ignore temporary emotions

Focus on:
- plans
- preferences
- decisions
- repeated behavior
- relationship changes

Return ONLY JSON list:

[
  {{
    "text": "",
    "type": "event / belief / opinion / relationship / habit",
    "importance": 0.0 to 1.0
  }}
]

Conversation:
User: {user_message}
{persona_name}: {bot_reply}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.choices[0].message.content

    clean = re.sub(r"```json|```", "", raw)

    start = clean.find("[")
    end = clean.rfind("]") + 1

    if start != -1 and end != -1:
        clean = clean[start:end]

    try:
        memories = json.loads(clean)

        # 🔥 strict filtering
        filtered = [
            m for m in memories
            if m.get("importance", 0) >= 0.7
            and len(m.get("text", "").split()) > 6
        ]

        return filtered

    except:
        return []