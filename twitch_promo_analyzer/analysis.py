from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from statistics import mean
from typing import Any

from .models import ChatMessage
from .promotions import PROMO_TERMS, detect_promotion_events
from .sentiment import detect_intents, score_sentiment, sentiment_label, tokenize_for_topics


STOPWORDS = {
    "and",
    "are",
    "but",
    "can",
    "for",
    "how",
    "just",
    "like",
    "link",
    "not",
    "now",
    "off",
    "the",
    "this",
    "that",
    "use",
    "what",
    "where",
    "with",
    "you",
    "your",
}


def analyze_campaign(
    messages: list[ChatMessage],
    influencers: set[str] | None = None,
    brands: set[str] | None = None,
    window_minutes: int = 5,
    baseline_minutes: int = 5,
) -> dict[str, Any]:
    sorted_messages = sorted(messages, key=lambda item: item.timestamp)
    events = detect_promotion_events(sorted_messages, influencers=influencers, brands=brands)
    event_results: list[dict[str, Any]] = []

    for event in events:
        response_start = event.timestamp
        response_end = response_start + timedelta(minutes=window_minutes)
        baseline_start = response_start - timedelta(minutes=baseline_minutes)

        response_messages = [
            item
            for item in sorted_messages
            if response_start < item.timestamp <= response_end
            and item.user.lower() != event.influencer.lower()
        ]
        baseline_messages = [
            item
            for item in sorted_messages
            if baseline_start <= item.timestamp < response_start
            and item.user.lower() != event.influencer.lower()
        ]

        response = summarize_window(response_messages, window_minutes)
        baseline = summarize_window(baseline_messages, baseline_minutes)
        engagement_lift = safe_lift(response["messages_per_minute"], baseline["messages_per_minute"])
        sentiment_delta = response["sentiment_avg"] - baseline["sentiment_avg"]

        event_results.append(
            {
                **event.to_dict(),
                "window_minutes": window_minutes,
                "baseline_minutes": baseline_minutes,
                "response": response,
                "baseline": baseline,
                "engagement_lift": round(engagement_lift, 3),
                "sentiment_delta": round(sentiment_delta, 3),
                "viewer_count_delta": viewer_delta(response_messages, baseline_messages),
            }
        )

    return {
        "summary": build_summary(sorted_messages, event_results),
        "events": event_results,
        "settings": {
            "window_minutes": window_minutes,
            "baseline_minutes": baseline_minutes,
            "influencers": sorted(influencers or []),
            "brands": sorted(brands or []),
        },
    }


def summarize_window(messages: list[ChatMessage], span_minutes: int) -> dict[str, Any]:
    users = {message.user.lower() for message in messages}
    sentiment_scores = [score_sentiment(message.message) for message in messages]
    sentiment_counts: Counter[str] = Counter(sentiment_label(score) for score in sentiment_scores)
    intents: Counter[str] = Counter()
    topics: Counter[str] = Counter()

    for message in messages:
        intents.update(detect_intents(message.message))
        topics.update(
            token
            for token in tokenize_for_topics(message.message)
            if token not in STOPWORDS and token not in PROMO_TERMS
        )

    samples = select_sample_comments(messages, sentiment_scores)

    return {
        "message_count": len(messages),
        "unique_chatters": len(users),
        "messages_per_minute": round(len(messages) / max(span_minutes, 1), 3),
        "sentiment_avg": round(mean(sentiment_scores), 3) if sentiment_scores else 0.0,
        "sentiment_counts": {
            "positive": sentiment_counts.get("positive", 0),
            "neutral": sentiment_counts.get("neutral", 0),
            "negative": sentiment_counts.get("negative", 0),
        },
        "intents": dict(intents),
        "top_terms": topics.most_common(8),
        "sample_comments": samples,
        "viewer_count": viewer_snapshot(messages),
    }


def build_summary(messages: list[ChatMessage], events: list[dict[str, Any]]) -> dict[str, Any]:
    influencer_stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"events": 0, "avg_lift": 0.0, "avg_sentiment": 0.0}
    )
    for event in events:
        stats = influencer_stats[event["influencer"]]
        stats["events"] += 1
        stats["avg_lift"] += event["engagement_lift"]
        stats["avg_sentiment"] += event["response"]["sentiment_avg"]

    for stats in influencer_stats.values():
        event_count = max(int(stats["events"]), 1)
        stats["avg_lift"] = round(stats["avg_lift"] / event_count, 3)
        stats["avg_sentiment"] = round(stats["avg_sentiment"] / event_count, 3)

    best_event = None
    if events:
        best_event = max(
            events,
            key=lambda event: (
                event["engagement_lift"],
                event["response"]["sentiment_avg"],
                event["response"]["intents"].get("purchase_intent", 0),
            ),
        )["event_id"]

    return {
        "message_count": len(messages),
        "unique_chatters": len({message.user.lower() for message in messages}),
        "detected_promotions": len(events),
        "avg_engagement_lift": round(mean(event["engagement_lift"] for event in events), 3)
        if events
        else 0.0,
        "avg_response_sentiment": round(
            mean(event["response"]["sentiment_avg"] for event in events), 3
        )
        if events
        else 0.0,
        "best_event": best_event,
        "influencers": dict(influencer_stats),
    }


def safe_lift(current: float, baseline: float) -> float:
    if baseline <= 0 and current > 0:
        return 1.0
    if baseline <= 0:
        return 0.0
    return (current - baseline) / baseline


def viewer_snapshot(messages: list[ChatMessage]) -> dict[str, int | None]:
    values = [message.viewer_count for message in messages if message.viewer_count is not None]
    if not values:
        return {"start": None, "end": None, "max": None}
    return {"start": values[0], "end": values[-1], "max": max(values)}


def viewer_delta(response_messages: list[ChatMessage], baseline_messages: list[ChatMessage]) -> int | None:
    before_values = [message.viewer_count for message in baseline_messages if message.viewer_count is not None]
    after_values = [message.viewer_count for message in response_messages if message.viewer_count is not None]
    if not before_values or not after_values:
        return None
    return after_values[-1] - before_values[-1]


def select_sample_comments(messages: list[ChatMessage], scores: list[float]) -> list[dict[str, Any]]:
    ranked = sorted(
        zip(messages, scores),
        key=lambda pair: (abs(pair[1]), pair[0].timestamp),
        reverse=True,
    )
    samples = []
    for message, score in ranked[:5]:
        samples.append(
            {
                "timestamp": message.timestamp.isoformat(),
                "user": message.user,
                "message": message.message,
                "sentiment": sentiment_label(score),
                "score": round(score, 3),
            }
        )
    return samples
