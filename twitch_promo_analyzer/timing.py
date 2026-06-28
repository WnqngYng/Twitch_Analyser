from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from .models import ChatMessage


def stream_origin(messages: list[ChatMessage]) -> datetime:
    if not messages:
        raise ValueError("cannot determine stream origin from empty message list")
    offset_messages = [message for message in messages if message.stream_offset_seconds is not None]
    if offset_messages:
        return min(
            message.timestamp - timedelta(seconds=message.stream_offset_seconds or 0)
            for message in offset_messages
        )
    return min(message.timestamp for message in messages)


def offset_seconds(message: ChatMessage, origin: datetime) -> float:
    if message.stream_offset_seconds is not None:
        return message.stream_offset_seconds
    return (message.timestamp - origin).total_seconds()


def offset_minutes(message: ChatMessage, origin: datetime) -> float:
    return offset_seconds(message, origin) / 60.0


def filter_by_minutes(
    messages: list[ChatMessage],
    start_minute: float,
    end_minute: float,
    origin: datetime | None = None,
) -> list[ChatMessage]:
    if start_minute >= end_minute:
        raise ValueError("start_minute must be less than end_minute")

    origin_time = origin or stream_origin(messages)
    return [
        message
        for message in messages
        if start_minute <= offset_minutes(message, origin_time) < end_minute
    ]


def minute_bucket_counts(
    messages: list[ChatMessage],
    origin: datetime | None = None,
    exclude_users: set[str] | None = None,
) -> dict[int, int]:
    origin_time = origin or stream_origin(messages)
    excluded = {user.lower() for user in exclude_users or set()}
    buckets: dict[int, int] = {}
    for message in messages:
        if message.user.lower() in excluded:
            continue
        minute = int(offset_minutes(message, origin_time))
        buckets[minute] = buckets.get(minute, 0) + 1
    return buckets


def align_messages_to_window(
    messages: list[ChatMessage],
    expected_start_minute: float,
    expected_end_minute: float,
    *,
    tolerance_minutes: float = 10.0,
) -> tuple[list[ChatMessage], dict[str, Any]]:
    """Return messages with usable stream offsets plus transparent timing diagnostics.

    TwitchDownloader JSON exports include ``content_offset_seconds``. Some older CSV
    exports in this project lost that field, so a trimmed promo chat can look as if it
    starts at stream minute 0. When the observed CSV duration closely matches the
    requested analysis window, infer a stream offset from the expected window start.
    """
    if not messages:
        return [], {
            "message_count": 0,
            "alignment": "empty",
            "warnings": ["No chat messages were provided."],
        }

    sorted_messages = sorted(messages, key=lambda item: item.timestamp)
    offset_count = sum(message.stream_offset_seconds is not None for message in sorted_messages)
    origin = stream_origin(sorted_messages)
    observed_minutes = [offset_minutes(message, origin) for message in sorted_messages]
    observed_start = min(observed_minutes)
    observed_end = max(observed_minutes)
    observed_duration = max(observed_end - observed_start, 0.0)
    expected_duration = max(expected_end_minute - expected_start_minute, 0.0)

    diagnostics: dict[str, Any] = {
        "message_count": len(sorted_messages),
        "stream_offset_messages": offset_count,
        "stream_offset_coverage": round(offset_count / len(sorted_messages), 3),
        "observed_minute_range": [round(observed_start, 3), round(observed_end, 3)],
        "expected_window_minutes": [expected_start_minute, expected_end_minute],
        "alignment": "native_offsets" if offset_count else "timestamp_origin",
        "warnings": [],
    }

    if offset_count:
        return sorted_messages, diagnostics

    duration_tolerance = max(2.0, min(tolerance_minutes, expected_duration * 0.2))
    duration_matches_window = (
        expected_duration > 0
        and observed_duration <= expected_duration + duration_tolerance
        and abs(observed_duration - expected_duration) <= duration_tolerance
    )
    starts_like_trimmed_export = observed_start <= 1.0 and expected_start_minute > 1.0

    if starts_like_trimmed_export and duration_matches_window:
        first_timestamp = min(message.timestamp for message in sorted_messages)
        inferred_messages = [
            replace(
                message,
                stream_offset_seconds=(
                    (message.timestamp - first_timestamp).total_seconds()
                    + expected_start_minute * 60
                ),
            )
            for message in sorted_messages
        ]
        inferred_origin = stream_origin(inferred_messages)
        inferred_minutes = [offset_minutes(message, inferred_origin) for message in inferred_messages]
        diagnostics.update(
            {
                "alignment": "inferred_trimmed_csv_offset",
                "inferred_minute_range": [
                    round(min(inferred_minutes), 3),
                    round(max(inferred_minutes), 3),
                ],
                "inferred_offset_seconds": round(expected_start_minute * 60, 3),
            }
        )
        diagnostics["warnings"].append(
            "Chat messages had no stream offsets and looked like a trimmed export; "
            "stream offsets were inferred from the requested analysis window."
        )
        return inferred_messages, diagnostics

    if expected_start_minute > observed_end or expected_end_minute < observed_start:
        diagnostics["warnings"].append(
            "Chat minute range does not overlap the requested analysis window. "
            "Use TwitchDownloader JSON or regenerate CSV with stream_offset_seconds."
        )
    elif offset_count == 0 and expected_start_minute > 1.0:
        diagnostics["warnings"].append(
            "Chat messages have no stream offsets. If this is a trimmed export, "
            "absolute stream-minute alignment may be unreliable."
        )

    return sorted_messages, diagnostics
