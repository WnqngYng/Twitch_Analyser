from __future__ import annotations

from collections import Counter
from typing import Any


def attach_recommendations(analysis: dict[str, Any]) -> dict[str, Any]:
    event_recommendations = {
        event["event_id"]: recommend_for_event(event) for event in analysis.get("events", [])
    }
    campaign_recommendations = recommend_for_campaign(analysis)

    analysis["recommendations"] = {
        "campaign": campaign_recommendations,
        "events": event_recommendations,
    }
    return analysis


def recommend_for_event(event: dict[str, Any]) -> list[str]:
    response = event["response"]
    baseline = event["baseline"]
    intents = Counter(response.get("intents", {}))
    sentiment_counts = response.get("sentiment_counts", {})
    recommendations: list[str] = []

    if event["engagement_lift"] < 0.15:
        recommendations.append(
            "Move the promotion closer to a high-attention moment, and lead with a clearer viewer benefit before the code or link."
        )

    if response["message_count"] < max(5, baseline["message_count"] * 0.8):
        recommendations.append(
            "Add an interactive prompt such as a poll, chat challenge, or product choice so viewers have a reason to respond."
        )

    if response["sentiment_avg"] < -0.05 or sentiment_counts.get("negative", 0) > sentiment_counts.get("positive", 0):
        recommendations.append(
            "Handle objections in the stream: acknowledge sponsorship, show the product in use, and address price or trust concerns directly."
        )

    if intents["confusion"] >= 2 or intents["link_or_code_request"] >= 3:
        recommendations.append(
            "Simplify the call to action and pin a chat command with the offer, link, code, expiry, and one-line product value."
        )

    if intents["purchase_intent"] >= 2 and response["sentiment_avg"] >= 0:
        recommendations.append(
            "Follow up within the same stream while intent is hot: repeat the code once, answer buying questions, and reinforce scarcity honestly."
        )

    if intents["objection"] >= 2:
        recommendations.append(
            "Test a softer creative angle next time: creator story first, offer second, with proof points instead of a hard sales read."
        )

    if event.get("viewer_count_delta") is not None and event["viewer_count_delta"] < -20:
        recommendations.append(
            "Shorten the ad read or integrate it into gameplay/content; viewer count dropped during the response window."
        )

    if event["cta_type"] == "promo_code" and intents["link_or_code_request"] == 0:
        recommendations.append(
            "Make the code visually and verbally memorable, then repeat it once near the end of the segment."
        )

    if not recommendations:
        recommendations.append(
            "This promotion performed well. Preserve the timing and creator voice, then test one variable next time: offer size, CTA wording, or segment length."
        )

    return recommendations[:5]


def recommend_for_campaign(analysis: dict[str, Any]) -> list[str]:
    summary = analysis.get("summary", {})
    events = analysis.get("events", [])
    recommendations: list[str] = []

    if not events:
        return [
            "No promotional moments were detected. Provide influencer handles and brand terms, or add explicit markers for ad reads in the chat export.",
            "Capture at least five minutes before and after each promotion so the analyzer can compare response against a baseline.",
        ]

    cta_counter = Counter(event["cta_type"] for event in events)
    best_event_id = summary.get("best_event")
    best_event = next((event for event in events if event["event_id"] == best_event_id), None)

    if best_event:
        recommendations.append(
            f"Use {best_event['event_id']} as the creative reference: it had the strongest lift with a {best_event['cta_type']} CTA."
        )

    if summary.get("avg_engagement_lift", 0) < 0.2:
        recommendations.append(
            "The campaign is not reliably lifting chat activity. Test promotion timing around content peaks instead of placing reads in low-energy gaps."
        )
    else:
        recommendations.append(
            "Average chat lift is positive. Keep the campaign structure, then optimize CTA clarity and offer framing event by event."
        )

    if summary.get("avg_response_sentiment", 0) < 0:
        recommendations.append(
            "Campaign sentiment is net negative. Add transparent disclosure and more creator-led product context before mentioning the offer."
        )

    if len(cta_counter) == 1 and len(events) >= 3:
        recommendations.append(
            "All detected promotions use the same CTA style. A/B test code-first, demo-first, and giveaway-first formats to find the best viewer response."
        )

    influencer_stats = summary.get("influencers", {})
    if len(influencer_stats) > 1:
        best_influencer = max(
            influencer_stats.items(),
            key=lambda item: (item[1]["avg_lift"], item[1]["avg_sentiment"]),
        )[0]
        recommendations.append(
            f"Allocate more campaign weight to {best_influencer}; their average lift and sentiment are strongest in this dataset."
        )

    recommendations.append(
        "Join this chat analysis with click, coupon, affiliate, and sales data so future recommendations optimize for revenue, not engagement alone."
    )
    return recommendations[:6]
