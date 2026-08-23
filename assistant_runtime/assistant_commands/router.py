from __future__ import annotations

import re

from .models import ParsedIntent, WindowContext
from .normalization import normalize_text
from .parser import IntentParser


COMMAND_START = (
    r"(?:abre|abra|abrir|inicia|inicie|iniciar|entra|entre|entrar|"
    r"fecha|feche|fechar|encerra|encerre|encerrar|"
    r"aumenta|aumente|abaixa|abaixe|diminui|diminua|reduz|"
    r"pesquisa|pesquise|procura|procure|busca|busque|"
    r"minimiza|maximiza|muta|desmuta|toca|pausa|"
    r"escreve|escreva|digita|digite|aperta|aperte|pressiona|pressione)"
)
COMPOUND_BOUNDARY = re.compile(
    rf"\s+(?:e\s+depois|depois|e)\s+(?={COMMAND_START}\b)"
)


class CommandRouter:
    """Turns one transcript into validated intents before execution begins."""

    def __init__(self, parser: IntentParser) -> None:
        self.parser = parser

    def parse(self, transcript: str, context: WindowContext) -> tuple[ParsedIntent, ...]:
        text = normalize_text(transcript)
        clauses = tuple(
            clause.strip()
            for clause in COMPOUND_BOUNDARY.split(text, maxsplit=4)
            if clause.strip()
        )
        if len(clauses) == 1:
            intent = self.parser.parse(text, context)
            return (intent,) if intent else ()

        intents: list[ParsedIntent] = []
        for clause in clauses:
            intent = self.parser.parse(clause, context)
            if intent is None:
                return ()
            intents.append(intent)
        return tuple(intents)
