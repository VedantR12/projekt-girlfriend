import os
import re
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def generate_persona(chat_data, user_name, persona_name):

    if not chat_data:
      return '{"error": "Empty chat data"}'

    # 🔥 Step 1: format chat into readable text
    total = len(chat_data)

    # 🔥 optimized sampling
    first_part = chat_data[:80]

    mid_start = max(total // 2 - 40, 0)
    middle_part = chat_data[mid_start:mid_start + 80]

    late_start = max(total - 160, 0)
    late_part = chat_data[late_start:late_start + 80]

    selected_msgs = first_part + middle_part + late_part
    
    seen = set()
    unique_msgs = []

    for msg in selected_msgs:
      key = (msg['speaker'], msg['text'])
      if key not in seen:
        seen.add(key)
        unique_msgs.append(msg)

    selected_msgs = unique_msgs
    
    # format for LLM
    formatted_chat = "\n".join(
        [f"{msg['speaker']}: {msg['text'][:200]}" for msg in selected_msgs]
    )

    # 🔥 Step 2: prompt
    prompt = f"""
You are a forensic behavioral analyst.

Your job is to extract precise behavioral patterns from chat data.

User: {user_name}
Target Persona: {persona_name}

--------------------------------------

STRICT RULES:

1. NEVER give generic traits like:
   - friendly
   - nice
   - responsive
   - informative

2. ONLY extract traits that are:
   - repeated behavior
   - clearly visible in multiple messages
   - specific to THIS person

3. EVERY trait MUST:
   - include real message evidence
   - reflect a pattern (not one-time)

4. If behavior is not repeated → IGNORE it

5. If unsure → return "unknown"

--------------------------------------

TRAIT STYLE REQUIREMENTS:

GOOD:
✔ "uses short replies like 'hmm', 'ok' to close conversations"
✔ "gives direct advice without softening tone"
✔ "avoids emotional confrontation by changing topic"
✔ "switches to sarcasm in uncomfortable situations"

BAD:
❌ "nice"
❌ "friendly"
❌ "informative"
❌ "responsive"

--------------------------------------

COMMUNICATION RULES:

- message_length → based on pattern (short/medium/mixed)
- emoji_usage → none/rare/frequent (based on actual count)
- slang_level → none/mild/heavy/genz (based on words used)
- typing_style → lowercase/clean/broken

--------------------------------------

COMMON PHRASES RULE:

- Only include phrases used 3+ times
- Ignore generic words unless dominant

--------------------------------------

OUTPUT FORMAT (STRICT JSON):

{{
  "persona_core": {{
    "name": "{persona_name}",

    "personality_traits": [
      {{
        "trait": "",
        "evidence": ""
      }}
    ],

    "communication_style": {{
      "message_length": "",
      "emoji_usage": "",
      "slang_level": "",
      "tone": "",
      "typing_style": ""
    }},

    "behavior_patterns": {{
      "common_phrases": [],
      "response_behavior": "",
      "conversation_style": ""
    }},

    "emotional_model": {{
      "emotional_range": "",
      "anger_style": "",
      "affection_style": "",
      "humor_type": ""
    }}
  }},

  "relationship_model": {{
    "with_user": "",
    "interaction_style": "",
    "power_dynamic": ""
  }}
}}

--------------------------------------

IMPORTANT:

- If something is unclear → "unknown"
- Do NOT fill just to complete structure
- Precision > completeness

--------------------------------------

CHAT DATA:
{formatted_chat}
"""

    # 🔥 Step 3: call LLM
    try:
        response = client.chat.completions.create(
          model="llama-3.3-70b-versatile",
          messages=[{"role": "user", "content": prompt}],
          temperature=0.2
      )
    except Exception as e:
      return json.dumps({
          "error": "LLM failed",
          "details": str(e)
      })

    # 🔥 Step 4: clean output
    raw_output = response.choices[0].message.content or ""

    clean_output = re.sub(r"```json|```", "", raw_output).strip()

    match = re.search(r"\{[\s\S]*\}", clean_output)

    if match:
      cleaned = match.group(0)
    
      # sanity check
      if len(cleaned) < 50:
          return json.dumps({
              "error": "Output too short",
              "raw": cleaned
          })
    
      return cleaned
    else:
        return json.dumps({
            "error": "No valid JSON found",
            "raw": clean_output[:200]
        })