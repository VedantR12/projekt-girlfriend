import re
from collections import Counter

# ──────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────
FILLERS = [
    "hmm", "ok", "okay", "yes", "no", "k", "lol", "haha", "hm", "oh",
    "acha", "accha", "ha", "hahaha", "lmao", "lmfao", "💀", "😂"
]

MIN_WORDS = 3

SIGNAL_KEYWORDS = [
    "always", "never", "like", "love", "hate",
    "think", "feel", "believe", "want",
    "should", "need", "prefer",
    "because", "why", "how", "what",
    "when", "who", "where",
    "scared", "happy", "sad", "angry", "excited",
    "miss", "wish", "hope", "dream", "remember",
    "used to", "plan", "going to", "want to"
]

# ──────────────────────────────────────────
# SIGNAL CAP CONFIG
#
# Groq llama-3.3-70b-versatile context: 8192 tokens
# 200 signals @ ~80 chars avg = ~4000 tokens
# + prompt overhead ~300 + output buffer ~1024 = ~5300 total — fits 8192 ✓
#
# Zone breakdown (sums to 200):
#   start(30) + start_mid(60) + mid(40) + mid_end(50) + end(20) = 200
# ──────────────────────────────────────────
SIGNAL_CAP = {
    "start":     40,
    "start_mid": 70,
    "mid":       50,
    "mid_end":   40,
    "end":       20,
}
SIGNAL_TOTAL_CAP = sum(SIGNAL_CAP.values())  # 300


# ──────────────────────────────────────────
# FILLER ANALYSIS
# ──────────────────────────────────────────

def count_fillers(messages: list, target_person: str) -> tuple:
    counter = Counter()
    total = 0
    for msg in messages:
        if target_person.lower() not in msg["speaker"].lower():
            continue
        words = re.findall(r"[\w😂💀🙂☹️]+", msg["text"].lower())
        for w in words:
            if w in FILLERS:
                counter[w] += 1
                total += 1
    return counter, total


def get_level(freq: float) -> str:
    if freq > 0.25:   return "very_high"
    elif freq > 0.15: return "high"
    elif freq > 0.08: return "moderate"
    elif freq > 0.03: return "low"
    return "rare"


def build_behavior_context(counter: Counter, total: int) -> list:
    context = []
    for word, count in counter.most_common():
        freq = count / total if total > 0 else 0
        context.append({"token": word, "count": count, "frequency": get_level(freq)})
    return context


# ──────────────────────────────────────────
# KEYWORD METADATA
# ──────────────────────────────────────────

def extract_keyword_metadata(messages: list, target_person: str, top_n: int = 30) -> list:
    stop_words = set([
        "the", "a", "an", "is", "was", "are", "were", "i", "you", "he", "she",
        "we", "they", "it", "this", "that", "and", "or", "but", "in", "on",
        "at", "to", "of", "for", "with", "my", "your", "his", "her", "our",
        "me", "him", "us", "them", "be", "do", "does", "did", "have", "has",
        "had", "will", "would", "could", "should", "just", "not", "so", "if",
        "then", "than", "too", "very", "much", "also", "its", "about",
        # Hindi stop words
        "bhi", "hai", "hain", "toh", "kya", "koi", "nahi", "na", "aur",
        "mein", "se", "ka", "ki", "ko", "ne", "pe", "par", "wo", "yeh",
        "main", "hun", "tha", "kar", "raha", "rahi", "kuch",
        # WhatsApp artifacts
        "media", "omitted", "null", "deleted", "message",
        "http", "https", "www", "com",
        "image", "video", "audio", "sticker", "gif"
    ])

    word_count = Counter()
    for msg in messages:
        if target_person.lower() not in msg["speaker"].lower():
            continue
        if "omitted" in msg["text"].lower():
            continue
        words = re.findall(r"\b[a-zA-Z]{3,}\b", msg["text"].lower())
        for w in words:
            if w not in stop_words and w not in FILLERS:
                word_count[w] += 1

    return [{"word": w, "count": c} for w, c in word_count.most_common(top_n)]


# ──────────────────────────────────────────
# SIGNAL EXTRACTION
# ──────────────────────────────────────────

def is_noise(text: str) -> bool:
    t = text.lower().strip()
    if len(t) < 2:
        return True
    if t in FILLERS:
        return True
    if re.match(r"^[^a-zA-Z\u0900-\u097F]+$", t):
        return True
    if len(t.split()) < MIN_WORDS:
        return True
    if any(x in t for x in [
        "<media omitted>", "sticker omitted", "omitted",
        "deleted this message", "you deleted",
        "missed voice call", "missed video call", "null"
    ]):
        return True
    return False


def is_signal(text: str) -> bool:
    t = text.lower()
    if "?" in t and len(t.split()) >= 4:
        return True
    if any(k in t for k in SIGNAL_KEYWORDS):
        return True
    if any(e in text for e in ["❤", "😭", "😢", "🥺", "😤", "🙄"]):
        return True
    return False


def extract_signals(messages: list) -> list:
    return [msg for msg in messages if not is_noise(msg["text"]) and is_signal(msg["text"])]


# ──────────────────────────────────────────
# SIGNAL CAPPING
# ──────────────────────────────────────────

def cap_signals(signals: list) -> list:
    total = len(signals)
    if total <= SIGNAL_TOTAL_CAP:
        return signals

    cap = SIGNAL_CAP
    result = []
    seen = set()

    def add_slice(msgs):
        for m in msgs:
            key = (m["speaker"], m["text"])
            if key not in seen:
                seen.add(key)
                result.append(m)

    q1 = total // 4
    q2 = total // 2
    q3 = (total * 3) // 4

    add_slice(signals[:cap["start"]])
    add_slice(signals[q1: q1 + cap["start_mid"]])
    add_slice(signals[q2 - cap["mid"] // 2: q2 + cap["mid"] // 2])
    add_slice(signals[q3 - cap["mid_end"] // 2: q3 + cap["mid_end"] // 2])
    add_slice(signals[-cap["end"]:])

    print(f"✂️  Signal cap: {total} → {len(result)} sent to LLM")
    return result[:SIGNAL_TOTAL_CAP]


# ──────────────────────────────────────────
# BUILD FINAL CLEAN PAYLOAD
# ──────────────────────────────────────────

def build_clean_payload(messages: list, target_person: str) -> dict:
    counter, total = count_fillers(messages, target_person)
    behavior_context = build_behavior_context(counter, total)
    keyword_metadata = extract_keyword_metadata(messages, target_person)

    all_signals = extract_signals(messages)
    capped_signals = cap_signals(all_signals)

    formatted_chat = "\n".join(
        [f"{m['speaker']}: {m['text']}" for m in capped_signals]
    )

    return {
        "behavior_context": behavior_context,
        "keyword_metadata": keyword_metadata,
        "clean_chat":       formatted_chat,
        "signal_messages":  capped_signals,
        "signal_count":     len(capped_signals),
        "total_signals":    len(all_signals),
        "total_messages":   len(messages)
    }