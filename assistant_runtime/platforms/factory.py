from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from .base import PlatformActions, PlatformInfo


def detect_platform() -> PlatformInfo:
    machine = platform.machine().lower() or "unknown"
    if sys.platform == "win32":
        return PlatformInfo(
            "windows", machine, "WindowsAdapter",
            ("tray", "autostart", "applications", "windows", "media", "system"),
        )
    if sys.platform == "darwin":
        return PlatformInfo(
            "macos", machine, "MacOSAdapter",
            ("menu-bar", "autostart", "applications", "folders", "web"),
        )
    if sys.platform.startswith("linux"):
        return PlatformInfo(
            "linux", machine, "LinuxAdapter",
            ("tray", "autostart", "applications", "folders", "web"),
        )
    return PlatformInfo(sys.platform, machine, "UnsupportedAdapter", ())


def create_platform_actions(
    *,
    resource_opener: Callable[[str], None] | None = None,
    program_starter: Callable[[tuple[str, ...]], None] | None = None,
    app_command_sender: Callable[[int, int], None] | None = None,
    now_provider: Callable[[], datetime] = datetime.now,
    shortcut_roots: tuple[Path, ...] | None = None,
    shortcut_sender: Callable[[tuple[str, ...]], None] | None = None,
    text_sender: Callable[[str], None] | None = None,
) -> PlatformActions:
    options: dict[str, object] = {"now_provider": now_provider}
    if resource_opener is not None:
        options["resource_opener"] = resource_opener
    if program_starter is not None:
        options["program_starter"] = program_starter
    if shortcut_roots is not None:
        options["shortcut_roots"] = shortcut_roots
    if sys.platform == "win32":
        from .windows import WindowsAdapter

        if app_command_sender is not None:
            options["app_command_sender"] = app_command_sender
        if shortcut_sender is not None:
            options["shortcut_sender"] = shortcut_sender
        if text_sender is not None:
            options["text_sender"] = text_sender
        return WindowsAdapter(**options)  # type: ignore[arg-type]
    if sys.platform == "darwin":
        from .macos import MacOSAdapter

        return MacOSAdapter(**options)  # type: ignore[arg-type]
    if sys.platform.startswith("linux"):
        from .linux import LinuxAdapter

        return LinuxAdapter(**options)  # type: ignore[arg-type]
    raise RuntimeError(f"Sistema operacional sem adapter: {sys.platform}")
