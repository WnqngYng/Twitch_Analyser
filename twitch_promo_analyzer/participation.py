from __future__ import annotations

import re
from collections import Counter
from statistics import mean
from typing import Any

from .models import ChatMessage
from .sentiment import detect_intents, score_sentiment, sentiment_label
from .timing import filter_by_minutes, stream_origin


DEFAULT_BOT_USERS = {"streamelements", "nightbot", "moobot", "fossabot"}

PARTICIPATION_ISSUE_PATTERNS: dict[str, tuple[str, ...]] = {
    "how_to_participate": (
        r"\b(how do i|how to|how does|where do i|where is|what is the code|which code)\b",
        r"\b(come funziona|come si fa|come faccio|dove metto|dove trovo|quale codice|che codice)\b",
        r"\b(spieg|non capisco|non ho capito|huh|confused)\b",
    ),
    "code_or_link_request": (
        r"\b(!temu|!code|!deal|link|url|coupon|codice|buono)\b",
        r"\b(kav3769|temu\.com)\b",
    ),
    "app_or_signup_issue": (
        r"\b(app|applicaz|scaric|download|registr|account|login|nuovo utente)\b",
        r"\b(non riesco|non mi fa|non va|non funziona|errore|bug)\b",
    ),
    "offer_clarity": (
        r"\b(sconto|coupon|100.?€|euro|gratis|free|offerta|promo)\b",
        r"\b(cosa ricevo|cosa è|che cos'è|che vuol dire)\b",
    ),
    "trust_or_objection": (
        r"\b(scam|truffa|fake|sellout|sponsor|#ad|troppo|non vale|pessimo)\b",
        r"\b(non compro|no grazie|skip|nah|nope)\b",
    ),
}


def classify_participation_issue(text: str) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for issue_type, patterns in PARTICIPATION_ISSUE_PATTERNS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            hits.append(issue_type)
    return hits


def analyze_participation_issues(
    messages: list[ChatMessage],
    start_minute: float,
    end_minute: float,
    product_id: str | None = None,
    product_name: str | None = None,
) -> dict[str, Any]:
    origin = stream_origin(messages)
    window = [
        message
        for message in filter_by_minutes(messages, start_minute, end_minute, origin)
        if message.user.lower() not in DEFAULT_BOT_USERS
    ]

    issue_messages: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    for message in window:
        issues = classify_participation_issue(message.message)
        intents = detect_intents(message.message)
        if intents.get("confusion"):
            issues.append("how_to_participate")
        if intents.get("link_or_code_request"):
            issues.append("code_or_link_request")
        if intents.get("objection"):
            issues.append("trust_or_objection")

        unique_issues = sorted(set(issues))
        if not unique_issues:
            continue

        for issue in unique_issues:
            issue_counts[issue] += 1

        issue_messages.append(
            {
                "timestamp": message.timestamp.isoformat(),
                "user": message.user,
                "message": message.message,
                "issues": unique_issues,
                "sentiment": sentiment_label(score_sentiment(message.message)),
            }
        )

    return {
        "product_id": product_id,
        "product_name": product_name,
        "stream_minutes": [start_minute, end_minute],
        "viewer_messages_in_period": len(window),
        "issue_message_count": len(issue_messages),
        "issue_counts": dict(issue_counts),
        "sample_issues": issue_messages[:12],
    }


def analyze_participation_by_product(
    messages: list[ChatMessage],
    product_segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    for segment in product_segments:
        result = analyze_participation_issues(
            messages,
            segment["stream_minute_start"],
            segment["stream_minute_end"],
            product_id=segment.get("product_id"),
            product_name=segment.get("product_name"),
        )
        results.append({**segment, "participation_issues": result})
    return results
