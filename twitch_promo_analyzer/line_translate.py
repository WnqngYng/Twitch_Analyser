from __future__ import annotations

import time
from typing import Iterable


def translate_italian_lines(
    lines: Iterable[str],
    *,
    batch_size: int = 25,
    pause_seconds: float = 0.4,
) -> list[str]:
    try:
        from deep_translator import GoogleTranslator
    except ImportError as exc:
        import sys

        raise ImportError(
            f"Install deep-translator for the Python running this script ({sys.executable}):\n"
            f"  {sys.executable} -m pip install deep-translator\n"
            "Or skip translation: add --skip-translate to the command."
        ) from exc

    translator = GoogleTranslator(source="it", target="en")
    texts = [text.strip() for text in lines]
    translated: list[str] = []

    for start in range(0, len(texts), batch_size):
        chunk = texts[start : start + batch_size]
        for text in chunk:
            if not text:
                translated.append("")
                continue
            try:
                translated.append(translator.translate(text[:4500]))
            except Exception:
                translated.append("")
        if start + batch_size < len(texts):
            time.sleep(pause_seconds)

    return translated
