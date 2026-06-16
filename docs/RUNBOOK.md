# End-to-end runbook: analyze any Twitch promotion VOD

This guide runs the full pipeline from a blank setup to product headcount, viewer sentiment, and participation-issue reports.

## 0. One-time setup

```bash
cd /path/to/Twich

# TwitchDownloader CLI (macOS)
bash scripts/setup_twitch_downloader_macos.sh
tools/twitchdownloader/TwitchDownloaderCLI ffmpeg -d   # bundles ffmpeg

# Python extras (transcription + translation + optional analysis)
pip3 install openai-whisper deep-translator

# Optional: product catalog extraction
export GEMINI_API_KEY=your_key_here
```

## 1. Collect inputs for the new VOD

You need:

| Input | How to get it |
|-------|----------------|
| **VOD URL or id** | e.g. `https://www.twitch.tv/videos/1234567890` |
| **Promo start / end (minutes)** | When the sponsorship banner / product segment starts and ends |
| **Promo code** | e.g. `KAV3769` |
| **Brand / CTA keywords** | e.g. `temu`, `!temu` |
| **Influencer login** | e.g. `therealmarzaa` |

Optional: TwitchTracker avg/peak viewers → `examples/stream_stats_<vod_id>.json`.

## 2. Run the full pipeline (recommended)

```bash
python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/2776778244" \
  --promo-start 9 \
  --promo-end 48 \
  --promo-code KAV3769 \
  --influencer therealmarzaa \
  --brand temu \
  --cta '!temu' \
  --extract-products
```

**Chat-only** (no video / no Whisper):

```bash
python scripts/run_vod_analysis.py \
  --vod-id 1234567890 \
  --promo-start 10 --promo-end 55 \
  --skip-video --skip-transcribe
```

### What each step does

| Step | Action | Output |
|------|--------|--------|
| 1 | Download chat (+ promo audio segment) | `data/<vod_id>/` |
| 2 | Promotion window analysis | `reports/<vod_id>_promotion_*.json/html` |
| 3 | Whisper transcription | `data/<vod_id>/<vod_id>_influencer_transcript.json/.csv` |
| 4 | English translation + VOD-specific product catalog | `english`, `product_id`, `data/<vod_id>/<vod_id>_product_catalog.json` |
| 5 | Viewer response export | `data/<vod_id>/<vod_id>_viewer_responses.csv` |
| 6 | Product + post-promo reports | `reports/<vod_id>_product_*.csv` |
| 7 | **Plain-text findings report** | `reports/<vod_id>_findings_report.txt` |

## 3. Run steps manually (if you prefer control)

```bash
VOD="https://www.twitch.tv/videos/2776778244"
ID=2776778244
START=9
END=48

# A) Download chat
python -m twitch_promo_analyzer download-vod "$VOD" --skip-video

# B) Download promo audio only (for Whisper)
python -m twitch_promo_analyzer download-vod "$VOD" \
  --quality Audio --beginning 00:09:00 --ending 00:48:00 --skip-chat

# C) Promotion chat analysis
python scripts/analyze_promotion.py \
  --vod-id $ID --promo-start $START --promo-end $END --promo-code KAV3769

# D) Transcribe + export influencer transcript
python scripts/export_influencer_transcript.py --run-whisper

# E) Extract VOD-specific products with Gemini
python products_name/extract_catalog.py data/$ID/${ID}_influencer_transcript.csv \
  --out data/$ID/${ID}_product_catalog.json

# F) Translate, product tags, headcount, sentiment, participation issues
pip install deep-translator
python scripts/enrich_transcript_analysis.py --vod-id $ID \
  --promo-start $START --promo-end $END
```

## 4. Generate plain-text findings report

After analysis JSON/CSV files exist:

```bash
python scripts/generate_findings_report.py --vod-id 2776778244
```

Output: `reports/2776778244_findings_report.txt` — all results in one readable file.

## 5. Key outputs for your three questions

### Headcount per product presenting period

`reports/<vod_id>_product_headcount.csv`

| Column | Meaning |
|--------|---------|
| `unique_chatters` | Distinct viewers who chatted during that product segment |
| `unique_chatters_first_3min` | Headcount in first 3 minutes after product intro |
| `presenting_period_minutes` | Length of segment (until next product) |
| `stream_minute_start/end` | VOD timeline |

### Product sentiment from viewers

`reports/<vod_id>_product_sentiment.csv`

| Column | Meaning |
|--------|---------|
| `avg_sentiment` | Mean heuristic sentiment (−1 to +1) for segment |
| `positive` / `neutral` / `negative` | Message counts |
| `positive_pct` | Share of positive messages |

### Event / campaign participation issues

`reports/<vod_id>_participation_issues.csv`

Issue types:

| `issue_type` | Examples |
|--------------|----------|
| `how_to_participate` | "come funziona", "how does it work" |
| `code_or_link_request` | `!temu`, "codice", "link" |
| `app_or_signup_issue` | app download, "non funziona" |
| `offer_clarity` | coupon / discount confusion |
| `trust_or_objection` | scam, sellout, #ad |

Full JSON with sample viewer quotes: `reports/<vod_id>_product_analysis.json`.

### After the banner ends

`reports/<vod_id>_post_promo_analysis.json` — Temu/code mentions during vs after promo.

## 6. Reuse on another brand / language

1. Run with `--extract-products` or create `data/<vod_id>/<vod_id>_product_catalog.json` with `products_name/extract_catalog.py`.
2. Review the JSON catalog if product names or keywords look wrong.
3. Edit `PARTICIPATION_ISSUE_PATTERNS` in `twitch_promo_analyzer/participation.py` for other languages.
4. Change `--promo-code`, `--brand`, `--cta` on the CLI.
5. Only edit the built-in `PRODUCT_CATALOG` in `twitch_promo_analyzer/products.py` when you want a shared fallback catalog, not for every VOD.

## 7. Verify

```bash
python -m unittest discover -s tests
```

## Reference: 2776778244 (TheRealMarzaa / Temu)

```bash
python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/2776778244" \
  --promo-start 9 --promo-end 48 \
  --promo-code KAV3769 \
  --skip-download \
  --skip-transcribe \
  --extract-products       # if data and transcript already exist
```
