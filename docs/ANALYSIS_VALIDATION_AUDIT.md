# Analysis Validation Audit

This document answers a practical question: do the analysis perspectives process data logically, and do they generate useful, tested insights?

Short answer: yes for directional campaign analysis, with important caveats. The project now covers the main perspectives needed for a Twitch promotion review, and the core data flow is logical. The strongest insights are direct counts and time-window comparisons. The weakest insights are sentiment, intent, and final scoring, because those are heuristic rules rather than statistically trained or sales-validated models.

## Validation Status By Analysis Perspective

| Perspective | Current Status | Why It Is Useful | Main Caveat |
|---|---|---|---|
| Promotion window analysis | Strong | Compares pre-promo, during-promo, and post-promo chat volume, unique chatters, CTA use, brand/code mentions, and sentiment delta | The performance grade uses handcrafted weights, so treat it as a campaign health score, not financial ROI |
| Chat peak analysis | Strong | Finds the highest-response minutes and strongest rolling windows during the promotion | Peaks explain attention, but not necessarily purchase intent |
| Promo code and CTA tracking | Strong | Counts `!temu`, promo code, and brand mentions, with basic bot/copy-paste separation | Organic/bot separation is rule-based and may miss unknown bot accounts |
| Influencer transcript analysis | Medium to strong | Connects product presentation moments to chat response windows | Transcript quality depends on Whisper/audio quality and language accuracy |
| Product catalog extraction | Medium | Gemini creates a VOD-specific product catalog so users do not need to edit `products.py` manually | Product names and keywords should still be reviewed by a human before final reporting |
| Product headcount | Strong | Counts unique chatters and messages during each product presentation period | Requires correct product segment detection and stream-minute alignment |
| Product sentiment | Medium | Gives a quick positive/neutral/negative directional read by product | Sentiment is keyword-based, so sarcasm, slang, and mixed Italian/English can be misclassified |
| Participation issues | Medium | Detects repeated confusion, link/code requests, app/signup issues, offer clarity problems, and trust objections | Pattern-based detection can undercount novel wording or overcount harmless mentions |
| Post-promotion interest | Strong for mentions | Measures whether Temu/code discussion continues after the banner ends | It measures chat interest, not clicks or sales |
| Final recommendations | Useful but advisory | Recommendations are tied to measured signals such as low CTA use, confusion, objections, and weak engagement lift | They should be checked against brand goals and conversion data before business decisions |

## What Is Directly Evidenced

These outputs are based on direct counts from the data:

- Number of messages in each time window.
- Number of unique chatters.
- Messages per minute.
- Promo code mentions.
- CTA command mentions.
- Brand mentions.
- Product-window headcount.
- First-3-minute product response volume.
- Post-promo brand/code mentions.

These are the safest metrics to quote in a report.

## What Is Heuristic

These outputs are useful but should be described as signals, not facts:

- Sentiment score.
- Positive/neutral/negative labels.
- Purchase intent detection.
- Confusion detection.
- Trust objection detection.
- Campaign performance grade.
- Product response score.
- Final recommendation priority.

The project uses transparent rules for these. That is good for explainability, but it is not the same as a validated machine-learning classifier or actual sales attribution.

## Timing And Headcount Logic

The project now preserves and uses `stream_offset_seconds` from TwitchDownloader exports. This is important because downloaded or trimmed chat files can otherwise appear to start at minute `0`, even when the promotion happened much later in the original livestream.

The timing filter now compares stream minutes directly through `offset_minutes()`. This makes product headcount more robust when `stream_offset_seconds` is available.

Current safeguards:

1. `scripts/validate_data_pipeline.py` checks chat, transcript, and product segment alignment for each VOD.
2. Old CSV exports can be regenerated from TwitchDownloader JSON with `--repair-csv`.
3. If chat has no offsets but clearly looks like a trimmed export, the analyzer infers stream offsets from the requested promo window and records a warning in `data_quality`.
4. Whisper timestamps are auto-detected as either full-stream timestamps or trimmed-audio-relative timestamps, preventing double-shifted influencer transcripts.
5. Fixed-window promotion analysis now uses the requested `baseline_minutes` immediately before the promo, not the whole stream from minute `0`.
6. Product response uses a fixed first-3-minute response window after product intro, making product comparisons less biased by segment length.

Correct headcount depends on:

1. Chat messages having reliable stream offsets or reliable timestamps.
2. Transcript lines having correct `stream_minute` values.
3. Product segments being detected at the right transcript lines.
4. Bot users being excluded where appropriate.
5. The report consumer reading `data_quality` warnings before comparing creators or products.

If baseline chat is missing, the report marks the grade as `low_baseline_missing`. In that case, chat counts during the promo are still useful, but engagement lift and the letter grade should not be used as a fair influencer-performance comparison.

## Test Coverage

The current tests verify:

- Promotion detection and recommendation attachment.
- Twitch VOD id extraction.
- TwitchDownloader JSON loading.
- Stream offset alignment for trimmed chat.
- Promotion-window analysis.
- Peak analysis and promo code tracking.
- Translation recommendation for Italian-heavy chat.
- Participation issue classification.
- Product headcount using stream offsets.
- Text findings report generation.

Current test command:

```bash
python -m unittest discover -s tests
```

Latest local result:

```text
Ran 19 tests
OK
```

## Remaining Validation Gaps

The project is useful now, but these gaps should be closed before presenting the results as fully validated analytics:

1. Add small synthetic fixtures for the full product pipeline, so tests do not depend on private `data/` files.
2. Add tests for product catalog JSON loading and transcript product annotation.
3. Add tests proving bot messages are excluded consistently from headcount and CTA summaries.
4. Compare sentiment/intent labels against a manually labeled sample of real chat.
5. Compare final recommendations against real campaign KPIs such as clicks, coupon redemptions, orders, or affiliate revenue.
6. Human-review product catalogs for every VOD before making product-level claims in external reports.

## Practical Conclusion

The project now processes the livestream data logically enough for campaign diagnosis and improvement suggestions. It is especially strong for time-window engagement, chat peaks, CTA/code tracking, product headcount, and post-promo interest.

The insights are useful and partially tested, but not fully scientifically validated. Use them as evidence-backed recommendations, not as final proof of commercial performance. For business decisions, join this analysis with TwitchTracker context, click data, coupon redemption, affiliate sales, and a small human review of product labels and sentiment samples.
