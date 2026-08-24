from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .normalization import normalize_text


ENTITY_ALIASES = {
    "youtube": ("youtube", "you tube", "yutube", "iutube", "yt", "you tubi", "youtubee", "you tu be"),
    "chrome": ("chrome", "google chrome", "crome"),
    "edge": ("edge", "microsoft edge"),
    "firefox": ("firefox", "fire fox"),
    "spotify": ("spotify", "spotfy", "spotifi"),
    "whats app": ("whatsapp", "whats app", "zap"),
    "valorant": (
        "valorant",
        "valorante",
        "valor antes",
        "valor ante",
        "valora antes",
    ),
    "github": ("github", "git hub"),
    "google": ("google",),
    "gmail": ("gmail",),
    "instagram": ("instagram",),
    "netflix": ("netflix",),
    "facebook": ("facebook",),
    "discord": ("discord",),
    "steam": ("steam",),
    "riot": ("riot",),
    "vs code": ("vs code", "visual studio code"),
}


@dataclass(frozen=True)
class EntityMatch:
    value: str
    confidence: float
    method: str


class EntityResolver:
    def __init__(self, aliases: dict[str, tuple[str, ...]] = ENTITY_ALIASES) -> None:
        self.aliases = aliases
        self._lookup = {
            normalize_text(alias): canonical
            for canonical, variants in aliases.items()
            for alias in variants
        }

    def resolve(
        self,
        value: str,
        *,
        allowed: set[str] | None = None,
        threshold: float = 0.82,
    ) -> EntityMatch:
        clean = normalize_text(value)
        clean = clean.removeprefix("o ").removeprefix("a ").strip()
        exact = self._lookup.get(clean)
        if exact and (allowed is None or exact in allowed):
            method = "exact" if clean == exact else "alias"
            return EntityMatch(exact, 1.0 if method == "exact" else 0.98, method)

        candidates = [
            (SequenceMatcher(None, clean, alias).ratio(), canonical)
            for alias, canonical in self._lookup.items()
            if allowed is None or canonical in allowed
        ]
        candidates.sort(reverse=True)
        if not candidates or candidates[0][0] < threshold:
            return EntityMatch(clean, 0.0, "unresolved")
        if len(candidates) > 1 and candidates[0][1] != candidates[1][1] and candidates[0][0] - candidates[1][0] < 0.08:
            return EntityMatch(clean, 0.0, "ambiguous")
        return EntityMatch(candidates[0][1], round(candidates[0][0], 3), "fuzzy")
