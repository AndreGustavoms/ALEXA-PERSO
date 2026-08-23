from __future__ import annotations

import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path

from ..app_paths import APP_DIRECTORY_NAME, APP_SLUG, is_frozen, resource_root


def executable_command() -> tuple[str, ...]:
    if is_frozen():
        return (str(Path(sys.executable)),)
    return (str(Path(sys.executable)), str(resource_root() / "assistant_runtime/main.py"))


def open_desktop_window(url: str) -> None:
    if sys.platform == "win32":
        candidates = (
            Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        )
        browser = next((candidate for candidate in candidates if candidate.exists()), None)
        if browser:
            subprocess.Popen(
                (str(browser), f"--app={url}", "--window-size=1180,820"),
                creationflags=0x00000008,
                close_fds=True,
            )
            return
    webbrowser.open(url)


def autostart_file() -> Path:
    if sys.platform == "win32":
        return (
            Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
            / "Microsoft/Windows/Start Menu/Programs/Startup/Doktor Assistant.cmd"
        )
    if sys.platform == "darwin":
        return Path.home() / "Library/LaunchAgents/com.doktor.assistant.plist"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "autostart/doktor-assistant.desktop"


def is_autostart_enabled() -> bool:
    return autostart_file().exists()


def set_autostart(enabled: bool) -> None:
    target = autostart_file()
    if not enabled:
        target.unlink(missing_ok=True)
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    command = executable_command()
    if sys.platform == "win32":
        quoted = " ".join(f'"{part}"' for part in command)
        target.write_text(f"@echo off\nstart \"\" /b {quoted}\n", encoding="utf-8")
        return
    if sys.platform == "darwin":
        arguments = "".join(f"<string>{part}</string>" for part in command)
        target.write_text(
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
            "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">\n"
            "<plist version=\"1.0\"><dict>"
            "<key>Label</key><string>com.doktor.assistant</string>"
            f"<key>ProgramArguments</key><array>{arguments}</array>"
            "<key>RunAtLoad</key><true/></dict></plist>\n",
            encoding="utf-8",
        )
        return
    executable = shutil.which(command[0]) or command[0]
    args = " ".join((executable, *command[1:]))
    target.write_text(
        "[Desktop Entry]\nType=Application\n"
        f"Name={APP_DIRECTORY_NAME}\nExec={args}\n"
        f"X-GNOME-Autostart-enabled=true\nStartupWMClass={APP_SLUG}\n",
        encoding="utf-8",
    )
