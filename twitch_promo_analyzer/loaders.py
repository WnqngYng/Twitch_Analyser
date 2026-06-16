from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .models import ChatMessage


TIMESTAMP_FIELDS = ("timestamp", "time", "created_at", "sent_at", "tmi-sent-ts", "offset")
USER_FIELDS = ("user", "username", "display_name", "author", "author_name", "login")
MESSAGE_FIELDS = ("message", "msg", "text", "body", "comment", "content")
VIEWER_FIELDS = ("viewer_count", "viewers", "viewerCount", "concurrent_viewers")
STREAM_OFFSET_FIELDS = ("stream_offset_seconds", "content_offset_seconds", "offset_seconds")
CHANNEL_FIELDS = ("channel", "room", "room_id")
BADGE_FIELDS = ("badges", "badge_info")


def load_messages(path: str | Path) -> list[ChatMessage]:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return load_csv_messages(source)
    if suffix in {".json", ".ndjson", ".jsonl"}:
        return load_json_messages(source)
    raise ValueError(f"unsupported input type: {source.suffix}")


def preferred_chat_export(
    folder: str | Path,
    vod_id: str,
    explicit: str | Path | None = None,
    prefer_json: bool = True,
) -> Path:
    if explicit:
        return Path(explicit)

    source_folder = Path(folder)
    json_path = source_folder / f"{vod_id}_chat.json"
    csv_path = source_folder / f"{vod_id}_chat.csv"
    candidates = (json_path, csv_path) if prefer_json else (csv_path, json_path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_csv_messages(path: Path) -> list[ChatMessage]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [_message_from_mapping(row) for row in reader if row]


def load_json_messages(path: Path) -> list[ChatMessage]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []

    if text[0] in "[{":
        payload = json.loads(text)
        if isinstance(payload, dict):
            records = payload.get("messages", payload.get("comments", []))
        else:
            records = payload
    else:
        records = [json.loads(line) for line in text.splitlines() if line.strip()]

    if not isinstance(records, list):
        raise ValueError("JSON input must be a list or contain a messages list")

    return [_message_from_mapping(record) for record in records if isinstance(record, dict)]


def save_messages_csv(messages: Iterable[ChatMessage], path: str | Path) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "stream_offset_seconds",
                "user",
                "message",
                "viewer_count",
                "channel",
                "badges",
            ],
        )
        writer.writeheader()
        for message in messages:
            writer.writerow(
                {
                    "timestamp": message.timestamp.isoformat(),
                    "stream_offset_seconds": message.stream_offset_seconds
                    if message.stream_offset_seconds is not None
                    else "",
                    "user": message.user,
                    "message": message.message,
                    "viewer_count": message.viewer_count or "",
                    "channel": message.channel or "",
                    "badges": ",".join(message.badges),
                }
            )


def _message_from_mapping(row: dict) -> ChatMessage:
    if "commenter" in row and "message" in row:
        return _message_from_twitch_downloader(row)

    return ChatMessage.from_fields(
        timestamp=_first(row, TIMESTAMP_FIELDS),
        user=_first(row, USER_FIELDS),
        message=_first(row, MESSAGE_FIELDS),
        viewer_count=_first(row, VIEWER_FIELDS),
        stream_offset_seconds=_first(row, STREAM_OFFSET_FIELDS),
        channel=_first(row, CHANNEL_FIELDS),
        badges=_first(row, BADGE_FIELDS),
        raw=dict(row),
    )


def _first(row: dict, names: tuple[str, ...]) -> object:
    lower_map = {str(key).lower(): value for key, value in row.items()}
    for name in names:
        if name in row and row[name] not in ("", None):
            return row[name]
        lower_name = name.lower()
        if lower_name in lower_map and lower_map[lower_name] not in ("", None):
            return lower_map[lower_name]
    return None


def _message_from_twitch_downloader(row: dict) -> ChatMessage:
    commenter = row.get("commenter") or {}
    message = row.get("message") or {}
    badges = message.get("user_badges") or []
    badge_names = []
    for badge in badges:
        if isinstance(badge, dict):
            name = badge.get("_id") or badge.get("id") or badge.get("name")
            if name:
                badge_names.append(str(name))
        elif badge:
            badge_names.append(str(badge))

    timestamp = row.get("created_at")
    if not timestamp and row.get("content_offset_seconds") is not None:
        timestamp = str(row["content_offset_seconds"])

    return ChatMessage.from_fields(
        timestamp=timestamp,
        user=commenter.get("display_name") or commenter.get("name") or row.get("user"),
        message=message.get("body") or row.get("body") or row.get("message"),
        stream_offset_seconds=row.get("content_offset_seconds"),
        channel=row.get("channel_id"),
        badges=badge_names,
        raw=dict(row),
    )
