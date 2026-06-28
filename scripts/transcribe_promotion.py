#!/usr/bin/env python3
"""
Transcribe the promotion video segment and export in the same format as viewer chat responses.

Outputs (under data/<vod_id>/):
  <vod>_influencer_transcript.json   — influencer lines only
  <vod>_influencer_transcript.csv
  <vod>_viewer_responses.json        — chat lines in promo window
  <vod>_viewer_responses.csv
  <vod>_responses.json               — merged timeline (influencer + viewers)
  <vod>_responses.csv

Requires: ffmpeg + whisper (pip install openai-whisper) for transcription.
Viewer exports work from chat alone without video.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twitch_promo_analyzer.loaders import load_messages, preferred_chat_export
from twitch_promo_analyzer.transcribe import (
    build_merged_corpus_from_files,
    transcribe_promotion_segment,
)
from twitch_promo_analyzer.timing import align_messages_to_window, stream_origin
from twitch_promo_analyzer.utterances import (
    merge_response_corpus,
    viewer_utterances_from_chat,
    write_responses_csv,
    write_responses_json,
)


DEFAULTS = {
    "vod_id": "2776778244",
    "vod_url": "https://www.twitch.tv/videos/2776778244",
    "promo_start": 9.0,
    "promo_end": 48.0,
    "influencer": "therealmarzaa",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export viewer + influencer responses in one format.")
    parser.add_argument("--vod-id", default=DEFAULTS["vod_id"])
    parser.add_argument("--vod-url", default=DEFAULTS["vod_url"])
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--promo-start", type=float, default=DEFAULTS["promo_start"])
    parser.add_argument("--promo-end", type=float, default=DEFAULTS["promo_end"])
    parser.add_argument("--influencer", default=DEFAULTS["influencer"])
    parser.add_argument("--chat", default=None)
    parser.add_argument("--video", default=None)
    parser.add_argument("--skip-transcribe", action="store_true", help="Only export chat; do not run Whisper.")
    parser.add_argument("--import-whisper", default=None, help="Use existing Whisper JSON path.")
    parser.add_argument("--import-srt", default=None, help="Use existing SRT transcript path.")
    args = parser.parse_args(argv)

    folder = Path(args.data_dir) / args.vod_id
    chat_path = preferred_chat_export(folder, args.vod_id, args.chat)
    if not chat_path.exists():
        print(f"Chat not found in {folder}", file=sys.stderr)
        return 1

    messages, timing_diagnostics = align_messages_to_window(
        load_messages(chat_path),
        args.promo_start,
        args.promo_end,
    )
    for warning in timing_diagnostics.get("warnings", []):
        print(f"Timing warning: {warning}", file=sys.stderr)
    stream_start = stream_origin(messages).isoformat()
    viewer_rows = viewer_utterances_from_chat(
        messages,
        args.promo_start,
        args.promo_end,
        influencer_name=args.influencer,
    )

    viewer_json = folder / f"{args.vod_id}_viewer_responses.json"
    viewer_csv = folder / f"{args.vod_id}_viewer_responses.csv"
    write_responses_json(
        {
            "schema_version": "1",
            "vod_id": args.vod_id,
            "speaker_role": "viewer",
            "promo_window_minutes": [args.promo_start, args.promo_end],
            "utterances": viewer_rows,
        },
        viewer_json,
    )
    write_responses_csv(viewer_rows, viewer_csv)
    print(f"Viewer responses: {len(viewer_rows)} rows")
    print(f"  JSON: {viewer_json.resolve()}")
    print(f"  CSV:  {viewer_csv.resolve()}")

    if args.import_whisper:
        from twitch_promo_analyzer.influencer_transcript import (
            build_from_whisper,
            influencer_transcript_path,
            write_influencer_transcript,
        )

        document = build_from_whisper(
            args.import_whisper,
            vod_id=args.vod_id,
            influencer=args.influencer,
            promo_start_minute=args.promo_start,
            promo_end_minute=args.promo_end,
            stream_start_iso=stream_start,
        )
        inf_json = influencer_transcript_path(args.data_dir, args.vod_id)
        write_influencer_transcript(document, inf_json)
        print(f"Influencer transcript: {document['line_count']} lines -> {inf_json.resolve()}")
    elif args.import_srt:
        from twitch_promo_analyzer.influencer_transcript import (
            build_from_srt,
            influencer_transcript_path,
            write_influencer_transcript,
        )

        document = build_from_srt(
            args.import_srt,
            vod_id=args.vod_id,
            influencer=args.influencer,
            promo_start_minute=args.promo_start,
            promo_end_minute=args.promo_end,
            stream_start_iso=stream_start,
        )
        inf_json = influencer_transcript_path(args.data_dir, args.vod_id)
        write_influencer_transcript(document, inf_json)
        print(f"Influencer transcript: {document['line_count']} lines -> {inf_json.resolve()}")
    elif not args.skip_transcribe:
        tx = transcribe_promotion_segment(
            vod_id=args.vod_id,
            vod_url=args.vod_url,
            data_dir=args.data_dir,
            promo_start_minute=args.promo_start,
            promo_end_minute=args.promo_end,
            stream_start_iso=stream_start,
            influencer_name=args.influencer,
            video_path=args.video,
        )
        print(json.dumps(tx, indent=2))
        if tx.get("status") not in {"ok", "cached"}:
            print("Transcription skipped or failed; merged export will be viewer-only.", file=sys.stderr)

    merged = build_merged_corpus_from_files(
        vod_id=args.vod_id,
        data_dir=args.data_dir,
        promo_start_minute=args.promo_start,
        promo_end_minute=args.promo_end,
        viewer_utterances=viewer_rows,
        stream_start_iso=stream_start,
    )
    print(f"Merged corpus: {merged['corpus']['counts']}")
    print(f"  JSON: {merged['merged_json']}")
    print(f"  CSV:  {merged['merged_csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
