# Twitch Promotion Campaign Analyzer

Analyze Twitch chat around influencer promotions, measure viewer response, and generate practical suggestions for improving a campaign.

The project works in two modes:

- **Offline analysis** from CSV, JSON, or NDJSON chat exports.
- **Live capture** from Twitch IRC, then analysis of the captured chat.

It uses only the Python standard library, so it can run immediately without installing third-party packages.

## Promotion Window Analysis (VOD + minutes)

For a known promotion segment (e.g. minutes 9–48 on VOD `2776778244`):

```bash
python scripts/analyze_promotion.py
# or
python -m twitch_promo_analyzer analyze-promotion --vod-id 2776778244 --promo-start 9 --promo-end 48
```

Outputs:

- `reports/<vod_id>_promotion_analysis.json` — chat word metrics, lifts, performance grade
- `reports/<vod_id>_promotion_report.html` — summary report

Reuse on another VOD by changing `--vod-id`, `--promo-start`, `--promo-end`, and optional `--brand` / `--cta` keywords.

Optional TwitchTracker context: copy stream avg/peak viewers into `examples/stream_stats_2776778244.json`.

The report also includes:

- **Chat peaks** per promo minute (where reactions spike)
- **Promo code `KAV3769`** tracking (organic vs bot copy-paste)
- **Influencer script alignment** via `examples/2776778244_influencer_script.json` (fill from VOD or Whisper transcript)
- **Translation recommendation** for English stakeholder reports (Italian chat → translate peaks/objections only)

Video + transcript workflow:

```bash
# 1) Download promo segment MP4, then extract audio
python -m twitch_promo_analyzer download-vod "https://www.twitch.tv/videos/2776778244" \
  --quality 360p30 --beginning 00:09:00 --ending 00:48:00

# 2) Optional: whisper data/2776778244/promo.wav --language Italian -ojson > data/2776778244/transcript.json
# 3) Fill script segments in examples/2776778244_influencer_script.json and re-run analysis
```

### Unified response format (chat + transcript)

Viewer chat and influencer speech use the **same row shape** (JSON + CSV), so you can translate or review them together:

```bash
# Export chat now; transcribe when ffmpeg + whisper are installed
python scripts/transcribe_promotion.py --skip-transcribe

# Full pipeline (download segment, whisper, merge)
pip install openai-whisper   # once
brew install ffmpeg          # once
python scripts/transcribe_promotion.py

# Or import an existing Whisper/SRT file
python scripts/transcribe_promotion.py --import-whisper path/to/promo.json
```

Files in `data/2776778244/`:

| File | Contents |
|------|----------|
| `2776778244_viewer_responses.json` | All promo-window chat lines |
| `2776778244_influencer_transcript.json` / `.csv` | Influencer speech, timestamps, **english**, **product_id** |
| `reports/2776778244_product_analysis.json` | Which Temu products drove the strongest chat |
| `reports/2776778244_post_promo_analysis.json` | Temu interest after the banner ends (min 48+) |

```bash
pip install deep-translator
python scripts/enrich_transcript_analysis.py
```

| `2776778244_responses.json` | Merged timeline sorted by `stream_minute` |
| `reports/2776778244_product_headcount.csv` | Unique chatters per product presenting period |
| `reports/2776778244_product_sentiment.csv` | Viewer sentiment per product |
| `reports/2776778244_participation_issues.csv` | Campaign participation friction by product |

**Full runbook for any VOD:** see [docs/RUNBOOK.md](docs/RUNBOOK.md)

**Detailed English/Chinese project guide and GitHub publishing checklist:** see [docs/PROJECT_GUIDE_EN_ZH.md](docs/PROJECT_GUIDE_EN_ZH.md)

```bash
python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/2776778244" \
  --promo-start 9 --promo-end 48 --promo-code KAV3769
```

Each utterance includes: `speaker_role`, `stream_minute`, `promo_minute`, `user`, `original`, `english`, `translate_to`. See `examples/sample_response_utterance.json`.

## Quick Start

```bash
python -m twitch_promo_analyzer analyze \
  --input examples/sample_chat.csv \
  --influencer StreamerOne \
  --brand BrandPulse \
  --out reports/sample_analysis.json \
  --report reports/sample_report.html
```

Open `reports/sample_report.html` in a browser to view the campaign report.

You can also run the test suite:

```bash
python -m unittest discover -s tests
```

## Third-Party Tools And Data

This project can call TwitchDownloader, FFmpeg, OpenAI Whisper, deep-translator, and Gemini. These tools are installed locally by the user and are not redistributed in this repository. Downloaded Twitch VODs, chats, transcripts, private notes, reports, API keys, and OAuth tokens should stay out of Git unless you have the right to share them.

## Download A Twitch VOD On Mac

TwitchDownloader has a cross-platform CLI. On Mac, use the CLI binary rather than the Windows GUI.

Install the latest macOS CLI release into this project:

```bash
bash scripts/setup_twitch_downloader_macos.sh
```

Download chat JSON, normalized chat CSV, and video MP4 for a VOD:

```bash
python -m twitch_promo_analyzer download-vod \
  "https://www.twitch.tv/videos/2776778244?sr=a" \
  --quality 360p30
```

This creates:

```text
data/2776778244/
  2776778244_chat.json
  2776778244_chat.csv
  2776778244_video.mp4
```

If you only need chat first:

```bash
python -m twitch_promo_analyzer download-vod \
  "https://www.twitch.tv/videos/2776778244?sr=a" \
  --skip-video
```

For this specific VOD, TwitchDownloader reports a 6:30:12 length. Approximate full-video sizes are:

```text
1080p60     ~23.19 GiB
720p60      ~9.50 GiB
480p30      ~4.18 GiB
360p30      ~2.02 GiB
160p30      ~811.7 MiB
Audio Only  ~790.4 MiB
```

To download only a segment:

```bash
python -m twitch_promo_analyzer download-vod \
  "https://www.twitch.tv/videos/2776778244?sr=a" \
  --quality 360p30 \
  --beginning 01:27:25 \
  --ending 04:02:56
```

If macOS blocks the binary, run:

```bash
xattr -d com.apple.quarantine tools/twitchdownloader/TwitchDownloaderCLI
chmod +x tools/twitchdownloader/TwitchDownloaderCLI
```

## Input Format

CSV files should include at least:

```csv
timestamp,user,message,viewer_count
2026-05-31T18:05:00Z,StreamerOne,"Use code TWITCH20 for 20% off BrandPulse!",1240
```

For TwitchDownloader exports or any trimmed chat export, include
`stream_offset_seconds` when available. Product-level headcounts use this
field to align chat with transcript/video stream minutes.

Supported timestamp formats:

- ISO timestamps, including `Z` suffix.
- Unix seconds or milliseconds.
- Stream-relative values like `00:05:12`.

JSON files can be either:

- A list of message objects.
- An object with a `messages` list.
- NDJSON, one message object per line.

The loader recognizes common field aliases such as `author`, `username`, `text`, `body`, `created_at`, and `viewerCount`.

## Live Twitch Capture

Twitch chat capture uses Twitch IRC. You need:

- Twitch channel name.
- Twitch nickname.
- OAuth token, usually shaped like `oauth:...`.

Capture 10 minutes of chat:

```bash
python -m twitch_promo_analyzer capture \
  --channel your_channel \
  --nickname your_twitch_name \
  --oauth oauth:your_token \
  --duration-minutes 10 \
  --output data/live_chat.csv
```

Then analyze the captured file:

```bash
python -m twitch_promo_analyzer analyze \
  --input data/live_chat.csv \
  --influencer your_channel \
  --brand YourBrand \
  --report reports/live_report.html
```

## What The Analyzer Measures

For each promotional moment, the analyzer compares the response window after the promotion with a baseline window before it.

Metrics include:

- Message volume and engagement lift.
- Unique chatters.
- Sentiment distribution.
- Viewer count change, when the data includes viewer counts.
- Purchase intent, link/code requests, confusion, objections, excitement, and spam signals.
- Sample viewer comments.
- Per-event and campaign-level recommendations.

## Recommendations

Suggestions are generated from the measured response, not from a fixed checklist. For example:

- High confusion leads to clearer CTA and chat command recommendations.
- Negative sentiment or viewer drop leads to disclosure, demo, pacing, and objection-handling recommendations.
- High purchase intent leads to follow-up, retargeting, and offer-extension recommendations.
- Weak engagement lift leads to timing and creative recommendations.

## Project Layout

```text
twitch_promo_analyzer/
  analysis.py         Core campaign analysis
  cli.py              Command line interface
  live.py             Twitch IRC capture
  loaders.py          CSV/JSON/NDJSON loading
  models.py           Shared data structures
  promotions.py       Promotion detection
  recommendations.py  Campaign suggestions
  report.py           HTML and JSON report output
  sentiment.py        Lightweight sentiment and intent heuristics
examples/
  sample_chat.csv
tests/
  test_analysis.py
```

## Notes

This is a production-ready starter rather than a black-box ML system. The heuristic rules are intentionally transparent and easy to tune for a brand, influencer, language, or campaign type. A natural next step is to add platform metrics such as clicks, coupon redemptions, affiliate sales, or Twitch viewer-minute data and join them by timestamp.
