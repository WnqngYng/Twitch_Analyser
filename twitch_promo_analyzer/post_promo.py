from __future__ import annotations

from collections import Counter
from typing import Any

from .analysis import safe_lift
from .models import ChatMessage
from .timing import align_messages_to_window, filter_by_minutes, stream_origin


DEFAULT_BOT_USERS = {"streamelements", "nightbot", "moobot", "fossabot"}
PROMO_SIGNAL_RE = __import__("re").compile(r"!temu|kav3769|temu\.com|\btemu\b", __import__("re").I)


def analyze_post_promotion_interest(
    messages: list[ChatMessage],
    promo_start_minute: float,
    promo_end_minute: float,
    post_windows: list[tuple[float, float]] | None = None,
) -> dict[str, Any]:
    aligned_messages, timing_diagnostics = align_messages_to_window(
        messages,
        promo_start_minute,
        promo_end_minute,
    )
    origin = stream_origin(aligned_messages)
    if post_windows is None:
        duration = (
            max(aligned_messages, key=lambda item: item.timestamp).timestamp - origin
        ).total_seconds() / 60
        post_windows = [
            (promo_end_minute, promo_end_minute + 30),
            (promo_end_minute + 30, promo_end_minute + 90),
            (promo_end_minute + 90, duration),
        ]

    promo_messages = audience_window(aligned_messages, origin, promo_start_minute, promo_end_minute)
    windows: list[dict[str, Any]] = []

    for start, end in post_windows:
        if start >= end:
            continue
        window_messages = audience_window(aligned_messages, origin, start, end)
        promo_signals = [message for message in window_messages if PROMO_SIGNAL_RE.search(message.message)]
        windows.append(
            {
                "label": window_label(start, end, promo_end_minute),
                "stream_minutes": [start, end],
                "message_count": len(window_messages),
                "unique_chatters": len({message.user.lower() for message in window_messages}),
                "promo_signal_messages": len(promo_signals),
                "promo_signals_per_100_messages": round(
                    (len(promo_signals) / max(len(window_messages), 1)) * 100,
                    2,
                ),
                "sample_comments": [message.message[:200] for message in promo_signals[:5]],
            }
        )

    promo_signal_rate = len([message for message in promo_messages if PROMO_SIGNAL_RE.search(message.message)])
    post_first = windows[0] if windows else None
    retention_ratio = None
    if post_first and promo_signal_rate:
        retention_ratio = round(post_first["promo_signal_messages"] / promo_signal_rate, 3)

    return {
        "promo_window_minutes": [promo_start_minute, promo_end_minute],
        "during_promo": {
            "messages": len(promo_messages),
            "promo_signal_messages": promo_signal_rate,
            "promo_signals_per_100_messages": round(
                (promo_signal_rate / max(len(promo_messages), 1)) * 100,
                2,
            ),
        },
        "post_promo_windows": windows,
        "retention_ratio_first_30min": retention_ratio,
        "data_quality": timing_diagnostics,
        "verdict": build_post_promo_verdict(windows, promo_signal_rate, retention_ratio),
    }


def audience_window(
    messages: list[ChatMessage],
    origin,
    start: float,
    end: float,
) -> list[ChatMessage]:
    window = filter_by_minutes(messages, start, end, origin)
    return [message for message in window if message.user.lower() not in DEFAULT_BOT_USERS]


def window_label(start: float, end: float, promo_end: float) -> str:
    if start < promo_end:
        return "during_promo"
    if end <= promo_end + 30:
        return "post_0_30min_after_banner"
    if end <= promo_end + 90:
        return "post_30_90min_after_banner"
    return "post_90min_plus_after_banner"


def build_post_promo_verdict(
    windows: list[dict[str, Any]],
    promo_signals: int,
    retention_ratio: float | None,
) -> str:
    if not windows:
        return "No post-promotion windows to compare."

    first = windows[0]
    post_rate = first.get("promo_signals_per_100_messages", 0)

    parts = [
        f"During the promo window, {promo_signals} chat lines mentioned Temu/code/banner.",
        f"In the first 30 minutes after the banner ended: {first['promo_signal_messages']} mentions "
        f"({post_rate} per 100 messages).",
    ]

    if retention_ratio is not None:
        if retention_ratio >= 0.25:
            parts.append(
                "Interest persists after the banner: a meaningful share of promo-era signal continues in early post-promo chat."
            )
        elif retention_ratio >= 0.1:
            parts.append(
                "Some post-promo mentions remain, but most Temu discussion happened while the banner/code was live."
            )
        else:
            parts.append(
                "After the banner ended, Temu/code chatter largely stopped; viewers moved on from the promotion."
            )

    if len(windows) > 1:
        late = windows[-1]
        lift = safe_lift(late["promo_signals_per_100_messages"], first["promo_signals_per_100_messages"])
        if lift < -0.5:
            parts.append("Long-tail post-promo mentions fade further later in the stream.")

    return " ".join(parts)
