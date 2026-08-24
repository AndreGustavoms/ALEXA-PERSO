from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import subprocess
import time
from ctypes import wintypes
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus

from .context import process_name_for_pid
from .models import ParsedIntent, WindowContext
from .normalization import normalize_text

DETACHED_PROCESS = 0x00000008
WM_APPCOMMAND = 0x0319
WM_CLOSE = 0x0010
HWND_BROADCAST = 0xFFFF
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
INPUT_KEYBOARD = 1

VK = {
    "ALT": 0x12, "CTRL": 0x11, "SHIFT": 0x10, "WIN": 0x5B,
    "TAB": 0x09, "ENTER": 0x0D, "ESC": 0x1B, "LEFT": 0x25, "UP": 0x26,
    "RIGHT": 0x27, "HOME": 0x24, "DELETE": 0x2E, "PRINTSCREEN": 0x2C,
    "F2": 0x71, "F11": 0x7A, "+": 0xBB, "-": 0xBD,
}
VK.update({character: ord(character) for character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"})

APP_ALIASES = {
    "chrome": ("Chrome", "chrome.exe"),
    "google chrome": ("Chrome", "chrome.exe"),
    "edge": ("Edge", "msedge.exe"),
    "microsoft edge": ("Edge", "msedge.exe"),
    "firefox": ("Firefox", "firefox.exe"),
    "discord": ("Discord", "Discord.exe"),
    "whats app": ("WhatsApp", "WhatsApp.exe"),
    "valorant": ("Valorant", "RiotClientServices.exe"),
    "riot": ("Riot Games", "RiotClientServices.exe"),
    "spotify": ("Spotify", "Spotify.exe"),
    "steam": ("Steam", "steam.exe"),
    "vs code": ("Visual Studio Code", "Code.exe"),
    "visual studio code": ("Visual Studio Code", "Code.exe"),
    "code": ("Visual Studio Code", "Code.exe"),
    "bloco de notas": ("Bloco de Notas", "notepad.exe"),
    "notepad": ("Bloco de Notas", "notepad.exe"),
    "calculadora": ("Calculadora", "calc.exe"),
    "explorador": ("Explorador", "explorer.exe"),
    "explorador de arquivos": ("Explorador", "explorer.exe"),
    "terminal": ("Terminal", "wt.exe"),
    "windows terminal": ("Terminal", "wt.exe"),
    "powershell": ("PowerShell", "powershell.exe"),
    "cmd": ("Prompt de Comando", "cmd.exe"),
    "prompt de comando": ("Prompt de Comando", "cmd.exe"),
    "paint": ("Paint", "mspaint.exe"),
    "ferramenta de captura": ("Ferramenta de Captura", "SnippingTool.exe"),
    "gerenciador de tarefas": ("Gerenciador de Tarefas", "taskmgr.exe"),
}

CLOSE_PROCESS_ALIASES = {
    **{name: (data[1].lower(),) for name, data in APP_ALIASES.items()},
    "valorant": ("valorant-win64-shipping.exe", "riotclientservices.exe"),
}


def resolve_running_window_handles(
    requested_name: str,
    windows: list[tuple[int, str, str]],
    threshold: float = 0.82,
) -> tuple[int, ...]:
    """Resolve a spoken app name against visible process names and titles."""
    requested = normalize_text(requested_name)
    expected_processes = CLOSE_PROCESS_ALIASES.get(requested, ())
    exact_process = tuple(
        handle
        for handle, process_name, _title in windows
        if process_name.lower() in expected_processes
    )
    if exact_process:
        return exact_process

    ranked: list[tuple[float, int, str]] = []
    for handle, process_name, title in windows:
        process = normalize_text(process_name.removesuffix(".exe").replace("_", " "))
        normalized_title = normalize_text(title)
        title_parts = tuple(
            part.strip()
            for part in re.split(r"\s+(?:-|\|)\s+", normalized_title)
            if part.strip()
        )
        score = SequenceMatcher(None, requested, process).ratio()
        score = max(
            (score, *(SequenceMatcher(None, requested, part).ratio() for part in title_parts)),
        )
        if requested == process:
            score = 1.0
        elif len(requested) >= 4 and requested in normalized_title:
            score = max(score, 0.95)
        ranked.append((score, handle, process_name))

    ranked.sort(reverse=True)
    if not ranked or ranked[0][0] < threshold:
        return ()
    if len(ranked) > 1 and ranked[0][2] != ranked[1][2] and ranked[0][0] - ranked[1][0] < 0.08:
        return ()
    best_process = ranked[0][2]
    return tuple(
        handle
        for score, handle, process_name in ranked
        if process_name == best_process and score >= threshold
    )


def open_resource(target: str) -> None:
    os.startfile(target)  # type: ignore[attr-defined]


def start_program(arguments: tuple[str, ...]) -> None:
    subprocess.Popen(
        list(arguments),
        creationflags=DETACHED_PROCESS if os.name == "nt" else 0,
        close_fds=True,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
    )


def send_windows_app_command(command: int, repeats: int = 1) -> None:
    if os.name != "nt":
        raise RuntimeError("Comando disponivel somente no Windows.")
    for _ in range(repeats):
        ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_APPCOMMAND, 0, command << 16)


def send_shortcut(keys: tuple[str, ...]) -> None:
    if os.name != "nt":
        raise RuntimeError("Atalho disponivel somente no Windows.")
    codes = [VK[key] for key in keys]
    for code in codes:
        ctypes.windll.user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        ctypes.windll.user32.keybd_event(code, 0, KEYEVENTF_KEYUP, 0)


def send_unicode_text(value: str) -> None:
    if os.name != "nt":
        return

    class KeyboardInput(ctypes.Structure):
        _fields_ = (
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", wintypes.WPARAM),
        )

    class InputUnion(ctypes.Union):
        _fields_ = (("keyboard", KeyboardInput),)

    class Input(ctypes.Structure):
        _anonymous_ = ("payload",)
        _fields_ = (("type", wintypes.DWORD), ("payload", InputUnion))

    for character in value:
        code = ord(character)
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            event = Input(
                type=INPUT_KEYBOARD,
                keyboard=KeyboardInput(0, code, flags, 0, 0),
            )
            sent = ctypes.windll.user32.SendInput(
                1,
                ctypes.byref(event),
                ctypes.sizeof(event),
            )
            if sent != 1:
                raise RuntimeError("O Windows recusou a digitacao do texto.")


def get_start_menu_roots() -> tuple[Path, ...]:
    candidates = (
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("USERPROFILE", "")) / "Desktop",
        Path(os.environ.get("PUBLIC", "")) / "Desktop",
    )
    return tuple(path for path in candidates if str(path) and path.exists())


class ApplicationResolver:
    def __init__(self, shortcut_roots: tuple[Path, ...] | None = None) -> None:
        self.shortcut_roots = shortcut_roots if shortcut_roots is not None else get_start_menu_roots()
        self._shortcut_cache: list[tuple[str, Path]] | None = None

    def resolve(self, requested_name: str) -> tuple[str, tuple[str, ...] | str] | None:
        name = normalize_text(requested_name)
        if name in {"configuracoes", "configuracao"}:
            return "Configuracoes", "ms-settings:"
        known = APP_ALIASES.get(name)
        if known:
            label, executable = known
            executable_path = self._find_executable(executable)
            if executable_path:
                return label, (executable_path,)
        shortcuts = self._shortcuts()
        exact = [(label, path) for normalized, label, path in shortcuts if normalized == name]
        partial = [(label, path) for normalized, label, path in shortcuts if len(name) >= 3 and name in normalized]
        matches = exact or sorted(partial, key=lambda item: len(item[0]))
        if matches:
            label, path = matches[0]
            return label, str(path)
        return None

    def executable_for_browser(self, context: WindowContext) -> str | None:
        requested = {"chrome.exe": "chrome", "msedge.exe": "edge", "firefox.exe": "firefox"}.get(context.process_name, "")
        resolved = self.resolve(requested) if requested else None
        if resolved and isinstance(resolved[1], tuple):
            return resolved[1][0]
        for fallback in ("chrome", "edge", "firefox"):
            resolved = self.resolve(fallback)
            if resolved and isinstance(resolved[1], tuple):
                return resolved[1][0]
        return None

    def _shortcuts(self) -> list[tuple[str, str, Path]]:
        if self._shortcut_cache is not None:
            return [(name, path.stem, path) for name, path in self._shortcut_cache]
        cache: list[tuple[str, Path]] = []
        for root in self.shortcut_roots:
            try:
                cache.extend((normalize_text(path.stem), path) for path in root.rglob("*.lnk"))
            except OSError:
                logging.exception("Nao foi possivel consultar atalhos em %s.", root)
        self._shortcut_cache = cache
        return [(name, path.stem, path) for name, path in cache]

    @staticmethod
    def _find_executable(executable: str) -> str | None:
        import shutil

        found = shutil.which(executable)
        if found:
            return found
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        program_files = Path(os.environ.get("PROGRAMFILES", ""))
        program_files_x86 = Path(os.environ.get("PROGRAMFILES(X86)", ""))
        fallbacks = {
            "chrome.exe": (
                program_files / "Google/Chrome/Application/chrome.exe",
                program_files_x86 / "Google/Chrome/Application/chrome.exe",
                local_app_data / "Google/Chrome/Application/chrome.exe",
            ),
            "msedge.exe": (
                program_files / "Microsoft/Edge/Application/msedge.exe",
                program_files_x86 / "Microsoft/Edge/Application/msedge.exe",
            ),
            "firefox.exe": (
                program_files / "Mozilla Firefox/firefox.exe",
                program_files_x86 / "Mozilla Firefox/firefox.exe",
            ),
            "Discord.exe": (local_app_data / "Discord/Update.exe",),
            "Spotify.exe": (
                Path(os.environ.get("APPDATA", "")) / "Spotify/Spotify.exe",
            ),
            "Code.exe": (
                local_app_data / "Programs/Microsoft VS Code/Code.exe",
            ),
            "RiotClientServices.exe": (
                local_app_data / "Riot Games/Riot Client/RiotClientServices.exe",
                Path(os.environ.get("SYSTEMDRIVE", "C:")) / "Riot Games/Riot Client/RiotClientServices.exe",
            ),
        }
        if executable == "RiotClientServices.exe":
            manifest = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Riot Games/RiotClientInstalls.json"
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                configured = Path(str(payload.get("rc_live") or payload.get("rc_default") or ""))
                if configured.is_file():
                    return str(configured)
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                pass
        for candidate in fallbacks.get(executable, ()):
            if candidate.exists():
                return str(candidate)
        if os.name == "nt":
            try:
                import winreg

                key_path = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable}"
                for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                    try:
                        with winreg.OpenKey(hive, key_path) as key:
                            value, _ = winreg.QueryValueEx(key, None)
                            if Path(value).exists():
                                return str(value)
                    except OSError:
                        continue
            except ImportError:
                pass
        return None


class WindowsActions:
    def __init__(
        self,
        *,
        resource_opener: Callable[[str], None] = open_resource,
        program_starter: Callable[[tuple[str, ...]], None] = start_program,
        app_command_sender: Callable[[int, int], None] = send_windows_app_command,
        shortcut_sender: Callable[[tuple[str, ...]], None] = send_shortcut,
        text_sender: Callable[[str], None] = send_unicode_text,
        now_provider: Callable[[], datetime] = datetime.now,
        shortcut_roots: tuple[Path, ...] | None = None,
    ) -> None:
        self.resource_opener = resource_opener
        self.program_starter = program_starter
        self.app_command_sender = app_command_sender
        self.shortcut_sender = shortcut_sender
        self.text_sender = text_sender
        self.now_provider = now_provider
        self.apps = ApplicationResolver(shortcut_roots)
        self._last_brightness: int | None = None

    def execute(self, intent: ParsedIntent, context: WindowContext) -> str:
        handler = getattr(self, f"do_{intent.spec.executor}", None)
        if handler is None or not callable(handler):
            raise RuntimeError(f"Executor nao registrado: {intent.spec.executor}")
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
        self.program_starter(("explorer.exe", str(intent.parameters["target"])))
        return self._format_success(intent)

    def do_open_named_folder(self, intent: ParsedIntent, _context: WindowContext) -> str:
        requested = normalize_text(str(intent.parameters["name"]))
        home = Path.home()
        roots = tuple(
            path
            for path in (
                home,
                home / "Desktop",
                home / "Documents",
                home / "Downloads",
                home / "OneDrive",
            )
            if path.exists()
        )
        matches: list[Path] = []
        for root in roots:
            try:
                matches.extend(
                    child
                    for child in root.iterdir()
                    if child.is_dir() and normalize_text(child.name) == requested
                )
            except OSError:
                continue
        unique_matches = list(dict.fromkeys(matches))
        if len(unique_matches) != 1:
            raise FileNotFoundError(
                f"Pasta nao encontrada de forma inequivoca: {requested}"
            )
        self.program_starter(("explorer.exe", str(unique_matches[0])))
        return self._format_success(intent)

    def do_open_application(self, intent: ParsedIntent, _context: WindowContext) -> str:
        requested = str(intent.parameters["application"])
        resolved = self.apps.resolve(requested)
        if not resolved:
            raise FileNotFoundError(f"Aplicativo nao encontrado: {requested}")
        label, target = resolved
        if isinstance(target, str):
            self.resource_opener(target)
        else:
            if normalize_text(requested) == "valorant":
                self.program_starter(
                    (
                        target[0],
                        "--launch-product=valorant",
                        "--launch-patchline=live",
                    )
                )
            elif requested == "discord" and target[0].lower().endswith("update.exe"):
                self.program_starter((target[0], "--processStart", "Discord.exe"))
            else:
                self.program_starter(target)
        return f"Abri {label}."

    def do_close_application(self, intent: ParsedIntent, _context: WindowContext) -> str:
        requested = normalize_text(str(intent.parameters["application"]))
        windows: list[tuple[int, str, str]] = []
        if os.name != "nt":
            raise RuntimeError("Acao disponivel somente no Windows.")
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def collect(handle: int, _parameter: int) -> bool:
            if not ctypes.windll.user32.IsWindowVisible(handle):
                return True
            process_id = wintypes.DWORD()
            ctypes.windll.user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
            process_name = process_name_for_pid(process_id.value)
            title_length = ctypes.windll.user32.GetWindowTextLengthW(handle)
            title_buffer = ctypes.create_unicode_buffer(max(1, title_length + 1))
            ctypes.windll.user32.GetWindowTextW(handle, title_buffer, len(title_buffer))
            if process_name and title_buffer.value.strip():
                windows.append((int(handle), process_name, title_buffer.value.strip()))
            return True

        ctypes.windll.user32.EnumWindows(callback_type(collect), 0)
        handles = resolve_running_window_handles(requested, windows)
        if not handles:
            raise FileNotFoundError(f"Aplicativo nao esta aberto: {requested}")
        for handle in handles:
            ctypes.windll.user32.PostMessageW(handle, WM_CLOSE, 0, 0)
        return self._format_success(intent)

    def do_shortcut(self, intent: ParsedIntent, context: WindowContext) -> str:
        required = intent.parameters.get("context")
        if required and context.kind != required:
            label = "navegador" if required == "browser" else "Explorador de Arquivos"
            raise RuntimeError(f"O {label} precisa estar em foco.")
        target = normalize_text(str(intent.parameters.get("target", "")))
        if target and target not in normalize_text(context.title):
            raise FileNotFoundError(f"O alvo nao esta na aba ativa: {target}")
        self.shortcut_sender(tuple(intent.parameters["keys"]))
        return self._format_success(intent)

    def do_type_text(self, intent: ParsedIntent, _context: WindowContext) -> str:
        text = str(intent.parameters["text"]).strip()
        if not text:
            raise ValueError("Texto vazio.")
        self.text_sender(text)
        return self._format_success(intent)

    def do_browser_duplicate(self, intent: ParsedIntent, context: WindowContext) -> str:
        if context.kind != "browser":
            raise RuntimeError("O navegador precisa estar em foco.")
        self.shortcut_sender(("CTRL", "L"))
        self.shortcut_sender(("ALT", "ENTER"))
        return self._format_success(intent)

    def do_browser_private(self, intent: ParsedIntent, context: WindowContext) -> str:
        executable = self.apps.executable_for_browser(context)
        if not executable:
            raise FileNotFoundError("Nenhum navegador compativel foi encontrado.")
        flag = "-private-window" if executable.lower().endswith("firefox.exe") else "--incognito"
        self.program_starter((executable, flag))
        return self._format_success(intent)

    def do_window(self, intent: ParsedIntent, context: WindowContext) -> str:
        if not context.available:
            raise RuntimeError("Nenhuma janela ativa foi identificada.")
        operation = intent.parameters["operation"]
        if operation == "close":
            ctypes.windll.user32.PostMessageW(context.handle, WM_CLOSE, 0, 0)
        else:
            mode = {"minimize": SW_MINIMIZE, "maximize": SW_MAXIMIZE, "restore": SW_RESTORE}[str(operation)]
            ctypes.windll.user32.ShowWindow(context.handle, mode)
        return self._format_success(intent)

    def do_media_key(self, intent: ParsedIntent, _context: WindowContext) -> str:
        self.app_command_sender(int(intent.parameters["code"]), 1)
        return self._format_success(intent)

    def do_volume_relative(self, intent: ParsedIntent, _context: WindowContext) -> str:
        direction = int(intent.parameters["direction"])
        amount_match = re.search(r"\b(?:em )?(\d{1,2})\b", intent.normalized_text)
        amount = int(intent.parameters.get("amount", 0))
        if not amount:
            amount = min(100, int(amount_match.group(1))) if amount_match else 8
        repeats = max(1, round(amount / 2))
        self.app_command_sender(10 if direction > 0 else 9, repeats)
        return self._format_success(intent)

    def do_set_volume(self, intent: ParsedIntent, _context: WindowContext) -> str:
        value = int(intent.parameters["value"])
        try:
            endpoint = self._endpoint_volume()
            endpoint.SetMasterVolumeLevelScalar(value / 100, None)
        except Exception as error:
            raise RuntimeError("O controle de volume exato nao esta disponivel.") from error
        return self._format_success(intent)

    def do_set_mute(self, intent: ParsedIntent, _context: WindowContext) -> str:
        try:
            self._endpoint_volume().SetMute(bool(intent.parameters["muted"]), None)
        except Exception as error:
            raise RuntimeError("O controle de mudo nao esta disponivel.") from error
        return self._format_success(intent)

    @staticmethod
    def _endpoint_volume():
        from pycaw.pycaw import AudioUtilities

        device = AudioUtilities.GetSpeakers()
        endpoint = getattr(device, "EndpointVolume", None)
        if endpoint is not None:
            return endpoint

        from comtypes import CLSCTX_ALL
        from ctypes import POINTER, cast
        from pycaw.pycaw import IAudioEndpointVolume

        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def do_web_search(self, intent: ParsedIntent, _context: WindowContext) -> str:
        query = str(intent.parameters["query"])
        if not query:
            raise ValueError("Pesquisa sem texto.")
        if intent.parameters["destination"] == "youtube":
            url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        else:
            url = f"https://www.google.com/search?q={quote_plus(query)}"
        self.resource_opener(url)
        return self._format_success(intent)

    def do_windows_search(self, intent: ParsedIntent, _context: WindowContext) -> str:
        self.shortcut_sender(("WIN", "S"))
        query = str(intent.parameters.get("query", ""))
        if query:
            time.sleep(0.25)
            send_unicode_text(query)
        return self._format_success(intent)

    def do_system(self, intent: ParsedIntent, _context: WindowContext) -> str:
        operation = intent.parameters["operation"]
        if operation == "lock":
            if not ctypes.windll.user32.LockWorkStation():
                raise RuntimeError("O Windows recusou o bloqueio.")
        elif operation == "shutdown":
            self.program_starter(("shutdown.exe", "/s", "/t", "0"))
        elif operation == "restart":
            self.program_starter(("shutdown.exe", "/r", "/t", "0"))
        elif operation == "sign_out":
            self.program_starter(("shutdown.exe", "/l"))
        elif operation in {"sleep", "hibernate"}:
            hibernate = operation == "hibernate"
            if not ctypes.windll.powrprof.SetSuspendState(hibernate, False, False):
                raise RuntimeError("O hardware recusou essa operacao de energia.")
        return self._format_success(intent)

    def do_set_brightness(self, intent: ParsedIntent, _context: WindowContext) -> str:
        self._set_brightness(int(intent.parameters["value"]))
        return self._format_success(intent)

    def do_change_brightness(self, intent: ParsedIntent, _context: WindowContext) -> str:
        current = self._get_brightness()
        value = max(0, min(100, current + int(intent.parameters["amount"])))
        self._set_brightness(value)
        return f"Brilho em {value}%."

    def _get_brightness(self) -> int:
        script = "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"
        completed = subprocess.run(
            ("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script),
            capture_output=True, text=True, timeout=5, check=True,
        )
        values = re.findall(r"\d+", completed.stdout)
        if not values:
            raise RuntimeError("Este monitor nao oferece controle de brilho.")
        return int(values[0])

    def _set_brightness(self, value: int) -> None:
        value = max(0, min(100, value))
        script = f"Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | ForEach-Object {{ $_.WmiSetBrightness(0, {value}) | Out-Null }}"
        subprocess.run(
            ("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script),
            capture_output=True, text=True, timeout=6, check=True,
        )
        self._last_brightness = value

    def do_tell_time(self, _intent: ParsedIntent, _context: WindowContext) -> str:
        return f"Agora são {self.now_provider():%H:%M}."

    def do_tell_date(self, _intent: ParsedIntent, _context: WindowContext) -> str:
        return f"Hoje é dia {self.now_provider():%d/%m/%Y}."

    def do_tell_weekday(self, _intent: ParsedIntent, _context: WindowContext) -> str:
        names = ("segunda-feira", "terca-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sabado", "domingo")
        return f"Hoje é {names[self.now_provider().weekday()]}."
