from __future__ import annotations

import re
import unicodedata

WAKE_PREFIX = re.compile(
    r"^(?:(?:ola)\s+)?(?:doktor|doutor)[,:]?\s+"
)
POLITE_SUFFIX = re.compile(
    r"\s+(?:por favor|para mim|pra mim|se puder|por gentileza)$"
)
FILLER_PREFIX = re.compile(
    r"^(?:(?:bom|bem|entao)[, ]+)?(?:eu )?(?:queria|gostaria)(?: que)? "
    r"(?:voce )?"
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    without_accents = "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    )
    clean = without_accents.lower().replace("%", " por cento ")
    clean = re.sub(r"[^a-z0-9.:/\\?&=_#\-\s]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    clean = WAKE_PREFIX.sub("", clean)
    clean = FILLER_PREFIX.sub("", clean)
    clean = re.sub(r"^(?:poderia (?:voce )?|pode voce )", "", clean)
    clean = POLITE_SUFFIX.sub("", clean)
    return clean.strip()


def contains_term(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def extract_percent(text: str) -> int | None:
    match = re.search(r"\b(100|[1-9]?\d)\s*(?:por cento)?\b", text)
    if not match:
        return None
    return max(0, min(100, int(match.group(1))))
