from __future__ import annotations

import unittest

from twitch_promo_analyzer.loaders import load_messages
from twitch_promo_analyzer.timing import filter_by_minutes, stream_origin
from twitch_promo_analyzer.window_analysis import analyze_promotion_window


class PromotionWindowTests(unittest.TestCase):
    def test_filter_by_minutes(self) -> None:
        messages = load_messages("data/2776778244/2776778244_chat.csv")
        origin = stream_origin(messages)
        promo = filter_by_minutes(messages, 9, 48, origin)
        self.assertGreater(len(promo), 1000)

    def test_analyze_promotion_window(self) -> None:
        messages = load_messages("data/2776778244/2776778244_chat.csv")
        analysis = analyze_promotion_window(
            messages,
            promo_start_minute=9,
            promo_end_minute=48,
            brand_keywords={"temu"},
            cta_keywords={"!temu"},
        )
        self.assertGreater(analysis["lifts"]["messages_per_minute"], 0)
        self.assertGreater(analysis["word_analysis"]["cta_command_count"], 5)
        self.assertIn("grade", analysis["performance"])


if __name__ == "__main__":
    unittest.main()
