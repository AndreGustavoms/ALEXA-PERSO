from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from .models import ParsedIntent
from .normalization import normalize_text

CONFIRM_WORDS = {
    "sim",
    "pode",
    "confirma",
    "confirmado",
    "pode fazer",
    "isso",
}
CANCEL_WORDS = {
    "nao",
    "cancela",
    "cancelar",
    "deixa",
    "deixa quieto",
    "deixa pra la",
    "esquece",
    "nao faz",
}


@dataclass(frozen=True)
class ConfirmationResolution:
    state: str
    intent: ParsedIntent | None = None


class ConfirmationManager:
    def __init__(self, timeout_seconds: float = 15.0) -> None:
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._pending: ParsedIntent | None = None
        self._expires_at = 0.0

    def request(self, intent: ParsedIntent) -> None:
        with self._lock:
            self._pending = intent
            self._expires_at = time.monotonic() + self.timeout_seconds

    def resolve(self, transcript: str) -> ConfirmationResolution:
        text = normalize_text(transcript)
        with self._lock:
            if not self._pending:
                return ConfirmationResolution("none")
            if time.monotonic() >= self._expires_at:
                self._pending = None
                return ConfirmationResolution("expired")
            if text in CANCEL_WORDS:
                self._pending = None
                return ConfirmationResolution("cancelled")
            if text in CONFIRM_WORDS:
                intent = self._pending
                self._pending = None
                return ConfirmationResolution("confirmed", intent)
            return ConfirmationResolution("waiting")

    def has_pending(self) -> bool:
        with self._lock:
            if self._pending and time.monotonic() >= self._expires_at:
                self._pending = None
            return self._pending is not None

    def discard(self) -> None:
        with self._lock:
            self._pending = None
            self._expires_at = 0.0
