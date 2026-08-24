from __future__ import annotations

import re
from dataclasses import replace

from .entities import EntityResolver
from .models import ParsedIntent, WindowContext
from .normalization import is_actionable_command, normalize_natural_command
from .parser import IntentParser, WEBSITES


SEMANTIC_CLOSE_WORDS = re.compile(
    r"\b(?:remove|remova|some com|dispensa|derruba|tira|fecha|encerra|finaliza)\b"
)
CONTEXT_TARGETS = re.compile(r"\b(?:isso|esse|essa|dai|da tela|a aba|a pagina)\b")


class SemanticIntentClassifier:
    """Conservative local fallback that emits intents, never executable text."""

    def __init__(self, parser: IntentParser) -> None:
        self.parser = parser
        self.entities = EntityResolver()

    def classify(
        self,
        transcript: str,
        context: WindowContext,
        previous_target: str = "",
    ) -> ParsedIntent | None:
        if not is_actionable_command(transcript):
            return None
        text = normalize_natural_command(transcript)
        if not SEMANTIC_CLOSE_WORDS.search(text):
            return None
        if re.search(r"\b(?:pagina|aba)\b", text) and context.kind != "browser":
            return None

        resolved = self.entities.resolve(text)
        target = resolved.value if resolved.confidence else ""
        if target not in WEBSITES and resolved.method == "unresolved":
            target = next(
                (
                    canonical
                    for canonical, aliases in self.entities.aliases.items()
                    if any(re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text) for alias in aliases)
                ),
                "",
            )

        if target:
            canonical = f"fecha {target}"
        elif CONTEXT_TARGETS.search(text):
            canonical = "fecha isso"
        else:
            return None

        parsed = self.parser.parse(canonical, context, previous_target)
        if not parsed:
            return None
        return replace(
            parsed,
            confidence=min(parsed.confidence, 0.9),
            normalized_text=normalize_natural_command(transcript),
            source="semantic-local",
        )
