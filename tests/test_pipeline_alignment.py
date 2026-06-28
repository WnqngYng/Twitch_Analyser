from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from twitch_promo_analyzer.models import ChatMessage
from twitch_promo_analyzer.products import summarize_products
from twitch_promo_analyzer.timing import align_messages_to_window, offset_minutes, stream_origin
from twitch_promo_analyzer.utterances import influencer_utterances_from_whisper
from twitch_promo_analyzer.window_analysis import analyze_promotion_window


class PipelineAlignmentTests(unittest.TestCase):
    def test_trimmed_csv_without_offsets_is_inferred_to_promo_window(self) -> None:
        messages = [
            ChatMessage.from_fields("2026-05-14T18:00:00Z", "a", "first"),
            ChatMessage.from_fields("2026-05-14T18:29:00Z", "b", "last"),
        ]

        aligned, diagnostics = align_messages_to_window(messages, 150.0, 180.0)
        origin = stream_origin(aligned)
        minutes = [offset_minutes(message, origin) for message in aligned]

        self.assertEqual(diagnostics["alignment"], "inferred_trimmed_csv_offset")
        self.assertAlmostEqual(minutes[0], 150.0)
        self.assertAlmostEqual(minutes[-1], 179.0)

    def test_promo_baseline_uses_requested_minutes_before_start(self) -> None:
        messages = [
            ChatMessage.from_fields("2026-01-01T00:00:00Z", "viewer", "too early"),
            ChatMessage.from_fields("2026-01-01T00:08:00Z", "viewer", "baseline"),
            ChatMessage.from_fields("2026-01-01T00:10:00Z", "viewer", "temu"),
            ChatMessage.from_fields("2026-01-01T00:11:00Z", "viewer", "!temu"),
        ]

        analysis = analyze_promotion_window(
            messages,
            promo_start_minute=10.0,
            promo_end_minute=12.0,
            baseline_minutes=3.0,
            brand_keywords={"temu"},
            cta_keywords={"!temu"},
        )

        self.assertEqual(analysis["windows"]["baseline_minutes"], [7.0, 10.0])
        self.assertEqual(analysis["summaries"]["baseline"]["message_count"], 1)

    def test_whisper_trimmed_timestamps_are_shifted_to_stream_minutes(self) -> None:
        payload = {
            "language": "it",
            "segments": [
                {"start": 0.0, "end": 5.0, "text": "inizio promo"},
                {"start": 60.0, "end": 65.0, "text": "prodotto"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "whisper.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            rows = influencer_utterances_from_whisper(path, 30.0, 72.0)

        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0]["stream_minute"], 30.0)
        self.assertAlmostEqual(rows[1]["stream_minute"], 31.0)

    def test_whisper_full_stream_timestamps_are_not_double_shifted(self) -> None:
        payload = {
            "language": "it",
            "segments": [
                {"start": 1800.0, "end": 1805.0, "text": "inizio promo"},
                {"start": 1860.0, "end": 1865.0, "text": "prodotto"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "whisper.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            rows = influencer_utterances_from_whisper(path, 30.0, 72.0)

        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0]["stream_minute"], 30.0)
        self.assertAlmostEqual(rows[1]["stream_minute"], 31.0)

    def test_single_product_summary_is_not_blank(self) -> None:
        summary = summarize_products(
            [
                {
                    "product_name": "Phone Case",
                    "response_score": 12.5,
                    "chat": {"messages_first_3min": 4},
                }
            ]
        )

        self.assertIn("Phone Case", summary)
        self.assertIn("Strongest chat response", summary)


if __name__ == "__main__":
    unittest.main()
