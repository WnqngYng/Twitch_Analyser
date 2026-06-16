from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


def analyze_video_segment(
    video_path: str | Path,
    start_minute: float,
    end_minute: float,
    ffmpeg_path: str | None = None,
    ffprobe_path: str | None = None,
) -> dict[str, Any]:
    source = Path(video_path)
    result: dict[str, Any] = {
        "video_path": str(source),
        "start_minute": start_minute,
        "end_minute": end_minute,
        "available": source.exists(),
    }
    if not source.exists():
        result["status"] = "missing"
        result["note"] = (
            "Video file not found. Download with: "
            "python -m twitch_promo_analyzer download-vod <url> --quality 360p30 "
            f"--beginning {format_hms(start_minute * 60)} --ending {format_hms(end_minute * 60)}"
        )
        return result

    ffprobe = resolve_binary(ffprobe_path, "ffprobe")
    ffmpeg = resolve_binary(ffmpeg_path, "ffmpeg")
    if not ffprobe or not ffmpeg:
        result["status"] = "ffmpeg_unavailable"
        result["note"] = "Install ffmpeg/ffprobe to enable scene-change and segment metadata analysis."
        result["file_size_mb"] = round(source.stat().st_size / (1024 * 1024), 2)
        return result

    start_seconds = start_minute * 60
    duration_seconds = max((end_minute - start_minute) * 60, 1)

    probe = run_json(
        [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(source),
        ]
    )
    video_stream = next(
        (stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"),
        {},
    )
    format_info = probe.get("format", {})

    scene_changes = count_scene_changes(ffmpeg, source, start_seconds, duration_seconds)

    result.update(
        {
            "status": "ok",
            "duration_seconds": round(float(format_info.get("duration", 0) or 0), 2),
            "file_size_mb": round(source.stat().st_size / (1024 * 1024), 2),
            "resolution": f"{video_stream.get('width')}x{video_stream.get('height')}",
            "codec": video_stream.get("codec_name"),
            "avg_fps": parse_fps(video_stream.get("avg_frame_rate")),
            "segment": {
                "start_seconds": round(start_seconds, 2),
                "duration_seconds": round(duration_seconds, 2),
                "scene_changes": scene_changes,
                "scene_changes_per_minute": round(scene_changes / max(duration_seconds / 60, 1), 3),
            },
            "interpretation": interpret_scene_density(scene_changes, duration_seconds / 60),
        }
    )
    return result


def resolve_binary(explicit: str | None, name: str) -> str | None:
    if explicit and Path(explicit).exists():
        return explicit
    return shutil.which(name)


def run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def count_scene_changes(
    ffmpeg: str,
    source: Path,
    start_seconds: float,
    duration_seconds: float,
) -> int:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "info",
        "-ss",
        str(start_seconds),
        "-t",
        str(duration_seconds),
        "-i",
        str(source),
        "-filter:v",
        "select='gt(scene,0.35)',showinfo",
        "-f",
        "null",
        "-",
    ]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError:
        return 0

    return len(re.findall(r"Parsed_showinfo", completed.stderr))


def parse_fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        numerator, denominator = value.split("/", 1)
        try:
            return round(float(numerator) / float(denominator), 3)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    try:
        return round(float(value), 3)
    except ValueError:
        return None


def format_hms(total_seconds: float) -> str:
    seconds = int(total_seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def interpret_scene_density(scene_changes: int, duration_minutes: float) -> str:
    per_minute = scene_changes / max(duration_minutes, 1)
    if per_minute >= 8:
        return "high_cut_density"
    if per_minute >= 3:
        return "moderate_visual_pacing"
    return "low_cut_density"
