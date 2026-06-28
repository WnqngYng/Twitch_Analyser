from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from statistics import mean
from typing import Any

from .analysis import STOPWORDS, safe_lift, summarize_window
from .models import ChatMessage
from .sentiment import detect_intents, score_sentiment, sentiment_label, tokenize_for_topics
from .timing import align_messages_to_window, filter_by_minutes, minute_bucket_counts, stream_origin


DEFAULT_BOT_USERS = {"streamelements", "nightbot", "moobot", "fossabot"}


def analyze_promotion_window(
    messages: list[ChatMessage],
    promo_start_minute: float,
    promo_end_minute: float,
    baseline_minutes: float = 9.0,
    post_minutes: float | None = None,
    brand_keywords: set[str] | None = None,
    cta_keywords: set[str] | None = None,
    promo_code: str = "KAV3769",
    exclude_users: set[str] | None = None,
    stream_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sorted_messages, timing_diagnostics = align_messages_to_window(
        messages,
        promo_start_minute,
        promo_end_minute,
    )
    origin = stream_origin(sorted_messages)
    baseline_start = max(0.0, promo_start_minute - baseline_minutes)
    promo_end = promo_end_minute
    post_end = promo_end + (post_minutes if post_minutes is not None else promo_end - promo_start_minute)

    brands = {item.lower() for item in brand_keywords or set()}
    brands.add(promo_code.lower())
    ctas = {item.lower() for item in cta_keywords or set()}
    ctas.add(promo_code.lower())
    excluded = DEFAULT_BOT_USERS | {user.lower() for user in exclude_users or set()}

    windows = {
        "baseline": filter_by_minutes(sorted_messages, baseline_start, promo_start_minute, origin),
        "promotion": filter_by_minutes(sorted_messages, promo_start_minute, promo_end, origin),
        "post_promotion": filter_by_minutes(sorted_messages, promo_end, post_end, origin),
    }

    audience_windows = {
        name: [message for message in window if message.user.lower() not in excluded]
        for name, window in windows.items()
    }

    baseline_span = max(promo_start_minute - baseline_start, 1)
    promo_span = max(promo_end - promo_start_minute, 1)
    post_span = max(post_end - promo_end, 1)

    summaries = {
        "baseline": summarize_window(audience_windows["baseline"], int(baseline_span)),
        "promotion": summarize_window(audience_windows["promotion"], int(promo_span)),
        "post_promotion": summarize_window(audience_windows["post_promotion"], int(post_span)),
    }

    word_analysis = build_word_analysis(audience_windows, brands, ctas)
    minute_series = minute_bucket_counts(sorted_messages, origin, exclude_users=excluded)

    performance = score_promotion_performance(
        summaries["baseline"],
        summaries["promotion"],
        summaries["post_promotion"],
        word_analysis,
        stream_stats,
        baseline_available=bool(audience_windows["baseline"]),
    )
    timing_diagnostics["baseline_message_count"] = len(audience_windows["baseline"])
    timing_diagnostics["promotion_message_count"] = len(audience_windows["promotion"])
    if not audience_windows["baseline"]:
        timing_diagnostics["warnings"].append(
            "Baseline window has no audience chat. Engagement lift and grade are low-confidence."
        )

    return {
        "vod": {
            "message_count": len(sorted_messages),
            "stream_start": origin.isoformat(),
            "stream_duration_minutes": round(
                (sorted_messages[-1].timestamp - origin).total_seconds() / 60,
                2,
            ),
        },
        "windows": {
            "baseline_minutes": [baseline_start, promo_start_minute],
            "promotion_minutes": [promo_start_minute, promo_end],
            "post_promotion_minutes": [promo_end, post_end],
        },
        "summaries": summaries,
        "lifts": {
            "messages_per_minute": round(
                safe_lift(
                    summaries["promotion"]["messages_per_minute"],
                    summaries["baseline"]["messages_per_minute"],
                ),
                3,
            ),
            "total_messages": round(
                safe_lift(
                    summaries["promotion"]["message_count"],
                    summaries["baseline"]["message_count"],
                ),
                3,
            ),
            "unique_chatters": round(
                safe_lift(
                    summaries["promotion"]["unique_chatters"],
                    summaries["baseline"]["unique_chatters"],
                ),
                3,
            ),
            "sentiment_delta": round(
                summaries["promotion"]["sentiment_avg"] - summaries["baseline"]["sentiment_avg"],
                3,
            ),
        },
        "word_analysis": word_analysis,
        "minute_message_series": [
            {"minute": minute, "messages": count}
            for minute, count in sorted(minute_series.items())
        ],
        "performance": performance,
        "stream_stats": stream_stats or {},
        "data_quality": timing_diagnostics,
        "settings": {
            "promo_start_minute": promo_start_minute,
            "promo_end_minute": promo_end,
            "baseline_minutes": baseline_minutes,
            "post_minutes": post_minutes,
            "promo_code": promo_code.upper(),
            "brand_keywords": sorted(brands),
            "cta_keywords": sorted(ctas),
            "exclude_users": sorted(excluded),
        },
    }


def build_word_analysis(
    windows: dict[str, list[ChatMessage]],
    brands: set[str],
    ctas: set[str],
) -> dict[str, Any]:
    promo_messages = windows["promotion"]
    baseline_messages = windows["baseline"]

    promo_terms = term_counter(promo_messages)
    baseline_terms = term_counter(baseline_messages)

    brand_mentions = count_keyword_hits(promo_messages, brands)
    cta_mentions = count_keyword_hits(promo_messages, ctas)
    cta_commands = count_pattern(promo_messages, re.compile(r"!temu\b", re.IGNORECASE))

    promo_sentiments = Counter(sentiment_label(score_sentiment(message.message)) for message in promo_messages)
    intent_totals: Counter[str] = Counter()
    for message in promo_messages:
        intent_totals.update(detect_intents(message.message))

    notable_comments = select_notable_comments(promo_messages)

    return {
        "promotion_top_terms": promo_terms.most_common(20),
        "baseline_top_terms": baseline_terms.most_common(20),
        "terms_lift": term_lift(promo_terms, baseline_terms, limit=15),
        "brand_mentions": brand_mentions,
        "cta_mentions": cta_mentions,
        "cta_command_count": cta_commands,
        "sentiment_distribution": dict(promo_sentiments),
        "intent_totals": dict(intent_totals),
        "notable_comments": notable_comments,
    }


def term_counter(messages: list[ChatMessage]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for message in messages:
        for token in tokenize_for_topics(message.message):
            if token not in STOPWORDS and len(token) > 2:
                counter[token] += 1
    return counter


def count_keyword_hits(messages: list[ChatMessage], keywords: set[str]) -> dict[str, int]:
    counts = {keyword: 0 for keyword in sorted(keywords)}
    if not keywords:
        return counts
    for message in messages:
        lowered = message.message.lower()
        for keyword in keywords:
            if keyword in lowered:
                counts[keyword] += 1
    return counts


def count_pattern(messages: list[ChatMessage], pattern: re.Pattern[str]) -> int:
    return sum(1 for message in messages if pattern.search(message.message))


def term_lift(promo: Counter[str], baseline: Counter[str], limit: int = 15) -> list[dict[str, Any]]:
    lifts: list[dict[str, Any]] = []
    for term, promo_count in promo.most_common(50):
        baseline_count = baseline.get(term, 0)
        lifts.append(
            {
                "term": term,
                "promotion_count": promo_count,
                "baseline_count": baseline_count,
                "lift": round(safe_lift(promo_count, baseline_count), 3),
            }
        )
    lifts.sort(key=lambda item: (item["lift"], item["promotion_count"]), reverse=True)
    return lifts[:limit]


def select_notable_comments(messages: list[ChatMessage], limit: int = 12) -> list[dict[str, Any]]:
    ranked = sorted(
        messages,
        key=lambda message: (abs(score_sentiment(message.message)), message.timestamp),
        reverse=True,
    )
    samples = []
    for message in ranked[:limit]:
        score = score_sentiment(message.message)
        samples.append(
            {
                "timestamp": message.timestamp.isoformat(),
                "user": message.user,
                "message": message.message,
                "sentiment": sentiment_label(score),
                "intents": list(detect_intents(message.message).keys()),
            }
        )
    return samples


def score_promotion_performance(
    baseline: dict[str, Any],
    promotion: dict[str, Any],
    post_promotion: dict[str, Any],
    word_analysis: dict[str, Any],
    stream_stats: dict[str, Any] | None,
    baseline_available: bool = True,
) -> dict[str, Any]:
    engagement_lift = safe_lift(
        promotion["messages_per_minute"],
        baseline["messages_per_minute"],
    )
    volume_lift = safe_lift(promotion["message_count"], baseline["message_count"])
    chatter_lift = safe_lift(
        promotion["unique_chatters"],
        baseline["unique_chatters"],
    )
    sentiment_delta = promotion["sentiment_avg"] - baseline["sentiment_avg"]
    intents = word_analysis.get("intent_totals", {})
    cta_commands = word_analysis.get("cta_command_count", 0)
    brand_total = sum(word_analysis.get("brand_mentions", {}).values())

    score = 0.0
    score += min(engagement_lift, 2.0) * 15
    score += min(volume_lift, 5.0) * 10
    score += min(chatter_lift, 2.0) * 25
    score += max(min(sentiment_delta, 0.5), -0.5) * 15
    score += min(cta_commands / 30.0, 1.0) * 15
    score += min(brand_total / 80.0, 1.0) * 10
    score += min(intents.get("purchase_intent", 0) / 5.0, 1.0) * 10
    score -= min(intents.get("objection", 0) / 8.0, 1.0) * 10
    score -= min(intents.get("confusion", 0) / 8.0, 1.0) * 5

    post_decay = safe_lift(
        post_promotion["messages_per_minute"],
        promotion["messages_per_minute"],
    )
    if post_decay < -0.25:
        score -= 5

    grade = grade_from_score(score)
    verdict = build_verdict(
        engagement_lift,
        chatter_lift,
        volume_lift,
        sentiment_delta,
        cta_commands,
        intents,
        grade,
    )

    result: dict[str, Any] = {
        "score": round(score, 1),
        "grade": grade,
        "verdict": verdict,
        "confidence": "normal" if baseline_available else "low_baseline_missing",
        "signals": {
            "engagement_lift": round(engagement_lift, 3),
            "volume_lift": round(volume_lift, 3),
            "unique_chatter_lift": round(chatter_lift, 3),
            "sentiment_delta": round(sentiment_delta, 3),
            "cta_command_count": cta_commands,
            "brand_mention_total": brand_total,
            "post_promotion_decay": round(post_decay, 3),
        },
    }
    if stream_stats:
        result["stream_context"] = {
            "avg_viewers": stream_stats.get("avg_viewers"),
            "peak_viewers": stream_stats.get("peak_viewers"),
            "hours_watched": stream_stats.get("hours_watched"),
            "source": stream_stats.get("source"),
        }
    if not baseline_available:
        result["note"] = (
            "No baseline chat was available before the promotion window. "
            "Use the grade only as a directional chat-health signal, not as proof of influencer performance."
        )
    return result


def grade_from_score(score: float) -> str:
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 45:
        return "C"
    if score >= 30:
        return "D"
    return "F"


def build_verdict(
    engagement_lift: float,
    chatter_lift: float,
    volume_lift: float,
    sentiment_delta: float,
    cta_commands: int,
    intents: dict[str, int],
    grade: str,
) -> str:
    parts: list[str] = []
    if engagement_lift >= 0.5:
        parts.append("Chat engagement rose strongly during the promotion window.")
    elif engagement_lift >= 0.15:
        parts.append("Chat engagement increased moderately during the promotion.")
    elif chatter_lift >= 0.5 or volume_lift >= 1.0:
        parts.append(
            "Per-minute chat pace was similar to the opening, but total participation and message volume rose sharply during the promotion."
        )
    else:
        parts.append("Chat engagement did not lift meaningfully versus the pre-promo baseline.")

    if sentiment_delta >= 0.05:
        parts.append("Sentiment trended slightly positive.")
    elif sentiment_delta <= -0.05:
        parts.append("Sentiment trended negative; monitor objections in chat.")
    else:
        parts.append("Sentiment stayed roughly neutral.")

    if cta_commands >= 15:
        parts.append(f"Viewers used the CTA command frequently ({cta_commands} times).")
    elif cta_commands >= 5:
        parts.append(f"Some viewers engaged with the CTA command ({cta_commands} times).")
    else:
        parts.append("CTA command usage was limited; consider a clearer on-screen prompt.")

    if intents.get("objection", 0) >= 3:
        parts.append("Multiple objection signals appeared; address trust and ad disclosure on stream.")

    parts.append(f"Overall grade: {grade}.")
    return " ".join(parts)
