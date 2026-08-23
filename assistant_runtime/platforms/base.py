from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..assistant_commands.models import ParsedIntent, WindowContext


class ApplicationCatalog(Protocol):
    def resolve(self, requested_name: str) -> object | None: ...


class PlatformActions(Protocol):
    apps: ApplicationCatalog

    def execute(self, intent: ParsedIntent, context: WindowContext) -> str: ...


@dataclass(frozen=True)
class PlatformInfo:
    system: str
    architecture: str
    adapter: str
    capabilities: tuple[str, ...]
