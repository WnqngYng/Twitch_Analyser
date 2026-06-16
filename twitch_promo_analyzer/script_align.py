from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_influencer_script(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"influencer script not found: {source}")

    payload = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        segments = payload.get("segments", payload.get("script", []))
    else:
        segments = payload

    if not isinstance(segments, list):
        raise ValueError("script file must contain a segments list")

    normalized: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue
        start = float(segment["start_minute"])
        end = float(segment.get("end_minute", start + 1))
        normalized.append(
            {
                "segment_id": segment.get("id", f"seg-{index}"),
                "start_minute": start,
                "end_minute": end,
                "topic": segment.get("topic", ""),
                "text": segment.get("text", ""),
                "notes": segment.get("notes", ""),
            }
        )
    normalized.sort(key=lambda item: item["start_minute"])
    return normalized


def align_peaks_to_script(
    peaks: list[dict[str, Any]],
    script_segments: list[dict[str, Any]],
    rolling_windows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    peak_alignments = []
    for peak in peaks:
        stream_minute = peak.get("stream_minute")
        if stream_minute is None:
            continue
        segment = find_segment_for_minute(stream_minute, script_segments)
        peak_alignments.append(
            {
                **peak,
                "aligned_script": segment,
                "alignment_note": describe_alignment(peak, segment),
            }
        )

    rolling_alignments = []
    for window in rolling_windows or []:
        midpoint = window["stream_minute_start"] + window["window_minutes"] / 2
        segment = find_segment_for_minute(midpoint, script_segments)
        rolling_alignments.append({**window, "aligned_script": segment})

    coverage = script_coverage(script_segments, peaks)

    return {
        "segments": script_segments,
        "peak_alignments": peak_alignments,
        "rolling_alignments": rolling_alignments[:5],
        "coverage": coverage,
        "summary": build_alignment_summary(peak_alignments, coverage),
    }


def find_segment_for_minute(minute: float, segments: list[dict[str, Any]]) -> dict[str, Any] | None:
    for segment in segments:
        if segment["start_minute"] <= minute < segment["end_minute"]:
            return segment
    nearest = min(
        segments,
        key=lambda item: min(abs(minute - item["start_minute"]), abs(minute - item["end_minute"])),
        default=None,
    )
    if nearest is None:
        return None
    distance = min(abs(minute - nearest["start_minute"]), abs(minute - nearest["end_minute"]))
    return {**nearest, "match": "nearest", "distance_minutes": round(distance, 2)}


def describe_alignment(peak: dict[str, Any], segment: dict[str, Any] | None) -> str:
    if not segment:
        return "No script segment covers this peak; add transcript segments for this timestamp."
    topic = segment.get("topic") or "untitled segment"
    if segment.get("match") == "nearest":
        return (
            f"Nearest script segment ({topic}) is ~{segment['distance_minutes']} min away. "
            "Refine script timestamps or check if the peak matches unscripted banter."
        )
    return f"Peak aligns with script segment: {topic}."


def script_coverage(script_segments: list[dict[str, Any]], peaks: list[dict[str, Any]]) -> dict[str, Any]:
    from collections import Counter

    hit_segments: Counter[str] = Counter()
    for peak in peaks:
        segment = find_segment_for_minute(peak.get("stream_minute", 0), script_segments)
        if segment and segment.get("match") != "nearest":
            hit_segments[segment["segment_id"]] += 1

    return {
        "segments_with_chat_peaks": dict(hit_segments),
        "segments_without_peaks": [
            segment["segment_id"]
            for segment in script_segments
            if segment["segment_id"] not in hit_segments
        ],
    }


def build_alignment_summary(peak_alignments: list[dict[str, Any]], coverage: dict[str, Any]) -> str:
    if not peak_alignments:
        return "Add an influencer script JSON to correlate chat peaks with on-stream talking points."
    aligned = [
        item for item in peak_alignments if item.get("aligned_script") and item["aligned_script"].get("match") != "nearest"
    ]
    if not aligned:
        return (
            "Chat peaks exist but do not line up with current script timestamps. "
            "Re-time script segments after reviewing the VOD."
        )
    top = aligned[0]
    topic = top["aligned_script"].get("topic", "segment")
    return (
        f"Highest chat peak (promo minute {top['promo_minute']}) maps to script topic '{topic}'. "
        f"Segments without strong peaks: {', '.join(coverage.get('segments_without_peaks', [])[:5]) or 'none'}."
    )


def script_template(vod_id: str, promo_start: float, promo_end: float) -> dict[str, Any]:
    """Starter structure for manual or Whisper-filled influencer script."""
    return {
        "vod_id": vod_id,
        "language": "it",
        "promo_code": "KAV3769",
        "notes": "Fill segments from VOD review or transcript. Minutes are stream-relative from VOD start.",
        "segments": [
            {
                "id": "intro-temu",
                "start_minute": promo_start,
                "end_minute": promo_start + 5,
                "topic": "Temu sponsorship intro / #AD disclosure",
                "text": "",
            },
            {
                "id": "pack-opening",
                "start_minute": promo_start + 5,
                "end_minute": promo_start + 20,
                "topic": "Pack opening / surprise boxes",
                "text": "",
            },
            {
                "id": "code-cta",
                "start_minute": promo_start + 20,
                "end_minute": promo_end,
                "topic": "Code KAV3769 + app link CTA",
                "text": "",
            },
        ],
    }
