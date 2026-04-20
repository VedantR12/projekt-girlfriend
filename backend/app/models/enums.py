from enum import Enum


# ─── RELATIONSHIP ───

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


# ─── COMMUNICATION ───

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


# ─── EMOTIONAL ───

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


# ─── BEHAVIOR ───

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
