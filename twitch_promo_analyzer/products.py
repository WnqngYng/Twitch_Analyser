from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from .models import ChatMessage
from .participation import analyze_participation_by_product, analyze_participation_issues
from .sentiment import detect_intents, score_sentiment, sentiment_label
from .timing import align_messages_to_window, filter_by_minutes, offset_minutes, stream_origin


DEFAULT_BOT_USERS = {"streamelements", "nightbot", "moobot", "fossabot"}

PRODUCT_CATALOG = [
    # 1. Promozioni, App e Codici Sconto
    ("promos_app_codes", "App Promos & Discount Codes", ('acquisto', 'app', 'applicaz', 'articoli', 'barra di ricerca', 'campa', 'codice', 'codicino', 'comprare', 'efo', 'kav3769', 'link', 'offerta', 'prenderveli', 'prodotti', 'profilo', 'scaricate', 'sconto', 'spendere', 'temo', 'temu', 'zero', 'zero euro')),
    
    # 2. Cibo e Bevande
    ("beverages", "Beverages / Sodas", ('coca', 'coca cola', 'coca-cola', 'lemon', 'lemon soda')),
    ("sweet_snacks", "Sweet Snacks / Candy / Chocolate", ('bueno', 'caramell', 'dolce', 'dolci', 'gusto', 'kidcott', 'kinder', 'kinder bueno', 'kitkat', 'lion', 'mangiati', 'paccone', 'salati', 'scade', 'scadono', 'scatola', 'scatole', 'smartis', 'sneakers', 'vafer rolls')),
    ("savory_spicy_food", "Savory & Spicy Snacks / Salami", ('challenge', 'fadela', 'filchie salami', 'finocchio', 'food', 'ingerire', 'mangiare', 'mangiato', 'marca', 'pacco', 'piccante', 'prodotto', 'questa', 'roba', 'salame', 'stalada')),
    
    # 3. Gadget, Maschere e Oggetti a Sorpresa
    ("masks_and_costumes", "Masks / Costumes / Gag Items", ('allargai', 'cavocci', 'cloud', 'giappanna', 'giapponisti', 'halloween', 'illuminarsi', 'inbotitura', 'incolumità', 'indossa', 'indossare', 'joker', 'led', 'mandato', 'maschera', 'maschere', 'parruca', 'parrucca', 'passamontagna', 'respirando', 'respirare', 'robotizzato', 'scarica', 'simpatica')),
    ("mystery_boxes", "Mystery Boxes & Packs", ('arrivato box', 'box 109', 'busta', 'casa', 'pacco', 'scatola', 'sorpresa')),
    ("toys_gadgets_games", "Toys, Card Games & Gadgets", ('appoggiata', 'automatic card shuffler', 'automatico', 'card schaffler', 'carina', 'carta', 'carte', 'chimia', 'cimietta', 'decks', 'far far west', 'gameplay options', 'metamazzo', 'mischia', 'mischie', 'misuratore di riflessi', 'pelus', 'pile', 'portiamo', 'reaction challenge', 'vedrete', 'zazzone')),
    
    # 4. Dispositivi Mobile e Accessori
    ("smartphones_and_tablets", "Smartphones & Tablets", ('15c', 'cellulare', 'fps', 'piota', 'poco', 'quattro euro', 'recensioni', 'redmi', 'smartphone', 'tablet', 'telefono', 'xiaomi')),
    ("device_cases_protectors", "Phone/Tablet Cases & Protectors", ('cover', 'filtrin', 'gigantesca', 'inserire', 'iphone', 'nuovo', 'packaging', 'pellicol', 'protezione', 'tablet', 'telefono')),
    ("smart_wearables_accessories", "Smart Wearables & Accessories", ('bella', 'bluetooth', 'dispositivo', 'drone', 'dura', 'euro', 'figa', 'ia', 'intelligenti', 'occhiali', 'plastico', 'questa', 'radella', 'radema', 'telefono', 'tradutore', 'traduzione', 'translator')),
    
    # 5. Gaming e Periferiche PC
    ("video_games", "Video Games", ('gioco', 'minecraft', 'play', 'requiemma', 'residentivo')),
    ("gaming_controllers", "Gaming Controllers & Joysticks", ('adatta', 'controller', 'controllo', 'gallardo', 'giocace', 'giocato', 'iphone', 'joystick', 'oggettino', 'pada', 'personal', 'prodotto', 'questo', 'telefono', 'usb', 'vibrazione', 'wireless')),
    ("pc_peripherals", "Keyboards / Mice / Mousepads", ('carina', 'codicino', 'componenti', 'controller', 'dentro', 'display', 'euro', 'gamey', 'giocare', 'giogielino', 'led', 'leggerissima', 'mausa', 'meccanica', 'mouse', 'pada', 'pade', 'patterne', 'pc', 'playstation', 'sconto', 'stomhouse', 'tassierina', 'tastiera', 'telefons', 'temo', 'transparente', 'trasparente', 'wireless')),
    ("pc_components_projectors", "PC Components & Projectors", ('case', 'gireto', 'gramma nata', 'pc', 'plastikume', 'prenderei', 'proiettore', 'proiettori', 'scheda madre', 'temu', 'vendono')),
    
    # 6. Audio, Video e Illuminazione
    ("streaming_and_audio", "Streaming Deck & Audio", ('carino', 'cassa', 'gigante', 'live streaming', 'monitor', 'programmabile', 'schermo', 'simpaticissimo', 'soundbar', 'stream deck')),
    ("cameras_and_optics", "Cameras & Stabilizers", ('bianco e nero', 'bodicam', 'body camera', 'cagatina', 'colori', 'flesh', 'foto', 'life camera', 'registra', 'riprende', 'stabilizzatore', 'telecamera', 'vlog')),
    ("lighting_led", "LED Lights & Panels", ('attaccarlo', 'base', 'carino', 'catenella', 'figo', 'funziona', 'led', 'prezzo', 'prodotto', 'usb', 'viti')),
    ("drones", "Drones", ('altezza', 'cossa', 'drone', 'fatto', 'metri', 'possibile', 'potenti', 'provato', 'scontato', 'volare')),
    
    # 7. Casa, Arredamento, Moda e Cura della persona
    ("furniture_chairs", "Gaming Chairs & Armchairs", ('cavo usb', 'confiabile', 'cuscinetto', 'giardino', 'massaggente', 'monterò', 'pacco gigante', 'poltrona', 'reclinabile', 'sedia', 'vibra')),
    ("home_kitchen_decor", "Home, Kitchen & Decor", ('3d', 'acciaio', 'casa', 'cubetti', 'fetto', 'ghiaccio', 'legno', 'murali', 'pacchi', 'padelle', 'pannelli', 'pressa')),
    ("beauty_and_apparel", "Beauty & Clothing", ('chinder trissi', 'gobo', 'ingrazio', 'primer', 'prodotti', 'questo primer', 'vestiario'))
]

ProductCatalog = list[tuple[str, str, tuple[str, ...]]]


def load_product_catalog(path: str | Path | None) -> ProductCatalog:
    if not path:
        return PRODUCT_CATALOG

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"product catalog not found: {source}")

    import json

    payload = json.loads(source.read_text(encoding="utf-8"))
    records = payload.get("products", payload) if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise ValueError("product catalog must be a JSON list or contain a products list")

    catalog: ProductCatalog = []
    for record in records:
        if isinstance(record, dict):
            product_id = record.get("product_id") or record.get("category_slug") or record.get("id")
            label = record.get("product_name") or record.get("label") or record.get("name")
            keywords = record.get("keywords", [])
        elif isinstance(record, (list, tuple)) and len(record) >= 3:
            product_id, label, keywords = record[:3]
        else:
            continue

        if not product_id or not label:
            continue
        keyword_tuple = tuple(str(keyword).strip().lower() for keyword in keywords if str(keyword).strip())
        if not keyword_tuple:
            continue
        catalog.append((str(product_id), str(label), keyword_tuple))

    if not catalog:
        raise ValueError(f"product catalog has no usable products: {source}")
    return catalog


def classify_product_line(text: str, product_catalog: ProductCatalog | None = None) -> str | None:
    lowered = text.lower()
    for product_id, _name, keywords in product_catalog or PRODUCT_CATALOG:
        if any(keyword in lowered for keyword in keywords):
            return product_id
    return None


def build_product_segments(
    transcript: list[dict[str, Any]],
    product_catalog: ProductCatalog | None = None,
    promo_end_minute: float | None = None,
) -> list[dict[str, Any]]:
    """Group transcript into product reveal segments from first mention of each product."""
    anchors: list[tuple[str, str, float, str]] = []
    seen: set[str] = set()
    catalog = product_catalog or PRODUCT_CATALOG

    for line in sorted(transcript, key=lambda item: float(item.get("stream_minute", 0))):
        product_id = str(line.get("product_id") or "").strip() or classify_product_line(
            str(line.get("text", "")),
            catalog,
        )
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)
        anchors.append(
            (
                product_id,
                product_label(product_id, catalog),
                float(line["stream_minute"]),
                str(line.get("text", "")),
            )
        )

    if not anchors:
        return []

    transcript_end = max(float(line.get("stream_minute", 0)) for line in transcript)
    promo_end = promo_end_minute if promo_end_minute is not None else transcript_end
    segments: list[dict[str, Any]] = []
    for index, (product_id, name, start_minute, intro_text) in enumerate(anchors):
        end_minute = anchors[index + 1][2] if index + 1 < len(anchors) else promo_end
        segment_lines = [
            line
            for line in transcript
            if start_minute <= float(line.get("stream_minute", 0)) < end_minute
        ]
        segments.append(
            {
                "product_id": product_id,
                "product_name": name,
                "stream_minute_start": round(start_minute, 3),
                "stream_minute_end": round(end_minute, 3),
                "promo_minute_start": None,
                "promo_minute_end": None,
                "intro_text": intro_text,
                "transcript_line_count": len(segment_lines),
                "segment_source": "annotated_transcript"
                if any(str(line.get("product_id") or "").strip() for line in transcript)
                else "keyword_catalog",
            }
        )
    return segments


def product_label(product_id: str, product_catalog: ProductCatalog | None = None) -> str:
    for item_id, name, _keywords in product_catalog or PRODUCT_CATALOG:
        if item_id == product_id:
            return name
    return product_id


def analyze_product_chat_response(
    messages: list[ChatMessage],
    segments: list[dict[str, Any]],
    promo_start_minute: float,
    promo_end_minute: float | None = None,
    response_window_minutes: float = 3.0,
    product_catalog: ProductCatalog | None = None,
) -> list[dict[str, Any]]:
    expected_end = promo_end_minute if promo_end_minute is not None else (
        max(segment["stream_minute_end"] for segment in segments) if segments else promo_start_minute
    )
    aligned_messages, _timing_diagnostics = align_messages_to_window(
        messages,
        promo_start_minute,
        expected_end,
    )
    origin = stream_origin(aligned_messages)
    results: list[dict[str, Any]] = []
    catalog = product_catalog or PRODUCT_CATALOG

    for segment in segments:
        start = segment["stream_minute_start"]
        end = segment["stream_minute_end"]
        response_end = min(start + response_window_minutes, expected_end)

        segment_messages = audience_messages(aligned_messages, origin, start, end)
        response_messages = audience_messages(aligned_messages, origin, start, response_end)

        product_chat = [
            message
            for message in segment_messages
            if mentions_product(message.message, segment["product_id"], catalog)
        ]
        temu_chat = [message for message in segment_messages if "temu" in message.message.lower() or "kav3769" in message.message.lower()]

        response_sentiments = [score_sentiment(message.message) for message in response_messages]
        segment_sentiments = [score_sentiment(message.message) for message in segment_messages]
        sentiment_labels = Counter(sentiment_label(score) for score in segment_sentiments)
        intents: Counter[str] = Counter()
        for message in response_messages:
            intents.update(detect_intents(message.message))

        participation = analyze_participation_issues(
            aligned_messages,
            start,
            end,
            product_id=segment["product_id"],
            product_name=segment["product_name"],
        )

        results.append(
            {
                **segment,
                "promo_minute_start": round(start - promo_start_minute, 3),
                "promo_minute_end": round(end - promo_start_minute, 3),
                "presenting_period_minutes": round(end - start, 2),
                "headcount": {
                    "unique_chatters": len({message.user.lower() for message in segment_messages}),
                    "total_messages": len(segment_messages),
                    "messages_first_3min": len(response_messages),
                    "unique_chatters_first_3min": len({message.user.lower() for message in response_messages}),
                    "response_window_minutes": round(response_end - start, 3),
                },
                "viewer_sentiment": {
                    "avg_score": round(mean(segment_sentiments), 3) if segment_sentiments else 0.0,
                    "avg_score_first_3min": round(mean(response_sentiments), 3) if response_sentiments else 0.0,
                    "positive": sentiment_labels.get("positive", 0),
                    "neutral": sentiment_labels.get("neutral", 0),
                    "negative": sentiment_labels.get("negative", 0),
                    "positive_pct": round(
                        sentiment_labels.get("positive", 0) / max(len(segment_messages), 1) * 100,
                        1,
                    ),
                },
                "participation_issues": participation,
                "chat": {
                    "messages_in_segment": len(segment_messages),
                    "messages_first_3min": len(response_messages),
                    "unique_chatters": len({message.user.lower() for message in segment_messages}),
                    "messages_per_minute": round(
                        len(segment_messages) / max(end - start, 0.5),
                        2,
                    ),
                    "product_keyword_mentions": len(product_chat),
                    "temu_or_code_mentions": len(temu_chat),
                    "avg_sentiment_burst": round(mean(response_sentiments), 3) if response_sentiments else 0.0,
                    "intents_burst": dict(intents),
                },
                "response_score": score_product_response(
                    len(response_messages),
                    len({message.user.lower() for message in response_messages}),
                    len(product_chat),
                    len(temu_chat),
                    intents,
                    response_minutes=response_end - start,
                ),
            }
        )

    ranked = sorted(results, key=lambda item: item["response_score"], reverse=True)
    for rank, item in enumerate(ranked, start=1):
        item["response_rank"] = rank
    return ranked


def audience_messages(
    messages: list[ChatMessage],
    origin,
    start_minute: float,
    end_minute: float,
) -> list[ChatMessage]:
    window = filter_by_minutes(messages, start_minute, end_minute, origin)
    return [message for message in window if message.user.lower() not in DEFAULT_BOT_USERS]


def mentions_product(
    text: str,
    product_id: str,
    product_catalog: ProductCatalog | None = None,
) -> bool:
    lowered = text.lower()
    for item_id, _name, keywords in product_catalog or PRODUCT_CATALOG:
        if item_id == product_id and any(keyword.strip() in lowered for keyword in keywords):
            return True
    return False


def score_product_response(
    response_count: int,
    response_unique_chatters: int,
    product_mentions: int,
    temu_mentions: int,
    intents: Counter[str],
    response_minutes: float = 3.0,
) -> float:
    minutes = max(response_minutes, 0.5)
    message_rate = response_count / minutes
    unique_rate = response_unique_chatters / minutes
    score = message_rate * 3
    score += unique_rate * 5
    score += product_mentions * 3
    score += temu_mentions * 1.5
    score += intents.get("purchase_intent", 0) * 5
    score += intents.get("excitement", 0) * 3
    score -= intents.get("objection", 0) * 4
    score -= intents.get("confusion", 0) * 2
    return round(score, 2)


def annotate_transcript_products(
    transcript: list[dict[str, Any]],
    product_catalog: ProductCatalog | None = None,
) -> list[dict[str, Any]]:
    current_product = None
    annotated: list[dict[str, Any]] = []
    catalog = product_catalog or PRODUCT_CATALOG
    for line in transcript:
        detected = classify_product_line(str(line.get("text", "")), catalog)
        if detected:
            current_product = detected
        row = dict(line)
        row["product_id"] = current_product
        row["product_name"] = product_label(current_product, catalog) if current_product else ""
        annotated.append(row)
    return annotated


def build_product_analysis(
    transcript_document: dict[str, Any],
    messages: list[ChatMessage],
    promo_start_minute: float,
    promo_end_minute: float,
    product_catalog: ProductCatalog | None = None,
) -> dict[str, Any]:
    transcript = transcript_document.get("transcript", [])
    catalog = product_catalog or PRODUCT_CATALOG
    aligned_messages, timing_diagnostics = align_messages_to_window(
        messages,
        promo_start_minute,
        promo_end_minute,
    )
    segments = build_product_segments(transcript, catalog, promo_end_minute=promo_end_minute)
    ranked = analyze_product_chat_response(
        aligned_messages,
        segments,
        promo_start_minute,
        promo_end_minute=promo_end_minute,
        product_catalog=catalog,
    )

    promo_participation = analyze_participation_issues(
        aligned_messages,
        promo_start_minute,
        promo_end_minute,
        product_id="all_promo",
        product_name="Full promotion window",
    )

    return {
        "promo_window_minutes": [promo_start_minute, promo_end_minute],
        "data_quality": {
            **timing_diagnostics,
            "product_segment_count": len(ranked),
            "product_segment_source": "annotated_transcript"
            if any(str(line.get("product_id") or "").strip() for line in transcript)
            else "keyword_catalog",
            "notes": [
                "Headcount and sentiment are direct chat-window measurements.",
                "Sentiment, intent, and response_score are heuristic signals, not sales attribution.",
                "Product labels should be human-reviewed when generated from keywords or speech transcription.",
            ],
        },
        "product_segments": ranked,
        "best_product": ranked[0] if ranked else None,
        "promo_participation_issues": promo_participation,
        "summary": summarize_products(ranked),
        "headcount_summary": summarize_headcount(ranked),
        "sentiment_summary": summarize_sentiment(ranked),
        "participation_summary": summarize_participation(ranked, promo_participation),
    }


def summarize_headcount(ranked: list[dict[str, Any]]) -> str:
    if not ranked:
        return "No product periods detected."
    top = max(ranked, key=lambda item: item["headcount"]["unique_chatters"])
    return (
        f"Highest unique chatter headcount: {top['product_name']} "
        f"({top['headcount']['unique_chatters']} chatters, "
        f"stream min {top['stream_minute_start']}–{top['stream_minute_end']})."
    )


def summarize_sentiment(ranked: list[dict[str, Any]]) -> str:
    if not ranked:
        return "No sentiment data."
    best = max(ranked, key=lambda item: item["viewer_sentiment"]["avg_score"])
    worst = min(ranked, key=lambda item: item["viewer_sentiment"]["avg_score"])
    return (
        f"Most positive segment: {best['product_name']} "
        f"(avg {best['viewer_sentiment']['avg_score']}). "
        f"Most negative: {worst['product_name']} (avg {worst['viewer_sentiment']['avg_score']})."
    )


def summarize_participation(
    ranked: list[dict[str, Any]],
    promo_wide: dict[str, Any],
) -> str:
    if not ranked:
        return "No participation issue data."
    top = max(
        ranked,
        key=lambda item: item["participation_issues"]["issue_message_count"],
    )
    counts = promo_wide.get("issue_counts", {})
    top_issue = max(counts, key=counts.get) if counts else "none"
    return (
        f"Most participation friction during: {top['product_name']} "
        f"({top['participation_issues']['issue_message_count']} issue messages). "
        f"Promo-wide top issue type: {top_issue} ({counts.get(top_issue, 0)} mentions)."
    )


def summarize_products(ranked: list[dict[str, Any]]) -> str:
    if not ranked:
        return "No product segments detected in transcript."
    best = ranked[0]
    summary = (
        f"Strongest chat response: {best['product_name']} "
        f"(score {best['response_score']}, {best['chat']['messages_first_3min']} messages in first 3 min)."
    )
    if len(ranked) > 1:
        summary += f" Runner-up: {ranked[1]['product_name']} (score {ranked[1]['response_score']})."
    return summary
