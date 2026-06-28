# Beginner Setup And Run Guide

This guide is written for someone with no coding experience. Follow it slowly, one step at a time. You do not need to understand every command before using it.

The project analyzes a Twitch livestream promotion. It can:

1. Download Twitch chat and optional audio from a VOD.
2. Transcribe what the influencer says during the promotion.
3. Extract product names from the transcript.
4. Compare influencer product moments with viewer chat response.
5. Create reports with suggestions for improving the promotion campaign.

This guide is Mac-first because the project was built and tested on a MacBook.

---

## 0. What You Need Before Starting

You need:

1. A Mac with internet access.
2. A Twitch VOD link, for example:

```text
https://www.twitch.tv/videos/2776778244
```

3. The promotion start and end time, in minutes.

For the current example:

```text
Promotion starts: 9 minutes
Promotion ends:   48 minutes
Promo code:       KAV3769
Influencer:       therealmarzaa
Brand:            temu
Chat command:     !temu
```

4. Optional but recommended: a Gemini API key for automatic product name extraction.

Get one here:

```text
https://aistudio.google.com/apikey
```

Do not share your API key publicly.

---

## 1. The Two Ways To Run This Project

There are two common ways to run the project.

### Option A: Easier Run

Use this if the project already has the downloaded Twitch chat and influencer transcript in the `data/` folder.

This is the fastest path.

You will run:

```bash
python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/2776778244" \
  --promo-start 9 \
  --promo-end 48 \
  --promo-code KAV3769 \
  --influencer therealmarzaa \
  --brand temu \
  --cta '!temu' \
  --skip-download \
  --skip-transcribe \
  --extract-products
```

### Option B: Full Run For A New Twitch VOD

Use this if you want the project to download chat and audio for a new livestream.

You will run something like:

```bash
python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/YOUR_VOD_ID" \
  --promo-start START_MINUTE \
  --promo-end END_MINUTE \
  --promo-code YOUR_CODE \
  --influencer TWITCH_USERNAME \
  --brand BRAND_NAME \
  --cta 'CHAT_COMMAND' \
  --extract-products
```

The full run takes longer because it downloads data and may transcribe audio.

---

## 2. Install Basic Mac Tools

You only need to do this once.

### 2.1 Open Terminal

1. Press `Command + Space`.
2. Type `Terminal`.
3. Press `Enter`.

You will see a window where you can paste commands.

### 2.2 Install Apple Command Line Tools

Copy and paste this into Terminal:

```bash
xcode-select --install
```

If a popup appears, click `Install`.

If Terminal says the tools are already installed, that is fine.

### 2.3 Install Homebrew

Homebrew helps install Python, Git, and FFmpeg.

Go to:

```text
https://brew.sh/
```

Copy the install command shown on that page and paste it into Terminal.

After Homebrew finishes, close Terminal and open it again.

### 2.4 Install Python, Git, and FFmpeg

Paste this into Terminal:

```bash
brew install python git ffmpeg
```

This may take several minutes.

Check that Python works:

```bash
python3 --version
```

You should see something like:

```text
Python 3.10.x
```

Any Python version `3.10` or newer is fine.

---

## 3. Get The Project Onto Your Computer

Use one of these methods.

### Method 1: Download ZIP From GitHub

This is easiest for non-technical users.

1. Open the GitHub project page.
2. Click the green `Code` button.
3. Click `Download ZIP`.
4. Open the downloaded ZIP file.
5. Move the folder somewhere simple, for example:

```text
Desktop/twitch-promo-analyzer
```

### Method 2: Clone With Git

Use this if you are comfortable pasting one command.

```bash
cd ~/Desktop
git clone https://github.com/YOUR_USER/YOUR_REPO.git twitch-promo-analyzer
```

Replace `YOUR_USER/YOUR_REPO` with the real GitHub repository address.

---

## 4. Open The Project Folder In Terminal

If the project is on your Desktop and named `twitch-promo-analyzer`, run:

```bash
cd ~/Desktop/twitch-promo-analyzer
```

If you are not sure where the folder is:

1. Type `cd ` in Terminal, including the space after `cd`.
2. Drag the project folder from Finder into the Terminal window.
3. Press `Enter`.

Check you are in the right folder:

```bash
ls
```

You should see files and folders like:

```text
README.md
scripts
twitch_promo_analyzer
docs
examples
```

---

## 5. Create A Safe Python Environment

This keeps the project packages separate from the rest of your computer.

Run:

```bash
python3 -m venv .venv
```

Turn it on:

```bash
source .venv/bin/activate
```

After this, your Terminal line may start with:

```text
(.venv)
```

That means the environment is active.

If you close Terminal and come back later, go to the project folder again and run:

```bash
source .venv/bin/activate
```

---

## 6. Install The Project Packages

With the Python environment active, run:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[full]"
```

This installs:

1. The Twitch promotion analyzer project.
2. Whisper, used for transcription.
3. deep-translator, used for translation.

If Whisper installation fails, you can still run the project with an existing transcript by using `--skip-transcribe`.

---

## 7. Install TwitchDownloader

TwitchDownloader is the tool that downloads Twitch chat and VOD/audio data.

Run this from the project folder:

```bash
bash scripts/setup_twitch_downloader_macos.sh
```

Check that it installed:

```bash
tools/twitchdownloader/TwitchDownloaderCLI --version
```

If macOS blocks the tool, run:

```bash
xattr -d com.apple.quarantine tools/twitchdownloader/TwitchDownloaderCLI
chmod +x tools/twitchdownloader/TwitchDownloaderCLI
```

Then try the version command again.

---

## 8. Add Your Gemini API Key

This step is only needed if you want automatic product-name extraction.

In Terminal, run:

```bash
export GEMINI_API_KEY="PASTE_YOUR_KEY_HERE"
```

Replace `PASTE_YOUR_KEY_HERE` with your real key.

Example:

```bash
export GEMINI_API_KEY="YOUR_REAL_GEMINI_KEY"
```

This only saves the key for the current Terminal window. If you close Terminal, you need to run it again.

Do not put your real API key in GitHub, screenshots, reports, or shared documents.

---

## 9. Run A Quick Test

Before analyzing a real VOD, check that the project works:

```bash
python -m unittest discover -s tests
```

Success looks like this:

```text
Ran 19 tests

OK
```

If you see `OK`, the project is ready.

---

## 10. Run The Existing Example Analysis

Use this when the project already has data for VOD `2776778244`.

Make sure you are in the project folder and the Python environment is active:

```bash
cd ~/Desktop/twitch-promo-analyzer
source .venv/bin/activate
```

Set your Gemini key if you want automatic product extraction:

```bash
export GEMINI_API_KEY="PASTE_YOUR_KEY_HERE"
```

Run:

```bash
python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/2776778244" \
  --promo-start 9 \
  --promo-end 48 \
  --promo-code KAV3769 \
  --influencer therealmarzaa \
  --brand temu \
  --cta '!temu' \
  --skip-download \
  --skip-transcribe \
  --extract-products
```

This means:

| Part | Meaning |
|---|---|
| `--vod-url` | Which Twitch video to analyze |
| `--promo-start 9` | Promotion starts at minute 9 |
| `--promo-end 48` | Promotion ends at minute 48 |
| `--promo-code KAV3769` | Track this promo code |
| `--influencer therealmarzaa` | Streamer username |
| `--brand temu` | Track brand mentions |
| `--cta '!temu'` | Track chat command |
| `--skip-download` | Use data already downloaded |
| `--skip-transcribe` | Use transcript already created |
| `--extract-products` | Use Gemini to create product catalog |

When it finishes, look in:

```text
reports/
```

The most useful file is:

```text
reports/2776778244_findings_report.txt
```

---

## 11. Run A New Twitch VOD From Scratch

Use this when you want to analyze a different Twitch video.

### 11.1 Collect Information

Write down:

```text
VOD URL:
Promotion start minute:
Promotion end minute:
Promo code:
Influencer Twitch username:
Brand name:
Chat command:
```

Example:

```text
VOD URL: https://www.twitch.tv/videos/2776778244
Promotion start minute: 9
Promotion end minute: 48
Promo code: KAV3769
Influencer Twitch username: therealmarzaa
Brand name: temu
Chat command: !temu
```

### 11.2 Run The Full Command

Replace the example values with your new values:

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

The project will:

1. Download chat.
2. Download the promotion audio segment.
3. Transcribe the influencer speech with Whisper.
4. Translate transcript lines.
5. Ask Gemini to extract product names.
6. Analyze viewer response by product.
7. Create final reports.

### 11.3 If You Only Want Chat First

If you do not want to download video/audio yet, run:

```bash
python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/2776778244" \
  --promo-start 9 \
  --promo-end 48 \
  --promo-code KAV3769 \
  --influencer therealmarzaa \
  --brand temu \
  --cta '!temu' \
  --skip-video \
  --skip-transcribe
```

This will not create the full product analysis because it needs the influencer transcript, but it is useful for checking chat response.

---

## 12. Where To Find Results

After a successful run, open the project folder in Finder.

Generated data is in:

```text
data/<vod_id>/
```

Reports are in:

```text
reports/
```

Important report files:

| File | What It Shows |
|---|---|
| `<vod_id>_findings_report.txt` | Best overall report to read first |
| `<vod_id>_promotion_report.html` | Browser-friendly campaign summary |
| `<vod_id>_product_headcount.csv` | Unique viewers chatting during each product |
| `<vod_id>_product_sentiment.csv` | Positive, neutral, negative response by product |
| `<vod_id>_participation_issues.csv` | Confusion, link requests, app issues, trust objections |
| `<vod_id>_product_analysis.json` | Full machine-readable product analysis |
| `<vod_id>_post_promo_analysis.json` | Whether viewers kept talking about the brand after the promo |

To open the main text report from Terminal:

```bash
open reports/2776778244_findings_report.txt
```

To open the HTML report:

```bash
open reports/2776778244_promotion_report.html
```

Replace `2776778244` with your VOD id.

---

## 13. How To Run It Again Later

Every time you open a new Terminal window, do this first:

```bash
cd ~/Desktop/twitch-promo-analyzer
source .venv/bin/activate
export GEMINI_API_KEY="PASTE_YOUR_KEY_HERE"
```

Then run the analysis command.

If data and transcript already exist:

```bash
python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/2776778244" \
  --promo-start 9 \
  --promo-end 48 \
  --promo-code KAV3769 \
  --influencer therealmarzaa \
  --brand temu \
  --cta '!temu' \
  --skip-download \
  --skip-transcribe \
  --extract-products
```

If you already have a product catalog and do not want to call Gemini again:

```bash
python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/2776778244" \
  --promo-start 9 \
  --promo-end 48 \
  --promo-code KAV3769 \
  --influencer therealmarzaa \
  --brand temu \
  --cta '!temu' \
  --skip-download \
  --skip-transcribe \
  --product-catalog data/2776778244/2776778244_product_catalog.json
```

---

## 14. Common Problems And Fixes

### Problem: `python: command not found`

Use `python3` instead:

```bash
python3 --version
```

If `python3` also fails, install Python:

```bash
brew install python
```

### Problem: `No such file or directory`

You are probably not inside the project folder.

Run:

```bash
pwd
ls
```

If you do not see `README.md`, `scripts`, and `twitch_promo_analyzer`, go back to the project:

```bash
cd ~/Desktop/twitch-promo-analyzer
```

### Problem: `TwitchDownloaderCLI was not found`

Run:

```bash
bash scripts/setup_twitch_downloader_macos.sh
```

Then try the analysis again.

### Problem: macOS says the app cannot be opened

Run:

```bash
xattr -d com.apple.quarantine tools/twitchdownloader/TwitchDownloaderCLI
chmod +x tools/twitchdownloader/TwitchDownloaderCLI
```

### Problem: Whisper is not available

Install the full dependencies again:

```bash
python -m pip install -e ".[full]"
```

If it still fails, run with:

```text
--skip-transcribe
```

This works only if the transcript already exists.

### Problem: Gemini product extraction fails

Check that your API key is set:

```bash
echo $GEMINI_API_KEY
```

If nothing appears, set it again:

```bash
export GEMINI_API_KEY="PASTE_YOUR_KEY_HERE"
```

If it still fails, run without `--extract-products` or use an existing product catalog:

```text
--product-catalog data/<vod_id>/<vod_id>_product_catalog.json
```

### Problem: A product has zero headcount

This can be normal if:

1. The product segment is very short.
2. Nobody chatted during that exact product window.
3. The product catalog keyword does not match what the streamer actually said.

If many products show zero headcount even when chat was active, check that the chat file has `stream_offset_seconds`. This project uses that field to align chat with the original VOD timeline.

### Problem: The command is stuck for a long time

This can be normal during:

1. Twitch chat download.
2. Audio download.
3. Whisper transcription.
4. Gemini product extraction.

Wait a few minutes before stopping it.

---

## 15. Privacy And Sharing Rules

Be careful before uploading anything to GitHub or sending files to others.

Safe to share:

```text
source code
documentation
small fake examples
test files
```

Do not share unless you have permission:

```text
downloaded Twitch VOD files
raw Twitch chat exports
full influencer transcripts
reports containing real viewer comments
private spreadsheets or notes
API keys
OAuth tokens
.env files
ffmpeg or ffprobe binaries copied into the project
```

The project already ignores many local-only folders:

```text
data/
reports/
tools/
sidenotes/
.env
ffmpeg
ffprobe
version.json
```

Before uploading to GitHub, check:

```bash
git status --short
git ls-files ffmpeg ffprobe version.json data reports tools sidenotes
```

If `ffmpeg`, `ffprobe`, or `version.json` appear, remove them from Git tracking:

```bash
git rm --cached ffmpeg ffprobe version.json
```

This keeps the files on your computer but removes them from the GitHub upload.

---

## 16. Simple Checklist

Use this checklist when helping a new person run the project.

```text
[ ] Install Apple Command Line Tools
[ ] Install Homebrew
[ ] Install Python, Git, and FFmpeg
[ ] Download or clone the project
[ ] Open Terminal in the project folder
[ ] Create Python environment with python3 -m venv .venv
[ ] Activate it with source .venv/bin/activate
[ ] Install packages with python -m pip install -e ".[full]"
[ ] Install TwitchDownloader with bash scripts/setup_twitch_downloader_macos.sh
[ ] Set GEMINI_API_KEY if product extraction is needed
[ ] Run python -m unittest discover -s tests
[ ] Run scripts/run_vod_analysis.py with the right VOD and promo minutes
[ ] Open reports/<vod_id>_findings_report.txt
```

---

## 17. The Most Important Command To Remember

For the current VOD, when data and transcript already exist:

```bash
python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/2776778244" \
  --promo-start 9 \
  --promo-end 48 \
  --promo-code KAV3769 \
  --influencer therealmarzaa \
  --brand temu \
  --cta '!temu' \
  --skip-download \
  --skip-transcribe \
  --extract-products
```

Read this report first:

```text
reports/2776778244_findings_report.txt
```
