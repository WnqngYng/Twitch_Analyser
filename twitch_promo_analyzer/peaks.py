from __future__ import annotations

import re
from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from .models import ChatMessage
from .sentiment import detect_intents, score_sentiment, sentiment_label
from .timing import align_messages_to_window, offset_minutes, stream_origin


DEFAULT_BOT_USERS = {"streamelements", "nightbot", "moobot", "fossabot"}
BOT_COPY_MARKERS = ("clicca su https://app.temu.com", "app solo per nuovi utenti")


def analyze_promotion_peaks(
    messages: list[ChatMessage],
    promo_start_minute: float,
    promo_end_minute: float,
    promo_code: str = "KAV3769",
    exclude_users: set[str] | None = None,
    top_n: int = 8,
    rolling_window_minutes: int = 3,
) -> dict[str, Any]:
    sorted_messages, timing_diagnostics = align_messages_to_window(
        messages,
        promo_start_minute,
        promo_end_minute,
    )
    origin = stream_origin(sorted_messages)
    excluded = DEFAULT_BOT_USERS | {user.lower() for user in exclude_users or set()}
    code_pattern = re.compile(re.escape(promo_code), re.IGNORECASE)

    promo_messages = [
        message
        for message in sorted_messages
        if promo_start_minute <= offset_minutes(message, origin) < promo_end_minute
        and message.user.lower() not in excluded
    ]

    minute_counts = Counter(int(offset_minutes(message, origin)) for message in promo_messages)
    promo_relative = {
        minute - int(promo_start_minute): count
        for minute, count in minute_counts.items()
        if promo_start_minute <= minute < promo_end_minute
    }

    peaks = build_peak_rankings(
        promo_messages,
        origin,
        promo_start_minute,
        promo_code=code_pattern,
        top_n=top_n,
    )
    rolling = rolling_message_rate(
        minute_counts,
        int(promo_start_minute),
        int(promo_end_minute),
        window_minutes=rolling_window_minutes,
    )

    code_stats = analyze_promo_code(
        [
            message
            for message in sorted_messages
            if promo_start_minute <= offset_minutes(message, origin) < promo_end_minute
        ],
        code_pattern,
        origin,
        int(promo_start_minute),
    )

    return {
        "promo_code": promo_code.upper(),
        "promo_window_minutes": [promo_start_minute, promo_end_minute],
        "minute_message_counts": [
            {
                "stream_minute": minute,
                "promo_minute": round(minute - promo_start_minute, 2),
                "messages": count,
            }
            for minute, count in sorted(minute_counts.items())
        ],
        "promo_relative_counts": [
            {"promo_minute": minute, "messages": count}
            for minute, count in sorted(promo_relative.items())
        ],
        "top_peaks_by_minute": peaks,
        "top_rolling_windows": rolling[:top_n],
        "promo_code_activity": code_stats,
        "data_quality": timing_diagnostics,
        "summary": summarize_peaks(peaks, rolling, code_stats),
    }


def build_peak_rankings(
    promo_messages: list[ChatMessage],
    origin,
    promo_start_minute: float,
    promo_code: re.Pattern[str],
    top_n: int,
) -> list[dict[str, Any]]:
    buckets: dict[int, list[ChatMessage]] = defaultdict(list)
    for message in promo_messages:
        minute = int(offset_minutes(message, origin))
        buckets[minute].append(message)

    ranked = sorted(buckets.items(), key=lambda item: len(item[1]), reverse=True)[:top_n]
    peaks: list[dict[str, Any]] = []
    for stream_minute, bucket in ranked:
        promo_minute = round(stream_minute - promo_start_minute, 2)
        scores = [score_sentiment(message.message) for message in bucket]
        intents: Counter[str] = Counter()
        for message in bucket:
            intents.update(detect_intents(message.message))

        code_hits = sum(1 for message in bucket if promo_code.search(message.message))
        sample = select_peak_samples(bucket, promo_code)

        peaks.append(
            {
                "stream_minute": stream_minute,
                "promo_minute": promo_minute,
                "timestamp_hint": bucket[0].timestamp.isoformat(),
                "message_count": len(bucket),
                "unique_chatters": len({message.user.lower() for message in bucket}),
                "promo_code_mentions": code_hits,
                "avg_sentiment": round(mean(scores), 3) if scores else 0.0,
                "intents": dict(intents),
                "top_reactions": sample,
            }
        )
    return peaks


def select_peak_samples(
    bucket: list[ChatMessage],
    promo_code: re.Pattern[str],
    limit: int = 6,
) -> list[dict[str, Any]]:
    organic = [
        message
        for message in bucket
        if not any(marker in message.message.lower() for marker in BOT_COPY_MARKERS)
    ]
    pool = organic or bucket
    ranked = sorted(
        pool,
        key=lambda message: (
            bool(promo_code.search(message.message)),
            abs(score_sentiment(message.message)),
        ),
        reverse=True,
    )
    samples = []
    for message in ranked[:limit]:
        score = score_sentiment(message.message)
        samples.append(
            {
                "user": message.user,
                "message": message.message[:280],
                "sentiment": sentiment_label(score),
                "mentions_promo_code": bool(promo_code.search(message.message)),
            }
        )
    return samples


def rolling_message_rate(
    minute_counts: Counter[int],
    start_minute: int,
    end_minute: int,
    window_minutes: int = 3,
) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    for minute in range(start_minute, end_minute - window_minutes + 1):
        total = sum(minute_counts.get(minute + offset, 0) for offset in range(window_minutes))
        windows.append(
            {
                "stream_minute_start": minute,
                "stream_minute_end": minute + window_minutes,
                "promo_minute_start": minute - start_minute,
                "window_minutes": window_minutes,
                "messages": total,
                "messages_per_minute": round(total / window_minutes, 2),
            }
        )
    windows.sort(key=lambda item: item["messages"], reverse=True)
    return windows


def analyze_promo_code(
    messages: list[ChatMessage],
    code_pattern: re.Pattern[str],
    origin,
    promo_start_minute: int,
) -> dict[str, Any]:
    hits = [message for message in messages if code_pattern.search(message.message)]
    organic = [
        message
        for message in hits
        if message.user.lower() not in DEFAULT_BOT_USERS
        and not any(marker in message.message.lower() for marker in BOT_COPY_MARKERS)
    ]
    bot_copy = [message for message in hits if message not in organic]

    by_minute = Counter(int(offset_minutes(message, origin)) for message in hits)
    organic_by_minute = Counter(int(offset_minutes(message, origin)) for message in organic)

    return {
        "total_mentions": len(hits),
        "organic_mentions": len(organic),
        "bot_or_copy_paste_mentions": len(bot_copy),
        "unique_users_with_code": len({message.user.lower() for message in organic}),
        "by_stream_minute": [
            {
                "stream_minute": minute,
                "promo_minute": minute - promo_start_minute,
                "mentions": count,
            }
            for minute, count in organic_by_minute.most_common(10)
        ],
        "peak_code_minutes": [
            {"stream_minute": minute, "mentions": count}
            for minute, count in by_minute.most_common(5)
        ],
    }


def summarize_peaks(
    peaks: list[dict[str, Any]],
    rolling: list[dict[str, Any]],
    code_stats: dict[str, Any],
) -> str:
    if not peaks:
        return "No promotion chat peaks detected."

    top = peaks[0]
    roll = rolling[0] if rolling else None
    parts = [
        f"Strongest single minute: promo minute {top['promo_minute']} "
        f"(stream {top['stream_minute']}) with {top['message_count']} messages."
    ]
    if roll:
        parts.append(
            f"Strongest {roll['window_minutes']}-minute burst: promo minutes "
            f"{roll['promo_minute_start']}–{roll['promo_minute_start'] + roll['window_minutes']} "
            f"({roll['messages']} messages)."
        )
    if code_stats.get("organic_mentions"):
        parts.append(
            f"Promo code appeared {code_stats['organic_mentions']} times in organic chat "
            f"({code_stats['total_mentions']} including bot/copy-paste)."
        )
    else:
        parts.append("Promo code was mostly pushed via bot CTA copy-paste, not organic chat.")
    return " ".join(parts)
