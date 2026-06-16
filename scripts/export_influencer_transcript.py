#!/usr/bin/env python3
"""
Write a single influencer transcript file with timestamps.

Output: data/<vod_id>/<vod_id>_influencer_transcript.json and .csv

Usage:
  python scripts/export_influencer_transcript.py
  python scripts/export_influencer_transcript.py --import-whisper path/to.json
  python scripts/export_influencer_transcript.py --run-whisper
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twitch_promo_analyzer.influencer_transcript import (
    build_from_srt,
    build_from_whisper,
    export_transcript_json_to_csv,
    influencer_transcript_csv_path,
    influencer_transcript_path,
    write_influencer_transcript,
)
from twitch_promo_analyzer.loaders import load_messages, preferred_chat_export
from twitch_promo_analyzer.timing import stream_origin
from twitch_promo_analyzer.transcribe import transcribe_promotion_segment


DEFAULTS = {
    "vod_id": "2776778244",
    "vod_url": "https://www.twitch.tv/videos/2776778244",
    "promo_start": 9.0,
    "promo_end": 48.0,
    "influencer": "therealmarzaa",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export one influencer transcript JSON file.")
    parser.add_argument("--vod-id", default=DEFAULTS["vod_id"])
    parser.add_argument("--vod-url", default=DEFAULTS["vod_url"])
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--promo-start", type=float, default=DEFAULTS["promo_start"])
    parser.add_argument("--promo-end", type=float, default=DEFAULTS["promo_end"])
    parser.add_argument("--influencer", default=DEFAULTS["influencer"])
    parser.add_argument("--chat", default=None)
    parser.add_argument("--import-whisper", default=None)
    parser.add_argument("--import-srt", default=None)
    parser.add_argument("--run-whisper", action="store_true")
    parser.add_argument(
        "--json-to-csv",
        action="store_true",
        help="Convert existing influencer_transcript.json to CSV only.",
    )
    args = parser.parse_args(argv)

    folder = Path(args.data_dir) / args.vod_id

    if args.json_to_csv:
        json_path = influencer_transcript_path(args.data_dir, args.vod_id)
        if not json_path.exists():
            print(f"Not found: {json_path}", file=sys.stderr)
            return 1
        csv_path = export_transcript_json_to_csv(json_path)
        print(f"Wrote {csv_path.resolve()}")
        return 0
    chat_path = preferred_chat_export(folder, args.vod_id, args.chat)
    stream_start = None
    if chat_path.exists():
        stream_start = stream_origin(load_messages(chat_path)).isoformat()

    out_path = influencer_transcript_path(args.data_dir, args.vod_id)

    if args.run_whisper:
        result = transcribe_promotion_segment(
            vod_id=args.vod_id,
            vod_url=args.vod_url,
            data_dir=args.data_dir,
            promo_start_minute=args.promo_start,
            promo_end_minute=args.promo_end,
            stream_start_iso=stream_start,
            influencer_name=args.influencer,
        )
        print(result)
        if result.get("status") != "ok":
            return 1
        print(f"Wrote {out_path.resolve()} ({result.get('line_count', 0)} lines)")
        print(f"Wrote {influencer_transcript_csv_path(args.data_dir, args.vod_id).resolve()}")
        return 0

    if args.import_whisper:
        document = build_from_whisper(
            args.import_whisper,
            vod_id=args.vod_id,
            influencer=args.influencer,
            promo_start_minute=args.promo_start,
            promo_end_minute=args.promo_end,
            stream_start_iso=stream_start,
        )
    elif args.import_srt:
        document = build_from_srt(
            args.import_srt,
            vod_id=args.vod_id,
            influencer=args.influencer,
            promo_start_minute=args.promo_start,
            promo_end_minute=args.promo_end,
            stream_start_iso=stream_start,
        )
    else:
        print(
            "No transcript source. Use --run-whisper (needs ffmpeg + whisper) or --import-whisper/--import-srt.",
            file=sys.stderr,
        )
        return 1

    write_influencer_transcript(document, out_path)
    print(f"Wrote {out_path.resolve()} ({document['line_count']} lines)")
    print(f"Wrote {influencer_transcript_csv_path(args.data_dir, args.vod_id).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
