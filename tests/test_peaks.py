from __future__ import annotations

import unittest

from twitch_promo_analyzer.loaders import load_messages
from twitch_promo_analyzer.peaks import analyze_promotion_peaks
from twitch_promo_analyzer.script_align import align_peaks_to_script, load_influencer_script
from twitch_promo_analyzer.translation import assess_translation_need


class PeakAnalysisTests(unittest.TestCase):
    def test_peaks_and_code_tracking(self) -> None:
        messages = load_messages("data/2776778244/2776778244_chat.csv")
        peaks = analyze_promotion_peaks(messages, 9, 48, promo_code="KAV3769")
        self.assertGreater(len(peaks["top_peaks_by_minute"]), 0)
        self.assertEqual(peaks["promo_code"], "KAV3769")
        self.assertIn("summary", peaks)

    def test_script_alignment(self) -> None:
        messages = load_messages("data/2776778244/2776778244_chat.csv")
        peaks = analyze_promotion_peaks(messages, 9, 48)
        script = load_influencer_script("examples/2776778244_influencer_script.json")
        alignment = align_peaks_to_script(peaks["top_peaks_by_minute"], script)
        self.assertIn("summary", alignment)
        self.assertTrue(alignment["peak_alignments"][0].get("aligned_script"))

    def test_translation_recommendation(self) -> None:
        messages = load_messages("data/2776778244/2776778244_chat.csv")
        peaks = analyze_promotion_peaks(messages, 9, 48)
        result = assess_translation_need(messages, 9, 48, peaks["top_peaks_by_minute"])
        self.assertEqual(result["language_mix"]["primary"], "italian")
        self.assertTrue(result["recommendation"]["translate_viewer_responses"])


if __name__ == "__main__":
    unittest.main()
