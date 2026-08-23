from __future__ import annotations

from pathlib import Path

from .posix import PosixAdapter, PosixApplicationCatalog


class LinuxApplicationCatalog(PosixApplicationCatalog):
    ALIASES = {
        "chrome": ("Chrome", ("google-chrome",)),
        "google chrome": ("Chrome", ("google-chrome",)),
        "firefox": ("Firefox", ("firefox",)),
        "discord": ("Discord", ("discord",)),
        "spotify": ("Spotify", ("spotify",)),
        "steam": ("Steam", ("steam",)),
        "vs code": ("Visual Studio Code", ("code",)),
        "calculadora": ("Calculadora", ("gnome-calculator",)),
    }


class LinuxAdapter(PosixAdapter):
    def __init__(self, **options: object) -> None:
        super().__init__(**options)  # type: ignore[arg-type]
        self.apps = LinuxApplicationCatalog()

    def _open_path(self, path: Path) -> None:
        self.program_starter(("xdg-open", str(path)))
