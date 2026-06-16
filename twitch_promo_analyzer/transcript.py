from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def build_script_from_transcript(
    transcript_path: str | Path,
    influencer: str | None = None,
    min_segment_seconds: int = 45,
) -> list[dict[str, Any]]:
    """
    Convert Whisper JSON or SRT transcript into influencer script segments.
    Minutes are stream-relative from transcript timestamps.
    """
    source = Path(transcript_path)
    suffix = source.suffix.lower()
    if suffix == ".json":
        return segments_from_whisper_json(source, influencer, min_segment_seconds)
    if suffix == ".srt":
        return segments_from_srt(source, min_segment_seconds)
    raise ValueError(f"unsupported transcript format: {suffix}")


def segments_from_whisper_json(
    path: Path,
    influencer: str | None,
    min_segment_seconds: int,
) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    segments = payload.get("segments", [])
    if not segments:
        raise ValueError("Whisper JSON has no segments")

    grouped: list[dict[str, Any]] = []
    buffer_text: list[str] = []
    start_seconds = float(segments[0].get("start", 0))
    last_end = start_seconds

    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start = float(segment.get("start", last_end))
        end = float(segment.get("end", start))
        if influencer and not speaker_matches(segment, influencer):
            continue

        if buffer_text and (end - start_seconds) >= min_segment_seconds:
            grouped.append(make_script_segment(start_seconds, last_end, buffer_text))
            buffer_text = []
            start_seconds = start

        buffer_text.append(text)
        last_end = end

    if buffer_text:
        grouped.append(make_script_segment(start_seconds, last_end, buffer_text))
    return grouped


def segments_from_srt(path: Path, min_segment_seconds: int) -> list[dict[str, Any]]:
    blocks = parse_srt(path.read_text(encoding="utf-8", errors="replace"))
    grouped: list[dict[str, Any]] = []
    buffer_text: list[str] = []
    start_seconds = blocks[0]["start"] if blocks else 0.0
    last_end = start_seconds

    for block in blocks:
        if buffer_text and (block["end"] - start_seconds) >= min_segment_seconds:
            grouped.append(make_script_segment(start_seconds, last_end, buffer_text))
            buffer_text = []
            start_seconds = block["start"]
        buffer_text.append(block["text"])
        last_end = block["end"]

    if buffer_text:
        grouped.append(make_script_segment(start_seconds, last_end, buffer_text))
    return grouped


def make_script_segment(start_seconds: float, end_seconds: float, lines: list[str]) -> dict[str, Any]:
    text = " ".join(lines).strip()
    topic = infer_topic(text)
    return {
        "id": f"transcript-{int(start_seconds)}",
        "start_minute": round(start_seconds / 60, 2),
        "end_minute": round(end_seconds / 60, 2),
        "topic": topic,
        "text": text,
        "source": "transcript",
    }


def infer_topic(text: str) -> str:
    lowered = text.lower()
    if "kav3769" in lowered or "codice" in lowered or "temu" in lowered:
        return "Temu CTA / code KAV3769"
    if "#ad" in lowered or "sponsor" in lowered:
        return "Sponsorship disclosure"
    if "pack" in lowered or "sorpresa" in lowered:
        return "Pack opening"
    return "General stream talk"


def speaker_matches(segment: dict[str, Any], influencer: str) -> bool:
    speaker = str(segment.get("speaker", "")).lower()
    return influencer.lower() in speaker if speaker else True


def parse_srt(content: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\n\s*\n", content.strip())
    parsed: list[dict[str, Any]] = []
    time_re = re.compile(
        r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
    )
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        match = time_re.search(block)
        if not match:
            continue
        start = srt_timestamp_to_seconds(match.groups()[0:4])
        end = srt_timestamp_to_seconds(match.groups()[4:8])
        text_lines = [line for line in lines if "-->" not in line and not line.isdigit()]
        parsed.append({"start": start, "end": end, "text": " ".join(text_lines).strip()})
    return parsed


def srt_timestamp_to_seconds(parts: tuple[str, str, str, str]) -> float:
    hours, minutes, seconds, millis = parts
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(millis) / 1000


def extract_audio_for_transcription(
    video_path: str | Path,
    output_wav: str | Path,
    start_minute: float,
    end_minute: float,
    ffmpeg_path: str | None = None,
) -> dict[str, Any]:
    ffmpeg = ffmpeg_path or shutil.which("ffmpeg")
    if not ffmpeg:
        return {
            "status": "ffmpeg_unavailable",
            "note": "Install ffmpeg, then run Whisper on the exported WAV.",
        }

    source = Path(video_path)
    destination = Path(output_wav)
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(start_minute * 60),
        "-to",
        str(end_minute * 60),
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        str(destination),
    ]
    subprocess.run(command, check=True)
    return {
        "status": "ok",
        "wav_path": str(destination.resolve()),
        "whisper_hint": f"whisper {destination} --language Italian --output_format json",
    }
