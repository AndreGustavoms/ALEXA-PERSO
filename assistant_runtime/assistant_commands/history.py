from __future__ import annotations

import threading
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class HistoryEntry:
    timestamp: str
    transcript: str
    intent: str
    parameters: dict[str, Any]
    confidence: float
    executed: bool
    response: str


class CommandHistory:
    def __init__(self, capacity: int = 20) -> None:
        self._entries: deque[HistoryEntry] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def add(
        self,
        transcript: str,
        intent: str,
        parameters: dict[str, Any],
        confidence: float,
        executed: bool,
        response: str,
    ) -> None:
        entry = HistoryEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            transcript=transcript[:240],
            intent=intent,
            parameters=dict(parameters),
            confidence=confidence,
            executed=executed,
            response=response,
        )
        with self._lock:
            self._entries.append(entry)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(entry) for entry in self._entries]

    def last_target(self) -> str:
        with self._lock:
            for entry in reversed(self._entries):
                target = entry.parameters.get("application") or entry.parameters.get("target")
                if isinstance(target, str) and target and not target.startswith(("http://", "https://", "ms-settings:", "shell:")):
                    return target
        return ""
