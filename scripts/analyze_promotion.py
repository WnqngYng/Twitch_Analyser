#!/usr/bin/env python3
"""
Reusable promotion window analysis for a Twitch VOD folder.

Defaults target VOD 2776778244 (TheRealMarzaa / Temu) with promotion at 9–48 minutes
and promo code KAV3769.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twitch_promo_analyzer.loaders import load_messages, preferred_chat_export
from twitch_promo_analyzer.peaks import analyze_promotion_peaks
from twitch_promo_analyzer.script_align import align_peaks_to_script, load_influencer_script
from twitch_promo_analyzer.translation import assess_translation_need
from twitch_promo_analyzer.video import analyze_video_segment
from twitch_promo_analyzer.timing import align_messages_to_window, stream_origin
from twitch_promo_analyzer.transcribe import build_merged_corpus_from_files
from twitch_promo_analyzer.utterances import viewer_utterances_from_chat
from twitch_promo_analyzer.window_analysis import analyze_promotion_window


ANALYSIS_DEFAULTS = {
    "vod_id": "2776778244",
    "promo_start_minute": 9.0,
    "promo_end_minute": 48.0,
    "baseline_minutes": 9.0,
    "promo_code": "KAV3769",
    "brand_keywords": ["temu", "kav3769", "coupon", "sconto", "codice"],
    "cta_keywords": ["!temu", "temu.com", "link", "codice", "coupon", "kav3769"],
    "stream_stats_path": None,
    "script_path": None,
}


def vod_paths(vod_id: str, data_dir: Path) -> dict[str, Path]:
    folder = data_dir / vod_id
    return {
        "folder": folder,
        "chat_csv": folder / f"{vod_id}_chat.csv",
        "chat_json": folder / f"{vod_id}_chat.json",
        "video_mp4": folder / f"{vod_id}_video.mp4",
    }


def load_stream_stats(path: Path | None) -> dict | None:
    if not path or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def resolve_chat_path(paths: dict[str, Path], explicit: str | None) -> Path:
    vod_id = paths["folder"].name
    candidate = preferred_chat_export(paths["folder"], vod_id, explicit)
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        f"No chat export found in {paths['folder']}. "
        "Run: python -m twitch_promo_analyzer download-vod <url> --skip-video"
    )


def run_full_analysis(
    messages,
    *,
    vod_id: str,
    promo_start: float,
    promo_end: float,
    promo_code: str,
    brands: set[str],
    ctas: set[str],
    stream_stats: dict | None,
    script_path: Path | None,
    video_path: Path,
) -> dict:
    analysis = analyze_promotion_window(
        messages,
        promo_start_minute=promo_start,
        promo_end_minute=promo_end,
        baseline_minutes=ANALYSIS_DEFAULTS["baseline_minutes"],
        brand_keywords=brands,
        cta_keywords=ctas,
        promo_code=promo_code,
        stream_stats=stream_stats,
    )

    peaks = analyze_promotion_peaks(
        messages,
        promo_start_minute=promo_start,
        promo_end_minute=promo_end,
        promo_code=promo_code,
    )
    analysis["chat_peaks"] = peaks

    if script_path and script_path.exists():
        script = load_influencer_script(script_path)
        alignment = align_peaks_to_script(
            peaks["top_peaks_by_minute"],
            script,
            rolling_windows=peaks.get("top_rolling_windows"),
        )
        analysis["script_alignment"] = alignment
        peaks["top_peaks_by_minute"] = alignment["peak_alignments"]
    else:
        script_note = (
            f"No influencer script at {script_path}. "
            "Add examples/<vod>_influencer_script.json or a Whisper transcript."
            if script_path
            else "No influencer script provided; peak alignment was skipped."
        )
        analysis["script_alignment"] = {
            "summary": script_note,
            "segments": [],
        }

    analysis["translation"] = assess_translation_need(
        messages,
        promo_start_minute=promo_start,
        promo_end_minute=promo_end,
        peak_samples=peaks["top_peaks_by_minute"],
    )

    analysis["video"] = analyze_video_segment(
        video_path,
        start_minute=promo_start,
        end_minute=promo_end,
    )
    return analysis


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze a Twitch promotion time window.")
    parser.add_argument("--vod-id", default=ANALYSIS_DEFAULTS["vod_id"])
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--chat", default=None)
    parser.add_argument("--video", default=None)
    parser.add_argument("--promo-start", type=float, default=ANALYSIS_DEFAULTS["promo_start_minute"])
    parser.add_argument("--promo-end", type=float, default=ANALYSIS_DEFAULTS["promo_end_minute"])
    parser.add_argument("--promo-code", default=ANALYSIS_DEFAULTS["promo_code"])
    parser.add_argument("--influencer", default="therealmarzaa")
    parser.add_argument("--brand", action="append", default=[])
    parser.add_argument("--cta", action="append", default=[])
    parser.add_argument("--script", default=None)
    parser.add_argument("--stream-stats", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--report", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    vod_id = args.vod_id
    paths = vod_paths(vod_id, Path(args.data_dir))

    brands = set(ANALYSIS_DEFAULTS["brand_keywords"]) | {item.lower() for item in args.brand}
    ctas = set(ANALYSIS_DEFAULTS["cta_keywords"]) | {item.lower() for item in args.cta}
    brands.add(args.promo_code.lower())
    ctas.add(args.promo_code.lower())

    chat_path = resolve_chat_path(paths, args.chat)
    messages, timing_diagnostics = align_messages_to_window(
        load_messages(chat_path),
        args.promo_start,
        args.promo_end,
    )
    for warning in timing_diagnostics.get("warnings", []):
        print(f"Timing warning: {warning}", file=sys.stderr)
    stream_stats = load_stream_stats(Path(args.stream_stats) if args.stream_stats else None)
    if stream_stats is None:
        stream_stats = {
            "source": "not_provided",
        }

    script_path = Path(args.script) if args.script else None
    video_path = Path(args.video) if args.video else paths["video_mp4"]

    analysis = run_full_analysis(
        messages,
        vod_id=vod_id,
        promo_start=args.promo_start,
        promo_end=args.promo_end,
        promo_code=args.promo_code,
        brands=brands,
        ctas=ctas,
        stream_stats=stream_stats,
        script_path=script_path,
        video_path=video_path,
    )
    analysis["inputs"] = {
        "vod_id": vod_id,
        "chat_path": str(chat_path.resolve()),
        "video_path": str(video_path.resolve()),
        "script_path": str(script_path.resolve()) if script_path else None,
        "promo_code": args.promo_code.upper(),
        "twitch_vod_url": f"https://www.twitch.tv/videos/{vod_id}",
    }

    out_path = Path(args.out or f"reports/{vod_id}_promotion_analysis.json")
    report_path = Path(args.report or f"reports/{vod_id}_promotion_report.html")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    viewer_rows = viewer_utterances_from_chat(
        messages,
        args.promo_start,
        args.promo_end,
        influencer_name=args.influencer,
    )
    merged = build_merged_corpus_from_files(
        vod_id=vod_id,
        data_dir=args.data_dir,
        promo_start_minute=args.promo_start,
        promo_end_minute=args.promo_end,
        viewer_utterances=viewer_rows,
        stream_start_iso=stream_origin(messages).isoformat(),
    )
    analysis["responses_corpus"] = {
        "counts": merged["corpus"]["counts"],
        "merged_json": merged["merged_json"],
        "merged_csv": merged["merged_csv"],
    }
    out_path.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(render_promotion_html(analysis), encoding="utf-8")

    perf = analysis["performance"]
    peaks = analysis["chat_peaks"]
    translation = analysis["translation"]["recommendation"]
    print(f"VOD {vod_id}: promotion {args.promo_start}-{args.promo_end} min · code {args.promo_code}")
    print(f"Grade: {perf['grade']} ({perf['score']}/100)")
    print(f"Grade confidence: {perf.get('confidence', 'n/a')}")
    if perf.get("note"):
        print(f"Note: {perf['note']}")
    print(peaks["summary"])
    if analysis.get("script_alignment", {}).get("summary"):
        print(analysis["script_alignment"]["summary"])
    print(f"Translate viewer chat: {translation['translate_viewer_responses']} — {translation['rationale']}")
    print(f"Responses corpus: {merged['merged_json']}")
    print(f"JSON: {out_path.resolve()}")
    print(f"HTML: {report_path.resolve()}")
    return 0


def render_promotion_html(analysis: dict) -> str:
    perf = analysis["performance"]
    words = analysis["word_analysis"]
    peaks = analysis.get("chat_peaks", {})
    script = analysis.get("script_alignment", {})
    translation = analysis.get("translation", {})

    peak_rows = ""
    for peak in peaks.get("top_peaks_by_minute", [])[:6]:
        seg = peak.get("aligned_script") or {}
        topic = seg.get("topic", "")
        peak_rows += (
            f"<tr><td>{peak['promo_minute']}</td><td>{peak['message_count']}</td>"
            f"<td>{html.escape(topic)}</td><td>{peak.get('promo_code_mentions', 0)}</td></tr>"
        )

    reaction_list = ""
    for peak in peaks.get("top_peaks_by_minute", [])[:3]:
        reaction_list += f"<h3>Promo minute {peak['promo_minute']}</h3><ul>"
        for item in peak.get("top_reactions", [])[:4]:
            reaction_list += (
                f"<li><strong>{html.escape(item['user'])}</strong>: "
                f"{html.escape(item['message'])}</li>"
            )
        reaction_list += "</ul>"

    translate_note = translation.get("recommendation", {})
    translate_rows = ""
    for item in translation.get("messages_to_translate", [])[:15]:
        translate_rows += (
            f"<tr><td>{item.get('promo_minute', '')}</td>"
            f"<td>{html.escape(item.get('original', ''))}</td></tr>"
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Promotion Report</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 24px; max-width: 960px; }}
.card {{ border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border-bottom: 1px solid #eee; padding: 8px; text-align: left; vertical-align: top; }}
</style></head><body>
<h1>Promotion analysis</h1>
<p>{html.escape(analysis['inputs']['twitch_vod_url'])} · code {html.escape(analysis['inputs']['promo_code'])}</p>
<div class="card"><h2>Performance</h2>
<p>Grade {perf['grade']} ({perf['score']}/100). Confidence: {html.escape(str(perf.get('confidence', 'n/a')))}.</p>
<p>{html.escape(perf['verdict'])}</p>
<p>{html.escape(perf.get('note', ''))}</p></div>
<div class="card"><h2>Chat peaks (promo minute)</h2>
<p>{html.escape(peaks.get('summary', ''))}</p>
<table><tr><th>Promo min</th><th>Messages</th><th>Script topic</th><th>Code mentions</th></tr>{peak_rows}</table>
{reaction_list}</div>
<div class="card"><h2>Script alignment</h2>
<p>{html.escape(script.get('summary', 'No script loaded.'))}</p></div>
<div class="card"><h2>Translation</h2>
<p><strong>Translate?</strong> {translate_note.get('translate_viewer_responses')} — {html.escape(translate_note.get('rationale', ''))}</p>
<p>Primary chat language: {translation.get('language_mix', {}).get('primary', 'n/a')}</p>
<table><tr><th>Promo min</th><th>Original (translate to EN)</th></tr>{translate_rows}</table></div>
<div class="card"><h2>CTA</h2>
<p>!temu: {words['cta_command_count']} · Promo code organic mentions: {peaks.get('promo_code_activity', {}).get('organic_mentions', 0)}</p></div>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
