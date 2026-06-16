from __future__ import annotations

import csv
import socket
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import ChatMessage


IRC_HOST = "irc.chat.twitch.tv"
IRC_PORT = 6697


def capture_chat(
    channel: str,
    nickname: str,
    oauth_token: str,
    output_path: str | Path,
    duration_minutes: float | None = None,
    limit_messages: int | None = None,
) -> int:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    deadline = time.monotonic() + duration_minutes * 60 if duration_minutes else None
    count = 0

    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "user", "message", "viewer_count", "channel", "badges"],
        )
        writer.writeheader()

        for message in iter_twitch_chat(channel, nickname, oauth_token):
            writer.writerow(
                {
                    "timestamp": message.timestamp.isoformat(),
                    "user": message.user,
                    "message": message.message,
                    "viewer_count": message.viewer_count or "",
                    "channel": message.channel or channel,
                    "badges": ",".join(message.badges),
                }
            )
            handle.flush()
            count += 1
            if limit_messages and count >= limit_messages:
                break
            if deadline and time.monotonic() >= deadline:
                break

    return count


def iter_twitch_chat(channel: str, nickname: str, oauth_token: str) -> Iterator[ChatMessage]:
    clean_channel = channel.lstrip("#").lower()
    token = oauth_token if oauth_token.startswith("oauth:") else f"oauth:{oauth_token}"
    context = ssl.create_default_context()

    with socket.create_connection((IRC_HOST, IRC_PORT), timeout=30) as raw_socket:
        with context.wrap_socket(raw_socket, server_hostname=IRC_HOST) as sock:
            sock.sendall(f"PASS {token}\r\n".encode("utf-8"))
            sock.sendall(f"NICK {nickname}\r\n".encode("utf-8"))
            sock.sendall(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
            sock.sendall(f"JOIN #{clean_channel}\r\n".encode("utf-8"))

            buffer = ""
            while True:
                chunk = sock.recv(4096).decode("utf-8", errors="ignore")
                if not chunk:
                    return
                buffer += chunk
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    if line.startswith("PING"):
                        sock.sendall(b"PONG :tmi.twitch.tv\r\n")
                        continue
                    message = parse_irc_privmsg(line, clean_channel)
                    if message:
                        yield message


def parse_irc_privmsg(line: str, channel: str) -> ChatMessage | None:
    if " PRIVMSG " not in line:
        return None

    tags: dict[str, str] = {}
    rest = line
    if line.startswith("@"):
        tag_part, rest = line.split(" ", 1)
        tags = parse_tags(tag_part[1:])

    try:
        prefix, trailing = rest.split(" :", 1)
        user = prefix.split("!", 1)[0].lstrip(":")
    except ValueError:
        return None

    timestamp = datetime.now(timezone.utc)
    if "tmi-sent-ts" in tags:
        try:
            timestamp = datetime.fromtimestamp(int(tags["tmi-sent-ts"]) / 1000, tz=timezone.utc)
        except ValueError:
            pass

    badges = tuple(item.split("/", 1)[0] for item in tags.get("badges", "").split(",") if item)

    return ChatMessage.from_fields(
        timestamp=timestamp,
        user=tags.get("display-name") or user,
        message=trailing,
        channel=channel,
        badges=badges,
        raw={"irc": line, "tags": tags},
    )


def parse_tags(raw_tags: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for item in raw_tags.split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            tags[key] = value
    return tags
