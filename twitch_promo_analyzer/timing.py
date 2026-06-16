from __future__ import annotations

from datetime import datetime, timedelta

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
    start = origin_time + timedelta(minutes=start_minute)
    end = origin_time + timedelta(minutes=end_minute)
    return [message for message in messages if start <= message.timestamp < end]


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
