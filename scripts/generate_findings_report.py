#!/usr/bin/env python3
"""
Generate a plain-text findings report from all analysis JSON outputs.

Usage:
  python scripts/generate_findings_report.py
  python scripts/generate_findings_report.py --vod-id 2776778244
  python scripts/generate_findings_report.py --vod-id 2776778244 --out reports/custom.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from twitch_promo_analyzer.text_report import write_findings_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export all findings to a .txt report.")
    parser.add_argument("--vod-id", default="2776778244")
    parser.add_argument("--reports-dir", default="reports")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--out", default=None, help="Output .txt path")
    args = parser.parse_args(argv)

    path = write_findings_report(
        args.vod_id,
        args.out,
        reports_dir=args.reports_dir,
        data_dir=args.data_dir,
    )
    print(f"Findings report written to: {path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
