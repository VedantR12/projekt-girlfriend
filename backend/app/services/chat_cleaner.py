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
SIGNAL_CAP = {
    "start":     50,
    "start_mid": 80,
    "mid":       60,
    "mid_end":   80,
    "end":       50,
}
SIGNAL_TOTAL_CAP = sum(SIGNAL_CAP.values())  # 320

CASUAL_CAP = 50
TONE_SAMPLE_CAP = 5
QUIRK_SAMPLE_CAP = 30



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
# SIGNAL CAPPING — 5-zone sampling
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

    q1 = total // 4
    q2 = total // 2
    q3 = (total * 3) // 4

    add_slice(signals[:cap["start"]])
    add_slice(signals[q1: q1 + cap["start_mid"]])
    add_slice(signals[q2 - cap["mid"] // 2: q2 + cap["mid"] // 2])
    add_slice(signals[q3 - cap["mid_end"] // 2: q3 + cap["mid_end"] // 2])
    add_slice(signals[-cap["end"]:])

    print(f"✂️  Signals: {total} → {len(result)}")
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
# TONE SAMPLE EXTRACTION
# Real back-and-forth exchanges showing HOW she responds in sequence
# ──────────────────────────────────────────

def extract_tone_samples(messages: list, target_person: str, max_samples: int = TONE_SAMPLE_CAP) -> list:
    """
    Find 3-5 real exchanges: other person says something → persona replies (→ optional follow-up).
    Sampled from start, mid, end zones so it captures different conversation moods.
    """
    samples = []
    total = len(messages)
    zone_starts = [0, total // 3, (2 * total) // 3]

    for zone_start in zone_starts:
        zone = messages[zone_start: min(zone_start + 200, total)]

        for i, msg in enumerate(zone):
            if target_person.lower() not in msg["speaker"].lower():
                continue
            if is_noise(msg["text"]) or len(msg["text"].split()) < 3:
                continue

            # Find preceding message from the other person
            prev = None
            for j in range(i - 1, max(0, i - 3), -1):
                if target_person.lower() not in zone[j]["speaker"].lower():
                    if not is_noise(zone[j]["text"]):
                        prev = zone[j]
                        break

            if not prev:
                continue

            # Check for follow-up from persona
            followup = None
            if i + 1 < len(zone):
                nxt = zone[i + 1]
                if target_person.lower() in nxt["speaker"].lower() and not is_noise(nxt["text"]):
                    followup = nxt["text"].strip()

            samples.append({
                "trigger":  prev["text"].strip(),
                "response": msg["text"].strip(),
                "followup": followup,
            })

            if len(samples) >= max_samples:
                break

        if len(samples) >= max_samples:
            break

    return samples[:max_samples]


# ──────────────────────────────────────────
# TYPING QUIRKS EXTRACTION
# Specific idiosyncrasies that make it feel like THIS person
# ──────────────────────────────────────────

def extract_typing_quirks(messages: list, target_person: str) -> dict:
    """
    Analyzes target_person's messages for 6 concrete typing patterns.
    Returns dict of quirk_name → description string.
    """
    target_msgs = [
        m["text"] for m in messages
        if target_person.lower() in m["speaker"].lower()
        and not is_noise(m["text"])
    ]
    if not target_msgs:
        return {}

    total = len(target_msgs)
    # Sample from start, mid, end
    sample = (
        target_msgs[:QUIRK_SAMPLE_CAP]
        + target_msgs[total // 2: total // 2 + QUIRK_SAMPLE_CAP]
        + target_msgs[-QUIRK_SAMPLE_CAP:]
    )

    quirks = {}

    # 1. Question mark style
    q_counts = Counter()
    for msg in sample:
        if "?" in msg:
            q_counts[msg.count("?")] += 1
    if q_counts:
        most_q = q_counts.most_common(1)[0][0]
        if most_q >= 3:
            quirks["question_style"] = "uses ??? for questions"
        elif most_q == 2:
            quirks["question_style"] = "uses ?? for questions"
        else:
            quirks["question_style"] = "uses single ? for questions"

    # 2. Trailing ellipsis
    if sum(1 for m in sample if "..." in m or ".." in m) > len(sample) * 0.15:
        quirks["trailing_style"] = "often uses ... to trail off"

    # 3. Capitalization
    all_lower = sum(1 for m in sample if m == m.lower() and any(c.isalpha() for c in m))
    if all_lower / max(len(sample), 1) > 0.7:
        quirks["capitalization"] = "almost always lowercase"
    elif sum(1 for m in sample if any(c.isupper() for c in m)) / max(len(sample), 1) > 0.5:
        quirks["capitalization"] = "sometimes uses ALL CAPS for emphasis"

    # 4. Abbreviations actually used
    all_words = []
    for msg in sample:
        all_words.extend(re.findall(r"\b\w{2,5}\b", msg.lower()))
    freq = Counter(all_words)
    known = ["mko", "tko", "bc", "ngl", "idk", "tbh", "rn", "lmk", "omg", "ik", "np", "ty", "plz", "pls"]
    found = [a for a in known if freq.get(a, 0) >= 2]
    if found:
        quirks["abbreviations"] = f"uses: {', '.join(found[:6])}"

    # 5. Letter stretching (haaaaaa, noooo)
    examples = []
    for msg in sample:
        for w in re.findall(r"\b\w+\b", msg):
            if re.search(r"(.)\1{2,}", w):
                examples.append(w)
                break
    if len(examples) > len(sample) * 0.08:
        quirks["emphasis_style"] = f"stretches letters for emphasis (e.g. {examples[0]})"

    # 6. Sentence ending punctuation
    no_punct = sum(1 for m in sample if m and m[-1] not in ".!?")
    if no_punct / max(len(sample), 1) > 0.7:
        quirks["sentence_ending"] = "rarely ends with punctuation"

    return quirks

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

    # New: tone samples + typing quirks
    tone_samples  = extract_tone_samples(messages, target_person)
    typing_quirks = extract_typing_quirks(messages, target_person)

    print(f"📊 {target_person}: {len(messages)} total | "
          f"{len(signal_msgs)} signals → {len(capped_signals)} capped | "
          f"{len(casual_msgs)} casual → {len(capped_casual)} capped | "
          f"{len(tone_samples)} tone samples | {len(typing_quirks)} quirks")

    return {
        "trait_signals":  capped_signals,
        "casual_samples": capped_casual,
        "tone_samples":   tone_samples,
        "typing_quirks":  typing_quirks,
        "filler_tokens":  filler_tokens,
        "top_keywords":   top_keywords,
        "total_messages": len(messages),
        "target_signals": len(signal_msgs),
    }