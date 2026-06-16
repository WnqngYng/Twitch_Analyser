from __future__ import annotations

import re
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .loaders import load_messages, save_messages_csv


VOD_ID_RE = re.compile(r"(?:videos/|^)(\d{6,})")


def extract_vod_id(value: str) -> str:
    raw = value.strip()
    if raw.isdigit():
        return raw

    parsed = urlparse(raw)
    match = VOD_ID_RE.search(parsed.path.strip("/"))
    if match:
        return match.group(1)

    query = parse_qs(parsed.query)
    for key in ("v", "video", "id"):
        if key in query and query[key] and query[key][0].isdigit():
            return query[key][0]

    match = VOD_ID_RE.search(raw)
    if match:
        return match.group(1)

    raise ValueError(f"could not find a Twitch VOD id in: {value}")


def download_vod_data(
    vod: str,
    output_dir: str | Path = "data",
    twitch_downloader: str | Path | None = None,
    ffmpeg_path: str | Path | None = None,
    quality: str | None = None,
    beginning: str | None = None,
    ending: str | None = None,
    threads: int | None = None,
    oauth: str | None = None,
    temp_path: str | Path | None = None,
    download_chat: bool = True,
    download_video: bool = True,
    convert_chat_csv: bool = True,
) -> dict[str, Path | str | None]:
    vod_id = extract_vod_id(vod)
    destination = Path(output_dir) / vod_id
    destination.mkdir(parents=True, exist_ok=True)

    executable = resolve_twitch_downloader(twitch_downloader)
    chat_json = destination / f"{vod_id}_chat.json"
    chat_csv = destination / f"{vod_id}_chat.csv"
    video_mp4 = destination / f"{vod_id}_video.mp4"

    if download_chat:
        command = [
            executable,
            "chatdownload",
            "--id",
            vod_id,
            "-o",
            str(chat_json),
            "--collision",
            "Overwrite",
        ]
        append_common_options(command, beginning, ending, threads, oauth, temp_path)
        run_command(command)
        if convert_chat_csv:
            messages = load_messages(chat_json)
            save_messages_csv(messages, chat_csv)

    if download_video:
        command = [
            executable,
            "videodownload",
            "--id",
            vod_id,
            "-o",
            str(video_mp4),
            "--collision",
            "Overwrite",
        ]
        append_common_options(command, beginning, ending, threads, oauth, temp_path)
        if quality:
            command.extend(["--quality", quality])
        if ffmpeg_path:
            command.extend(["--ffmpeg-path", str(ffmpeg_path)])
        run_command(command)

    return {
        "vod_id": vod_id,
        "directory": destination,
        "chat_json": chat_json if download_chat else None,
        "chat_csv": chat_csv if download_chat and convert_chat_csv else None,
        "video_mp4": video_mp4 if download_video else None,
    }


def resolve_twitch_downloader(path: str | Path | None = None) -> str:
    candidates = []
    if path:
        candidates.append(str(path))
    candidates.extend(
        [
            "tools/twitchdownloader/TwitchDownloaderCLI",
            "TwitchDownloaderCLI",
            "TwitchDownloaderCLI.exe",
        ]
    )

    for candidate in candidates:
        candidate_path = Path(candidate)
        if candidate_path.exists():
            return str(candidate_path.resolve())
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    raise FileNotFoundError(
        "TwitchDownloaderCLI was not found. Run scripts/setup_twitch_downloader_macos.sh "
        "or pass --twitch-downloader /path/to/TwitchDownloaderCLI."
    )


def run_command(command: list[str]) -> None:
    env = os.environ.copy()
    if "DOTNET_BUNDLE_EXTRACT_BASE_DIR" not in env:
        cache_dir = Path(command[0]).resolve().parent / ".dotnet_bundle"
        cache_dir.mkdir(parents=True, exist_ok=True)
        env["DOTNET_BUNDLE_EXTRACT_BASE_DIR"] = str(cache_dir)
    subprocess.run(command, check=True, env=env)


def append_common_options(
    command: list[str],
    beginning: str | None = None,
    ending: str | None = None,
    threads: int | None = None,
    oauth: str | None = None,
    temp_path: str | Path | None = None,
) -> None:
    if beginning:
        command.extend(["--beginning", beginning])
    if ending:
        command.extend(["--ending", ending])
    if threads:
        command.extend(["--threads", str(threads)])
    if oauth:
        command.extend(["--oauth", oauth])
    if temp_path:
        command.extend(["--temp-path", str(temp_path)])
