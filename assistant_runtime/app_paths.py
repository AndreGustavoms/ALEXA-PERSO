from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


APP_SLUG = "doktor-assistant"
APP_DIRECTORY_NAME = "Doktor Assistant"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root)
    return Path(__file__).resolve().parents[1]


def user_data_root() -> Path:
    if not is_frozen():
        return resource_root() / "runtime"
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return base / APP_DIRECTORY_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support" / APP_DIRECTORY_NAME
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return base / APP_SLUG


def user_config_root() -> Path:
    if not is_frozen():
        return user_data_root() / "config"
    if sys.platform == "linux":
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        return base / APP_SLUG
    return user_data_root() / "config"


@dataclass(frozen=True)
class AppPaths:
    resources: Path
    data: Path
    config: Path
    web: Path
    model: Path
    logs: Path
    assets: Path
    voice_config: Path
    wake_config: Path
    voice_models: Path
    stt_config: Path
    vocabulary: Path

    @classmethod
    def detect(cls) -> "AppPaths":
        resources = resource_root()
        data = user_data_root()
        config = user_config_root()
        runtime_resources = resources / "assistant_runtime"
        return cls(
            resources=resources,
            data=data,
            config=config,
            web=resources / "dist",
            model=resources / "runtime/models/vosk-model-small-pt-0.3",
            logs=data / "logs",
            assets=resources / "assets",
            voice_config=runtime_resources / "voice_config.json",
            wake_config=runtime_resources / "wake_word_config.json",
            voice_models=runtime_resources / "models",
            stt_config=runtime_resources / "stt_config.json",
            vocabulary=runtime_resources / "transcription_vocabulary.txt",
        )


PATHS = AppPaths.detect()
