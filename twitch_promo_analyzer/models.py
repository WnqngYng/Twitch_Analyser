from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def parse_timestamp(value: Any) -> datetime:
    """Parse common chat export timestamps into timezone-aware datetimes."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if value is None:
        raise ValueError("timestamp is required")

    raw = str(value).strip()
    if not raw:
        raise ValueError("timestamp is empty")

    if raw.replace(".", "", 1).isdigit():
        number = float(raw)
        if number > 10_000_000_000:
            number = number / 1000
        return datetime.fromtimestamp(number, tz=timezone.utc)

    parts = raw.split(":")
    if len(parts) == 3 and all(part.replace(".", "", 1).isdigit() for part in parts):
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return datetime.fromtimestamp(hours * 3600 + minutes * 60 + seconds, tz=timezone.utc)

    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"unsupported timestamp format: {raw}") from exc

    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class ChatMessage:
    timestamp: datetime
    user: str
    message: str
    viewer_count: int | None = None
    stream_offset_seconds: float | None = None
    channel: str | None = None
    badges: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_fields(
        cls,
        timestamp: Any,
        user: Any,
        message: Any,
        viewer_count: Any = None,
        stream_offset_seconds: Any = None,
        channel: Any = None,
        badges: Any = None,
        raw: dict[str, Any] | None = None,
    ) -> "ChatMessage":
        clean_user = str(user or "").strip()
        clean_message = str(message or "").strip()
        if not clean_user:
            clean_user = "unknown"
        if viewer_count in ("", None):
            viewers = None
        else:
            try:
                viewers = int(float(str(viewer_count).strip()))
            except ValueError:
                viewers = None

        if stream_offset_seconds in ("", None):
            offset = None
        else:
            try:
                offset = float(str(stream_offset_seconds).strip())
            except ValueError:
                offset = None

        if isinstance(badges, str):
            badge_tuple = tuple(item for item in badges.split(",") if item)
        elif badges:
            badge_tuple = tuple(str(item) for item in badges)
        else:
            badge_tuple = ()

        return cls(
            timestamp=parse_timestamp(timestamp),
            user=clean_user,
            message=clean_message,
            viewer_count=viewers,
            stream_offset_seconds=offset,
            channel=str(channel).strip() if channel else None,
            badges=badge_tuple,
            raw=raw or {},
        )


@dataclass(frozen=True)
class PromotionEvent:
    event_id: str
    timestamp: datetime
    influencer: str
    message: str
    brand: str | None
    cta_type: str
    offer: str | None
    keyword_score: int
    source_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "influencer": self.influencer,
            "message": self.message,
            "brand": self.brand,
            "cta_type": self.cta_type,
            "offer": self.offer,
            "keyword_score": self.keyword_score,
            "source_index": self.source_index,
        }
