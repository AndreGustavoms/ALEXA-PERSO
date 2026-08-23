from __future__ import annotations

import shutil
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus

from ..assistant_commands.models import ParsedIntent, WindowContext
from ..assistant_commands.normalization import normalize_text


class PosixApplicationCatalog:
    ALIASES: dict[str, tuple[str, tuple[str, ...]]] = {}

    def resolve(self, requested_name: str) -> tuple[str, tuple[str, ...]] | None:
        known = self.ALIASES.get(normalize_text(requested_name))
        if not known:
            return None
        label, commands = known
        executable = shutil.which(commands[0])
        return (label, (executable, *commands[1:])) if executable else None


class PosixAdapter:
    def __init__(
        self,
        *,
        resource_opener: Callable[[str], None] = webbrowser.open,
        program_starter: Callable[[tuple[str, ...]], None] | None = None,
        now_provider: Callable[[], datetime] = datetime.now,
        shortcut_roots: tuple[Path, ...] | None = None,
    ) -> None:
        del shortcut_roots
        self.resource_opener = resource_opener
        self.program_starter = program_starter or self._start_program
        self.now_provider = now_provider
        self.apps = PosixApplicationCatalog()

    @staticmethod
    def _start_program(arguments: tuple[str, ...]) -> None:
        subprocess.Popen(
            arguments,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def execute(self, intent: ParsedIntent, context: WindowContext) -> str:
        handler = getattr(self, f"do_{intent.spec.executor}", None)
        if not callable(handler):
            raise RuntimeError("Este comando ainda nao e suportado nesta plataforma.")
        return str(handler(intent, context) or self._format_success(intent))

    @staticmethod
    def _format_success(intent: ParsedIntent) -> str:
        try:
            return intent.spec.success_message.format(**intent.parameters)
        except (KeyError, ValueError):
            return intent.spec.success_message

    def do_clarify(self, intent: ParsedIntent, _context: WindowContext) -> str:
        return intent.spec.success_message

    def do_unsupported(self, intent: ParsedIntent, _context: WindowContext) -> str:
        raise RuntimeError(intent.spec.error_message)

    def do_open_resource(self, intent: ParsedIntent, _context: WindowContext) -> str:
        self.resource_opener(str(intent.parameters["target"]))
        return self._format_success(intent)

    def do_open_folder(self, intent: ParsedIntent, _context: WindowContext) -> str:
        self._open_path(Path(str(intent.parameters["target"])))
        return self._format_success(intent)

    def do_open_named_folder(self, intent: ParsedIntent, _context: WindowContext) -> str:
        requested = normalize_text(str(intent.parameters["name"]))
        matches = [path for path in Path.home().iterdir() if path.is_dir() and normalize_text(path.name) == requested]
        if len(matches) != 1:
            raise FileNotFoundError(f"Pasta nao encontrada: {requested}")
        self._open_path(matches[0])
        return self._format_success(intent)

    def _open_path(self, path: Path) -> None:
        raise NotImplementedError

    def do_open_application(self, intent: ParsedIntent, _context: WindowContext) -> str:
        resolved = self.apps.resolve(str(intent.parameters["application"]))
        if not resolved:
            raise FileNotFoundError("Aplicativo nao encontrado.")
        label, command = resolved
        self.program_starter(command)
        return f"Abri {label}."

    def do_web_search(self, intent: ParsedIntent, _context: WindowContext) -> str:
        query = quote_plus(str(intent.parameters["query"]))
        base = "https://www.youtube.com/results?search_query=" if intent.parameters["destination"] == "youtube" else "https://www.google.com/search?q="
        self.resource_opener(base + query)
        return self._format_success(intent)

    def do_tell_time(self, _intent: ParsedIntent, _context: WindowContext) -> str:
        return f"Agora são {self.now_provider():%H:%M}."

    def do_tell_date(self, _intent: ParsedIntent, _context: WindowContext) -> str:
        return f"Hoje é dia {self.now_provider():%d/%m/%Y}."

    def do_tell_weekday(self, _intent: ParsedIntent, _context: WindowContext) -> str:
        names = ("segunda-feira", "terca-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sabado", "domingo")
        return f"Hoje é {names[self.now_provider().weekday()]} .".replace("  ", " ")
