from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from twitch_promo_analyzer.text_report import build_findings_report, write_findings_report


class TextReportTests(unittest.TestCase):
    def test_build_findings_report(self) -> None:
        text = build_findings_report("2776778244")
        self.assertIn("FINDINGS REPORT", text)
        self.assertIn("HEADCOUNT PER PRODUCT", text)

    def test_write_findings_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = write_findings_report(
                "2776778244",
                Path(tmp) / "out.txt",
                reports_dir="reports",
                data_dir="data",
            )
            self.assertTrue(path.exists())
            self.assertGreater(path.stat().st_size, 100)


if __name__ == "__main__":
    unittest.main()
