from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def write_product_headcount_csv(product_analysis: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "response_rank",
        "product_id",
        "product_name",
        "stream_minute_start",
        "stream_minute_end",
        "promo_minute_start",
        "promo_minute_end",
        "presenting_period_minutes",
        "unique_chatters",
        "unique_chatters_first_3min",
        "response_window_minutes",
        "total_messages",
        "messages_first_3min",
        "messages_per_minute",
        "response_score",
    ]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in product_analysis.get("product_segments", []):
            hc = item.get("headcount", {})
            writer.writerow(
                {
                    "response_rank": item.get("response_rank"),
                    "product_id": item.get("product_id"),
                    "product_name": item.get("product_name"),
                    "stream_minute_start": item.get("stream_minute_start"),
                    "stream_minute_end": item.get("stream_minute_end"),
                    "promo_minute_start": item.get("promo_minute_start"),
                    "promo_minute_end": item.get("promo_minute_end"),
                    "presenting_period_minutes": item.get("presenting_period_minutes"),
                    "unique_chatters": hc.get("unique_chatters"),
                    "unique_chatters_first_3min": hc.get("unique_chatters_first_3min"),
                    "response_window_minutes": hc.get("response_window_minutes"),
                    "total_messages": hc.get("total_messages"),
                    "messages_first_3min": hc.get("messages_first_3min"),
                    "messages_per_minute": item.get("chat", {}).get("messages_per_minute"),
                    "response_score": item.get("response_score"),
                }
            )
    return destination


def write_product_sentiment_csv(product_analysis: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "product_id",
        "product_name",
        "stream_minute_start",
        "stream_minute_end",
        "avg_sentiment",
        "avg_sentiment_first_3min",
        "positive",
        "neutral",
        "negative",
        "positive_pct",
        "response_rank",
    ]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in product_analysis.get("product_segments", []):
            sent = item.get("viewer_sentiment", {})
            writer.writerow(
                {
                    "product_id": item.get("product_id"),
                    "product_name": item.get("product_name"),
                    "stream_minute_start": item.get("stream_minute_start"),
                    "stream_minute_end": item.get("stream_minute_end"),
                    "avg_sentiment": sent.get("avg_score"),
                    "avg_sentiment_first_3min": sent.get("avg_score_first_3min"),
                    "positive": sent.get("positive"),
                    "neutral": sent.get("neutral"),
                    "negative": sent.get("negative"),
                    "positive_pct": sent.get("positive_pct"),
                    "response_rank": item.get("response_rank"),
                }
            )
    return destination


def write_participation_issues_csv(product_analysis: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "product_id",
        "product_name",
        "stream_minute_start",
        "stream_minute_end",
        "issue_type",
        "issue_count",
        "issue_message_count",
        "viewer_messages_in_period",
    ]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in product_analysis.get("product_segments", []):
            participation = item.get("participation_issues", {})
            counts = participation.get("issue_counts", {})
            if not counts:
                writer.writerow(
                    {
                        "product_id": item.get("product_id"),
                        "product_name": item.get("product_name"),
                        "stream_minute_start": item.get("stream_minute_start"),
                        "stream_minute_end": item.get("stream_minute_end"),
                        "issue_type": "",
                        "issue_count": 0,
                        "issue_message_count": participation.get("issue_message_count", 0),
                        "viewer_messages_in_period": participation.get("viewer_messages_in_period", 0),
                    }
                )
                continue
            for issue_type, count in sorted(counts.items(), key=lambda pair: pair[1], reverse=True):
                writer.writerow(
                    {
                        "product_id": item.get("product_id"),
                        "product_name": item.get("product_name"),
                        "stream_minute_start": item.get("stream_minute_start"),
                        "stream_minute_end": item.get("stream_minute_end"),
                        "issue_type": issue_type,
                        "issue_count": count,
                        "issue_message_count": participation.get("issue_message_count", 0),
                        "viewer_messages_in_period": participation.get("viewer_messages_in_period", 0),
                    }
                )
    return destination


def write_product_reports(
    product_analysis: dict[str, Any],
    reports_dir: str | Path,
    vod_id: str,
) -> dict[str, str]:
    folder = Path(reports_dir)
    json_path = folder / f"{vod_id}_product_analysis.json"
    json_path.write_text(json.dumps(product_analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    headcount_path = write_product_headcount_csv(product_analysis, folder / f"{vod_id}_product_headcount.csv")
    return {
        "json": str(json_path.resolve()),
        "headcount_csv": str(headcount_path.resolve()),
        "sentiment_csv": str(
            write_product_sentiment_csv(product_analysis, folder / f"{vod_id}_product_sentiment.csv")
        ),
        "participation_csv": str(
            write_participation_issues_csv(product_analysis, folder / f"{vod_id}_participation_issues.csv")
        ),
    }
