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
    user_id: str = None,
    temperature: float = 0.2,
    use_fast_model: bool = False
) -> str:
    model = GROQ_MODEL_GEN if use_fast_model else GROQ_MODEL_CHAT

    if user_id:
        user_key = get_api_key(user_id)
        if user_key:
            return _call_groq(prompt, user_key, temperature, model)

    if GROQ_DEV_KEY:
        return _call_groq(prompt, GROQ_DEV_KEY, temperature, model)

    raise PermissionError(
        "No Groq API key found. Add GROQ_DEV_KEY to .env or store a key via the API."
    )


def _call_groq(prompt: str, api_key: str, temperature: float, model: str) -> str:
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=1024
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
    user_id: str = None
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

    trait_signals   = signal_bundle.get("trait_signals", [])
    casual_samples  = signal_bundle.get("casual_samples", [])
    filler_tokens   = signal_bundle.get("filler_tokens", [])
    top_keywords    = signal_bundle.get("top_keywords", [])
    total_messages  = signal_bundle.get("total_messages", 0)

    if not trait_signals:
        return '{"error": "No signals found in chat"}'

    # Format signals as speaker: message
    signals_text = "\n".join(
        f"{m['speaker']}: {m['text']}" for m in trait_signals
    )

    casual_text = "\n".join(
        f"{m['speaker']}: {m['text']}" for m in casual_samples[:30]
    ) if casual_samples else "none found"

    filler_str = ", ".join(
        f"'{f['token']}' (x{f['count']})" for f in filler_tokens[:10]
    ) if filler_tokens else "none"

    keyword_str = ", ".join(
        kw["word"] for kw in top_keywords[:20]
    ) if top_keywords else "none"

    prompt = f"""You are extracting a behavioral persona from real WhatsApp chat messages.

Person: {persona_name} ({persona_gender})
Their relationship with {user_name} ({user_gender}): {relationship_type}
Total messages analyzed: {total_messages}
Their filler words: {filler_str}
Their frequent words: {keyword_str}

TASK: Analyze ONLY {persona_name}'s messages. Extract their personality, communication style, and behavioral patterns.

RULES:
- Return ONLY valid JSON, no explanation, no markdown
- Every trait MUST include 2-3 real message examples as evidence
- Evidence must be actual messages from the chat, not paraphrased
- communication_fingerprint must describe HOW they actually text, not labels
- casual_replies must be real messages they sent in casual/greeting moments
- Extract 4-6 personality traits maximum
- Be specific, not generic ("uses 😭 when overwhelmed" not "emotional")

OUTPUT FORMAT:
{{
  "persona_core": {{
    "name": "{persona_name}",
    "gender": "{persona_gender}",
    "personality_traits": [
      {{
        "trait": "one specific behavior pattern",
        "evidence": ["actual message 1", "actual message 2", "actual message 3"]
      }}
    ],
    "communication_fingerprint": {{
      "typical_message": "example of a typical message they send",
      "emoji_pattern": "describe actual emoji usage with examples or 'never uses emojis'",
      "language_mix": "describe actual language pattern e.g. 'Hinglish, mostly Hindi words with English phrases'",
      "message_length": "describe pattern e.g. 'usually 1 sentence, sometimes 3-4 when excited'",
      "punctuation_style": "describe e.g. 'no punctuation, lowercase, uses ??? for questions'"
    }},
    "casual_replies": []
  }},
  "relationship_context": {{
    "type": "{relationship_type}",
    "dynamic": "describe the actual dynamic visible in chat",
    "tone_with_user": "describe how they specifically talk to {user_name}"
  }}
}}

CASUAL MESSAGES (for greetings and small talk patterns):
{casual_text}

MAIN CHAT SIGNALS:
{signals_text}"""

    try:
        raw = call_llm(prompt, user_id=user_id, temperature=0.2, use_fast_model=True)
    except Exception as e:
        return json.dumps({"error": "LLM call failed", "details": str(e)})

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

    return json.dumps({"error": "No valid JSON found", "raw": clean[:300]})