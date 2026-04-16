import json
from enum import Enum
from fastapi import APIRouter, UploadFile, File, Form
from app.services.llm_service import generate_persona
from app.services.memory_service import extract_memories_ai
from app.utils.chat_parser import parse_chat
from app.services.db import supabase

class RelationshipType(str, Enum):
    friend = "friend"
    best_friend = "best_friend"
    crush = "crush"
    girlfriend = "girlfriend"
    ex = "ex"
    colleague = "colleague"


class InteractionDynamic(str, Enum):
    balanced = "balanced"
    dominant_persona = "dominant_persona"
    dominant_user = "dominant_user"
    teasing_dynamic = "teasing_dynamic"


class MessageLength(str, Enum):
    short = "short"
    medium = "medium"
    long = "long"
    mixed = "mixed"


class TypingStyle(str, Enum):
    clean = "clean"
    lowercase = "lowercase"
    broken = "broken"
    fast_typing = "fast_typing"


class SlangLevel(str, Enum):
    none = "none"
    mild = "mild"
    heavy = "heavy"
    genz = "genz"


class EmojiUsage(str, Enum):
    none = "none"
    rare = "rare"
    frequent = "frequent"
    overuse = "overuse"


class DefaultMood(str, Enum):
    neutral = "neutral"
    happy = "happy"
    anxious = "anxious"
    moody = "moody"
    playful = "playful"


class AffectionStyle(str, Enum):
    direct = "direct"
    subtle = "subtle"
    teasing = "teasing"
    avoidant = "avoidant"
    clingy = "clingy"


class HumorType(str, Enum):
    sarcastic = "sarcastic"
    dark = "dark"
    wholesome = "wholesome"
    random = "random"
    none = "none"


class ReplyBehavior(str, Enum):
    instant = "instant"
    delayed = "delayed"
    random = "random"
    seen_zone = "seen_zone"


class ConversationStyle(str, Enum):
    question_based = "question_based"
    statement_based = "statement_based"
    mixed = "mixed"
    dry_replies = "dry_replies"


class InitiativeLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

def apply_overrides(persona_data, user_inputs):

    core = persona_data.get("persona_core", {})
    comm = core.get("communication_style", {})
    emotion = core.get("emotional_model", {})
    behavior = core.get("behavior_patterns", {})

    # 🔥 SAFE relationship extraction
    relationship = persona_data.get("relationship_model", {})

    # 🔥 COMMUNICATION
    comm["message_length"] = user_inputs.get("message_length")
    comm["slang_level"] = user_inputs.get("slang_level")
    comm["emoji_usage"] = user_inputs.get("emoji_usage")
    comm["typing_style"] = user_inputs.get("typing_style")

    # 🔥 EMOTION
    emotion["affection_style"] = user_inputs.get("affection_style")
    emotion["humor_type"] = user_inputs.get("humor_type")
    emotion["emotional_range"] = user_inputs.get("default_mood")

    # 🔥 BEHAVIOR
    behavior["response_behavior"] = user_inputs.get("reply_behavior")
    behavior["conversation_style"] = user_inputs.get("conversation_style")

    # 🔥 RELATIONSHIP (SAFE)
    relationship["with_user"] = user_inputs.get("relationship_type")
    relationship["interaction_style"] = user_inputs.get("interaction_dynamic")

    persona_data["relationship_model"] = relationship

    return persona_data

router = APIRouter(
    prefix="/persona",
    tags=["Persona"]
)

@router.post("/create")
async def create_persona(
    file: UploadFile = File(...),

    user_name: str = Form(...),
    chat_speaker_name: str = Form(...),
    persona_name: str = Form(...),
    
    relationship_type: RelationshipType = Form(...),
    interaction_dynamic: InteractionDynamic = Form(...),

    message_length: MessageLength = Form(...),
    typing_style: TypingStyle = Form(...),
    slang_level: SlangLevel = Form(...),
    emoji_usage: EmojiUsage = Form(...),

    default_mood: DefaultMood = Form(...),
    affection_style: AffectionStyle = Form(...),
    humor_type: HumorType = Form(...),

    reply_behavior: ReplyBehavior = Form(...),
    conversation_style: ConversationStyle = Form(...),
    initiative_level: InitiativeLevel = Form(...)
    
):
    
    content = await file.read()
    text_data = content.decode("utf-8")

    parsed_chat = parse_chat(text_data)
    
    user_inputs = {
    "relationship_type": relationship_type.value,
    "interaction_dynamic": interaction_dynamic.value,

    "message_length": message_length.value,
    "typing_style": typing_style.value,
    "slang_level": slang_level.value,
    "emoji_usage": emoji_usage.value,

    "default_mood": default_mood.value,
    "affection_style": affection_style.value,
    "humor_type": humor_type.value,

    "reply_behavior": reply_behavior.value,
    "conversation_style": conversation_style.value,
    "initiative_level": initiative_level.value
}
    
    persona_raw = generate_persona(parsed_chat, user_name, chat_speaker_name)

    try:
        persona_data = json.loads(persona_raw)
        persona_data = apply_overrides(persona_data, user_inputs)
    except Exception as e:
        persona_data = {
            "error": "Invalid JSON from LLM",
            "raw_output": persona_raw,
            "details": str(e)
    }

    # ✅ NOW ADD IDENTITY (after parsing)
    persona_data["identity"] = {
        "chat_speaker_name": chat_speaker_name,
        "persona_name": persona_name
    }
    persona_data["user_overrides"] = user_inputs
    persona_data["control_strength"] = "strict"
        
    memories = extract_memories_ai(parsed_chat, chat_speaker_name)
    
    # 🔥 STORE PERSONA IN DB
    persona_insert = supabase.table("personas").insert({
        "user_name": user_name,
        "persona_name": persona_name,
        "persona_json": persona_data
    }).execute()

    # 🔥 EXTRACT persona_id
    persona_id = persona_insert.data[0]["id"]
    
    # 🔥 STORE PERSONA IN DB
    persona_insert = supabase.table("personas").insert({
        "user_name": user_name,
        "persona_name": persona_name,
        "persona_json": persona_data
    }).execute()

    # 🔥 EXTRACT persona_id
    persona_id = persona_insert.data[0]["id"]

    # extract unique speakers
    unique_speakers = list(set([msg["speaker"] for msg in parsed_chat]))

    return {
    "persona_id": persona_id,
    "total_messages": len(parsed_chat),
    "speakers": unique_speakers,
    "persona": persona_data,
    "memories_sample": memories[:5] if isinstance(memories, list) else [],
    "total_memories": len(memories) if isinstance(memories, list) else 0
}