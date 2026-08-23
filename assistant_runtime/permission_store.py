from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TERMS_VERSION = 1
PERMISSION_LEVEL = "total-user"


class PermissionStore:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.lock = threading.Lock()
        self.data = self._load()

    def _default_data(self) -> dict[str, Any]:
        return {
            "accepted": False,
            "acceptedAt": None,
            "level": PERMISSION_LEVEL,
            "termsVersion": TERMS_VERSION,
        }

    def _load(self) -> dict[str, Any]:
        try:
            stored = json.loads(self.file_path.read_text(encoding="utf-8"))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return self._default_data()

        if (
            not isinstance(stored, dict)
            or stored.get("termsVersion") != TERMS_VERSION
            or not isinstance(stored.get("accepted"), bool)
        ):
            return self._default_data()

        return {
            "accepted": stored["accepted"],
            "acceptedAt": stored.get("acceptedAt"),
            "level": PERMISSION_LEVEL,
            "termsVersion": TERMS_VERSION,
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return dict(self.data)

    def is_accepted(self) -> bool:
        with self.lock:
            return bool(self.data["accepted"])

    def set_accepted(self, accepted: bool) -> dict[str, Any]:
        with self.lock:
            self.data = {
                "accepted": accepted,
                "acceptedAt": (
                    datetime.now(timezone.utc).isoformat() if accepted else None
                ),
                "level": PERMISSION_LEVEL,
                "termsVersion": TERMS_VERSION,
            }
            self._persist()
            return dict(self.data)

    def _persist(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = self.file_path.with_suffix(".tmp")
        temporary_file.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_file.replace(self.file_path)
