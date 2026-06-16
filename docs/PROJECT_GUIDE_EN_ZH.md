# Twitch Promotion Campaign Analyzer - Project Guide

This document explains how the project works, how to run the next analysis cleanly, and how to publish the repository to GitHub while respecting Twitch content, user privacy, and third-party tools.

本文档说明本项目的工作原理、下次如何更顺畅地运行分析流程，以及如何把项目上传到 GitHub，同时尊重 Twitch 内容、用户隐私和第三方工具的许可证与使用条款。

---

## 1. English Guide

### 1.1 What This Project Does

The project analyzes a Twitch livestream promotion campaign from three angles:

1. Influencer speech: what the streamer says during the promotion window, which products are shown, and when each product is introduced.
2. Viewer response: what chat says during and after the promotion, including excitement, confusion, objections, code/link requests, and purchase intent.
3. Campaign performance: which products created stronger participation, which parts had low engagement, and what should be improved for the next campaign.

For the reference VOD `2776778244`, the promotion window is minutes `9` to `48`, the promo code is `KAV3769`, the influencer is `therealmarzaa`, and the brand is `temu`.

### 1.2 Main Project Folders

```text
twitch_promo_analyzer/
  analysis.py              Core campaign-level metrics
  loaders.py               Chat CSV/JSON loading and timestamp normalization
  timing.py                Stream-minute and promo-minute alignment
  products.py              Product catalog loading, tagging, and product analysis
  participation.py         Viewer participation issue detection
  sentiment.py             Lightweight sentiment scoring
  transcribe.py            Whisper-based influencer transcription
  line_translate.py        Transcript translation helpers
  post_promo.py            Post-promotion interest analysis
  report_export.py         CSV/JSON report writers
  text_report.py           Plain-text findings report

scripts/
  run_vod_analysis.py          Recommended end-to-end pipeline
  analyze_promotion.py         Promotion-window chat analysis
  generate_findings_report.py  Regenerate the final text report
  transcribe_promotion.py      Transcript-specific workflow
  enrich_transcript_analysis.py Rebuild product analysis from transcript/chat

products_name/
  extract_catalog.py       Gemini-based per-VOD product catalog extractor

examples/
  Sample chat, response, stream stats, and influencer script files

docs/
  RUNBOOK.md               Short operational runbook
  PROJECT_GUIDE_EN_ZH.md   This detailed bilingual guide

data/
  Local downloaded Twitch data and generated intermediate files
  Ignored by Git because it may contain VOD/chat/transcript data

reports/
  Generated analysis outputs
  Ignored by Git because reports may contain copied viewer comments

tools/
  Local TwitchDownloader binaries
  Ignored by Git because third-party binaries should not be redistributed here
```

### 1.3 Data Flow

The pipeline is built around one VOD id.

```text
Twitch VOD URL
  -> TwitchDownloader CLI downloads chat JSON and optional audio/video segment
  -> loaders.py normalizes chat into ChatMessage objects
  -> timing.py aligns chat to the original stream minute
  -> analyze_promotion.py measures promotion-window chat response
  -> transcribe.py uses Whisper to produce influencer speech transcript
  -> line_translate.py translates transcript lines to English when requested
  -> extract_catalog.py uses Gemini to identify products from transcript
  -> products.py tags transcript lines and builds product-level analysis
  -> participation.py detects viewer friction and campaign participation issues
  -> post_promo.py checks whether interest continues after the promo window
  -> text_report.py writes a readable findings report
```

### 1.4 Why Timing Matters

TwitchDownloader chat exports can use offsets that are relative to the downloaded segment instead of the original livestream. That can break product-level headcount analysis, because the product segment may be at stream minute `30`, while the trimmed chat appears to start at minute `0`.

The project now uses `stream_offset_seconds` when it exists. That means product headcounts are aligned to the original stream timeline, not only the trimmed file timeline. This is the reason some previous false zero-headcount cases were fixed: chat was present, but the old alignment put it outside the product presentation window.

Important fields:

| Field | Meaning |
|---|---|
| `content_offset_seconds` | Offset from TwitchDownloader, often relative to the exported content |
| `stream_offset_seconds` | Offset from the original livestream start, used for reliable stream-minute matching |
| `stream_minute` | Minute in the original VOD timeline |
| `promo_minute` | Minute relative to promotion start |

### 1.5 Main Inputs

For each new VOD, collect:

| Input | Example | Used For |
|---|---:|---|
| VOD URL or id | `https://www.twitch.tv/videos/2776778244` | Download and file naming |
| Promo start minute | `9` | Promotion-window metrics |
| Promo end minute | `48` | Promotion-window metrics |
| Promo code | `KAV3769` | Code mention tracking |
| Influencer login | `therealmarzaa` | Filtering influencer messages from viewer chat |
| Brand keyword | `temu` | Brand mention tracking |
| CTA command | `!temu` | Link/code request tracking |
| Gemini API key | `GEMINI_API_KEY` | Optional automatic product catalog extraction |

### 1.6 Recommended Command For The Next Run

If the chat and transcript already exist locally and you want the optimized workflow with automatic product extraction:

```bash
export GEMINI_API_KEY="your_key_here"

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

This command now does the work that previously required three separate steps:

1. Loads existing chat and transcript data.
2. Extracts a VOD-specific product catalog with Gemini.
3. Builds product headcount, sentiment, participation issues, post-promo analysis, and final findings report.

You normally do not need to run `scripts/generate_findings_report.py` after this command, because `run_vod_analysis.py` already writes the final findings report.

### 1.7 If You Already Have A Product Catalog

If `data/<vod_id>/<vod_id>_product_catalog.json` already exists, you can avoid another Gemini API call:

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

### 1.8 For A Completely New VOD

Use this when the project needs to download chat and the audio segment:

```bash
export GEMINI_API_KEY="your_key_here"

python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/<vod_id>" \
  --promo-start <start_minute> \
  --promo-end <end_minute> \
  --promo-code <promo_code> \
  --influencer <twitch_login> \
  --brand <brand_keyword> \
  --cta '<chat_command>' \
  --extract-products
```

If Whisper or FFmpeg is not installed yet, run with `--skip-transcribe` after creating or importing the transcript. If you only need chat first, add `--skip-video`.

### 1.9 Product Catalog Extraction

Previously, the workflow was:

1. Run `products_name/extract_catalog.py`.
2. Copy the output manually.
3. Paste it into `twitch_promo_analyzer/products.py`.
4. Re-run the analysis.

The optimized workflow writes a JSON catalog instead:

```bash
python3 products_name/extract_catalog.py \
  data/2776778244/2776778244_influencer_transcript.csv \
  --out data/2776778244/2776778244_product_catalog.json
```

The JSON file can be loaded directly by the main pipeline. You should not edit `products.py` every time you analyze a new livestream.

Expected catalog shape:

```json
{
  "schema_version": "1",
  "source": "gemini",
  "products": [
    {
      "product_id": "led_light_panel",
      "product_name": "LED light panel",
      "keywords": ["led", "pannello"],
      "approx_start_minute": 20.7
    }
  ]
}
```

### 1.10 Main Outputs

| Output | Meaning |
|---|---|
| `data/<vod_id>/<vod_id>_chat.json` | Original TwitchDownloader chat export |
| `data/<vod_id>/<vod_id>_chat.csv` | Normalized chat export |
| `data/<vod_id>/<vod_id>_influencer_transcript.json` | Influencer transcript with timestamps, English translation, and product tags |
| `data/<vod_id>/<vod_id>_influencer_transcript.csv` | Spreadsheet-friendly transcript |
| `data/<vod_id>/<vod_id>_product_catalog.json` | VOD-specific product names and keywords |
| `data/<vod_id>/<vod_id>_viewer_responses.json` | Viewer chat lines in the promotion window |
| `reports/<vod_id>_promotion_analysis.json` | Chat volume, code/CTA/brand mentions, campaign grade |
| `reports/<vod_id>_promotion_report.html` | Browser-friendly promotion report |
| `reports/<vod_id>_product_headcount.csv` | Unique chatters per product presentation period |
| `reports/<vod_id>_product_sentiment.csv` | Viewer sentiment by product |
| `reports/<vod_id>_participation_issues.csv` | Confusion, link/code requests, trust objections, signup/app issues |
| `reports/<vod_id>_post_promo_analysis.json` | Whether brand interest continued after the promo window |
| `reports/<vod_id>_findings_report.txt` | Final readable recommendations report |

### 1.11 How The Suggestions Are Generated

The final recommendations are based on measured signals, not only generic marketing advice.

Examples:

| Signal | Possible Recommendation |
|---|---|
| High `!temu` or code requests | Pin the CTA, repeat the command verbally, add a clearer overlay |
| High confusion words | Explain how to redeem the offer before showing more products |
| Low unique chatters during a product | Shorten that product demo or add a direct question/poll |
| Positive sentiment and high headcount | Use that product type earlier next time |
| Strong post-promo interest | Continue reminders after the main segment instead of ending abruptly |
| Trust objections | Make sponsorship disclosure and value proposition clearer |

### 1.12 Verification

Run the test suite before publishing or sharing results:

```bash
python -m unittest discover -s tests
```

You can also regenerate the final report only:

```bash
python scripts/generate_findings_report.py --vod-id 2776778244
```

Only use the report-only command after the intermediate JSON/CSV analysis files already exist.

### 1.13 GitHub Publishing Principles

The GitHub repository should share source code and small examples, not private analysis data or redistributed third-party binaries.

Commit these:

```text
twitch_promo_analyzer/
scripts/
products_name/
tests/
examples/
docs/
README.md
pyproject.toml
.gitignore
.env.example
```

Do not commit these:

```text
data/
reports/
tools/
sidenotes/
.env
ffmpeg
ffprobe
version.json
*.mp4
*.wav
*.m4a
downloaded Twitch chat with real viewer comments, unless you have permission
full transcripts, unless you have permission and have checked privacy concerns
API keys, OAuth tokens, cookies, or local credentials
```

The current repository has root-level `ffmpeg`, `ffprobe`, and `version.json` tracked by Git. Before pushing to GitHub, remove them from Git tracking:

```bash
git rm --cached ffmpeg ffprobe version.json
```

That command removes the files from the repository index but leaves the local files on your computer.

### 1.14 Respecting Third-Party Tools

This project uses or integrates with several external tools. The clean approach is to document them, install them locally, and avoid redistributing their binaries unless you intentionally comply with their licenses.

| Tool | Role | Respectful Use |
|---|---|---|
| TwitchDownloader | Downloads Twitch chat and optional VOD/audio segments | Link to the project, keep its license notice, install under `tools/` locally, do not claim it as your own |
| FFmpeg | Finalizes/extracts media and supports Whisper/audio workflows | Prefer system install or local user install; do not commit downloaded binaries into this repo |
| OpenAI Whisper | Speech recognition for influencer transcript | Install as a dependency, credit it, and do not imply perfect transcript accuracy |
| deep-translator | Optional transcript translation | Install as a dependency and credit the project |
| Gemini API | Extracts product names from transcript | Keep `GEMINI_API_KEY` private, review Google API terms, avoid sending private data without permission |
| Twitch content | Source livestream/chat data | Do not upload VODs, raw chat, private notes, or viewer-identifiable data without permission |

Useful upstream references:

- TwitchDownloader: https://github.com/lay295/TwitchDownloader
- FFmpeg legal page: https://ffmpeg.org/legal.html
- OpenAI Whisper: https://github.com/openai/whisper
- deep-translator: https://pypi.org/project/deep-translator/
- Gemini API keys: https://aistudio.google.com/apikey

### 1.15 Recommended GitHub Upload Steps

Start by checking what Git sees:

```bash
git status --short
git ls-files ffmpeg ffprobe version.json data reports tools sidenotes
```

Remove tracked third-party binaries from the repository index:

```bash
git rm --cached ffmpeg ffprobe version.json
```

Run tests:

```bash
python -m unittest discover -s tests
```

Stage source files and documentation:

```bash
git add .gitignore .env.example README.md pyproject.toml docs examples products_name scripts tests twitch_promo_analyzer
```

Review the staged files before committing:

```bash
git status --short
git diff --cached --stat
```

Commit:

```bash
git commit -m "Document Twitch promotion analysis pipeline"
```

Create a private GitHub repository first. Private is safer while you check licenses, secrets, and data:

```bash
gh repo create twitch-promo-analyzer --private --source . --remote origin --push
```

If you are not using GitHub CLI, create an empty repository on GitHub, then run:

```bash
git remote add origin git@github.com:<your-user>/<repo-name>.git
git branch -M main
git push -u origin main
```

Before making the repository public:

1. Confirm `data/`, `reports/`, `tools/`, and `sidenotes/` are not tracked.
2. Confirm `ffmpeg`, `ffprobe`, and `version.json` are no longer tracked.
3. Search for secrets:

```bash
rg -n "GEMINI_API_KEY|oauth:|api[_-]?key|token|secret|password" .
```

4. Add or review the project license.
5. Add third-party acknowledgements in `README.md` or a `THIRD_PARTY_NOTICES.md` file.
6. Use sample or synthetic data in `examples/`, not full raw Twitch exports.

### 1.16 Suggested README Note

You can add this short notice to the README:

```markdown
## Third-Party Tools And Data

This project can call TwitchDownloader, FFmpeg, OpenAI Whisper, deep-translator, and Gemini. These tools are installed locally by the user and are not redistributed in this repository. Downloaded Twitch VODs, chats, transcripts, private notes, reports, API keys, and OAuth tokens should stay out of Git unless you have the right to share them.
```

---

## 2. 中文指南

### 2.1 项目用途

这个项目用于分析 Twitch 直播中的推广活动，主要从三个角度判断推广效果：

1. 主播说了什么：推广期间主播讲了哪些卖点、展示了哪些产品、每个产品从什么时候开始介绍。
2. 观众如何反应：弹幕里是否出现兴奋、困惑、质疑、要链接、要优惠码、购买意向等信号。
3. 推广表现如何：哪些产品带来了更强互动，哪些部分参与度低，下一次推广应该如何改进。

以当前参考视频 `2776778244` 为例，推广时间段是第 `9` 分钟到第 `48` 分钟，优惠码是 `KAV3769`，主播是 `therealmarzaa`，品牌是 `temu`。

### 2.2 主要目录

```text
twitch_promo_analyzer/
  analysis.py              活动整体指标分析
  loaders.py               读取并标准化聊天 CSV/JSON
  timing.py                对齐直播原始时间和推广时间
  products.py              读取产品目录、给转录打产品标签、生成产品分析
  participation.py         检测观众参与障碍
  sentiment.py             简单情绪判断
  transcribe.py            使用 Whisper 转录主播语音
  line_translate.py        转录文本翻译
  post_promo.py            推广结束后的兴趣延续分析
  report_export.py         输出 CSV/JSON 报告
  text_report.py           输出最终文字报告

scripts/
  run_vod_analysis.py          推荐使用的一站式主流程
  analyze_promotion.py         推广窗口弹幕分析
  generate_findings_report.py  重新生成最终文字报告
  transcribe_promotion.py      单独处理转录流程
  enrich_transcript_analysis.py 基于已有转录和弹幕重建产品分析

products_name/
  extract_catalog.py       使用 Gemini 从主播转录中提取产品目录

examples/
  示例弹幕、示例观众回应、直播统计、主播脚本示例

docs/
  RUNBOOK.md               简短运行手册
  PROJECT_GUIDE_EN_ZH.md   当前这份中英文详细说明

data/
  本地下载的 Twitch 数据和中间文件
  默认不上传 Git，因为可能包含 VOD、弹幕和转录隐私数据

reports/
  生成的分析报告
  默认不上传 Git，因为报告里可能包含真实观众评论

tools/
  本地安装的 TwitchDownloader 工具
  默认不上传 Git，因为不应该在本项目里重新分发第三方二进制文件
```

### 2.3 数据流程

整个流程围绕一个 VOD id 运行。

```text
Twitch VOD 链接
  -> TwitchDownloader CLI 下载弹幕 JSON，并可选择下载音频/视频片段
  -> loaders.py 把弹幕标准化为 ChatMessage
  -> timing.py 对齐到原始直播分钟
  -> analyze_promotion.py 分析推广窗口内的弹幕反应
  -> transcribe.py 使用 Whisper 生成主播语音转录
  -> line_translate.py 按需把转录翻译成英文
  -> extract_catalog.py 使用 Gemini 从转录里识别产品
  -> products.py 给转录打产品标签并生成产品级分析
  -> participation.py 检测参与障碍和用户困惑
  -> post_promo.py 检查推广结束后品牌兴趣是否延续
  -> text_report.py 输出可读的最终建议报告
```

### 2.4 为什么时间对齐很重要

TwitchDownloader 导出的弹幕时间有时是相对于下载片段的时间，而不是相对于整场直播开头的时间。这样会影响产品级 headcount，因为产品可能在原直播第 `30` 分钟展示，但被截取后的弹幕文件却从 `0` 分钟开始。

项目现在优先使用 `stream_offset_seconds`。这表示产品 headcount 会对齐到原始直播时间线，而不是只对齐到截取文件内部时间线。之前有些产品在主播展示时 headcount 显示为 `0`，原因就是旧逻辑把弹幕时间放错了位置。

关键字段：

| 字段 | 含义 |
|---|---|
| `content_offset_seconds` | TwitchDownloader 提供的偏移量，通常可能相对于导出内容 |
| `stream_offset_seconds` | 相对于原始直播开始的偏移量，用于可靠匹配直播分钟 |
| `stream_minute` | 原始 VOD 时间线上的分钟 |
| `promo_minute` | 相对于推广开始的分钟 |

### 2.5 每次新分析需要准备的信息

| 输入 | 示例 | 用途 |
|---|---:|---|
| VOD 链接或 id | `https://www.twitch.tv/videos/2776778244` | 下载数据和命名文件 |
| 推广开始分钟 | `9` | 推广窗口分析 |
| 推广结束分钟 | `48` | 推广窗口分析 |
| 优惠码 | `KAV3769` | 统计优惠码提及 |
| 主播 Twitch 用户名 | `therealmarzaa` | 区分主播和观众消息 |
| 品牌关键词 | `temu` | 统计品牌提及 |
| CTA 命令 | `!temu` | 统计链接/优惠码请求 |
| Gemini API key | `GEMINI_API_KEY` | 自动从转录中提取产品目录 |

### 2.6 下次推荐运行命令

如果本地已经有弹幕和主播转录，并且希望自动提取产品目录：

```bash
export GEMINI_API_KEY="your_key_here"

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

这个命令现在会完成以前需要分开做的事情：

1. 读取已有弹幕和转录。
2. 使用 Gemini 生成该 VOD 专属的产品目录。
3. 生成产品 headcount、情绪、参与问题、推广后兴趣分析和最终报告。

正常情况下，运行这个命令后不需要再单独运行 `scripts/generate_findings_report.py`，因为主流程已经会生成最终文字报告。

### 2.7 如果已经有产品目录

如果 `data/<vod_id>/<vod_id>_product_catalog.json` 已经存在，可以避免再次调用 Gemini：

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

### 2.8 分析一个全新的 VOD

如果需要下载弹幕和音频片段，使用：

```bash
export GEMINI_API_KEY="your_key_here"

python scripts/run_vod_analysis.py \
  --vod-url "https://www.twitch.tv/videos/<vod_id>" \
  --promo-start <start_minute> \
  --promo-end <end_minute> \
  --promo-code <promo_code> \
  --influencer <twitch_login> \
  --brand <brand_keyword> \
  --cta '<chat_command>' \
  --extract-products
```

如果还没有安装 Whisper 或 FFmpeg，可以先准备或导入转录，然后加 `--skip-transcribe`。如果一开始只想下载弹幕，可以加 `--skip-video`。

### 2.9 产品目录提取

以前的流程是：

1. 运行 `products_name/extract_catalog.py`。
2. 手动复制输出。
3. 粘贴到 `twitch_promo_analyzer/products.py`。
4. 再重新运行分析。

优化后的流程会直接写入 JSON：

```bash
python3 products_name/extract_catalog.py \
  data/2776778244/2776778244_influencer_transcript.csv \
  --out data/2776778244/2776778244_product_catalog.json
```

主流程可以直接读取这个 JSON 文件。以后分析新直播时，不应该每次都手动修改 `products.py`。

产品目录格式示例：

```json
{
  "schema_version": "1",
  "source": "gemini",
  "products": [
    {
      "product_id": "led_light_panel",
      "product_name": "LED light panel",
      "keywords": ["led", "pannello"],
      "approx_start_minute": 20.7
    }
  ]
}
```

### 2.10 主要输出文件

| 输出 | 含义 |
|---|---|
| `data/<vod_id>/<vod_id>_chat.json` | TwitchDownloader 原始弹幕导出 |
| `data/<vod_id>/<vod_id>_chat.csv` | 标准化后的弹幕 |
| `data/<vod_id>/<vod_id>_influencer_transcript.json` | 带时间、英文翻译、产品标签的主播转录 |
| `data/<vod_id>/<vod_id>_influencer_transcript.csv` | 适合表格查看的主播转录 |
| `data/<vod_id>/<vod_id>_product_catalog.json` | 该 VOD 专属产品名称和关键词 |
| `data/<vod_id>/<vod_id>_viewer_responses.json` | 推广窗口内的观众弹幕 |
| `reports/<vod_id>_promotion_analysis.json` | 弹幕量、优惠码/CTA/品牌提及、推广评分 |
| `reports/<vod_id>_promotion_report.html` | 可在浏览器打开的推广报告 |
| `reports/<vod_id>_product_headcount.csv` | 每个产品展示期间的独立发言观众数 |
| `reports/<vod_id>_product_sentiment.csv` | 每个产品对应的观众情绪 |
| `reports/<vod_id>_participation_issues.csv` | 困惑、链接/优惠码请求、信任问题、注册或 app 问题 |
| `reports/<vod_id>_post_promo_analysis.json` | 推广结束后品牌兴趣是否延续 |
| `reports/<vod_id>_findings_report.txt` | 最终可读建议报告 |

### 2.11 建议是如何生成的

最终建议来自实际测量信号，而不是固定模板。

示例：

| 信号 | 可能建议 |
|---|---|
| 大量 `!temu` 或优惠码请求 | 固定 CTA、主播口播重复命令、加更清楚的画面提示 |
| 大量困惑词 | 在继续展示产品前，先解释如何领取优惠 |
| 某产品独立发言人数低 | 缩短该产品展示时间，或者加入直接提问/投票 |
| 某产品情绪正面且 headcount 高 | 下次把类似产品提前展示 |
| 推广结束后仍有品牌兴趣 | 不要突然结束推广，可以在后续继续轻提醒 |
| 出现信任质疑 | 更清楚地说明赞助关系和用户能得到的实际价值 |

### 2.12 验证

上传或分享前建议运行测试：

```bash
python -m unittest discover -s tests
```

如果只想重新生成最终报告：

```bash
python scripts/generate_findings_report.py --vod-id 2776778244
```

这个命令只适合在中间 JSON/CSV 分析文件已经存在时使用。

### 2.13 上传 GitHub 的原则

GitHub 仓库应该分享源码和小型示例，不应该上传私有分析数据或重新分发第三方二进制文件。

可以提交：

```text
twitch_promo_analyzer/
scripts/
products_name/
tests/
examples/
docs/
README.md
pyproject.toml
.gitignore
.env.example
```

不要提交：

```text
data/
reports/
tools/
sidenotes/
.env
ffmpeg
ffprobe
version.json
*.mp4
*.wav
*.m4a
真实观众弹幕，除非你有分享权限
完整转录，除非你有分享权限并检查过隐私问题
API keys、OAuth tokens、cookies、本地凭证
```

当前仓库里根目录的 `ffmpeg`、`ffprobe` 和 `version.json` 已经被 Git 跟踪。上传 GitHub 前，先把它们从 Git 索引中移除：

```bash
git rm --cached ffmpeg ffprobe version.json
```

这个命令只会让 Git 不再跟踪它们，不会删除你电脑上的本地文件。

### 2.14 尊重第三方工具

本项目会调用或集成多个外部工具。比较安全、尊重版权和许可证的做法是：写清楚来源，本地安装，不把第三方二进制文件直接打包到本仓库里，除非你明确遵守它们的许可证要求。

| 工具 | 作用 | 推荐做法 |
|---|---|---|
| TwitchDownloader | 下载 Twitch 弹幕和可选 VOD/音频片段 | 链接原项目，保留许可证说明，本地安装在 `tools/`，不要声称是自己的工具 |
| FFmpeg | 处理媒体文件，支持 Whisper/audio 流程 | 优先系统安装或用户本地安装，不要把下载的二进制文件提交到本仓库 |
| OpenAI Whisper | 主播语音识别 | 作为依赖安装，注明来源，并说明转录可能有误差 |
| deep-translator | 可选文本翻译 | 作为依赖安装，注明来源 |
| Gemini API | 从转录中提取产品名 | 不提交 `GEMINI_API_KEY`，查看 Google API 条款，不要未经允许发送隐私数据 |
| Twitch 内容 | 原始直播和弹幕数据 | 未获许可时不要上传 VOD、原始弹幕、私人笔记或可识别观众的数据 |

上游参考链接：

- TwitchDownloader: https://github.com/lay295/TwitchDownloader
- FFmpeg legal page: https://ffmpeg.org/legal.html
- OpenAI Whisper: https://github.com/openai/whisper
- deep-translator: https://pypi.org/project/deep-translator/
- Gemini API keys: https://aistudio.google.com/apikey

### 2.15 推荐 GitHub 上传步骤

先检查 Git 当前看到哪些文件：

```bash
git status --short
git ls-files ffmpeg ffprobe version.json data reports tools sidenotes
```

移除已被跟踪的第三方二进制文件：

```bash
git rm --cached ffmpeg ffprobe version.json
```

运行测试：

```bash
python -m unittest discover -s tests
```

添加源码和文档：

```bash
git add .gitignore .env.example README.md pyproject.toml docs examples products_name scripts tests twitch_promo_analyzer
```

提交前再次检查：

```bash
git status --short
git diff --cached --stat
```

提交：

```bash
git commit -m "Document Twitch promotion analysis pipeline"
```

建议先创建私有 GitHub 仓库。私有仓库更适合先检查许可证、密钥和数据：

```bash
gh repo create twitch-promo-analyzer --private --source . --remote origin --push
```

如果不用 GitHub CLI，可以先在 GitHub 网页上创建空仓库，然后运行：

```bash
git remote add origin git@github.com:<your-user>/<repo-name>.git
git branch -M main
git push -u origin main
```

公开仓库前，请确认：

1. `data/`、`reports/`、`tools/`、`sidenotes/` 没有被 Git 跟踪。
2. `ffmpeg`、`ffprobe`、`version.json` 已经不再被 Git 跟踪。
3. 搜索密钥和 token：

```bash
rg -n "GEMINI_API_KEY|oauth:|api[_-]?key|token|secret|password" .
```

4. 添加或检查项目许可证。
5. 在 `README.md` 或 `THIRD_PARTY_NOTICES.md` 中添加第三方工具致谢。
6. `examples/` 里只放示例或合成数据，不放完整真实 Twitch 导出。

### 2.16 README 建议说明

可以在 README 里加入这段简短说明：

```markdown
## Third-Party Tools And Data

This project can call TwitchDownloader, FFmpeg, OpenAI Whisper, deep-translator, and Gemini. These tools are installed locally by the user and are not redistributed in this repository. Downloaded Twitch VODs, chats, transcripts, private notes, reports, API keys, and OAuth tokens should stay out of Git unless you have the right to share them.
```
