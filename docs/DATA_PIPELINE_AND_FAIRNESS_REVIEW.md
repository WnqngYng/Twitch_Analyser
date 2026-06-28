# Data Pipeline And Fairness Review

This project measures Twitch promotion performance from chat, optional video
transcripts, and product-level transcript annotations.

## Data Collection

Primary inputs:

- TwitchDownloader chat JSON: `data/<vod>/<vod>_chat.json`
- Normalized chat CSV: `data/<vod>/<vod>_chat.csv`
- Promo audio/video segment for Whisper transcription
- Influencer transcript JSON/CSV: `data/<vod>/<vod>_influencer_transcript.*`
- Optional reviewed product catalog or transcript product annotations
- Optional TwitchTracker/SullyGnome stream stats

The public repo should keep code, examples, docs, tests, and lightweight sample
files. Downloaded VODs, chat exports, transcripts, reports, OAuth tokens, API
keys, and private notes are excluded by `.gitignore`.

## Processing Flow

1. `download-vod` downloads Twitch chat/video through TwitchDownloader.
2. `loaders.py` normalizes chat into `ChatMessage`.
3. `timing.py` aligns all chat to VOD stream minutes.
4. `window_analysis.py` compares baseline, promotion, and post-promotion windows.
5. `peaks.py` finds chat spikes and promo-code activity.
6. `transcribe.py`/`utterances.py` convert Whisper output and chat into a shared timeline.
7. `products.py` connects product transcript segments to viewer response windows.
8. `report_export.py` and `text_report.py` write JSON/CSV/text outputs.

## Inconsistencies Found

1. Some old CSV exports lost `stream_offset_seconds` even though the raw JSON had
   `content_offset_seconds`. This made trimmed chat appear to start at minute `0`.
2. Whisper JSON files can contain either full-stream timestamps or trimmed-audio
   timestamps. The older logic could shift cached transcripts twice.
3. `--baseline-minutes` was stored in settings but fixed-window analysis used
   minute `0` to promo start as baseline.
4. Product "first 3 minutes" was clipped by segment end, so products with short
   transcript segments were not compared on the same response window.
5. Product segment labels can be noisy when generated from broad keyword rules.
   Product-level claims need human-reviewed catalogs or transcript annotations.

## Fixes Added

- `align_messages_to_window()` repairs clearly trimmed no-offset chat in memory
  and records warnings in `data_quality`.
- `scripts/validate_data_pipeline.py` audits each VOD and can repair CSVs from
  TwitchDownloader JSON with `--repair-csv`.
- Whisper timestamp offset is auto-detected from the JSON segment range.
- Baseline windows now use the requested minutes immediately before the promo.
- Product response uses a fixed first-3-minute response window after intro.
- Findings reports now include confidence notes and timing warnings.
- `examples/livestreams.json` stores the livestream list and known promo windows.

## Fairness Conclusion

The project is fair for measuring **chat response** when validation passes:

- message volume
- unique chatters
- messages per minute
- CTA/promo-code mentions
- product-window headcount
- post-promo brand/code mentions

The project is not enough by itself to prove total influencer ROI. These are
heuristic and should be treated as signals:

- sentiment
- intent labels
- product response score
- final grade
- recommendations

For public or business-facing conclusions, combine this analysis with coupon
redemptions, affiliate clicks, orders, TwitchTracker context, and manual review
of product labels and representative chat comments.
