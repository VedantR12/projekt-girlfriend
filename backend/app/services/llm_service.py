import os
import re
import json
from groq import Groq
from dotenv import load_dotenv
from app.services.api_key_service import get_api_key


load_dotenv()

# ──────────────────────────────────────────
# GROQ-ONLY LLM LAYER
#
# use_fast_model=True  → llama-3.3-70b-versatile  (persona/memory gen)
# use_fast_model=False → llama-3.3-70b-versatile  (chat replies)
# Both same model — change GROQ_MODEL_CHAT to upgrade chat quality independently
# ──────────────────────────────────────────

GROQ_DEV_KEY    = os.getenv("GROQ_DEV_KEY", "")
GROQ_MODEL_GEN  = "llama-3.3-70b-versatile"
GROQ_MODEL_CHAT = "llama-3.3-70b-versatile"


def call_llm(
    prompt: str,
    api_key: str,
    temperature: float = 0.2,
    use_fast_model: bool = False
) -> str:

    if not api_key:
        raise PermissionError("NO_API_KEY")

    model = GROQ_MODEL_GEN if use_fast_model else GROQ_MODEL_CHAT

    return _call_groq(prompt, api_key, temperature, model)


def _call_groq(prompt: str, api_key: str, temperature: float, model: str) -> str:
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=1200
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        raise RuntimeError(f"Groq call failed [{model}]: {str(e)}")


# ──────────────────────────────────────────
# PERSONA GENERATION
# Takes signal_bundle (from chat_cleaner) not clean_payload
# Produces persona with traits+evidence, style fingerprint, casual samples
# ──────────────────────────────────────────

def generate_persona(
    signal_bundle: dict,
    persona_name: str,
    user_name: str,
    relationship_type: str,
    persona_gender: str,
    user_gender: str,
    user_id: str = None,
    api_key: str = None
) -> str:
    """
    Generate persona JSON from signal bundle.

    signal_bundle keys:
        trait_signals:  300-400 signal messages (start/mid/end sampled)
        casual_samples: 30-50 casual messages (hi/hello/reactions)
        filler_tokens:  top repeated filler words with counts
        top_keywords:   top meaningful words
        total_messages: int
    """

    trait_signals  = signal_bundle.get("trait_signals", [])
    casual_samples = signal_bundle.get("casual_samples", [])
    tone_samples   = signal_bundle.get("tone_samples", [])
    typing_quirks  = signal_bundle.get("typing_quirks", {})
    filler_tokens  = signal_bundle.get("filler_tokens", [])
    top_keywords   = signal_bundle.get("top_keywords", [])
    total_messages = signal_bundle.get("total_messages", 0)

    if not trait_signals:
        return '{"error": "No signals found in chat"}'

    signals_text = "\n".join(f"{m['speaker']}: {m['text']}" for m in trait_signals)
    casual_text  = "\n".join(f"{m['speaker']}: {m['text']}" for m in casual_samples[:30]) or "none found"
    filler_str   = ", ".join(f"'{f['token']}' (x{f['count']})" for f in filler_tokens[:10]) or "none"
    keyword_str  = ", ".join(kw["word"] for kw in top_keywords[:20]) or "none"

    # Format tone samples
    tone_str = ""
    if tone_samples:
        lines = []
        for s in tone_samples[:3]:
            lines.append(f'  Trigger: "{s["trigger"]}"'  )
            lines.append(f'  {persona_name}: "{s["response"]}"'  )
            if s.get("followup"):
                lines.append(f'  {persona_name}: "{s["followup"]}"'  )
            lines.append("")
        tone_str = "\n".join(lines)

    # Format typing quirks
    quirk_str = "\n".join(f"  - {v}" for v in typing_quirks.values()) if typing_quirks else "none detected"

    prompt = f"""You are extracting a behavioral persona from real WhatsApp chat messages.

Person: {persona_name} ({persona_gender})
Their relationship with {user_name} ({user_gender}): {relationship_type}
Total messages: {total_messages}
Their filler words: {filler_str}
Their frequent words: {keyword_str}

TASK: Analyze ONLY {persona_name}'s messages. Extract personality, communication style, and behavioral patterns.

STRICT RULES:
- Return ONLY valid JSON, zero explanation, zero markdown
- All text fields: MESSAGE TEXT ONLY — never include "SpeakerName: " prefix
- Every trait needs 3 real message examples as evidence (text only, no prefix)
- casual_replies: 8-10 messages of MAX 6 WORDS each — ONLY greetings/reactions (haa, okay, haaaa, chup, are, thike, accha) — NO opinions, NO feelings, NO sentences containing lagta/chahiye/pata/kyunki/because/feel/think
- relationship_detail: describe the SPECIFIC dynamic — not generic labels
- unknown_topics: 3-5 topics that were NEVER discussed in this chat
- Be specific not generic ("uses 😭 when overwhelmed" not "emotional")

DETECTED TYPING QUIRKS:
{quirk_str}

TONE SAMPLES (real exchanges — use these in tone_samples field):
{tone_str if tone_str else "none extracted"}

OUTPUT FORMAT (text fields = message text only, no speaker prefix):
{{
  "persona_core": {{
    "name": "{persona_name}",
    "gender": "{persona_gender}",
    "personality_traits": [
      {{
        "trait": "specific behavior pattern",
        "evidence": ["message text only", "message text only", "message text only"]
      }}
    ],
    "communication_fingerprint": {{
      "typical_message": "a typical message she sends — text only",
      "emoji_pattern": "describe actual emoji usage with real examples",
      "language_mix": "describe actual language pattern",
      "message_length": "describe length pattern",
      "punctuation_style": "describe punctuation habits"
    }},
    "typing_quirks": "{quirk_str.replace(chr(10), "; ")}",
    "casual_replies": ["Haaaa", "Thike", "Are nahi yaar", "Accha suno"],
    "tone_samples": [
      {{
        "trigger": "what the other person said — text only",
        "response": "her reply — text only",
        "followup": "her follow-up if any — text only or null"
      }}
    ]
  }},
  "relationship_context": {{
    "type": "{relationship_type}",
    "relationship_detail": "specific dynamic — does she tease, use nicknames, act maternal, how she reacts to jokes",
    "tone_with_user": "specific tone — not generic",
    "unknown_topics": ["topic not discussed", "topic not discussed", "topic not discussed"]
  }}
}}

CASUAL MESSAGES (greeting/small talk patterns):
{casual_text}

MAIN CHAT SIGNALS:
{signals_text}"""

    if not api_key:
        api_key = get_api_key(user_id)

    if not api_key:
        raise RuntimeError("NO_API_KEY: User has not added API key")


    try:
        raw = call_llm(
    prompt,
    api_key,
    temperature=0.2,
    use_fast_model=True
)
    except Exception as e:
        raise RuntimeError(f"Persona generation failed: {str(e)}")

    return _clean_json_output(raw)


def _clean_json_output(raw: str) -> str:
    clean = re.sub(r"```json|```", "", raw).strip()

    try:
        return json.dumps(json.loads(clean))
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", clean)
    if match:
        try:
            return json.dumps(json.loads(match.group(0)))
        except Exception:
            pass

    raise RuntimeError("LLM returned invalid JSON format")