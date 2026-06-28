from __future__ import annotations

import argparse
from pathlib import Path

import json

from .analysis import analyze_campaign
from .live import capture_chat
from .loaders import load_messages, preferred_chat_export
from .recommendations import attach_recommendations
from .report import write_html_report, write_json_report
from .peaks import analyze_promotion_peaks
from .script_align import align_peaks_to_script, load_influencer_script
from .timing import align_messages_to_window
from .translation import assess_translation_need
from .video import analyze_video_segment
from .vod import download_vod_data
from .window_analysis import analyze_promotion_window


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "analyze":
        return analyze_command(args)
    if args.command == "capture":
        return capture_command(args)
    if args.command == "download-vod":
        return download_vod_command(args)
    if args.command == "analyze-promotion":
        return analyze_promotion_command(args)

    parser.print_help()
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="twitch-promo-analyzer",
        description="Analyze Twitch influencer promotions and viewer response.",
    )
    subparsers = parser.add_subparsers(dest="command")

    analyze = subparsers.add_parser("analyze", help="Analyze a CSV/JSON/NDJSON chat export.")
    analyze.add_argument("--input", required=True, help="Path to chat export.")
    analyze.add_argument("--influencer", action="append", default=[], help="Influencer handle. Can be repeated or comma-separated.")
    analyze.add_argument("--brand", action="append", default=[], help="Brand term. Can be repeated or comma-separated.")
    analyze.add_argument("--window-minutes", type=int, default=5, help="Response window after each promotion.")
    analyze.add_argument("--baseline-minutes", type=int, default=5, help="Baseline window before each promotion.")
    analyze.add_argument("--out", default="reports/analysis.json", help="JSON analysis output path.")
    analyze.add_argument("--report", default="reports/report.html", help="HTML report output path.")

    capture = subparsers.add_parser("capture", help="Capture live Twitch chat to CSV.")
    capture.add_argument("--channel", required=True, help="Twitch channel to join.")
    capture.add_argument("--nickname", required=True, help="Twitch nickname for IRC login.")
    capture.add_argument("--oauth", required=True, help="Twitch IRC OAuth token.")
    capture.add_argument("--output", default="data/live_chat.csv", help="CSV output path.")
    capture.add_argument("--duration-minutes", type=float, default=None, help="Capture duration.")
    capture.add_argument("--limit-messages", type=int, default=None, help="Stop after this many messages.")

    download = subparsers.add_parser(
        "download-vod",
        help="Download Twitch VOD chat/video with TwitchDownloaderCLI and normalize chat CSV.",
    )
    download.add_argument("vod", help="Twitch VOD URL or numeric VOD id.")
    download.add_argument("--output-dir", default="data", help="Base output directory.")
    download.add_argument(
        "--twitch-downloader",
        default=None,
        help="Path to TwitchDownloaderCLI. Defaults to tools/twitchdownloader/TwitchDownloaderCLI or PATH.",
    )
    download.add_argument("--ffmpeg-path", default=None, help="Optional path to ffmpeg.")
    download.add_argument("--quality", default=None, help="Video quality, for example 360p30, 480p30, 720p60, or 1080p60.")
    download.add_argument("--beginning", default=None, help="Trim start time, for example 01:27:25.")
    download.add_argument("--ending", default=None, help="Trim end time, for example 04:02:56.")
    download.add_argument("--threads", type=int, default=None, help="TwitchDownloader parallel download threads.")
    download.add_argument("--oauth", default=None, help="OAuth token for subscriber-only VODs. Do not share it.")
    download.add_argument("--temp-path", default=None, help="Temporary cache folder for TwitchDownloader.")
    download.add_argument("--skip-chat", action="store_true", help="Do not download chat JSON.")
    download.add_argument("--skip-video", action="store_true", help="Do not download video MP4.")
    download.add_argument("--no-chat-csv", action="store_true", help="Do not normalize chat JSON to CSV.")

    promo = subparsers.add_parser(
        "analyze-promotion",
        help="Analyze a fixed promotion time window (chat words + optional video segment).",
    )
    promo.add_argument("--vod-id", default=None, help="VOD id; resolves data/<id>/ paths.")
    promo.add_argument("--input", default=None, help="Chat CSV/JSON path (overrides --vod-id chat path).")
    promo.add_argument("--video", default=None, help="Video MP4 path.")
    promo.add_argument("--data-dir", default="data", help="Base data directory when using --vod-id.")
    promo.add_argument("--promo-start", type=float, default=9.0, help="Promotion start (minutes from stream start).")
    promo.add_argument("--promo-end", type=float, default=48.0, help="Promotion end (minutes from stream start).")
    promo.add_argument("--baseline-minutes", type=float, default=9.0, help="Baseline window length before promo.")
    promo.add_argument("--brand", action="append", default=[], help="Brand keyword (repeatable).")
    promo.add_argument("--cta", action="append", default=[], help="CTA keyword (repeatable).")
    promo.add_argument("--promo-code", default="KAV3769", help="Campaign promo code to track in chat.")
    promo.add_argument("--script", default=None, help="Influencer script JSON (stream-minute segments).")
    promo.add_argument("--stream-stats", default=None, help="Optional JSON with TwitchTracker/SullyGnome stats.")
    promo.add_argument("--out", default=None, help="JSON analysis output path.")
    promo.add_argument("--report", default=None, help="HTML report output path.")

    return parser


def analyze_command(args: argparse.Namespace) -> int:
    messages = load_messages(args.input)
    influencers = parse_multi_values(args.influencer)
    brands = parse_multi_values(args.brand)
    analysis = analyze_campaign(
        messages,
        influencers=influencers,
        brands=brands,
        window_minutes=args.window_minutes,
        baseline_minutes=args.baseline_minutes,
    )
    attach_recommendations(analysis)

    if args.out:
        write_json_report(analysis, args.out)
    if args.report:
        write_html_report(analysis, args.report)

    summary = analysis["summary"]
    print("Twitch promotion analysis complete")
    print(f"Messages analyzed: {summary['message_count']}")
    print(f"Promotions detected: {summary['detected_promotions']}")
    print(f"Average engagement lift: {round(summary['avg_engagement_lift'] * 100)}%")
    print(f"Average response sentiment: {summary['avg_response_sentiment']}")
    if args.out:
        print(f"JSON report: {Path(args.out).resolve()}")
    if args.report:
        print(f"HTML report: {Path(args.report).resolve()}")
    return 0


def capture_command(args: argparse.Namespace) -> int:
    count = capture_chat(
        channel=args.channel,
        nickname=args.nickname,
        oauth_token=args.oauth,
        output_path=args.output,
        duration_minutes=args.duration_minutes,
        limit_messages=args.limit_messages,
    )
    print(f"Captured {count} messages to {Path(args.output).resolve()}")
    return 0


def analyze_promotion_command(args: argparse.Namespace) -> int:
    vod_id = args.vod_id
    if args.input:
        chat_path = Path(args.input)
    elif vod_id:
        folder = Path(args.data_dir) / vod_id
        chat_path = preferred_chat_export(folder, vod_id)
    else:
        raise SystemExit("analyze-promotion requires --vod-id or --input")

    if not chat_path.exists():
        raise SystemExit(f"chat file not found: {chat_path}")

    if not vod_id and args.input:
        vod_id = chat_path.parent.name or chat_path.stem.split("_")[0]

    video_path = Path(args.video) if args.video else Path(args.data_dir) / str(vod_id) / f"{vod_id}_video.mp4"
    stream_stats = None
    if args.stream_stats:
        stream_stats = json.loads(Path(args.stream_stats).read_text(encoding="utf-8"))

    brands = parse_multi_values(args.brand)
    ctas = parse_multi_values(args.cta)
    brands.add(args.promo_code.lower())
    ctas.add(args.promo_code.lower())
    messages, timing_diagnostics = align_messages_to_window(
        load_messages(chat_path),
        args.promo_start,
        args.promo_end,
    )
    for warning in timing_diagnostics.get("warnings", []):
        print(f"Timing warning: {warning}")
    analysis = analyze_promotion_window(
        messages,
        promo_start_minute=args.promo_start,
        promo_end_minute=args.promo_end,
        baseline_minutes=args.baseline_minutes,
        brand_keywords=brands,
        cta_keywords=ctas,
        promo_code=args.promo_code,
        stream_stats=stream_stats,
    )
    peaks = analyze_promotion_peaks(
        messages,
        promo_start_minute=args.promo_start,
        promo_end_minute=args.promo_end,
        promo_code=args.promo_code,
    )
    analysis["chat_peaks"] = peaks
    if args.script:
        alignment = align_peaks_to_script(
            peaks["top_peaks_by_minute"],
            load_influencer_script(args.script),
            rolling_windows=peaks.get("top_rolling_windows"),
        )
        analysis["script_alignment"] = alignment
        peaks["top_peaks_by_minute"] = alignment["peak_alignments"]
    analysis["translation"] = assess_translation_need(
        messages,
        promo_start_minute=args.promo_start,
        promo_end_minute=args.promo_end,
        peak_samples=peaks["top_peaks_by_minute"],
    )
    analysis["video"] = analyze_video_segment(
        video_path,
        start_minute=args.promo_start,
        end_minute=args.promo_end,
    )
    analysis["inputs"] = {
        "vod_id": vod_id,
        "chat_path": str(chat_path.resolve()),
        "video_path": str(video_path.resolve()),
    }

    out_path = Path(args.out or f"reports/{vod_id}_promotion_analysis.json")
    write_json_report(analysis, out_path)

    perf = analysis["performance"]
    print("Promotion window analysis complete")
    print(f"VOD: {vod_id}")
    print(f"Window: {args.promo_start}-{args.promo_end} minutes")
    print(f"Grade: {perf['grade']} ({perf['score']}/100)")
    print(f"Grade confidence: {perf.get('confidence', 'n/a')}")
    if perf.get("note"):
        print(f"Note: {perf['note']}")
    print(f"Engagement lift: {round(analysis['lifts']['messages_per_minute'] * 100)}%")
    print(f"JSON: {out_path.resolve()}")
    return 0


def download_vod_command(args: argparse.Namespace) -> int:
    result = download_vod_data(
        vod=args.vod,
        output_dir=args.output_dir,
        twitch_downloader=args.twitch_downloader,
        ffmpeg_path=args.ffmpeg_path,
        quality=args.quality,
        beginning=args.beginning,
        ending=args.ending,
        threads=args.threads,
        oauth=args.oauth,
        temp_path=args.temp_path,
        download_chat=not args.skip_chat,
        download_video=not args.skip_video,
        convert_chat_csv=not args.no_chat_csv,
    )
    print(f"VOD id: {result['vod_id']}")
    print(f"Output directory: {Path(result['directory']).resolve()}")
    if result.get("chat_json"):
        print(f"Chat JSON: {Path(result['chat_json']).resolve()}")
    if result.get("chat_csv"):
        print(f"Chat CSV: {Path(result['chat_csv']).resolve()}")
    if result.get("video_mp4"):
        print(f"Video MP4: {Path(result['video_mp4']).resolve()}")
    return 0


def parse_multi_values(values: list[str]) -> set[str]:
    parsed: set[str] = set()
    for value in values:
        for item in value.split(","):
            clean = item.strip()
            if clean:
                parsed.add(clean)
    return parsed
