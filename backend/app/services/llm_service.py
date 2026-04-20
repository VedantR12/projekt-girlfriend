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
# No Ollama. No local model. Groq always.
#
# Key priority:
#   1. User's stored BYOK key  → their tokens, their limit
#   2. GROQ_DEV_KEY in .env   → your key for dev/testing
#   3. Nothing                → raise PermissionError
#
# Model routing:
#   generation (persona + memory) → llama-3.3-70b-versatile
#     - 8192 ctx window
#     - 500k tokens/day free tier
#     - fast, good at structured JSON extraction
#
#   chat (replies + live memory) → openai/gpt-oss-120b
#     - 128k ctx window
#     - 100k tokens/day free tier
#     - better reasoning, more natural replies
# ──────────────────────────────────────────

GROQ_DEV_KEY    = os.getenv("GROQ_DEV_KEY", "")
GROQ_MODEL_GEN  = "llama-3.3-70b-versatile"            # persona + memory generation
GROQ_MODEL_CHAT = "llama-3.3-70b-versatile"   # chat replies + live memory


def call_llm(
    prompt: str,
    user_id: str = None,
    temperature: float = 0.2,
    use_fast_model: bool = False
) -> str:
    """
    Unified Groq call.

    Key priority: user BYOK → GROQ_DEV_KEY → PermissionError

    use_fast_model=True  → llama-3.3-70b-versatile       (persona/memory generation)
    use_fast_model=False → openai/gpt-oss-120b (chat replies)
    """
    model = GROQ_MODEL_GEN if use_fast_model else GROQ_MODEL_CHAT

    # 1. User BYOK
    if user_id:
        user_key = get_api_key(user_id)
        if user_key:
            return _call_groq(prompt, user_key, temperature, model)

    # 2. Dev key
    if GROQ_DEV_KEY:
        return _call_groq(prompt, GROQ_DEV_KEY, temperature, model)

    # 3. Nothing
    raise PermissionError(
        "No Groq API key found. "
        "Add GROQ_DEV_KEY to .env or store a key via the API key endpoint."
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
# PERSONA GENERATION  (8b model)
# ──────────────────────────────────────────

def generate_persona(
    clean_payload: dict,
    user_name: str,
    persona_name: str,
    user_id: str = None
) -> str:
    """
    Extract structured persona JSON from cleaned chat signals.
    Uses llama-3.3-70b-versatile — fast, structured output, 8192 ctx.
    """

    clean_chat       = clean_payload.get("clean_chat", "")
    behavior_context = clean_payload.get("behavior_context", [])
    keyword_metadata = clean_payload.get("keyword_metadata", [])
    signal_count     = clean_payload.get("signal_count", 0)
    total_messages   = clean_payload.get("total_messages", 0)

    if not clean_chat:
        return '{"error": "No signal messages found in chat"}'

    if behavior_context:
        filler_lines = [
            f"  - '{b['token']}': {b['frequency']} (x{b.get('count', '?')})"
            for b in behavior_context[:10]
        ]
        behavior_block = "FILLER TOKENS:\n" + "\n".join(filler_lines)
    else:
        behavior_block = "FILLER TOKENS: none"

    keyword_block = ""
    if keyword_metadata:
        top_words = ", ".join([kw["word"] for kw in keyword_metadata[:20]])
        keyword_block = f"TOP WORDS: {top_words}"

    prompt = f"""You are a forensic behavioral analyst. Extract behavioral patterns from chat data. Return ONLY valid JSON — no explanation, no markdown, no text outside the JSON object.

User: {user_name} | Target: {persona_name} | Signals: {signal_count}/{total_messages}

{behavior_block}
{keyword_block}

RULES:
- Return ONLY the JSON object, nothing else
- No generic traits (friendly/nice/responsive) — only specific repeated behaviors
- Every trait needs evidence array with 2+ real message examples
- evidence must be a JSON array of strings
- Unknown values → "unknown"
- common_phrases: only phrases used 3+ times, include frequent fillers from above

OUTPUT FORMAT (fill exactly, no extra keys):
{{
  "persona_core": {{
    "name": "{persona_name}",
    "personality_traits": [{{"trait": "", "evidence": []}}],
    "communication_style": {{"message_length": "", "emoji_usage": "", "slang_level": "", "tone": "", "typing_style": ""}},
    "behavior_patterns": {{"common_phrases": [], "response_behavior": "", "conversation_style": ""}},
    "emotional_model": {{"emotional_range": "", "anger_style": "", "affection_style": "", "humor_type": ""}}
  }},
  "relationship_model": {{"with_user": "", "interaction_style": "", "power_dynamic": ""}}
}}

CHAT DATA:
{clean_chat}"""

    try:
        raw = call_llm(prompt, user_id=user_id, temperature=0.2, use_fast_model=True)
    except Exception as e:
        return json.dumps({"error": "LLM call failed", "details": str(e)})

    return _clean_json_output(raw)


# ──────────────────────────────────────────
# JSON OUTPUT CLEANER
# ──────────────────────────────────────────

def _clean_json_output(raw: str) -> str:
    def fix_evidence(text: str) -> str:
        return re.sub(
            r'"evidence"\s*:\s*"([^"]+)"\s*,\s*"([^"]+)"',
            r'"evidence": ["\1", "\2"]',
            text
        )

    clean = re.sub(r"```json|```", "", raw).strip()
    clean = fix_evidence(clean)

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