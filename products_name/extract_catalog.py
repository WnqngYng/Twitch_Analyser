"""
Gemini-based product elicitation from an influencer transcript CSV.

Sends the transcript to Google's Gemini API (free tier: Gemini 2.5 Flash or
Flash-Lite via Google AI Studio, no credit card required) in chunks and asks
it to identify each distinct product being shown/promoted, with an English
category name, a short label, and Italian keywords for downstream matching.

Output format matches PRODUCT_CATALOG used in products.py, with English
category names and no numeric "product_N_" prefixes:

    PRODUCT_CATALOG = [
        ("category_slug", "Readable English label", ("keyword1", "keyword2", ...)),
        ...
    ]

Setup:
    1. Get a free API key at https://aistudio.google.com/apikey (no card needed)
    2. export GEMINI_API_KEY=your_key_here

Usage:
    python3 elicit_products_gemini.py path/to/transcript.csv
"""

from __future__ import annotations

import csv
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# Free-tier model. Use "gemini-2.5-flash-lite" for higher RPD if you hit limits.
MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# Rows per chunk -- keeps each request well within the free tier's TPM limit.
CHUNK_SIZE = 250

# Free tier RPM is low (10 for Flash, 15 for Flash-Lite), so pause between calls.
SECONDS_BETWEEN_REQUESTS = 5


def load_rows(csv_path: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def chunk_rows(rows: list[dict], chunk_size: int) -> list[list[dict]]:
    return [rows[i:i + chunk_size] for i in range(0, len(rows), chunk_size)]


def format_chunk(rows: list[dict]) -> str:
    lines = []
    for r in rows:
        minute = r.get("stream_minute", "")
        it = r.get("text", "").strip()
        en = r.get("english", "").strip()
        lines.append(f"[{minute}] IT: {it} | EN: {en}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are analyzing a livestream transcript (Italian, with English \
translation) from an influencer "unboxing"/promo segment. Your job is to identify \
each distinct PHYSICAL PRODUCT being shown, unboxed, or promoted.

For each distinct product you find, return:
- "category_slug": short snake_case English category name (no numbers, no "product_N" prefixes), e.g. "led_light_panel", "phone_game_controller", "spicy_snack_pack"
- "label": short human-readable English label, e.g. "LED light panel"
- "keywords": 3-8 lowercase Italian (or transliterated) words/phrases that appear in the \
ORIGINAL ITALIAN TEXT and would reliably match mentions of this product later in the \
transcript (single words or short phrases, no punctuation, no accented-character issues \
that wouldn't match substrings)
- "approx_start_minute": the stream_minute where this product is first introduced/shown

Only include genuine distinct PHYSICAL PRODUCTS (skip generic chat, moderation, banter -- but \
DO include a general affiliate/app promo if one is present, e.g. a "use code X / download app" \
call to action).

Respond with ONLY a JSON array, no other text, no markdown fences. Example:

[
  {"category_slug": "led_light_panel", "label": "LED light panel", "keywords": ["led", "pannello"], "approx_start_minute": 20.7},
  {"category_slug": "phone_game_controller", "label": "Mobile gaming controller", "keywords": ["joystick", "telefono", "iphone", "cover"], "approx_start_minute": 23.9}
]
"""


def call_gemini(chunk_text: str, api_key: str) -> list[dict]:
    body = {
        "contents": [
            {"role": "user", "parts": [{"text": f"Transcript chunk:\n\n{chunk_text}"}]}
        ],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    req = urllib.request.Request(
        f"{API_URL}?key={api_key}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"HTTP {e.code} error from Gemini: {err_body}", file=sys.stderr)
        return []

    try:
        candidates = data["candidates"]
        parts = candidates[0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError):
        print("WARNING: unexpected Gemini response shape:", file=sys.stderr)
        print(json.dumps(data, indent=2), file=sys.stderr)
        return []

    # Strip markdown fences just in case.
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("WARNING: could not parse model output as JSON:", file=sys.stderr)
        print(text, file=sys.stderr)
        return []


def merge_products(all_products: list[dict]) -> list[dict]:
    """Merge duplicate/overlapping product entries (same category_slug)
    across chunks, unioning their keywords and keeping the earliest
    approx_start_minute."""
    merged: dict[str, dict] = {}
    for p in all_products:
        slug = p["category_slug"]
        if slug not in merged:
            merged[slug] = {
                "category_slug": slug,
                "label": p["label"],
                "keywords": list(dict.fromkeys(p.get("keywords", []))),
                "approx_start_minute": p.get("approx_start_minute", 0),
            }
        else:
            existing = merged[slug]
            for kw in p.get("keywords", []):
                if kw not in existing["keywords"]:
                    existing["keywords"].append(kw)
            existing["approx_start_minute"] = min(
                existing["approx_start_minute"],
                p.get("approx_start_minute", existing["approx_start_minute"]),
            )

    return sorted(merged.values(), key=lambda x: x["approx_start_minute"])


def infer_output_path(csv_path: str | Path) -> Path:
    source = Path(csv_path)
    stem = source.stem
    if stem.endswith("_influencer_transcript"):
        vod_id = stem.removesuffix("_influencer_transcript")
        return source.with_name(f"{vod_id}_product_catalog.json")
    return source.with_name(f"{stem}_product_catalog.json")


def product_catalog_document(products: list[dict], source_csv: str | Path) -> dict:
    return {
        "schema_version": "1",
        "source": "gemini",
        "source_transcript_csv": str(Path(source_csv)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "products": [
            {
                "product_id": product["category_slug"],
                "product_name": product["label"],
                "keywords": product.get("keywords", []),
                "approx_start_minute": product.get("approx_start_minute"),
            }
            for product in products
        ],
    }


def print_python_catalog(products: list[dict]) -> None:
    print("PRODUCT_CATALOG = [")
    for product in products:
        kw_repr = ", ".join(repr(keyword) for keyword in product["keywords"])
        if len(product["keywords"]) == 1:
            kw_repr += ","
        print(f'    ("{product["category_slug"]}", "{product["label"]}", ({kw_repr})),')
    print("]")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract a per-VOD product catalog from an influencer transcript CSV using Gemini."
    )
    parser.add_argument("transcript_csv", help="data/<vod>/<vod>_influencer_transcript.csv")
    parser.add_argument("--out", default=None, help="Output product catalog JSON path.")
    parser.add_argument(
        "--print-python",
        action="store_true",
        help="Also print a PRODUCT_CATALOG snippet for debugging/backward compatibility.",
    )
    args = parser.parse_args(argv)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: set GEMINI_API_KEY (get a free key at https://aistudio.google.com/apikey)", file=sys.stderr)
        return 1

    rows = load_rows(args.transcript_csv)
    chunks = chunk_rows(rows, CHUNK_SIZE)

    all_products = []
    for i, chunk in enumerate(chunks, start=1):
        print(f"Processing chunk {i}/{len(chunks)}...", file=sys.stderr)
        chunk_text = format_chunk(chunk)
        products = call_gemini(chunk_text, api_key)
        all_products.extend(products)
        if i < len(chunks):
            time.sleep(SECONDS_BETWEEN_REQUESTS)

    merged = merge_products(all_products)
    out_path = Path(args.out) if args.out else infer_output_path(args.transcript_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(product_catalog_document(merged, args.transcript_csv), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"Wrote product catalog: {out_path.resolve()}")
    print(f"Products: {len(merged)}")
    if args.print_python:
        print_python_catalog(merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
