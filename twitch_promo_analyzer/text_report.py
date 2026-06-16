from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LINE = "=" * 72
SUBLINE = "-" * 72


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{round(value * 100)}%"


def fmt_minutes(start: float | None, end: float | None) -> str:
    if start is None or end is None:
        return "n/a"
    return f"{start:.1f}–{end:.1f} min (stream)"


def section(title: str, lines: list[str]) -> list[str]:
    output = [LINE, title.upper(), LINE, *lines, ""]
    return output


def build_findings_report(
    vod_id: str,
    *,
    reports_dir: str | Path = "reports",
    data_dir: str | Path = "data",
) -> str:
    reports = Path(reports_dir)
    data = Path(data_dir) / vod_id

    promotion = load_json(reports / f"{vod_id}_promotion_analysis.json")
    product = load_json(reports / f"{vod_id}_product_analysis.json")
    post_promo = load_json(reports / f"{vod_id}_post_promo_analysis.json")
    transcript = load_json(data / f"{vod_id}_influencer_transcript.json")

    lines: list[str] = []
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines.extend(
        section(
            "Twitch Promotion Analysis — Findings Report",
            [
                f"VOD ID:           {vod_id}",
                f"Generated:        {generated}",
                f"Data folder:      {data.resolve()}",
                f"Reports folder:   {reports.resolve()}",
            ],
        )
    )

    if promotion:
        inputs = promotion.get("inputs", {})
        windows = promotion.get("windows", {})
        perf = promotion.get("performance", {})
        lifts = promotion.get("lifts", {})
        promo_summary = promotion.get("summaries", {}).get("promotion", {})
        baseline_summary = promotion.get("summaries", {}).get("baseline", {})
        settings = promotion.get("settings", {})

        lines.extend(
            section(
                "1. Campaign overview",
                [
                    f"Twitch URL:       {inputs.get('twitch_vod_url', 'n/a')}",
                    f"Promo code:       {inputs.get('promo_code', settings.get('promo_code', 'n/a'))}",
                    f"Promo window:     {windows.get('promotion_minutes', 'n/a')} (stream minutes)",
                    f"Stream start:     {promotion.get('vod', {}).get('stream_start', 'n/a')}",
                    f"Stream duration:  {promotion.get('vod', {}).get('stream_duration_minutes', 'n/a')} min",
                    "",
                    f"Performance grade: {perf.get('grade', 'n/a')} ({perf.get('score', 'n/a')}/100)",
                    f"Verdict:          {perf.get('verdict', 'n/a')}",
                    "",
                    "Engagement vs baseline (first 9 min):",
                    f"  Messages/min lift:     {pct(lifts.get('messages_per_minute'))}",
                    f"  Total message volume:  {pct(lifts.get('total_messages'))}",
                    f"  Unique chatters lift:  {pct(lifts.get('unique_chatters'))}",
                    f"  Sentiment delta:       {lifts.get('sentiment_delta', 'n/a')}",
                    "",
                    "During promotion window:",
                    f"  Chat messages:    {promo_summary.get('message_count', 'n/a')}",
                    f"  Unique chatters:  {promo_summary.get('unique_chatters', 'n/a')}",
                    f"  Messages/min:     {promo_summary.get('messages_per_minute', 'n/a')}",
                    f"  !temu commands:   {promotion.get('word_analysis', {}).get('cta_command_count', 'n/a')}",
                    "",
                    "Baseline (pre-promo):",
                    f"  Chat messages:    {baseline_summary.get('message_count', 'n/a')}",
                    f"  Unique chatters:  {baseline_summary.get('unique_chatters', 'n/a')}",
                ],
            )
        )

        peaks = promotion.get("chat_peaks", {})
        if peaks:
            peak_lines = [peaks.get("summary", ""), ""]
            peak_lines.append(f"{'Rank':<5} {'Promo min':<10} {'Msgs':<6} {'Code':<6} Product / script topic")
            peak_lines.append(SUBLINE)
            for index, peak in enumerate(peaks.get("top_peaks_by_minute", [])[:8], start=1):
                topic = ""
                aligned = peak.get("aligned_script") or {}
                topic = aligned.get("topic", "")
                peak_lines.append(
                    f"{index:<5} {peak.get('promo_minute', ''):<10} "
                    f"{peak.get('message_count', ''):<6} "
                    f"{peak.get('promo_code_mentions', ''):<6} {topic}"
                )
            peak_lines.append("")
            peak_lines.append("Sample reactions at top peaks:")
            for peak in peaks.get("top_peaks_by_minute", [])[:3]:
                peak_lines.append(f"  Promo minute {peak.get('promo_minute')}:")
                for reaction in peak.get("top_reactions", [])[:4]:
                    peak_lines.append(f"    [{reaction.get('user')}] {reaction.get('message', '')[:120]}")
            lines.extend(section("2. Chat peaks during promotion", peak_lines))

        code_stats = peaks.get("promo_code_activity", {}) if peaks else {}
        if code_stats:
            lines.extend(
                section(
                    "3. Promo code KAV3769 in chat",
                    [
                        f"Total code mentions:        {code_stats.get('total_mentions', 0)}",
                        f"Organic viewer mentions:    {code_stats.get('organic_mentions', 0)}",
                        f"Bot/copy-paste mentions:    {code_stats.get('bot_or_copy_paste_mentions', 0)}",
                        f"Unique users (organic):       {code_stats.get('unique_users_with_code', 0)}",
                    ],
                )
            )

    if product:
        lines.extend(
            section(
                "4. Executive summaries",
                [
                    product.get("summary", ""),
                    product.get("headcount_summary", ""),
                    product.get("sentiment_summary", ""),
                    product.get("participation_summary", ""),
                ],
            )
        )

        head_lines = [
            f"{'Rank':<5} {'Product':<28} {'Period (stream min)':<22} {'Chatters':<9} {'Msgs':<6} {'3-min msgs':<10}",
            SUBLINE,
        ]
        for item in product.get("product_segments", []):
            hc = item.get("headcount", {})
            head_lines.append(
                f"{item.get('response_rank', ''):<5} "
                f"{item.get('product_name', '')[:28]:<28} "
                f"{fmt_minutes(item.get('stream_minute_start'), item.get('stream_minute_end')):<22} "
                f"{hc.get('unique_chatters', ''):<9} "
                f"{hc.get('total_messages', ''):<6} "
                f"{hc.get('messages_first_3min', ''):<10}"
            )
        lines.extend(section("5. Headcount per product presenting period", head_lines))

        sent_lines = [
            f"{'Product':<28} {'Avg sent.':<10} {'Pos':<6} {'Neu':<6} {'Neg':<6} {'Pos %':<8}",
            SUBLINE,
        ]
        for item in product.get("product_segments", []):
            sent = item.get("viewer_sentiment", {})
            sent_lines.append(
                f"{item.get('product_name', '')[:28]:<28} "
                f"{sent.get('avg_score', ''):<10} "
                f"{sent.get('positive', ''):<6} "
                f"{sent.get('neutral', ''):<6} "
                f"{sent.get('negative', ''):<6} "
                f"{sent.get('positive_pct', '')}%"
            )
        lines.extend(section("6. Viewer sentiment by product", sent_lines))

        issue_lines = [
            "Issue types: how_to_participate | code_or_link_request | app_or_signup_issue | "
            "offer_clarity | trust_or_objection",
            "",
        ]
        for item in product.get("product_segments", []):
            participation = item.get("participation_issues", {})
            counts = participation.get("issue_counts", {})
            if not counts:
                continue
            issue_lines.append(
                f"{item.get('product_name')} ({fmt_minutes(item.get('stream_minute_start'), item.get('stream_minute_end'))})"
            )
            for issue_type, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True):
                issue_lines.append(f"  - {issue_type}: {count}")
            issue_lines.append("  Sample viewer comments:")
            for sample in participation.get("sample_issues", [])[:3]:
                issue_lines.append(f"    [{sample.get('user')}] {sample.get('message', '')[:140]}")
            issue_lines.append("")

        promo_wide = product.get("promo_participation_issues", {})
        if promo_wide.get("issue_counts"):
            issue_lines.append("Promo-wide participation issues:")
            for issue_type, count in sorted(
                promo_wide["issue_counts"].items(),
                key=lambda pair: pair[1],
                reverse=True,
            ):
                issue_lines.append(f"  - {issue_type}: {count}")
        lines.extend(section("7. Campaign participation issues (viewer chat)", issue_lines))

    if post_promo:
        during = post_promo.get("during_promo", {})
        post_lines = [
            post_promo.get("verdict", ""),
            "",
            f"During promo (banner live):  {during.get('promo_signal_messages', 0)} Temu/code mentions "
            f"({during.get('promo_signals_per_100_messages', 0)} per 100 messages)",
            "",
            f"{'Window':<32} {'Messages':<10} {'Temu/code':<12} {'Per 100 msgs':<12}",
            SUBLINE,
        ]
        for window in post_promo.get("post_promo_windows", []):
            post_lines.append(
                f"{window.get('label', ''):<32} "
                f"{window.get('message_count', ''):<10} "
                f"{window.get('promo_signal_messages', ''):<12} "
                f"{window.get('promo_signals_per_100_messages', ''):<12}"
            )
        post_lines.append("")
        post_lines.append(
            f"Retention ratio (first 30 min post-promo vs during promo): "
            f"{post_promo.get('retention_ratio_first_30min', 'n/a')}"
        )
        lines.extend(section("8. Post-promotion interest (after banner ends)", post_lines))

    if transcript:
        transcript_lines = [
            f"Influencer:     {transcript.get('influencer', 'n/a')}",
            f"Language:      {transcript.get('language', 'n/a')}",
            f"Line count:    {transcript.get('line_count', len(transcript.get('transcript', [])))}",
            f"Source:        {transcript.get('source', 'n/a')}",
            "",
            "Sample influencer lines (Italian + English):",
        ]
        for line in transcript.get("transcript", [])[:8]:
            transcript_lines.append(
                f"  [{line.get('stream_minute')} min] {line.get('text', '')[:100]}"
            )
            if line.get("english"):
                transcript_lines.append(f"           EN: {line.get('english', '')[:100]}")
        lines.extend(section("9. Influencer transcript sample", transcript_lines))

    lines.extend(
        section(
            "10. Output files referenced",
            [
                f"  {reports / f'{vod_id}_promotion_analysis.json'}",
                f"  {reports / f'{vod_id}_promotion_report.html'}",
                f"  {reports / f'{vod_id}_product_analysis.json'}",
                f"  {reports / f'{vod_id}_product_headcount.csv'}",
                f"  {reports / f'{vod_id}_product_sentiment.csv'}",
                f"  {reports / f'{vod_id}_participation_issues.csv'}",
                f"  {reports / f'{vod_id}_post_promo_analysis.json'}",
                f"  {data / f'{vod_id}_influencer_transcript.csv'}",
                f"  {data / f'{vod_id}_viewer_responses.csv'}",
            ],
        )
    )

    if not promotion and not product and not post_promo:
        lines.append("No analysis JSON files found. Run the pipeline first:")
        lines.append("  python scripts/run_vod_analysis.py --vod-url ... --promo-start ... --promo-end ...")

    return "\n".join(lines).strip() + "\n"


def write_findings_report(
    vod_id: str,
    output_path: str | Path | None = None,
    *,
    reports_dir: str | Path = "reports",
    data_dir: str | Path = "data",
) -> Path:
    destination = Path(output_path or Path(reports_dir) / f"{vod_id}_findings_report.txt")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        build_findings_report(vod_id, reports_dir=reports_dir, data_dir=data_dir),
        encoding="utf-8",
    )
    return destination
