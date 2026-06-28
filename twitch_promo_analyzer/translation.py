from __future__ import annotations

import re
from collections import Counter
from typing import Any

from .models import ChatMessage
from .timing import align_messages_to_window, filter_by_minutes, offset_minutes, stream_origin


ITALIAN_MARKERS = {
    "che",
    "non",
    "per",
    "con",
    "sono",
    "ciao",
    "grazie",
    "buonasera",
    "sera",
    "maestro",
    "anche",
    "questo",
    "quella",
    "perché",
    "perche",
    "come",
    "dove",
    "codice",
    "sconto",
    "compro",
    "acquisto",
    "link",
    "soldi",
    "euro",
    "ragazzi",
    "chat",
    "marzo",
    "temu",
}

ENGLISH_MARKERS = {
    "the",
    "and",
    "you",
    "what",
    "why",
    "how",
    "buy",
    "code",
    "link",
    "scam",
    "ad",
    "sponsored",
    "worth",
    "deal",
    "thanks",
    "please",
    "english",
}


def assess_translation_need(
    messages: list[ChatMessage],
    promo_start_minute: float,
    promo_end_minute: float,
    peak_samples: list[dict[str, Any]] | None = None,
    target_report_language: str = "en",
) -> dict[str, Any]:
    aligned_messages, timing_diagnostics = align_messages_to_window(
        messages,
        promo_start_minute,
        promo_end_minute,
    )
    origin = stream_origin(aligned_messages)
    promo_messages = [
        message
        for message in aligned_messages
        if promo_start_minute <= offset_minutes(message, origin) < promo_end_minute
        and message.user.lower() not in {"streamelements", "nightbot", "moobot", "fossabot"}
    ]

    language_mix = estimate_language_mix(promo_messages)
    recommendation = build_recommendation(language_mix, target_report_language)
    translate_items = select_messages_to_translate(
        promo_messages,
        peak_samples or [],
        recommendation["strategy"],
    )

    return {
        "target_report_language": target_report_language,
        "language_mix": language_mix,
        "recommendation": recommendation,
        "messages_to_translate": translate_items,
        "data_quality": timing_diagnostics,
        "implementation_notes": [
            "This project does not call external translation APIs (stdlib-only).",
            "Export the listed messages to your translation tool or enable translation in the final report pipeline.",
            "For stakeholder reports in English: translate peak-minute samples, objections, and purchase-intent lines.",
            "Keep original Italian in an appendix when quotes are used in creator-facing feedback.",
        ],
    }


def estimate_language_mix(messages: list[ChatMessage]) -> dict[str, Any]:
    italian_hits = 0
    english_hits = 0
    token_total = 0

    for message in messages:
        tokens = re.findall(r"[a-zA-Zàèéìòù']+", message.message.lower())
        if not tokens:
            continue
        token_total += len(tokens)
        italian_hits += sum(1 for token in tokens if token in ITALIAN_MARKERS)
        english_hits += sum(1 for token in tokens if token in ENGLISH_MARKERS)

    if token_total == 0:
        return {"italian_ratio": 0.0, "english_ratio": 0.0, "primary": "unknown"}

    italian_ratio = round(italian_hits / token_total, 3)
    english_ratio = round(english_hits / token_total, 3)
    if italian_ratio >= english_ratio * 1.5:
        primary = "italian"
    elif english_ratio >= italian_ratio * 1.5:
        primary = "english"
    else:
        primary = "mixed"

    return {
        "italian_ratio": italian_ratio,
        "english_ratio": english_ratio,
        "primary": primary,
        "sample_size": len(messages),
    }


def build_recommendation(language_mix: dict[str, Any], target: str) -> dict[str, Any]:
    primary = language_mix.get("primary", "unknown")
    if target != "en":
        return {
            "translate_viewer_responses": False,
            "strategy": "keep_original",
            "rationale": f"Report target language is {target}; keep chat in original language.",
        }

    if primary == "italian":
        return {
            "translate_viewer_responses": True,
            "strategy": "translate_peaks_and_intents",
            "rationale": (
                "Chat is predominantly Italian. Translate peak-minute reactions, objections, "
                "and CTA-related lines for English campaign reporting; keep originals alongside quotes."
            ),
        }
    if primary == "english":
        return {
            "translate_viewer_responses": False,
            "strategy": "keep_original",
            "rationale": "Chat is predominantly English already; translation adds little value.",
        }
    return {
        "translate_viewer_responses": True,
        "strategy": "translate_selective",
        "rationale": (
            "Mixed language chat. Translate only high-signal lines (peaks, objections, purchase intent) "
            "and leave general banter in Italian."
        ),
    }


def select_messages_to_translate(
    promo_messages: list[ChatMessage],
    peak_samples: list[dict[str, Any]],
    strategy: str,
    limit: int = 40,
) -> list[dict[str, Any]]:
    if strategy == "keep_original":
        return []

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for peak in peak_samples:
        for reaction in peak.get("top_reactions", []):
            text = reaction.get("message", "")
            if text in seen:
                continue
            seen.add(text)
            selected.append(
                {
                    "source": "peak_minute",
                    "promo_minute": peak.get("promo_minute"),
                    "user": reaction.get("user"),
                    "original": text,
                    "translate_to": "en",
                    "english": None,
                }
            )

    if strategy == "translate_peaks_and_intents":
        for message in promo_messages:
            lowered = message.message.lower()
            if any(
                marker in lowered
                for marker in ("scam", "sellout", "temu", "codice", "link", "compro", "acquisto", "sconto", "?")
            ):
                if message.message in seen:
                    continue
                seen.add(message.message)
                selected.append(
                    {
                        "source": "intent_or_brand",
                        "user": message.user,
                        "original": message.message,
                        "translate_to": "en",
                        "english": None,
                    }
                )
            if len(selected) >= limit:
                break

    return selected[:limit]
