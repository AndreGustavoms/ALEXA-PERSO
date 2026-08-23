from __future__ import annotations

from pathlib import Path
import sys


def _version_file() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root) / "VERSION"
    return Path(__file__).resolve().parents[1] / "VERSION"


def read_version() -> str:
    try:
        return _version_file().read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


__version__ = read_version()
