from __future__ import annotations

import unittest

from twitch_promo_analyzer.loaders import load_messages
from twitch_promo_analyzer.models import ChatMessage
from twitch_promo_analyzer.participation import analyze_participation_issues, classify_participation_issue
from twitch_promo_analyzer.products import build_product_analysis
from twitch_promo_analyzer.influencer_transcript import load_influencer_transcript


class ParticipationTests(unittest.TestCase):
    def test_classify_italian_participation(self) -> None:
        issues = classify_participation_issue("ma come funziona il buono sconto")
        self.assertIn("how_to_participate", issues)

    def test_product_analysis_includes_headcount_and_sentiment(self) -> None:
        path = "data/2776778244/2776778244_influencer_transcript.json"
        if not __import__("pathlib").Path(path).exists():
            self.skipTest("transcript missing")
        document = load_influencer_transcript(path)
        messages = load_messages("data/2776778244/2776778244_chat.csv")
        analysis = build_product_analysis(document, messages, 9, 48)
        segment = analysis["product_segments"][0]
        self.assertIn("headcount", segment)
        self.assertIn("viewer_sentiment", segment)
        self.assertIn("participation_issues", segment)

    def test_product_headcount_uses_stream_offsets_for_trimmed_chat(self) -> None:
        document = {
            "transcript": [
                {"stream_minute": 150.0, "text": "telefono cellulare poco xiaomi"},
                {"stream_minute": 150.5, "text": "fine segmento"},
            ]
        }
        messages = [
            ChatMessage.from_fields(
                "2026-05-14T18:00:52Z",
                "viewer_one",
                "che telefono è?",
                stream_offset_seconds=150 * 60 + 5,
            )
        ]

        analysis = build_product_analysis(document, messages, 150, 180)

        self.assertEqual(analysis["product_segments"][0]["headcount"]["unique_chatters"], 1)


if __name__ == "__main__":
    unittest.main()
