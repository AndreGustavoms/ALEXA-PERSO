from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RiskLevel(StrEnum):
    SAFE = "safe"
    CONTEXTUAL = "contextual"
    CONFIRMATION_REQUIRED = "confirmation_required"
    BLOCKED = "blocked"


class CommandIntent(StrEnum):
    OPEN_APPLICATION = "OPEN_APPLICATION"
    CLOSE_APPLICATION = "CLOSE_APPLICATION"
    MINIMIZE_APPLICATION = "MINIMIZE_APPLICATION"
    MAXIMIZE_APPLICATION = "MAXIMIZE_APPLICATION"
    FOCUS_APPLICATION = "FOCUS_APPLICATION"
    OPEN_URL = "OPEN_URL"
    SEARCH_WEB = "SEARCH_WEB"
    OPEN_YOUTUBE = "OPEN_YOUTUBE"
    SEARCH_YOUTUBE = "SEARCH_YOUTUBE"
    OPEN_YOUTUBE_RESULT = "OPEN_YOUTUBE_RESULT"
    PLAY = "PLAY"
    PAUSE = "PAUSE"
    NEXT = "NEXT"
    PREVIOUS = "PREVIOUS"
    VOLUME_UP = "VOLUME_UP"
    VOLUME_DOWN = "VOLUME_DOWN"
    SET_VOLUME = "SET_VOLUME"
    MUTE = "MUTE"
    UNMUTE = "UNMUTE"
    UNKNOWN = "UNKNOWN"


def intent_kind_for(command_id: str, parameters: dict[str, Any]) -> CommandIntent:
    if command_id in {"application.close", "browser.close_tab", "window.close"}:
        return CommandIntent.CLOSE_APPLICATION
    if command_id == "application.open":
        return CommandIntent.OPEN_APPLICATION
    if command_id in {"browser.open_site", "browser.open_url", "browser.open"}:
        target = str(parameters.get("target", ""))
        return CommandIntent.OPEN_YOUTUBE if "youtube" in target else CommandIntent.OPEN_URL
    if command_id == "browser.search":
        return (
            CommandIntent.SEARCH_YOUTUBE
            if parameters.get("destination") == "youtube"
            else CommandIntent.SEARCH_WEB
        )
    if command_id == "window.minimize":
        return CommandIntent.MINIMIZE_APPLICATION
    if command_id == "window.maximize":
        return CommandIntent.MAXIMIZE_APPLICATION
    if command_id == "audio.volume_up":
        return CommandIntent.VOLUME_UP
    if command_id == "audio.volume_down":
        return CommandIntent.VOLUME_DOWN
    if command_id == "audio.set_volume":
        return CommandIntent.SET_VOLUME
    if command_id == "audio.mute":
        return CommandIntent.MUTE
    if command_id == "audio.unmute":
        return CommandIntent.UNMUTE
    if command_id == "media.next":
        return CommandIntent.NEXT
    if command_id == "media.previous":
        return CommandIntent.PREVIOUS
    if command_id == "media.play_pause":
        return CommandIntent.PLAY
    return CommandIntent.UNKNOWN


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
    source: str = "deterministic"

    @property
    def kind(self) -> CommandIntent:
        return intent_kind_for(self.spec.id, self.parameters)


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
