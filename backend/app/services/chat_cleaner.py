import re
from collections import Counter

# ──────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────

FILLERS = [
    "hmm", "ok", "okay", "yes", "no", "k", "lol", "haha", "hm", "oh",
    "acha", "accha", "ha", "hahaha", "lmao", "lmfao", "💀", "😂"
]

MIN_WORDS_SIGNAL = 4   # min words to be a trait signal
MIN_WORDS_CASUAL = 1   # casual messages can be very short

SIGNAL_KEYWORDS = [
    "always", "never", "like", "love", "hate",
    "think", "feel", "believe", "want",
    "should", "need", "prefer",
    "because", "why", "how", "what",
    "when", "who", "where",
    "scared", "happy", "sad", "angry", "excited",
    "miss", "wish", "hope", "dream", "remember",
    "used to", "plan", "going to", "want to",
    "seriously", "literally", "actually", "honestly",
    "bhai", "yaar", "nahi", "kuch", "kya", "mujhe",
    "chahiye", "lagta", "pata", "tha", "hua"
]

CASUAL_PATTERNS = [
    r"^h[iae]+\b",           # hi, hii, hey, ha
    r"^hello",
    r"^what.?s up",
    r"^wassup",
    r"^sup\b",
    r"^kya (hua|kar|chal|baat)",
    r"^kaise",
    r"^kaisi",
    r"^aur bata",
    r"^bata",
    r"^suno",
    r"^arre",
    r"^are\b",
    r"^oye\b",
    r"^haan\b",
    r"^accha\b",
    r"^lol\b",
    r"^😂+$",
    r"^💀+$",
    r"^haha",
    r"^okay",
    r"^ok\b",
    r"^thik",
    r"^theek",
]

WHATSAPP_NOISE = [
    "media omitted", "sticker omitted", "omitted",
    "deleted this message", "you deleted",
    "missed voice call", "missed video call",
    "null", "changed the subject", "added", "left"
]

# Signal cap — 300-400 signals across 5 zones
# Sampling ratio: fewer from start, heavy toward recent end
SIGNAL_CAP = {
    "start":     20,
    "start_mid": 40,
    "mid":       50,
    "mid_end_a": 60,
    "mid_end_b": 60,
    "mid_end_c": 50,
    "end":       40,
}
SIGNAL_TOTAL_CAP = sum(SIGNAL_CAP.values())  # 320

CASUAL_CAP = 50


# ──────────────────────────────────────────
# FILTERS
# ──────────────────────────────────────────

def is_noise(text: str) -> bool:
    t = text.lower().strip()
    if len(t) < 1:
        return True
    if any(x in t for x in WHATSAPP_NOISE):
        return True
    if re.match(r"^https?://\S+$", t):
        return True
    return False


def is_casual(text: str) -> bool:
    t = text.lower().strip()
    for pattern in CASUAL_PATTERNS:
        if re.match(pattern, t):
            return True
    # Short reactions (1-2 words, no signal keyword)
    words = t.split()
    if len(words) <= 2 and not any(k in t for k in SIGNAL_KEYWORDS):
        return True
    return False


def is_signal(text: str) -> bool:
    t = text.lower()
    words = t.split()
    if len(words) < MIN_WORDS_SIGNAL:
        return False
    if "?" in t and len(words) >= 4:
        return True
    if any(k in t for k in SIGNAL_KEYWORDS):
        return True
    if any(e in text for e in ["❤", "😭", "😢", "🥺", "😤", "🙄", "😠"]):
        return True
    # Long enough message is a signal by itself
    if len(words) >= 8:
        return True
    return False


# ──────────────────────────────────────────
# SIGNAL CAPPING — 7-zone, recent-heavy sampling
# ──────────────────────────────────────────

def cap_signals(signals: list) -> list:
    total = len(signals)
    if total <= SIGNAL_TOTAL_CAP:
        return signals

    cap  = SIGNAL_CAP
    seen = set()
    result = []

    def add_slice(msgs):
        for m in msgs:
            key = (m["speaker"], m["text"])
            if key not in seen:
                seen.add(key)
                result.append(m)

    # 7 zones — recent chat (66-100%) gets 4 of 7 zones
    q1 = total // 6           # 16%
    q2 = total // 3           # 33%
    q3 = total // 2           # 50%
    q4 = (total * 2) // 3     # 66%
    q5 = (total * 5) // 6     # 83%

    add_slice(signals[:cap["start"]])                                              # 0–16%
    add_slice(signals[q1: q1 + cap["start_mid"]])                                 # 16–33%
    add_slice(signals[q2: q2 + cap["mid"]])                                       # 33–50%
    add_slice(signals[q3: q3 + cap["mid_end_a"]])                                 # 50–66%
    add_slice(signals[q4: q4 + cap["mid_end_b"]])                                 # 66–83%
    add_slice(signals[q5 - cap["mid_end_c"] // 2: q5 + cap["mid_end_c"] // 2])   # 75–91%
    add_slice(signals[-cap["end"]:])                                               # last 40

    print(f"✂️  Signals: {total} → {len(result)} (7-zone recent-heavy)")
    return result[:SIGNAL_TOTAL_CAP]


# ──────────────────────────────────────────
# METADATA EXTRACTION
# ──────────────────────────────────────────

def extract_fillers(messages: list, target_person: str) -> list:
    counter = Counter()
    total = 0
    for msg in messages:
        if target_person.lower() not in msg["speaker"].lower():
            continue
        words = re.findall(r"[\w😂💀]+", msg["text"].lower())
        for w in words:
            if w in FILLERS:
                counter[w] += 1
                total += 1

    result = []
    for word, count in counter.most_common(10):
        freq = count / total if total > 0 else 0
        level = "very_high" if freq > 0.25 else "high" if freq > 0.15 else "moderate" if freq > 0.08 else "low"
        result.append({"token": word, "count": count, "frequency": level})
    return result


def extract_keywords(messages: list, target_person: str, top_n: int = 25) -> list:
    stop_words = {
        "the", "a", "an", "is", "was", "are", "were", "i", "you", "he", "she",
        "we", "they", "it", "this", "that", "and", "or", "but", "in", "on",
        "at", "to", "of", "for", "with", "my", "your", "his", "her", "our",
        "me", "him", "us", "them", "be", "do", "does", "did", "have", "has",
        "had", "will", "would", "could", "should", "just", "not", "so", "if",
        "then", "than", "too", "very", "much", "also", "its", "about",
        "bhi", "hai", "hain", "toh", "kya", "koi", "nahi", "na", "aur",
        "mein", "se", "ka", "ki", "ko", "ne", "pe", "par", "wo", "yeh",
        "main", "hun", "tha", "kar", "raha", "rahi", "kuch",
        "media", "omitted", "null", "deleted", "message",
        "http", "https", "www", "com", "image", "video", "audio", "sticker"
    }
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
# MAIN ENTRY — build_signal_bundle
# ──────────────────────────────────────────

def build_signal_bundle(messages: list, target_person: str) -> dict:
    """
    Takes parsed messages, returns signal_bundle for persona generation.

    Keys:
        trait_signals:  320 capped signals from 5 zones (for personality/style extraction)
        casual_samples: up to 50 casual messages (for hi/hello behavior)
        filler_tokens:  top filler words with counts
        top_keywords:   top meaningful words
        total_messages: int
        target_signals: int (before cap)
    """

    # Filter to target person's messages only
    target_msgs = [
        m for m in messages
        if target_person.lower() in m["speaker"].lower()
        and not is_noise(m["text"])
    ]

    # Split into casual vs signal
    casual_msgs  = [m for m in target_msgs if is_casual(m["text"])]
    signal_msgs  = [m for m in target_msgs if is_signal(m["text"])]

    # Cap both
    capped_signals = cap_signals(signal_msgs)
    capped_casual  = casual_msgs[:CASUAL_CAP]

    # Metadata from ALL target messages
    filler_tokens = extract_fillers(messages, target_person)
    top_keywords  = extract_keywords(messages, target_person)

    print(f"📊 {target_person}: {len(messages)} total | "
          f"{len(signal_msgs)} signals → {len(capped_signals)} capped | "
          f"{len(casual_msgs)} casual → {len(capped_casual)} capped")

    return {
        "trait_signals":   capped_signals,
        "casual_samples":  capped_casual,
        "filler_tokens":   filler_tokens,
        "top_keywords":    top_keywords,
        "total_messages":  len(messages),
        "target_signals":  len(signal_msgs),
    }