from __future__ import annotations

import re


def repair_mojibake_tr(text: str) -> str:
    """
    Best-effort fix for common mojibake cases where UTF-8 bytes were decoded as Latin-1/CP1252
    (e.g. 'trileÃ§e' instead of 'trileçe').

    Safe-guard: only attempts repair when typical mojibake marker chars are present.
    """
    if not text:
        return text
    # Common markers for Turkish characters when mis-decoded
    if not any(ch in text for ch in ("Ã", "Ä", "Å", "Ð", "Þ")):
        return text
    try:
        return text.encode("latin1").decode("utf-8")
    except Exception:
        return text


def normalize_space(text: str) -> str:
    text = repair_mojibake_tr(text)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_number(value: str) -> float | None:
    """
    Parses strings like:
    - "12", "12.5", "12,5", "12,5g", "12.5 g"
    Returns float or None.
    """
    if not value:
        return None
    m = re.search(r"(-?\d+(?:[.,]\d+)?)", value)
    if not m:
        return None
    num = m.group(1).replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def contains_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text, flags=re.IGNORECASE) is not None





