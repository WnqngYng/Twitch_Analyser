from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .transcript import extract_audio_for_transcription
from .influencer_transcript import (
    build_from_srt,
    build_from_whisper,
    influencer_transcript_path,
    write_influencer_transcript,
)
from .utterances import (
    influencer_utterances_from_whisper,
    merge_response_corpus,
    write_responses_csv,
    write_responses_json,
)
from .vod import download_vod_data


def resolve_ffmpeg() -> str | None:
    candidates = [
        "tools/twitchdownloader/ffmpeg",
        "ffmpeg",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return str(path.resolve())
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def resolve_whisper_command() -> list[str] | None:
    for candidate in (
        ["whisper"],
        ["whisper-cli"],
        ["python3", "-m", "whisper"],
    ):
        executable = candidate[0]
        if shutil.which(executable):
            return candidate
    return None


def run_whisper_transcription(
    audio_path: str | Path,
    output_dir: str | Path,
    language: str = "Italian",
    model: str = "base",
) -> dict[str, Any]:
    whisper = resolve_whisper_command()
    if not whisper:
        return {
            "status": "whisper_unavailable",
            "note": "Install whisper: pip install openai-whisper, or brew install whisper",
        }

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    command = [
        *whisper,
        str(audio_path),
        "--language",
        language,
        "--model",
        model,
        "--output_dir",
        str(destination),
        "--output_format",
        "json",
    ]
    env = os.environ.copy()
    ffmpeg = resolve_ffmpeg()
    if ffmpeg:
        ffmpeg_dir = str(Path(ffmpeg).parent)
        env["PATH"] = ffmpeg_dir + os.pathsep + env.get("PATH", "")
    subprocess.run(command, check=True, env=env)
    stem = Path(audio_path).stem
    json_path = destination / f"{stem}.json"
    return {
        "status": "ok",
        "whisper_json": str(json_path.resolve()) if json_path.exists() else None,
        "output_dir": str(destination.resolve()),
    }


def transcribe_promotion_segment(
    *,
    vod_id: str,
    vod_url: str,
    data_dir: str | Path = "data",
    promo_start_minute: float = 9.0,
    promo_end_minute: float = 48.0,
    stream_start_iso: str | None = None,
    influencer_name: str = "therealmarzaa",
    video_path: str | Path | None = None,
    download_if_missing: bool = True,
    quality: str = "160p30",
    language: str = "Italian",
    whisper_model: str = "base",
) -> dict[str, Any]:
    folder = Path(data_dir) / vod_id
    folder.mkdir(parents=True, exist_ok=True)

    mp4 = Path(video_path) if video_path else folder / f"{vod_id}_video.mp4"
    promo_tag = f"{int(promo_start_minute)}_{int(promo_end_minute)}"
    m4a = folder / f"{vod_id}_promo_{promo_tag}.m4a"
    wav = folder / f"{vod_id}_promo_{promo_tag}.wav"
    promo_mp4 = folder / f"{vod_id}_promo_{promo_tag}.mp4"
    promo_mp4_alt = folder / f"{vod_id}_promo_{int(promo_start_minute):02d}_{int(promo_end_minute):02d}.mp4"
    whisper_json = folder / f"{vod_id}_promo_{int(promo_start_minute)}_{int(promo_end_minute)}.json"
    ffmpeg_path = resolve_ffmpeg()

    result: dict[str, Any] = {"vod_id": vod_id, "folder": str(folder.resolve())}

    audio_source = m4a if m4a.exists() else promo_mp4 if promo_mp4.exists() else promo_mp4_alt if promo_mp4_alt.exists() else mp4
    if not audio_source.exists() and download_if_missing:
        beginning = format_hms(promo_start_minute * 60)
        ending = format_hms(promo_end_minute * 60)
        m4a.parent.mkdir(parents=True, exist_ok=True)
        command = [
            str(Path("tools/twitchdownloader/TwitchDownloaderCLI").resolve()),
            "videodownload",
            "--id",
            vod_id,
            "-o",
            str(m4a),
            "--collision",
            "Overwrite",
            "--beginning",
            beginning,
            "--ending",
            ending,
            "--quality",
            "Audio",
        ]
        if ffmpeg_path:
            command.extend(["--ffmpeg-path", ffmpeg_path])
        subprocess.run(command, check=True)
        audio_source = m4a

    if not audio_source.exists():
        result["status"] = "audio_missing"
        result["note"] = f"Place audio at {m4a} or enable download_if_missing."
        return result

    if not wav.exists() and audio_source.exists() and ffmpeg_path:
        extract_audio_for_transcription(
            audio_source,
            wav,
            start_minute=0,
            end_minute=promo_end_minute - promo_start_minute,
            ffmpeg_path=ffmpeg_path,
        )

    if wav.exists():
        audio_input = wav
    elif audio_source.suffix.lower() in {".m4a", ".wav"}:
        audio_input = audio_source
    else:
        audio_result = extract_audio_for_transcription(
            audio_source,
            wav,
            start_minute=0,
            end_minute=promo_end_minute - promo_start_minute,
            ffmpeg_path=ffmpeg_path,
        )
        result["audio"] = audio_result
        if audio_result.get("status") != "ok":
            return result
        audio_input = wav

    audio_result = {"status": "ok", "audio_path": str(audio_source.resolve())}
    result["audio"] = audio_result

    if whisper_json.exists():
        result["whisper"] = {"status": "cached", "whisper_json": str(whisper_json.resolve())}
    else:
        result["whisper"] = run_whisper_transcription(
            audio_input, folder, language=language, model=whisper_model
        )
        cached = folder / f"{audio_input.stem}.json"
        if cached.exists():
            whisper_json = cached

    if not whisper_json.exists():
        result["status"] = "transcript_missing"
        return result

    trimmed_sources = {m4a, promo_mp4, promo_mp4_alt, wav}
    time_offset = promo_start_minute if audio_source in trimmed_sources or wav.exists() else 0.0
    document = build_from_whisper(
        whisper_json,
        vod_id=vod_id,
        influencer=influencer_name,
        promo_start_minute=promo_start_minute,
        promo_end_minute=promo_end_minute,
        stream_start_iso=stream_start_iso,
        time_offset_minutes=time_offset,
    )
    influencer_json = influencer_transcript_path(data_dir, vod_id)
    write_influencer_transcript(document, influencer_json)

    result["status"] = "ok"
    result["influencer_transcript_json"] = str(influencer_json.resolve())
    result["line_count"] = document["line_count"]
    return result


def build_merged_corpus_from_files(
    *,
    vod_id: str,
    data_dir: str | Path,
    promo_start_minute: float,
    promo_end_minute: float,
    viewer_utterances: list[dict[str, Any]],
    stream_start_iso: str | None = None,
) -> dict[str, Any]:
    folder = Path(data_dir) / vod_id
    influencer_rows: list[dict[str, Any]] = []

    whisper_path = folder / f"{vod_id}_promo_{int(promo_start_minute)}_{int(promo_end_minute)}.json"
    influencer_path = influencer_transcript_path(data_dir, vod_id)
    srt_path = folder / f"{vod_id}_promo_{int(promo_start_minute)}_{int(promo_end_minute)}.srt"

    influencer_rows: list[dict[str, Any]] = []
    if influencer_path.exists():
        payload = json.loads(influencer_path.read_text(encoding="utf-8"))
        if "transcript" in payload:
            for line in payload["transcript"]:
                influencer_rows.append(
                    {
                        "speaker_role": "influencer",
                        "source": "video_transcript",
                        "stream_minute": line.get("stream_minute"),
                        "promo_minute": line.get("promo_minute"),
                        "timestamp": line.get("timestamp"),
                        "user": payload.get("influencer", "therealmarzaa"),
                        "original": line.get("text", ""),
                        "english": None,
                        "translate_to": "en",
                        "language": payload.get("language", "it"),
                        "segment_start_seconds": line.get("start_seconds"),
                        "segment_end_seconds": line.get("end_seconds"),
                    }
                )
        else:
            influencer_rows = payload.get("utterances", [])
    elif whisper_path.exists():
        influencer_rows = influencer_utterances_from_whisper(
            whisper_path,
            promo_start_minute,
            promo_end_minute,
            stream_start_iso=stream_start_iso,
        )
    elif srt_path.exists():
        from .utterances import influencer_utterances_from_srt

        influencer_rows = influencer_utterances_from_srt(
            srt_path,
            promo_start_minute,
            promo_end_minute,
            stream_start_iso=stream_start_iso,
        )

    corpus = merge_response_corpus(
        viewer_utterances,
        influencer_rows,
        vod_id=vod_id,
        promo_start_minute=promo_start_minute,
        promo_end_minute=promo_end_minute,
    )
    merged_json = folder / f"{vod_id}_responses.json"
    merged_csv = folder / f"{vod_id}_responses.csv"
    write_responses_json(corpus, merged_json)
    write_responses_csv(corpus["utterances"], merged_csv)
    return {
        "corpus": corpus,
        "merged_json": str(merged_json.resolve()),
        "merged_csv": str(merged_csv.resolve()),
    }


def format_hms(total_seconds: float) -> str:
    seconds = int(total_seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
