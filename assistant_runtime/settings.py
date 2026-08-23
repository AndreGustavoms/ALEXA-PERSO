from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass(frozen=True)
class UserSettings:
    microphone_device: int | None = None
    update_channel: str = "stable"
    onboarding_complete: bool = False

    def __post_init__(self) -> None:
        if self.microphone_device is not None and self.microphone_device < 0:
            raise ValueError("microphone_device deve ser nulo ou positivo.")
        if self.update_channel not in {"stable", "beta", "dev"}:
            raise ValueError("Canal de atualizacao invalido.")


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._settings = self._load()

    def _load(self) -> UserSettings:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            allowed = {item.name for item in fields(UserSettings)}
            return UserSettings(**{key: value for key, value in payload.items() if key in allowed})
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return UserSettings()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return asdict(self._settings)

    def value(self) -> UserSettings:
        with self._lock:
            return self._settings

    def update(self, payload: dict[str, object]) -> UserSettings:
        allowed = {item.name for item in fields(UserSettings)}
        if set(payload) - allowed:
            raise ValueError("Configuracao desconhecida.")
        with self._lock:
            current = asdict(self._settings)
            current.update(payload)
            updated = UserSettings(**current)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(asdict(updated), indent=2), encoding="utf-8")
            temporary.replace(self.path)
            self._settings = updated
            return updated
