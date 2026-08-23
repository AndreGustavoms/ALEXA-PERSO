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
    match = re.search(r"\b(\d{1,3})\s*(?:por cento)?\b", text)
    if match:
        return int(match.group(1))

    units = {
        "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2,
        "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
        "sete": 7, "oito": 8, "nove": 9,
    }
    tens = {
        "dez": 10, "vinte": 20, "trinta": 30, "quarenta": 40,
        "cinquenta": 50, "sessenta": 60, "setenta": 70,
        "oitenta": 80, "noventa": 90, "cem": 100,
    }
    words = normalize_text(text).removesuffix(" por cento").split()
    if len(words) == 1:
        return tens.get(words[0], units.get(words[0]))
    if len(words) == 3 and words[0] in tens and words[1] == "e" and words[2] in units:
        return min(100, tens[words[0]] + units[words[2]])
    return None
