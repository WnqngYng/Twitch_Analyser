#!/usr/bin/env python3
"""
Add English translation + product tags to influencer transcript, then analyze
product chat response and post-promotion Temu interest.

Outputs:
  data/<vod_id>/<vod_id>_influencer_transcript.json
  data/<vod_id>/<vod_id>_influencer_transcript.csv
  reports/<vod_id>_product_analysis.json
  reports/<vod_id>_post_promo_analysis.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twitch_promo_analyzer.influencer_transcript import (
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


DEFAULTS = {
    "vod_id": "2776778244",
    "promo_start": 9.0,
    "promo_end": 48.0,
    "chat": None,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vod-id", default=DEFAULTS["vod_id"])
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--promo-start", type=float, default=DEFAULTS["promo_start"])
    parser.add_argument("--promo-end", type=float, default=DEFAULTS["promo_end"])
    parser.add_argument("--chat", default=DEFAULTS["chat"])
    parser.add_argument("--product-catalog", default=None)
    parser.add_argument("--skip-translate", action="store_true")
    args = parser.parse_args(argv)

    json_path = influencer_transcript_path(args.data_dir, args.vod_id)
    document = load_influencer_transcript(json_path)
    transcript = document.get("transcript", [])

    if not args.skip_translate:
        print(f"Translating {len(transcript)} lines to English...")
        english_lines = translate_italian_lines(line["text"] for line in transcript)
        for line, english in zip(transcript, english_lines):
            line["english"] = english

    folder = Path(args.data_dir) / args.vod_id
    catalog_path = Path(args.product_catalog) if args.product_catalog else folder / f"{args.vod_id}_product_catalog.json"
    product_catalog = load_product_catalog(catalog_path) if catalog_path.exists() else None

    transcript = annotate_transcript_products(transcript, product_catalog)
    document["transcript"] = transcript
    if catalog_path.exists():
        document["product_catalog_path"] = str(catalog_path)
    write_influencer_transcript(document, json_path)
    print(f"Updated transcript: {json_path.resolve()}")

    messages = load_messages(preferred_chat_export(folder, args.vod_id, args.chat))
    product_analysis = build_product_analysis(
        document,
        messages,
        args.promo_start,
        args.promo_end,
        product_catalog=product_catalog,
    )
    post_promo = analyze_post_promotion_interest(
        messages,
        args.promo_start,
        args.promo_end,
    )

    reports = Path("reports")
    reports.mkdir(parents=True, exist_ok=True)
    paths = write_product_reports(product_analysis, reports, args.vod_id)
    post_path = reports / f"{args.vod_id}_post_promo_analysis.json"
    post_path.write_text(json.dumps(post_promo, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== Headcount per product period ===")
    for item in product_analysis["product_segments"]:
        hc = item["headcount"]
        print(
            f"#{item['response_rank']} {item['product_name']} "
            f"(min {item['stream_minute_start']}-{item['stream_minute_end']}): "
            f"{hc['unique_chatters']} chatters, {hc['total_messages']} messages"
        )
    print(f"\n{product_analysis['headcount_summary']}")

    print("\n=== Product sentiment ===")
    for item in product_analysis["product_segments"]:
        sent = item["viewer_sentiment"]
        print(
            f"{item['product_name']}: avg {sent['avg_score']} | "
            f"+{sent['positive']} / ={sent['neutral']} / -{sent['negative']}"
        )
    print(f"\n{product_analysis['sentiment_summary']}")

    print("\n=== Participation issues ===")
    for item in product_analysis["product_segments"]:
        issues = item["participation_issues"]
        if issues.get("issue_message_count"):
            print(f"{item['product_name']}: {issues['issue_counts']}")
    print(f"\n{product_analysis['participation_summary']}")
    print(f"\n=== Post-promo ===\n{post_promo['verdict']}")
    for key, path in paths.items():
        print(f"{key}: {path}")
    print(f"post_promo: {post_path.resolve()}")

    from twitch_promo_analyzer.text_report import write_findings_report

    findings_path = write_findings_report(args.vod_id)
    print(f"findings_txt: {findings_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
