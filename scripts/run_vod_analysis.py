#!/usr/bin/env python3
"""
End-to-end Twitch promotion analysis for any VOD.

Example (reference VOD):
  python scripts/run_vod_analysis.py \\
    --vod-url "https://www.twitch.tv/videos/2776778244" \\
    --promo-start 9 --promo-end 48 \\
    --promo-code KAV3769 \\
    --brand temu --cta '!temu'

Example (another VOD, chat only — skip video/transcription):
  python scripts/run_vod_analysis.py \\
    --vod-id 1234567890 \\
    --promo-start 10 --promo-end 55 \\
    --skip-video --skip-transcribe
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twitch_promo_analyzer.influencer_transcript import (
    influencer_transcript_csv_path,
    influencer_transcript_path,
    load_influencer_transcript,
    write_influencer_transcript,
)
from twitch_promo_analyzer.line_translate import translate_italian_lines
from twitch_promo_analyzer.loaders import load_messages, preferred_chat_export
from twitch_promo_analyzer.post_promo import analyze_post_promotion_interest
from twitch_promo_analyzer.products import (
    annotate_transcript_products,
    build_product_analysis,
    load_product_catalog,
)
from twitch_promo_analyzer.report_export import write_product_reports
from twitch_promo_analyzer.timing import align_messages_to_window, stream_origin
from twitch_promo_analyzer.transcribe import transcribe_promotion_segment
from twitch_promo_analyzer.utterances import viewer_utterances_from_chat, write_responses_csv, write_responses_json
from twitch_promo_analyzer.vod import extract_vod_id


def run_step(label: str, command: list[str]) -> None:
    print(f"\n=== {label} ===")
    print(" ".join(command))
    subprocess.run(command, check=True, cwd=ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run full VOD promotion analysis pipeline.")
    parser.add_argument("--vod-url", default=None, help="Twitch VOD URL")
    parser.add_argument("--vod-id", default=None, help="Numeric VOD id (alternative to URL)")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--promo-start", type=float, required=True)
    parser.add_argument("--promo-end", type=float, required=True)
    parser.add_argument("--promo-code", default="KAV3769")
    parser.add_argument("--influencer", default="therealmarzaa")
    parser.add_argument("--brand", action="append", default=[])
    parser.add_argument("--cta", action="append", default=[])
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-video", action="store_true", help="Download chat only.")
    parser.add_argument("--skip-transcribe", action="store_true")
    parser.add_argument("--skip-translate", action="store_true")
    parser.add_argument("--skip-promotion-report", action="store_true")
    parser.add_argument(
        "--extract-products",
        action="store_true",
        help="Call Gemini extractor and write data/<vod>/<vod>_product_catalog.json.",
    )
    parser.add_argument(
        "--force-product-extract",
        action="store_true",
        help="Regenerate the product catalog even when it already exists.",
    )
    parser.add_argument(
        "--product-catalog",
        default=None,
        help="Optional product catalog JSON. Defaults to data/<vod>/<vod>_product_catalog.json when present.",
    )
    args = parser.parse_args(argv)

    vod_id = args.vod_id or extract_vod_id(args.vod_url or "")
    vod_url = args.vod_url or f"https://www.twitch.tv/videos/{vod_id}"
    folder = Path(args.data_dir) / vod_id
    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)

    brands = set(args.brand) or {"temu", args.promo_code.lower()}
    ctas = set(args.cta) or {"!temu", args.promo_code.lower()}

    print(f"VOD {vod_id} | promo {args.promo_start}-{args.promo_end} min | code {args.promo_code}")

    # Step 1 — Download chat (+ optional audio segment)
    if not args.skip_download:
        download_cmd = [
            sys.executable,
            "-m",
            "twitch_promo_analyzer",
            "download-vod",
            vod_url,
            "--output-dir",
            args.data_dir,
        ]
        if args.skip_video:
            download_cmd.append("--skip-video")
        else:
            download_cmd.extend(
                [
                    "--quality",
                    "Audio",
                    "--beginning",
                    format_hms(args.promo_start),
                    "--ending",
                    format_hms(args.promo_end),
                ]
            )
        run_step("1/6 Download VOD data", download_cmd)

    chat_path = preferred_chat_export(folder, vod_id)
    if not chat_path.exists():
        print(f"Missing chat export: {chat_path}", file=sys.stderr)
        return 1

    # Step 2 — Promotion window report (chat peaks, lifts, grade)
    if not args.skip_promotion_report:
        promo_cmd = [
            sys.executable,
            "scripts/analyze_promotion.py",
            "--vod-id",
            vod_id,
            "--data-dir",
            args.data_dir,
            "--promo-start",
            str(args.promo_start),
            "--promo-end",
            str(args.promo_end),
            "--promo-code",
            args.promo_code,
            "--influencer",
            args.influencer,
        ]
        for brand in brands:
            promo_cmd.extend(["--brand", brand])
        for cta in ctas:
            promo_cmd.extend(["--cta", cta])
        run_step("2/6 Promotion window analysis", promo_cmd)

    # Step 3 — Transcribe influencer audio (Whisper)
    messages, timing_diagnostics = align_messages_to_window(
        load_messages(chat_path),
        args.promo_start,
        args.promo_end,
    )
    for warning in timing_diagnostics.get("warnings", []):
        print(f"Timing warning: {warning}", file=sys.stderr)
    stream_start = stream_origin(messages).isoformat()
    transcript_path = influencer_transcript_path(args.data_dir, vod_id)

    if not args.skip_transcribe:
        result = transcribe_promotion_segment(
            vod_id=vod_id,
            vod_url=vod_url,
            data_dir=args.data_dir,
            promo_start_minute=args.promo_start,
            promo_end_minute=args.promo_end,
            stream_start_iso=stream_start,
            influencer_name=args.influencer,
            download_if_missing=not args.skip_download,
        )
        print(json.dumps(result, indent=2))
        if result.get("status") not in {"ok"} and not transcript_path.exists():
            print("Warning: transcription failed; product analysis needs a transcript.", file=sys.stderr)

    if not transcript_path.exists():
        print(f"Missing transcript: {transcript_path}", file=sys.stderr)
        print("Run without --skip-transcribe after installing whisper + ffmpeg.", file=sys.stderr)
        return 1

    # Step 4 — Translate transcript + tag products
    document = load_influencer_transcript(transcript_path)
    transcript = document.get("transcript", [])
    if not args.skip_translate:
        print(f"Translating {len(transcript)} transcript lines...")
        english = translate_italian_lines(line["text"] for line in transcript)
        for line, text_en in zip(transcript, english):
            line["english"] = text_en
    document["transcript"] = transcript
    write_influencer_transcript(document, transcript_path)

    catalog_path = Path(args.product_catalog) if args.product_catalog else folder / f"{vod_id}_product_catalog.json"
    if args.extract_products and (args.force_product_extract or not catalog_path.exists()):
        run_step(
            "4a/6 Extract product catalog",
            [
                sys.executable,
                "products_name/extract_catalog.py",
                str(influencer_transcript_csv_path(args.data_dir, vod_id)),
                "--out",
                str(catalog_path),
            ],
        )

    product_catalog = None
    if catalog_path.exists():
        product_catalog = load_product_catalog(catalog_path)
        document["product_catalog_path"] = str(catalog_path)
        print(f"Using product catalog: {catalog_path.resolve()}")
    else:
        print(
            "No VOD-specific product catalog JSON found. "
            "Using transcript product_id annotations when present, with the built-in catalog as fallback."
        )

    transcript = annotate_transcript_products(transcript, product_catalog)
    document["transcript"] = transcript
    write_influencer_transcript(document, transcript_path)

    # Step 5 — Export viewer responses (unified format)
    viewer_rows = viewer_utterances_from_chat(
        messages,
        args.promo_start,
        args.promo_end,
        influencer_name=args.influencer,
    )
    write_responses_json(
        {
            "schema_version": "1",
            "vod_id": vod_id,
            "speaker_role": "viewer",
            "promo_window_minutes": [args.promo_start, args.promo_end],
            "utterances": viewer_rows,
        },
        folder / f"{vod_id}_viewer_responses.json",
    )
    write_responses_csv(viewer_rows, folder / f"{vod_id}_viewer_responses.csv")

    # Step 6 — Product headcount, sentiment, participation issues
    product_analysis = build_product_analysis(
        document,
        messages,
        args.promo_start,
        args.promo_end,
        product_catalog=product_catalog,
    )
    paths = write_product_reports(product_analysis, reports, vod_id)

    post_promo = analyze_post_promotion_interest(messages, args.promo_start, args.promo_end)
    post_path = reports / f"{vod_id}_post_promo_analysis.json"
    post_path.write_text(json.dumps(post_promo, indent=2, ensure_ascii=False), encoding="utf-8")

    from twitch_promo_analyzer.text_report import write_findings_report

    findings_path = write_findings_report(vod_id, reports_dir=reports, data_dir=args.data_dir)

    print("\n=== RESULTS ===")
    print(product_analysis["headcount_summary"])
    print(product_analysis["sentiment_summary"])
    print(product_analysis["participation_summary"])
    print(post_promo["verdict"])
    print("\nOutputs:")
    for key, path in paths.items():
        print(f"  {key}: {path}")
    print(f"  post_promo: {post_path.resolve()}")
    print(f"  findings_txt: {findings_path.resolve()}")
    print(f"  transcript: {transcript_path.resolve()}")
    print(f"  promotion: {reports / f'{vod_id}_promotion_report.html'}")
    return 0


def format_hms(minutes: float) -> str:
    total = int(minutes * 60)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


if __name__ == "__main__":
    raise SystemExit(main())
