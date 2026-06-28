from __future__ import annotations

import csv
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from .models import parse_timestamp
from .utterances import (
    influencer_utterances_from_srt,
    influencer_utterances_from_whisper,
)


def build_influencer_transcript_document(
    lines: list[dict[str, Any]],
    *,
    vod_id: str,
    influencer: str,
    promo_start_minute: float,
    promo_end_minute: float,
    stream_start_iso: str | None = None,
    language: str = "it",
    source: str = "video_transcript",
) -> dict[str, Any]:
    transcript: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        transcript.append(
            {
                "index": index,
                "text": line.get("original", ""),
                "stream_minute": line.get("stream_minute"),
                "promo_minute": line.get("promo_minute"),
                "timestamp": line.get("timestamp"),
                "start_seconds": line.get("segment_start_seconds"),
                "end_seconds": line.get("segment_end_seconds"),
            }
        )

    return {
        "schema_version": "1",
        "vod_id": vod_id,
        "influencer": influencer,
        "language": language,
        "promo_window_minutes": [promo_start_minute, promo_end_minute],
        "stream_start": stream_start_iso,
        "source": source,
        "line_count": len(transcript),
        "transcript": transcript,
    }


def load_influencer_transcript(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "transcript" not in payload and "utterances" in payload:
        payload = build_influencer_transcript_document(
            payload["utterances"],
            vod_id=payload.get("vod_id", ""),
            influencer=payload.get("influencer", "therealmarzaa"),
            promo_start_minute=payload.get("promo_window_minutes", [0, 0])[0],
            promo_end_minute=payload.get("promo_window_minutes", [0, 0])[1],
            stream_start_iso=payload.get("stream_start"),
            language=payload.get("language", "it"),
            source=payload.get("source", "import"),
        )
    return payload


TRANSCRIPT_CSV_FIELDS = [
    "index",
    "text",
    "english",
    "product_id",
    "product_name",
    "stream_minute",
    "promo_minute",
    "timestamp",
    "start_seconds",
    "end_seconds",
    "influencer",
    "language",
]


def write_influencer_transcript(
    document: dict[str, Any],
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(document, indent=2, ensure_ascii=False), encoding="utf-8")
    write_influencer_transcript_csv(document, csv_path_for_json(destination))
    return destination


def csv_path_for_json(json_path: str | Path) -> Path:
    path = Path(json_path)
    return path.with_suffix(".csv")


def write_influencer_transcript_csv(
    document: dict[str, Any],
    path: str | Path,
) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    influencer = document.get("influencer", "")
    language = document.get("language", "")

    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRANSCRIPT_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for line in document.get("transcript", []):
            writer.writerow(
                {
                    "index": line.get("index", ""),
                    "text": line.get("text", ""),
                    "english": line.get("english", ""),
                    "product_id": line.get("product_id", ""),
                    "product_name": line.get("product_name", ""),
                    "stream_minute": line.get("stream_minute", ""),
                    "promo_minute": line.get("promo_minute", ""),
                    "timestamp": line.get("timestamp", ""),
                    "start_seconds": line.get("start_seconds", ""),
                    "end_seconds": line.get("end_seconds", ""),
                    "influencer": influencer,
                    "language": language,
                }
            )
    return destination


def export_transcript_json_to_csv(json_path: str | Path, csv_path: str | Path | None = None) -> Path:
    document = load_influencer_transcript(json_path)
    destination = Path(csv_path) if csv_path else csv_path_for_json(json_path)
    return write_influencer_transcript_csv(document, destination)


def influencer_transcript_path(data_dir: str | Path, vod_id: str) -> Path:
    return Path(data_dir) / vod_id / f"{vod_id}_influencer_transcript.json"


def influencer_transcript_csv_path(data_dir: str | Path, vod_id: str) -> Path:
    return csv_path_for_json(influencer_transcript_path(data_dir, vod_id))


def build_from_whisper(
    whisper_path: str | Path,
    *,
    vod_id: str,
    influencer: str,
    promo_start_minute: float,
    promo_end_minute: float,
    stream_start_iso: str | None,
    time_offset_minutes: float | None = None,
) -> dict[str, Any]:
    lines = influencer_utterances_from_whisper(
        whisper_path,
        promo_start_minute,
        promo_end_minute,
        stream_start_iso=stream_start_iso,
        influencer_name=influencer,
        time_offset_minutes=time_offset_minutes,
    )
    return build_influencer_transcript_document(
        lines,
        vod_id=vod_id,
        influencer=influencer,
        promo_start_minute=promo_start_minute,
        promo_end_minute=promo_end_minute,
        stream_start_iso=stream_start_iso,
        language=lines[0].get("language", "it") if lines else "it",
        source="whisper",
    )


def build_from_srt(
    srt_path: str | Path,
    *,
    vod_id: str,
    influencer: str,
    promo_start_minute: float,
    promo_end_minute: float,
    stream_start_iso: str | None,
) -> dict[str, Any]:
    lines = influencer_utterances_from_srt(
        srt_path,
        promo_start_minute,
        promo_end_minute,
        stream_start_iso=stream_start_iso,
        influencer_name=influencer,
    )
    return build_influencer_transcript_document(
        lines,
        vod_id=vod_id,
        influencer=influencer,
        promo_start_minute=promo_start_minute,
        promo_end_minute=promo_end_minute,
        stream_start_iso=stream_start_iso,
        source="srt",
    )


def segments_from_script(
    script_path: str | Path,
    stream_start_iso: str | None,
) -> list[dict[str, Any]]:
    payload = json.loads(Path(script_path).read_text(encoding="utf-8"))
    segments = payload.get("segments", [])
    origin = parse_timestamp(stream_start_iso) if stream_start_iso else None
    lines: list[dict[str, Any]] = []

    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start_minute = float(segment["start_minute"])
        end_minute = float(segment.get("end_minute", start_minute + 1))
        timestamp = None
        if origin is not None:
            timestamp = (origin + timedelta(minutes=start_minute)).isoformat()
        lines.append(
            {
                "original": text,
                "stream_minute": start_minute,
                "promo_minute": None,
                "timestamp": timestamp,
                "segment_start_seconds": round(start_minute * 60, 3),
                "segment_end_seconds": round(end_minute * 60, 3),
            }
        )
    return lines
