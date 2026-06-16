from __future__ import annotations

import re
from collections import Counter


POSITIVE_TERMS = {
    "amazing",
    "awesome",
    "best",
    "bello",
    "bravo",
    "buying",
    "bought",
    "clean",
    "compro",
    "cool",
    "deal",
    "fire",
    "forte",
    "good",
    "grande",
    "great",
    "hype",
    "love",
    "meglio",
    "nice",
    "ordered",
    "perfect",
    "pog",
    "saved",
    "sconto",
    "solid",
    "spettacolo",
    "thanks",
    "top",
    "want",
    "worth",
    "yes",
}

NEGATIVE_TERMS = {
    "annoying",
    "bad",
    "boring",
    "brutta",
    "cringe",
    "expensive",
    "fake",
    "hate",
    "lame",
    "nah",
    "nope",
    "noia",
    "overpriced",
    "pessimo",
    "scam",
    "schifo",
    "sellout",
    "skip",
    "sus",
    "trash",
    "ugh",
    "waste",
    "worse",
}

INTENT_PATTERNS = {
    "purchase_intent": (
        r"\b(buy|buying|bought|ordered|ordering|checkout|cart|need this|copping|grabbed)\b",
    ),
    "link_or_code_request": (
        r"\b(link|url|where|code|coupon|command|!code|!deal)\b",
    ),
    "confusion": (
        r"\b(what is|how does|how do|huh|confused|explain|where is|which one|does it)\b",
    ),
    "objection": (
        r"\b(expensive|overpriced|scam|fake|ad|sellout|too much|not worth|no thanks|skip)\b",
    ),
    "excitement": (
        r"\b(hype|pog|fire|love|awesome|lets go|let's go|need this|amazing|wow)\b",
    ),
    "spam": (
        r"(.)\1{5,}",
        r"\b(lol|lmao|pog|hype)\b(?:\s+\b\1\b){3,}",
    ),
}

WORD_RE = re.compile(r"[a-zA-Z0-9_']+")


def score_sentiment(text: str) -> float:
    tokens = [token.lower() for token in WORD_RE.findall(text)]
    if not tokens:
        return 0.0

    score = 0
    for token in tokens:
        if token in POSITIVE_TERMS:
            score += 1
        if token in NEGATIVE_TERMS:
            score -= 1

    lowered = text.lower()
    if "not " in lowered or "don't" in lowered or "dont" in lowered:
        score -= 0.5
    if "!!" in text and score > 0:
        score += 0.5
    if "??" in text and score < 0:
        score -= 0.5

    return max(-1.0, min(1.0, score / max(3, len(tokens) ** 0.5)))


def sentiment_label(score: float) -> str:
    if score >= 0.2:
        return "positive"
    if score <= -0.2:
        return "negative"
    return "neutral"


def detect_intents(text: str) -> Counter[str]:
    lowered = text.lower()
    counts: Counter[str] = Counter()
    for intent, patterns in INTENT_PATTERNS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            counts[intent] += 1
    return counts


def tokenize_for_topics(text: str) -> list[str]:
    return [token.lower() for token in WORD_RE.findall(text) if len(token) > 2]
