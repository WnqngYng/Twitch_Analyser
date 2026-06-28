#!/usr/bin/env python3
"""Audit chat/transcript/product timing before trusting campaign reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twitch_promo_analyzer.influencer_transcript import load_influencer_transcript
from twitch_promo_analyzer.loaders import load_messages, save_messages_csv
from twitch_promo_analyzer.products import build_product_analysis
from twitch_promo_analyzer.timing import align_messages_to_window, offset_minutes, stream_origin


def load_campaigns(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item["vod_id"]): item
        for item in payload.get("livestreams", [])
        if item.get("vod_id")
    }


def known_vod_ids(data_dir: Path, campaigns: dict[str, dict[str, Any]], explicit: str | None) -> list[str]:
    if explicit:
        return [explicit]
    ids = {path.name for path in data_dir.iterdir() if path.is_dir()} if data_dir.exists() else set()
    ids.update(campaigns)
    return sorted(ids)


def resolve_window(
    vod_id: str,
    folder: Path,
    campaign: dict[str, Any] | None,
) -> tuple[float | None, float | None, str]:
    if campaign and campaign.get("promo_start_minute") is not None and campaign.get("promo_end_minute") is not None:
        return float(campaign["promo_start_minute"]), float(campaign["promo_end_minute"]), "campaign_config"

    transcript_path = folder / f"{vod_id}_influencer_transcript.json"
    if transcript_path.exists():
        document = load_influencer_transcript(transcript_path)
        window = document.get("promo_window_minutes") or []
        if len(window) >= 2:
            return float(window[0]), float(window[1]), "transcript_document"

    return None, None, "missing"


def audit_vod(
    vod_id: str,
    *,
    data_dir: Path,
    campaign: dict[str, Any] | None,
    repair_csv: bool,
) -> tuple[list[str], bool]:
    folder = data_dir / vod_id
    chat_json = folder / f"{vod_id}_chat.json"
    chat_csv = folder / f"{vod_id}_chat.csv"
    transcript_path = folder / f"{vod_id}_influencer_transcript.json"
    lines = [f"== {vod_id} =="]
    ok = True

    start, end, window_source = resolve_window(vod_id, folder, campaign)
    if start is None or end is None:
        if not folder.exists():
            lines.append("SKIP not downloaded locally and no promo window is configured.")
            return lines, True
        lines.append("WARN no promo window in campaign config or transcript; cannot validate timing.")
        return lines, False
    lines.append(f"window: {start}-{end} min ({window_source})")

    if chat_json.exists():
        json_messages = load_messages(chat_json)
        json_offsets = sum(message.stream_offset_seconds is not None for message in json_messages)
        lines.append(f"chat JSON: {len(json_messages)} messages, offsets {json_offsets}/{len(json_messages)}")
        if repair_csv:
            save_messages_csv(json_messages, chat_csv)
            lines.append(f"repaired CSV from JSON: {chat_csv}")
    else:
        lines.append("WARN missing TwitchDownloader chat JSON.")
        ok = False

    chat_path = chat_json if chat_json.exists() else chat_csv
    if not chat_path.exists():
        lines.append("FAIL no chat export found.")
        return lines, False

    messages = load_messages(chat_path)
    aligned, diagnostics = align_messages_to_window(messages, start, end)
    origin = stream_origin(aligned)
    minute_range = [
        round(min(offset_minutes(message, origin) for message in aligned), 3),
        round(max(offset_minutes(message, origin) for message in aligned), 3),
    ]
    lines.append(
        f"chat used: {chat_path.name}, alignment {diagnostics['alignment']}, minutes {minute_range}"
    )
    for warning in diagnostics.get("warnings", []):
        lines.append(f"WARN {warning}")
        ok = False

    if chat_csv.exists():
        csv_messages = load_messages(chat_csv)
        csv_offsets = sum(message.stream_offset_seconds is not None for message in csv_messages)
        if csv_messages and csv_offsets == 0 and chat_json.exists():
            lines.append("WARN CSV has no stream_offset_seconds but JSON does. Run with --repair-csv.")
            ok = False

    if transcript_path.exists():
        document = load_influencer_transcript(transcript_path)
        transcript = document.get("transcript", [])
        transcript_minutes = [
            float(line["stream_minute"])
            for line in transcript
            if line.get("stream_minute") is not None
        ]
        if transcript_minutes:
            lines.append(
                "transcript: "
                f"{len(transcript)} lines, minutes {round(min(transcript_minutes), 3)}-"
                f"{round(max(transcript_minutes), 3)}"
            )
        annotated = sum(1 for line in transcript if line.get("product_id"))
        lines.append(f"product annotations: {annotated}/{len(transcript)} transcript lines")
        product = build_product_analysis(document, aligned, start, end)
        if not product.get("product_segments"):
            lines.append("WARN no product segments detected.")
            ok = False
        else:
            best = product["product_segments"][0]
            lines.append(
                "best product: "
                f"{best['product_name']} score {best['response_score']} "
                f"({best['headcount']['unique_chatters_first_3min']} chatters first 3 min)"
            )
        for warning in product.get("data_quality", {}).get("warnings", []):
            lines.append(f"WARN {warning}")
            ok = False
    else:
        lines.append("WARN no influencer transcript; product analysis cannot be validated.")
        ok = False

    return lines, ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Twitch promo data alignment.")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--campaigns", default="examples/livestreams.json")
    parser.add_argument("--vod-id", default=None)
    parser.add_argument("--repair-csv", action="store_true")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    campaigns = load_campaigns(Path(args.campaigns))
    overall_ok = True
    for vod_id in known_vod_ids(data_dir, campaigns, args.vod_id):
        lines, ok = audit_vod(
            vod_id,
            data_dir=data_dir,
            campaign=campaigns.get(vod_id),
            repair_csv=args.repair_csv,
        )
        print("\n".join(lines))
        print()
        overall_ok = overall_ok and ok
    return 0 if overall_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
