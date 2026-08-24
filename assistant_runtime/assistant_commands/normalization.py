from __future__ import annotations

import re
import unicodedata

WAKE_PREFIX = re.compile(
    r"^(?:(?:po|ei)\s+)?(?:(?:ola)\s+)?(?:doktor|doutor)[,:]?\s+"
)
POLITE_SUFFIX = re.compile(
    r"\s+(?:por favor|para mim|pra mim|se puder|por gentileza)$"
)
FILLER_PREFIX = re.compile(
    r"^(?:(?:bom|bem|entao)[, ]+)?(?:eu )?(?:queria|gostaria)(?: que)? "
    r"(?:voce )?"
)

REQUEST_PREFIX = re.compile(
    r"^(?:(?:eu )?confirmo )?(?:doktor )?"
    r"(?:(?:voce )?(?:pode|consegue)(?: por favor)? |"
    r"(?:eu )?quero (?:que )?|gostaria (?:que )?)"
)
ACTION_START = re.compile(
    r"^(?:fecha|feche|fechar|encerra|encerre|encerrar|finaliza|finalize|finalizar|"
    r"mata|matar|tira|tire|tirar|sai|sair|abre|abra|abrir|inicia|inicie|iniciar|"
    r"bota|botar|minimiza|minimize|minimizar|maximiza|maximize|maximizar|"
    r"restaura|restaure|restaurar|foca|foque|focar|troca|troque|alternar|"
    r"pesquisa|pesquise|pesquisar|procura|procure|procurar|busca|busque|buscar|"
    r"aumenta|aumente|aumentar|abaixa|abaixe|abaixar|diminui|diminua|diminuir|"
    r"reduz|reduzir|muta|desmuta|toca|tocar|pause|pausa|pausar|play|proxima|anterior)\b"
)
SOFTENERS = re.compile(
    r"\b(?:por favor|pra mim|para mim|ai|dai|rapidinho|por gentileza)\b"
)
CONTEXT_REFERENCES = re.compile(
    r"\b(?:ele|ela|esse negocio|essa coisa|isso daqui|isso ai)\b"
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


def normalize_natural_command(value: str) -> str:
    """Remove conversational framing while preserving intent parameters."""
    text = normalize_text(value).removesuffix("?").strip()
    previous = ""
    while text != previous:
        previous = text
        text = REQUEST_PREFIX.sub("", text).strip()

    if not ACTION_START.match(text):
        return text

    text = CONTEXT_REFERENCES.sub("isso", text)
    text = SOFTENERS.sub(" ", text)
    text = re.sub(r"\b(?:aqui|daqui)\s*$", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    replacements = (
        (r"^(?:fecha|feche|fechar)\b", "fecha"),
        (r"^(?:encerra|encerre|encerrar|finaliza|finalize|finalizar|mata|matar)\b", "fecha"),
        (
            r"^(?:tira|tire|tirar)\s+"
            r"(?!(?:(?:um |uma )?(?:print|screenshot|captura)|(?:o )?som (?:do )?mudo)(?:\s|$))",
            "fecha ",
        ),
        (r"^(?:sai|sair)\s+(?:do|da|de)\b", "fecha"),
        (r"^(?:bota|botar)\b", "abre"),
        (r"^(?:abra|abrir)\b", "abre"),
        (r"^(?:inicie|iniciar)\b", "inicia"),
        (r"^aumentar\b", "aumenta"),
        (r"^abaixar\b", "abaixa"),
        (r"^diminuir\b", "diminui"),
        (r"^reduzir\b", "reduz"),
        (r"^minimizar\b", "minimiza"),
        (r"^maximizar\b", "maximiza"),
        (r"^pausar\b", "pausa"),
        (r"^tocar\b", "toca"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text.strip()


NON_ACTIONABLE = (
    re.compile(r"^nao\s+(?:fecha|feche|fechar|encerra|finaliza|tira)\b"),
    re.compile(r"^(?:como|quando|por que|porque)\s+(?:fecha|fechar|encerra|finaliza|tira)\b"),
    re.compile(r"\b(?:eu|voce|ele|ela)\s+(?:fechei|fechou|encerrou|finalizou)\b"),
    re.compile(r"\b(?:deveria|devia|poderia ser melhor)\s+(?:fechar|encerrar|finalizar)\b"),
    re.compile(r"^sera que\b"),
)


def is_actionable_command(value: str) -> bool:
    """Reject negated, retrospective and informational close phrases."""
    text = normalize_text(value).removesuffix("?").strip()
    return not any(pattern.search(text) for pattern in NON_ACTIONABLE)


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
