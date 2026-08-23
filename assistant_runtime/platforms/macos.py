from __future__ import annotations

from pathlib import Path

from .posix import PosixAdapter, PosixApplicationCatalog


class MacOSApplicationCatalog(PosixApplicationCatalog):
    ALIASES = {
        "chrome": ("Chrome", ("open", "-a", "Google Chrome")),
        "google chrome": ("Chrome", ("open", "-a", "Google Chrome")),
        "safari": ("Safari", ("open", "-a", "Safari")),
        "firefox": ("Firefox", ("open", "-a", "Firefox")),
        "discord": ("Discord", ("open", "-a", "Discord")),
        "spotify": ("Spotify", ("open", "-a", "Spotify")),
        "vs code": ("Visual Studio Code", ("open", "-a", "Visual Studio Code")),
        "calculadora": ("Calculadora", ("open", "-a", "Calculator")),
    }


class MacOSAdapter(PosixAdapter):
    def __init__(self, **options: object) -> None:
        super().__init__(**options)  # type: ignore[arg-type]
        self.apps = MacOSApplicationCatalog()

    def _open_path(self, path: Path) -> None:
        self.program_starter(("open", str(path)))
