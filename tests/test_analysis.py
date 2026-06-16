from __future__ import annotations

import unittest

from twitch_promo_analyzer.analysis import analyze_campaign
from twitch_promo_analyzer.timing import filter_by_minutes, stream_origin
from twitch_promo_analyzer.loaders import load_messages
from twitch_promo_analyzer.recommendations import attach_recommendations
from twitch_promo_analyzer.vod import extract_vod_id


class CampaignAnalysisTests(unittest.TestCase):
    def test_sample_detects_promotions_and_recommendations(self) -> None:
        messages = load_messages("examples/sample_chat.csv")
        analysis = analyze_campaign(
            messages,
            influencers={"StreamerOne"},
            brands={"BrandPulse"},
            window_minutes=5,
            baseline_minutes=5,
        )
        attach_recommendations(analysis)

        self.assertEqual(analysis["summary"]["detected_promotions"], 2)
        self.assertGreater(analysis["events"][0]["engagement_lift"], 0)
        self.assertIn("recommendations", analysis)
        self.assertGreaterEqual(len(analysis["recommendations"]["campaign"]), 1)

    def test_no_promotions_gets_guidance(self) -> None:
        messages = load_messages("examples/sample_chat.csv")[:5]
        analysis = analyze_campaign(messages, influencers={"StreamerOne"}, brands={"BrandPulse"})
        attach_recommendations(analysis)

        self.assertEqual(analysis["summary"]["detected_promotions"], 0)
        self.assertIn("No promotional moments", analysis["recommendations"]["campaign"][0])

    def test_extract_vod_id_from_twitch_url(self) -> None:
        self.assertEqual(
            extract_vod_id("https://www.twitch.tv/videos/2776778244?sr=a"),
            "2776778244",
        )

    def test_loads_twitchdownloader_chat_json(self) -> None:
        messages = load_messages("examples/sample_twitchdownloader_chat.json")

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].user, "StreamerOne")
        self.assertIn("BrandPulse", messages[0].message)
        self.assertEqual(messages[0].stream_offset_seconds, 300.0)

    def test_twitchdownloader_offsets_align_trimmed_chat_to_stream_minutes(self) -> None:
        messages = load_messages("examples/sample_twitchdownloader_chat.json")
        origin = stream_origin(messages)
        window = filter_by_minutes(messages, 5.0, 5.5, origin)

        self.assertEqual(len(window), 2)


if __name__ == "__main__":
    unittest.main()
