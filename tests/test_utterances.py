from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from twitch_promo_analyzer.loaders import load_messages
from twitch_promo_analyzer.utterances import (
    influencer_utterances_from_whisper,
    merge_response_corpus,
    viewer_utterances_from_chat,
    write_responses_csv,
)


class UtteranceFormatTests(unittest.TestCase):
    def test_viewer_utterance_shape(self) -> None:
        messages = load_messages("data/2776778244/2776778244_chat.csv")
        rows = viewer_utterances_from_chat(messages, 9, 48)
        self.assertGreater(len(rows), 100)
        row = rows[0]
        for field in ("id", "speaker_role", "original", "translate_to", "user"):
            self.assertIn(field, row)
        self.assertEqual(row["speaker_role"], "viewer")

    def test_whisper_to_utterances(self) -> None:
        payload = {
            "language": "it",
            "segments": [
                {"start": 540.0, "end": 545.0, "text": "Ciao chat, codice KAV3769"},
                {"start": 960.0, "end": 965.0, "text": "Apriamo il pacco Temu"},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            rows = influencer_utterances_from_whisper(
                path,
                9,
                48,
                stream_start_iso="2026-05-20T19:05:02+00:00",
            )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["speaker_role"], "influencer")
        self.assertEqual(rows[0]["source"], "video_transcript")

    def test_merge_and_csv(self) -> None:
        messages = load_messages("data/2776778244/2776778244_chat.csv")
        viewer = viewer_utterances_from_chat(messages, 9, 10)[:3]
        influencer = [
            {
                "id": "influencer-00001",
                "speaker_role": "influencer",
                "source": "video_transcript",
                "stream_minute": 9.5,
                "promo_minute": 0.5,
                "timestamp": None,
                "user": "therealmarzaa",
                "original": "test",
                "english": None,
                "translate_to": "en",
                "language": "it",
            }
        ]
        corpus = merge_response_corpus(viewer, influencer, vod_id="2776778244", promo_start_minute=9, promo_end_minute=48)
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "out.csv"
            write_responses_csv(corpus["utterances"], csv_path)
            self.assertIn("speaker_role", csv_path.read_text(encoding="utf-8"))


class InfluencerTranscriptCsvTests(unittest.TestCase):
    def test_export_transcript_json_to_csv(self) -> None:
        from twitch_promo_analyzer.influencer_transcript import export_transcript_json_to_csv

        json_path = Path("data/2776778244/2776778244_influencer_transcript.json")
        if not json_path.exists():
            self.skipTest("transcript json not present")
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = export_transcript_json_to_csv(json_path, Path(tmp) / "out.csv")
            content = csv_path.read_text(encoding="utf-8")
            self.assertIn("stream_minute", content)
            self.assertIn("text", content)


if __name__ == "__main__":
    unittest.main()
