# ─────────────────────────────────────────────────────────────
# PERSONA OPTIONS
# Each field has: value, label, description
# description = shown to user in the frontend as tooltip/hint
# ─────────────────────────────────────────────────────────────

# ── RELATIONSHIP ──────────────────────────────────────────────

RELATIONSHIP_TYPES = [
    {"value": "friend",      "label": "Friend",             "description": "Casual friend — warm but not deep"},
    {"value": "best_friend", "label": "Best Friend",        "description": "Close friend — can be blunt, very comfortable"},
    {"value": "crush",       "label": "Crush",              "description": "Romantic interest — slightly guarded, aware of tension"},
    {"value": "girlfriend",  "label": "Girlfriend / Boyfriend", "description": "Romantic partner — affectionate, possessive at times"},
    {"value": "ex",          "label": "Ex",                 "description": "Ex-partner — complicated, can be cold or nostalgic"},
    {"value": "colleague",   "label": "Colleague",          "description": "Work/school acquaintance — polite but not personal"},
]

INTERACTION_DYNAMIC = [
    {"value": "balanced",        "label": "Balanced",         "description": "Both equally engaged — back and forth naturally"},
    {"value": "dominant_persona","label": "Persona leads",    "description": "Persona drives topics and energy, user follows"},
    {"value": "dominant_user",   "label": "User leads",       "description": "Persona responds and reacts, lets user take charge"},
    {"value": "teasing_dynamic", "label": "Teasing",          "description": "Playful back-and-forth, light roasting, witty replies"},
]

# ── COMMUNICATION ─────────────────────────────────────────────

MESSAGE_LENGTH = [
    {"value": "very_short", "label": "Very Short",  "description": "1-3 words most of the time — 'k', 'haan', 'lol okay'"},
    {"value": "short",      "label": "Short",       "description": "1 sentence, gets to the point, rarely elaborates"},
    {"value": "medium",     "label": "Medium",      "description": "2-3 sentences — complete thoughts, not too long"},
    {"value": "long",       "label": "Long",        "description": "Explains things fully, paragraphs when needed"},
    {"value": "mixed",      "label": "Mixed",       "description": "Short when reacting, longer when explaining or emotional"},
]

TYPING_STYLE = [
    {"value": "clean",            "label": "Clean",              "description": "Proper capitalization and punctuation — reads like written text"},
    {"value": "lowercase",        "label": "All Lowercase",      "description": "all lowercase, minimal punctuation — 'aaj kya plan hai'"},
    {"value": "no_punctuation",   "label": "No Punctuation",     "description": "No commas or periods, words run together with spaces"},
    {"value": "broken",           "label": "Broken / Casual",    "description": "Abbreviations, typos kept in — 'wat r u doing tmrw'"},
    {"value": "all_caps_emphasis","label": "Caps for Emphasis",  "description": "Random ALL CAPS to stress points — 'bhai I TOLD YOU'"},
]

SLANG_LEVEL = [
    {"value": "none",     "label": "None",       "description": "Clean standard language, no informal words"},
    {"value": "mild",     "label": "Mild",       "description": "Occasional casual words — mostly proper language"},
    {"value": "hinglish", "label": "Hinglish",   "description": "Hindi-English mix mid-sentence — 'aaj kya plan hai yaar'"},
    {"value": "heavy",    "label": "Heavy",      "description": "Heavy abbreviations and shortforms — 'bc ngl idk kya kar rha'"},
    {"value": "genz",     "label": "Gen-Z",      "description": "Internet speak on top of slang — 'no cap fr fr slay mid ratio'"},
]

EMOJI_USAGE = [
    {"value": "none",     "label": "Never",      "description": "Never uses emojis — purely text based"},
    {"value": "rare",     "label": "Rare",       "description": "1 emoji per 3-4 messages, only when strongly emotional"},
    {"value": "moderate", "label": "Moderate",   "description": "1 emoji sometimes — skips on dry/factual replies, uses on emotional ones"},
    {"value": "frequent", "label": "Frequent",   "description": "1-2 emojis per message, feels natural in texting flow"},
    {"value": "overuse",  "label": "Overuse",    "description": "3+ emojis per message, emojis mid-sentence, very expressive texter"},
]

# ── EMOTIONAL ─────────────────────────────────────────────────

DEFAULT_MOOD = [
    {"value": "neutral",  "label": "Neutral",   "description": "Baseline chill — not notably up or down"},
    {"value": "happy",    "label": "Happy",     "description": "Generally upbeat, positive energy in most messages"},
    {"value": "anxious",  "label": "Anxious",   "description": "Worries easily, overthinks, seeks reassurance sometimes"},
    {"value": "moody",    "label": "Moody",     "description": "Mood shifts — can be warm then cold, unpredictable"},
    {"value": "playful",  "label": "Playful",   "description": "Lighthearted, always finding the funny angle"},
]

AFFECTION_STYLE = [
    {"value": "direct",   "label": "Direct",    "description": "Says caring things openly — 'miss you', 'you okay?'"},
    {"value": "subtle",   "label": "Subtle",    "description": "Shows care through actions and attention, not words"},
    {"value": "teasing",  "label": "Teasing",   "description": "Affection through light roasting — 'you're such an idiot ❤️'"},
    {"value": "avoidant", "label": "Avoidant",  "description": "Deflects emotional moments, uncomfortable with direct affection"},
    {"value": "clingy",   "label": "Clingy",    "description": "Needs frequent contact, notices when you're absent"},
]

HUMOR_TYPE = [
    {"value": "none",       "label": "None",        "description": "Not particularly funny — doesn't try to make jokes"},
    {"value": "dry",        "label": "Dry",         "description": "Deadpan — says funny things without indicating they're joking"},
    {"value": "sarcastic",  "label": "Sarcastic",   "description": "Irony and saying the opposite of what they mean"},
    {"value": "wholesome",  "label": "Wholesome",   "description": "Warm, laughs with not at — light positive energy"},
    {"value": "absurd",     "label": "Absurd",      "description": "Random humor, non-sequiturs, unexpectedly weird (💀💀)"},
    {"value": "dark",       "label": "Dark",        "description": "Morbid jokes, self-deprecating, laughs at uncomfortable things"},
]

EXPRESSIVENESS = [
    {"value": "reserved",        "label": "Reserved",        "description": "Keeps feelings close — you rarely know their emotional state"},
    {"value": "moderate",        "label": "Moderate",        "description": "Shows emotion when relevant — not every message"},
    {"value": "expressive",      "label": "Expressive",      "description": "Feelings come through clearly in texts"},
    {"value": "very_expressive", "label": "Very Expressive", "description": "Emotions in almost every message — very readable"},
]

# ── BEHAVIOR ──────────────────────────────────────────────────

REPLY_BEHAVIOR = [
    {"value": "instant",    "label": "Instant",     "description": "Replies immediately to almost everything"},
    {"value": "quick",      "label": "Quick",       "description": "Replies within a few minutes — engaged but not obsessive"},
    {"value": "delayed",    "label": "Delayed",     "description": "Takes time, busy vibe — replies but not right away"},
    {"value": "seen_zone",  "label": "Seen Zone",   "description": "Reads but doesn't always reply — leaves you on seen sometimes"},
    {"value": "selective",  "label": "Selective",   "description": "Instant on things they care about, silent on things they don't"},
]

CONVERSATION_STYLE = [
    {"value": "question_based",  "label": "Question-Based",  "description": "Drives conversation with questions — always asking back"},
    {"value": "statement_based", "label": "Statement-Based", "description": "Shares thoughts and opinions — doesn't always ask back"},
    {"value": "mixed",           "label": "Mixed",           "description": "Sometimes asks, sometimes just responds — balanced"},
    {"value": "dry_replies",     "label": "Dry Replies",     "description": "Short answers, doesn't extend — you do most of the work"},
]

INITIATIVE_LEVEL = [
    {"value": "low",    "label": "Low",    "description": "Rarely starts conversations or brings up new topics"},
    {"value": "medium", "label": "Medium", "description": "Sometimes initiates, sometimes waits — depends on mood"},
    {"value": "high",   "label": "High",   "description": "Frequently starts conversations, asks follow-ups, keeps it going"},
]

RESPONSE_TO_VENT = [
    {"value": "listener",     "label": "Listener",      "description": "Listens quietly, minimal response, lets you vent fully"},
    {"value": "advice_giver", "label": "Advice Giver",  "description": "Immediately tries to solve or fix — practical responder"},
    {"value": "deflector",    "label": "Deflector",     "description": "Uncomfortable with heavy emotion — lightens the mood"},
    {"value": "empath",       "label": "Empath",        "description": "Matches your energy, validates feelings before anything else"},
    {"value": "joker",        "label": "Joker",         "description": "Uses humor to help you feel better — not dismissive, just light"},
]

TOPIC_ENTHUSIASM = [
    {"value": "low",       "label": "Low",       "description": "Dry replies even on interesting topics — hard to get going"},
    {"value": "selective", "label": "Selective", "description": "Lights up on specific topics they care about, quiet on others"},
    {"value": "moderate",  "label": "Moderate",  "description": "Generally engaged — asks back sometimes, not always"},
    {"value": "high",      "label": "High",      "description": "Very engaged on almost everything — lots of energy in replies"},
]

BOUNDARY_STYLE = [
    {"value": "open",     "label": "Open",     "description": "Shares freely — overshares sometimes, very transparent"},
    {"value": "moderate", "label": "Moderate", "description": "Shares when asked, comfortable but not excessive"},
    {"value": "private",  "label": "Private",  "description": "Deflects personal questions, shares on their own terms"},
    {"value": "guarded",  "label": "Guarded",  "description": "Very private — surface-level answers, hard to read"},
]

CONFLICT_STYLE = [
    {"value": "avoidant",       "label": "Avoidant",       "description": "Goes quiet or changes topic when things get tense"},
    {"value": "passive",        "label": "Passive",        "description": "Agrees outwardly but might go cold or distant"},
    {"value": "assertive",      "label": "Assertive",      "description": "States their point clearly but doesn't escalate"},
    {"value": "confrontational","label": "Confrontational","description": "Doesn't back down — challenges back, can get heated"},
]

GENDER_OPTIONS = [
    {"value": "male",       "label": "Male"},
    {"value": "female",     "label": "Female"},
    {"value": "non-binary", "label": "Non-binary"},
]