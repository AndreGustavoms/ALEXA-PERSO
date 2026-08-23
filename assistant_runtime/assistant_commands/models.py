from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    SAFE = "safe"
    CONTEXTUAL = "contextual"
    CONFIRMATION_REQUIRED = "confirmation_required"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class WindowContext:
    handle: int = 0
    process_id: int = 0
    process_name: str = ""
    title: str = ""
    application: str = ""
    kind: str = "unknown"

    @property
    def available(self) -> bool:
        return bool(self.handle)


@dataclass(frozen=True)
class CommandSpec:
    id: str
    name: str
    category: str
    description: str
    aliases: tuple[str, ...]
    executor: str
    risk: RiskLevel = RiskLevel.SAFE
    confirmation_prompt: str = ""
    success_message: str = "Feito."
    error_message: str = "Nao consegui fazer isso."
    executor_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedIntent:
    spec: CommandSpec
    parameters: dict[str, Any]
    confidence: float
    normalized_text: str


@dataclass(frozen=True)
class CommandResult:
    matched: bool
    executed: bool
    response: str
    action: str = ""
    intent_name: str = ""
    risk: RiskLevel = RiskLevel.SAFE
    status: str = "completed"
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0

    def as_state(self) -> dict[str, str | bool | float] | None:
        if not self.matched:
            return None
        return {
            "id": self.action,
            "name": self.intent_name or self.action,
            "executed": self.executed,
            "risk": self.risk.value,
            "status": self.status,
            "confidence": self.confidence,
        }
