from __future__ import annotations

import re
from datetime import timedelta
from urllib.parse import urlparse

from .models import ChatMessage, PromotionEvent


PROMO_TERMS = {
    "sponsored": 3,
    "ad ": 2,
    "#ad": 3,
    "partner": 2,
    "affiliate": 2,
    "promo": 3,
    "promotion": 3,
    "discount": 3,
    "coupon": 3,
    "use code": 4,
    "promo code": 4,
    "code ": 2,
    "!code": 4,
    "!deal": 4,
    "deal": 2,
    "limited time": 3,
    "link in chat": 4,
    "link below": 3,
    "checkout": 2,
    "check out": 2,
    "giveaway": 3,
    "free trial": 3,
    "20%": 2,
    "30%": 2,
    "50%": 2,
    "% off": 3,
}

URL_RE = re.compile(r"https?://\S+|(?:www\.)\S+", re.IGNORECASE)
CODE_RE = re.compile(
    r"(?:code|coupon|promo\s*code)\s*(?:is|:|-)?\s*([A-Z0-9][A-Z0-9_-]{2,24})",
    re.IGNORECASE,
)
PERCENT_RE = re.compile(r"\b\d{1,2}\s*%\s*off\b", re.IGNORECASE)


def detect_promotion_events(
    messages: list[ChatMessage],
    influencers: set[str] | None = None,
    brands: set[str] | None = None,
    merge_gap_seconds: int = 120,
) -> list[PromotionEvent]:
    influencer_set = {item.lower() for item in influencers or set() if item}
    brand_set = {item.lower() for item in brands or set() if item}
    events: list[PromotionEvent] = []
    last_event_by_key: dict[tuple[str, str | None, str], PromotionEvent] = {}

    for index, message in enumerate(messages):
        score = score_promotion_message(message.message, brand_set)
        user_key = message.user.lower()
        if influencer_set and user_key not in influencer_set:
            continue
        if user_key in influencer_set:
            score += 2

        if score < 3:
            continue

        brand = detect_brand(message.message, brands or set())
        cta_type = classify_cta(message.message)
        key = (user_key, brand.lower() if brand else None, cta_type)
        previous = last_event_by_key.get(key)
        if previous and message.timestamp - previous.timestamp <= timedelta(seconds=merge_gap_seconds):
            continue

        event = PromotionEvent(
            event_id=f"promo-{len(events) + 1}",
            timestamp=message.timestamp,
            influencer=message.user,
            message=message.message,
            brand=brand,
            cta_type=cta_type,
            offer=extract_offer(message.message),
            keyword_score=score,
            source_index=index,
        )
        events.append(event)
        last_event_by_key[key] = event

    return events


def score_promotion_message(text: str, brands: set[str] | None = None) -> int:
    normalized = f" {text.lower()} "
    score = 0
    for term, weight in PROMO_TERMS.items():
        if term in normalized:
            score += weight
    if URL_RE.search(text):
        score += 2
    if CODE_RE.search(text):
        score += 4
    if PERCENT_RE.search(text):
        score += 3
    for brand in brands or set():
        if brand and brand.lower() in normalized:
            score += 1
    return score


def classify_cta(text: str) -> str:
    lowered = text.lower()
    if "giveaway" in lowered or "win " in lowered:
        return "giveaway"
    if "free trial" in lowered or "trial" in lowered:
        return "trial"
    if "code" in lowered or "coupon" in lowered or "!code" in lowered:
        return "promo_code"
    if URL_RE.search(text) or "link" in lowered:
        return "link_click"
    if "discount" in lowered or "% off" in lowered or "deal" in lowered:
        return "discount"
    if "sponsored" in lowered or "#ad" in lowered:
        return "sponsorship_disclosure"
    return "product_mention"


def extract_offer(text: str) -> str | None:
    code_match = CODE_RE.search(text)
    percent_match = PERCENT_RE.search(text)
    url_match = URL_RE.search(text)

    pieces: list[str] = []
    if code_match:
        pieces.append(f"code {code_match.group(1).upper()}")
    if percent_match:
        pieces.append(percent_match.group(0).lower())
    if url_match:
        domain = urlparse(url_match.group(0) if "://" in url_match.group(0) else f"https://{url_match.group(0)}").netloc
        if domain:
            pieces.append(domain)
    return ", ".join(pieces) if pieces else None


def detect_brand(text: str, brands: set[str]) -> str | None:
    lowered = text.lower()
    for brand in sorted(brands, key=len, reverse=True):
        if brand and brand.lower() in lowered:
            return brand

    url_match = URL_RE.search(text)
    if url_match:
        raw_url = url_match.group(0)
        parsed = urlparse(raw_url if "://" in raw_url else f"https://{raw_url}")
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        if domain:
            return domain.split(".")[0].title()
    return None
