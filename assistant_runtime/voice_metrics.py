from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class VoiceMetrics:
    """Small aggregate metrics store. It never persists raw audio or API keys."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {
            "activations": 0,
            "transcriptions": 0,
            "errors": 0,
            "fallbacks": 0,
            "audioSeconds": 0.0,
            "lastLatencyMs": 0,
            "lastProvider": "",
            "estimatedCostUsd": None,
        }
        self._load()

    def _load(self) -> None:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return
        if isinstance(payload, dict):
            self._data.update(
                {key: payload[key] for key in self._data if key in payload}
            )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def activation(self) -> None:
        with self._lock:
            self._data["activations"] += 1
            self._save()

    def transcription(
        self,
        *,
        provider: str,
        audio_seconds: float,
        latency_ms: int,
        fallback: bool = False,
    ) -> None:
        with self._lock:
            self._data["transcriptions"] += 1
            self._data["audioSeconds"] = round(
                float(self._data["audioSeconds"]) + audio_seconds,
                2,
            )
            self._data["lastLatencyMs"] = max(0, latency_ms)
            self._data["lastProvider"] = provider
            if fallback:
                self._data["fallbacks"] += 1
            self._save()

    def error(self) -> None:
        with self._lock:
            self._data["errors"] += 1
            self._save()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)
