from __future__ import annotations

import csv
import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterable

from .models import ChatMessage
from .timing import align_messages_to_window, offset_minutes, stream_origin


SCHEMA_VERSION = "1"
UTTERANCE_CSV_FIELDS = [
    "id",
    "speaker_role",
    "source",
    "stream_minute",
    "promo_minute",
    "timestamp",
    "user",
    "original",
    "english",
    "translate_to",
    "language",
]


def make_utterance(
    *,
    utterance_id: str,
    speaker_role: str,
    source: str,
    user: str,
    original: str,
    stream_minute: float | None = None,
    promo_minute: float | None = None,
    timestamp: str | None = None,
    translate_to: str = "en",
    english: str | None = None,
    language: str = "it",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": utterance_id,
        "speaker_role": speaker_role,
        "source": source,
        "stream_minute": round(stream_minute, 3) if stream_minute is not None else None,
        "promo_minute": round(promo_minute, 3) if promo_minute is not None else None,
        "timestamp": timestamp,
        "user": user,
        "original": original.strip(),
        "english": english,
        "translate_to": translate_to,
        "language": language,
    }
    if extra:
        row.update(extra)
    return row


def viewer_utterances_from_chat(
    messages: list[ChatMessage],
    promo_start_minute: float,
    promo_end_minute: float,
    influencer_name: str = "therealmarzaa",
    exclude_bots: bool = True,
    translate_to: str = "en",
) -> list[dict[str, Any]]:
    """All viewer chat lines in the promo window, same shape as translation export."""
    aligned_messages, _diagnostics = align_messages_to_window(
        messages,
        promo_start_minute,
        promo_end_minute,
    )
    origin = stream_origin(aligned_messages)
    bots = {"streamelements", "nightbot", "moobot", "fossabot"}
    utterances: list[dict[str, Any]] = []
    index = 0

    for message in aligned_messages:
        minute = offset_minutes(message, origin)
        if minute < promo_start_minute or minute >= promo_end_minute:
            continue
        if exclude_bots and message.user.lower() in bots:
            continue

        index += 1
        utterances.append(
            make_utterance(
                utterance_id=f"viewer-{index:05d}",
                speaker_role="viewer",
                source="chat",
                user=message.user,
                original=message.message,
                stream_minute=minute,
                promo_minute=minute - promo_start_minute,
                timestamp=message.timestamp.isoformat(),
                translate_to=translate_to,
                language="it",
            )
        )
    return utterances


def influencer_utterances_from_whisper(
    whisper_path: str | Path,
    promo_start_minute: float,
    promo_end_minute: float,
    stream_start_iso: str | None = None,
    influencer_name: str = "therealmarzaa",
    translate_to: str = "en",
    time_offset_minutes: float | None = None,
) -> list[dict[str, Any]]:
    """Convert Whisper JSON segments to the same utterance rows as viewer chat."""
    payload = json.loads(Path(whisper_path).read_text(encoding="utf-8"))
    segments = payload.get("segments", [])
    if not segments:
        raise ValueError(f"no segments in whisper file: {whisper_path}")
    if time_offset_minutes is None:
        time_offset_minutes = infer_whisper_time_offset(
            segments,
            promo_start_minute,
            promo_end_minute,
        )

    origin = None
    if stream_start_iso:
        from .models import parse_timestamp

        origin = parse_timestamp(stream_start_iso)

    utterances: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start_seconds = float(segment.get("start", 0))
        end_seconds = float(segment.get("end", start_seconds))
        stream_minute = time_offset_minutes + start_seconds / 60
        if stream_minute < promo_start_minute or stream_minute >= promo_end_minute:
            continue

        timestamp = None
        if origin is not None:
            timestamp = (origin + timedelta(seconds=start_seconds + time_offset_minutes * 60)).isoformat()

        utterances.append(
            make_utterance(
                utterance_id=f"influencer-{index:05d}",
                speaker_role="influencer",
                source="video_transcript",
                user=influencer_name,
                original=text,
                stream_minute=stream_minute,
                promo_minute=stream_minute - promo_start_minute,
                timestamp=timestamp,
                translate_to=translate_to,
                language=str(payload.get("language", "it")),
                extra={
                    "segment_start_seconds": round(time_offset_minutes * 60 + start_seconds, 3),
                    "segment_end_seconds": round(time_offset_minutes * 60 + end_seconds, 3),
                },
            )
        )
    return utterances


def infer_whisper_time_offset(
    segments: list[dict[str, Any]],
    promo_start_minute: float,
    promo_end_minute: float,
    tolerance_minutes: float = 5.0,
) -> float:
    """Infer whether Whisper timestamps are full-stream or trimmed-audio relative."""
    starts = [float(segment.get("start", 0)) / 60 for segment in segments]
    ends = [float(segment.get("end", segment.get("start", 0))) / 60 for segment in segments]
    raw_start = min(starts)
    raw_end = max(ends)
    promo_duration = max(promo_end_minute - promo_start_minute, 0)

    if promo_start_minute <= raw_start <= promo_end_minute:
        return 0.0
    if raw_start <= 1.0 and raw_end <= promo_duration + tolerance_minutes:
        return promo_start_minute
    return 0.0


def influencer_utterances_from_srt(
    srt_path: str | Path,
    promo_start_minute: float,
    promo_end_minute: float,
    stream_start_iso: str | None = None,
    influencer_name: str = "therealmarzaa",
    translate_to: str = "en",
) -> list[dict[str, Any]]:
    from .transcript import parse_srt, srt_timestamp_to_seconds

    blocks = parse_srt(Path(srt_path).read_text(encoding="utf-8", errors="replace"))
    origin = None
    if stream_start_iso:
        from .models import parse_timestamp

        origin = parse_timestamp(stream_start_iso)

    utterances: list[dict[str, Any]] = []
    for index, block in enumerate(blocks, start=1):
        stream_minute = block["start"] / 60
        if stream_minute < promo_start_minute or stream_minute >= promo_end_minute:
            continue
        timestamp = None
        if origin is not None:
            timestamp = (origin + timedelta(seconds=block["start"])).isoformat()
        utterances.append(
            make_utterance(
                utterance_id=f"influencer-{index:05d}",
                speaker_role="influencer",
                source="video_transcript",
                user=influencer_name,
                original=block["text"],
                stream_minute=stream_minute,
                promo_minute=stream_minute - promo_start_minute,
                timestamp=timestamp,
                translate_to=translate_to,
                language="it",
                extra={
                    "segment_start_seconds": round(block["start"], 3),
                    "segment_end_seconds": round(block["end"], 3),
                },
            )
        )
    return utterances


def merge_response_corpus(
    viewer_utterances: list[dict[str, Any]],
    influencer_utterances: list[dict[str, Any]],
    *,
    vod_id: str,
    promo_start_minute: float,
    promo_end_minute: float,
) -> dict[str, Any]:
    combined = viewer_utterances + influencer_utterances
    combined.sort(
        key=lambda row: (
            row.get("stream_minute") if row.get("stream_minute") is not None else 0,
            0 if row.get("speaker_role") == "influencer" else 1,
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "vod_id": vod_id,
        "promo_window_minutes": [promo_start_minute, promo_end_minute],
        "utterance_format": {
            "description": "Shared row shape for viewer chat and influencer video transcript.",
            "fields": UTTERANCE_CSV_FIELDS,
        },
        "counts": {
            "viewer": len(viewer_utterances),
            "influencer": len(influencer_utterances),
            "total": len(combined),
        },
        "utterances": combined,
    }


def write_responses_json(corpus: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(corpus, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination


def write_responses_csv(utterances: Iterable[dict[str, Any]], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    rows = list(utterances)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=UTTERANCE_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in UTTERANCE_CSV_FIELDS})
    return destination


def translation_items_from_utterances(utterances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Subset compatible with legacy messages_to_translate in reports."""
    return [
        {
            "source": item["source"],
            "promo_minute": item.get("promo_minute"),
            "stream_minute": item.get("stream_minute"),
            "user": item.get("user"),
            "speaker_role": item.get("speaker_role"),
            "original": item.get("original"),
            "translate_to": item.get("translate_to"),
            "english": item.get("english"),
        }
        for item in utterances
        if item.get("english") is None and item.get("original")
    ]
