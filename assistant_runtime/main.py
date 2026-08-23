from __future__ import annotations

import argparse
import ctypes
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import unicodedata
from ctypes import wintypes
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pystray
import pyttsx3
import sounddevice as sd
import vosk
from PIL import Image

try:
    from .commands import CommandExecutor
    from .permission_store import PermissionStore
    from .replies import create_assistant_reply
    from .voice_activity import (
        VoiceActivityConfig,
        VoiceActivityEvent,
        VoiceActivitySession,
        TranscriptAccumulator,
    )
except ImportError:  # Execucao direta pelo inicializador local.
    from commands import CommandExecutor
    from permission_store import PermissionStore
    from replies import create_assistant_reply
    from voice_activity import (
        TranscriptAccumulator,
        VoiceActivityConfig,
        VoiceActivityEvent,
        VoiceActivitySession,
    )

APP_NAME = "Doktor Assistant"
WAKE_PHRASE = "Olá, Doktor"
WAKE_VARIANTS = (
    "ola doutor",
    "oi doutor",
    "ei doutor",
    "ola assistente",
    "ei assistente",
)
WEB_PORT = 3000
WEB_URL = f"http://localhost:{WEB_PORT}/"

PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
DIST_DIRECTORY = PROJECT_DIRECTORY / "dist"
MODEL_DIRECTORY = (
    PROJECT_DIRECTORY / "runtime" / "models" / "vosk-model-small-pt-0.3"
)
LOGS_DIRECTORY = PROJECT_DIRECTORY / "runtime" / "logs"
LOG_FILE = LOGS_DIRECTORY / "assistant.log"
PERMISSION_FILE = PROJECT_DIRECTORY / "runtime" / "config" / "permissions.json"
VOICE_CONFIG_FILE = PROJECT_DIRECTORY / "assistant_runtime" / "voice_config.json"
TRAY_ICON_PATH = PROJECT_DIRECTORY / "assets" / "doktor-assistant.png"
AUTOSTART_DIRECTORY = (
    Path(os.environ.get("APPDATA", ""))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
)
AUTOSTART_FILE = AUTOSTART_DIRECTORY / "Doktor Assistant.vbs"
LEGACY_AUTOSTART_FILE = AUTOSTART_DIRECTORY / "Assistente de voz.vbs"

DETACHED_PROCESS = 0x00000008
ERROR_ALREADY_EXISTS = 183
PYSTRAY_STOP_MESSAGE = 0x040A
TRAY_WINDOW_PREFIX = "assistente-voz"


def configure_logging(show_console: bool) -> None:
    LOGS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]

    if show_console:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
    )


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    ).lower()


def create_tray_image() -> Image.Image:
    with Image.open(TRAY_ICON_PATH) as source:
        return source.convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)


def find_browser() -> Path | None:
    candidates = (
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
    )
    return next((candidate for candidate in candidates if candidate.exists()), None)


def open_app_window() -> None:
    browser = find_browser()

    try:
        if browser:
            subprocess.Popen(
                [
                    str(browser),
                    f"--app={WEB_URL}",
                    "--window-size=1180,820",
                ],
                cwd=PROJECT_DIRECTORY,
                creationflags=DETACHED_PROCESS,
                close_fds=True,
            )
            return

        os.startfile(WEB_URL)  # type: ignore[attr-defined]
    except OSError:
        logging.exception("Não foi possível abrir a interface.")


def acquire_single_instance() -> tuple[int | None, bool]:
    if os.name != "nt":
        return None, False

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    handle = kernel32.CreateMutexW(None, False, "Local\\AssistenteVozBackground")
    return handle, kernel32.GetLastError() == ERROR_ALREADY_EXISTS


def request_existing_shutdown() -> bool:
    """Pede ao pystray existente para sair e remover o icone corretamente."""
    if os.name != "nt":
        return False

    matching_windows: list[int] = []
    enum_callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def find_tray_window(window_handle: int, _parameter: int) -> bool:
        class_name = ctypes.create_unicode_buffer(256)
        if not ctypes.windll.user32.GetClassNameW(
            window_handle,
            class_name,
            len(class_name),
        ):
            return True
        if (
            class_name.value.startswith(TRAY_WINDOW_PREFIX)
            and class_name.value.endswith("SystemTrayIcon")
        ):
            matching_windows.append(window_handle)
        return True

    ctypes.windll.user32.EnumWindows(enum_callback(find_tray_window), 0)
    for window_handle in matching_windows:
        ctypes.windll.user32.PostMessageW(
            window_handle,
            PYSTRAY_STOP_MESSAGE,
            0,
            0,
        )
    return bool(matching_windows)


def show_startup_error(message: str) -> None:
    if os.name != "nt":
        return

    ctypes.windll.user32.MessageBoxW(
        None,
        f"{message}\n\nConsulte runtime\\logs\\assistant.log para mais detalhes.",
        APP_NAME,
        0x10,
    )


class AssistantRuntime:
    def __init__(self) -> None:
        self.permission_store = PermissionStore(PERMISSION_FILE)
        self.command_executor = CommandExecutor(
            status_callback=lambda mode: self.update_state(mode=mode)
        )
        self.stop_event = threading.Event()
        self.listening_enabled = threading.Event()
        self.listening_enabled.set()
        self.reset_recognizer = threading.Event()
        self.state_lock = threading.Lock()
        self.state: dict[str, Any] = {
            "connected": True,
            "enabled": True,
            "error": "",
            "mode": "starting",
            "partial": "",
            "permission": self.permission_store.snapshot(),
            "response": "",
            "sequence": 0,
            "transcript": "",
            "wakePhrase": WAKE_PHRASE,
            "lastAction": None,
        }
        self.icon: pystray.Icon | None = None
        self.local_server: ThreadingHTTPServer | None = None
        self.speech_engine: pyttsx3.Engine | None = None

    def snapshot(self) -> dict[str, Any]:
        with self.state_lock:
            snapshot = dict(self.state)

        last_action = snapshot.get("lastAction")
        if (
            isinstance(last_action, dict)
            and last_action.get("status") == "awaiting_confirmation"
            and not self.command_executor.confirmations.has_pending()
        ):
            snapshot["lastAction"] = {**last_action, "status": "expired"}
        return snapshot

    def update_state(self, **changes: Any) -> None:
        with self.state_lock:
            self.state.update(changes)

        if self.icon:
            try:
                self.icon.update_menu()
            except RuntimeError:
                pass

    def set_listening(self, enabled: bool) -> None:
        if enabled:
            self.listening_enabled.set()
            self.update_state(enabled=True, error="", mode="wake", partial="")
        else:
            self.listening_enabled.clear()
            self.update_state(enabled=False, mode="paused", partial="")

        self.reset_recognizer.set()

    def toggle_listening(self) -> None:
        self.set_listening(not self.listening_enabled.is_set())

    def set_permission(self, accepted: bool) -> None:
        permission = self.permission_store.set_accepted(accepted)
        self.update_state(permission=permission)

    def ensure_web_assets(self) -> None:
        if not (DIST_DIRECTORY / "index.html").exists():
            raise RuntimeError(
                "A interface ainda não foi preparada. Execute INSTALAR_ASSISTENTE.cmd."
            )

    def start_local_server(self) -> None:
        runtime = self

        class LocalRequestHandler(SimpleHTTPRequestHandler):
            server_version = "AssistenteLocal"
            sys_version = ""

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, directory=str(DIST_DIRECTORY), **kwargs)

            def log_message(self, format_string: str, *args: Any) -> None:
                return

            def end_headers(self) -> None:
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; base-uri 'none'; object-src 'none'; "
                    "frame-ancestors 'none'; img-src 'self' data:; "
                    "connect-src 'self'; script-src 'self'; style-src 'self'",
                )
                self.send_header("Permissions-Policy", "microphone=(self)")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                super().end_headers()

            def request_path(self) -> str:
                return urlsplit(self.path).path

            def allowed_origin(self) -> str | None:
                origin = self.headers.get("Origin", "")
                try:
                    parsed_origin = urlsplit(origin)
                    port = parsed_origin.port
                except ValueError:
                    return None

                if (
                    parsed_origin.scheme == "http"
                    and parsed_origin.hostname in {"localhost", "127.0.0.1"}
                    and port in {WEB_PORT, 5173}
                ):
                    return origin
                return None

            def send_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                origin = self.allowed_origin()
                if origin:
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self) -> None:  # noqa: N802
                if self.request_path() not in {
                    "/api/listening",
                    "/api/open",
                    "/api/permission",
                }:
                    self.send_json(404, {"error": "Rota não encontrada."})
                    return

                origin = self.allowed_origin()
                if not origin:
                    self.send_json(403, {"error": "Origem não permitida."})
                    return
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Vary", "Origin")
                self.end_headers()

            def do_GET(self) -> None:  # noqa: N802
                request_path = self.request_path()
                if request_path == "/api/state":
                    self.send_json(200, runtime.snapshot())
                    return

                if request_path.startswith("/api/"):
                    self.send_json(404, {"error": "Rota não encontrada."})
                    return

                requested_file = Path(self.translate_path(self.path))
                if request_path == "/" or not requested_file.is_file():
                    self.path = "/index.html"
                super().do_GET()

            def do_POST(self) -> None:  # noqa: N802
                if not self.allowed_origin():
                    self.send_json(403, {"error": "Origem não permitida."})
                    return

                request_path = self.request_path()
                if request_path == "/api/open":
                    open_app_window()
                    self.send_json(200, {"ok": True})
                    return

                if request_path not in {"/api/listening", "/api/permission"}:
                    self.send_json(404, {"error": "Rota não encontrada."})
                    return

                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                    if content_length > 1_024:
                        self.send_json(413, {"error": "Requisição muito grande."})
                        return
                    payload = json.loads(self.rfile.read(content_length) or b"{}")
                    if not isinstance(payload, dict):
                        raise ValueError
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    self.send_json(400, {"error": "Conteúdo inválido."})
                    return

                if request_path == "/api/listening":
                    enabled = payload.get("enabled")
                    if not isinstance(enabled, bool):
                        self.send_json(400, {"error": "Estado de escuta inválido."})
                        return
                    runtime.set_listening(enabled)
                    self.send_json(200, runtime.snapshot())
                    return

                accepted = payload.get("accepted")
                if not isinstance(accepted, bool):
                    self.send_json(400, {"error": "Permissão inválida."})
                    return
                try:
                    runtime.set_permission(accepted)
                except OSError:
                    logging.exception("Não foi possível salvar a permissão.")
                    self.send_json(500, {"error": "Não foi possível salvar a permissão."})
                    return
                self.send_json(200, runtime.snapshot())

        self.local_server = ThreadingHTTPServer(
            ("127.0.0.1", WEB_PORT), LocalRequestHandler
        )
        self.local_server.daemon_threads = True
        threading.Thread(
            target=self.local_server.serve_forever,
            name="assistant-local-server",
            daemon=True,
        ).start()
        logging.info("Interface e API locais iniciadas em %s", WEB_URL)

    def create_recognizer(self, model: vosk.Model, sample_rate: int, wake: bool):
        if not wake:
            return vosk.KaldiRecognizer(model, sample_rate)

        grammar = json.dumps([*WAKE_VARIANTS, "[unk]"], ensure_ascii=False)
        return vosk.KaldiRecognizer(model, sample_rate, grammar)

    def contains_wake_phrase(self, text: str) -> bool:
        normalized = normalize_text(text)
        return any(normalize_text(phrase) in normalized for phrase in WAKE_VARIANTS)

    @staticmethod
    def extract_result(raw_result: str, key: str = "text") -> str:
        try:
            return str(json.loads(raw_result).get(key, "")).strip()
        except (TypeError, ValueError, json.JSONDecodeError):
            return ""

    @staticmethod
    def drain_audio(audio_queue: queue.Queue[bytes]) -> None:
        while True:
            try:
                audio_queue.get_nowait()
            except queue.Empty:
                return

    @staticmethod
    def play_activation_sound() -> None:
        try:
            import winsound

            winsound.Beep(880, 120)
        except (ImportError, RuntimeError):
            pass

    @staticmethod
    def choose_portuguese_voice(engine: pyttsx3.Engine) -> None:
        for voice in engine.getProperty("voices"):
            languages = " ".join(
                language.decode(errors="ignore")
                if isinstance(language, bytes)
                else str(language)
                for language in getattr(voice, "languages", [])
            ).lower()
            voice_description = f"{voice.id} {voice.name} {languages}".lower()
            if "pt-br" in voice_description or "maria" in voice_description:
                engine.setProperty("voice", voice.id)
                return

    def speak(self, text: str) -> None:
        if self.speech_engine is None:
            self.speech_engine = pyttsx3.init()
            self.choose_portuguese_voice(self.speech_engine)
            self.speech_engine.setProperty("rate", 178)
            self.speech_engine.setProperty("volume", 1.0)

        engine = self.speech_engine
        try:
            engine.say(text)
            engine.runAndWait()
        except Exception:
            engine.stop()
            self.speech_engine = None
            raise

    def complete_command(
        self, transcript: str, audio_queue: queue.Queue[bytes]
    ) -> None:
        clean_transcript = transcript.strip()
        if not clean_transcript:
            reply = f"Não consegui ouvir o comando. Diga {WAKE_PHRASE} para tentar novamente."
            action = None
        else:
            self.update_state(mode="processing", partial="")
            command_result = self.command_executor.execute(
                clean_transcript,
                authorized=self.permission_store.is_accepted(),
            )
            if command_result.matched:
                reply = command_result.response
                action = command_result.as_state()
                logging.info(
                    "Comando processado: action=%s executed=%s",
                    command_result.action,
                    command_result.executed,
                )
            else:
                reply = create_assistant_reply(clean_transcript)
                action = None

        current_sequence = int(self.snapshot()["sequence"]) + 1
        action_status = action.get("status") if action else ""
        self.update_state(
            mode=(
                "confirming"
                if action_status == "awaiting_confirmation"
                else "responding"
            ),
            lastAction=action,
            partial="",
            response=reply,
            sequence=current_sequence,
            transcript=clean_transcript,
        )

        try:
            self.speak(reply)
        except Exception:
            logging.exception("Falha ao reproduzir a resposta.")
            self.update_state(error="Não foi possível reproduzir a resposta em voz.")

        self.drain_audio(audio_queue)
        self.reset_recognizer.set()
        if self.listening_enabled.is_set():
            self.update_state(mode="wake", partial="")

    @staticmethod
    def select_input_sample_rate(preferred: int) -> int:
        candidates = tuple(dict.fromkeys((preferred, 16_000, 48_000, 32_000, 8_000)))
        failures: list[str] = []
        for sample_rate in candidates:
            try:
                sd.check_input_settings(
                    device=None,
                    channels=1,
                    dtype="int16",
                    samplerate=sample_rate,
                )
                return sample_rate
            except (sd.PortAudioError, ValueError) as error:
                failures.append(f"{sample_rate} Hz: {error}")

        details = "; ".join(failures)
        raise RuntimeError(f"O microfone não aceita uma taxa compatível com VAD. {details}")

    def run_audio_session(
        self,
        model: vosk.Model,
        configured_voice: VoiceActivityConfig,
    ) -> None:
        sample_rate = self.select_input_sample_rate(configured_voice.sample_rate)
        voice_config = configured_voice.with_sample_rate(sample_rate)
        audio_queue: queue.Queue[bytes] = queue.Queue(
            maxsize=voice_config.frames_for(6.0)
        )

        def audio_callback(indata: bytes, frames: int, time_info: Any, status: Any):
            del frames, time_info
            if status:
                logging.warning("Estado do microfone: %s", status)
            try:
                audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                try:
                    audio_queue.get_nowait()
                    audio_queue.put_nowait(bytes(indata))
                except queue.Empty:
                    pass

        wake_recognizer = self.create_recognizer(model, sample_rate, wake=True)
        command_recognizer = None
        voice_session: VoiceActivitySession | None = None
        transcript = TranscriptAccumulator()

        with sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=voice_config.frame_samples,
            device=None,
            dtype="int16",
            channels=1,
            callback=audio_callback,
        ):
            self.update_state(error="", mode="wake", partial="")
            logging.info(
                "Escuta contínua iniciada em %s Hz com frames de %s ms.",
                sample_rate,
                voice_config.frame_duration_ms,
            )

            while not self.stop_event.is_set():
                if self.reset_recognizer.is_set():
                    self.reset_recognizer.clear()
                    self.drain_audio(audio_queue)
                    wake_recognizer = self.create_recognizer(
                        model, sample_rate, wake=True
                    )
                    command_recognizer = None
                    voice_session = None
                    transcript = TranscriptAccumulator()

                if not self.listening_enabled.is_set():
                    self.update_state(mode="paused", partial="")
                    self.stop_event.wait(0.2)
                    self.drain_audio(audio_queue)
                    continue

                try:
                    data = audio_queue.get(timeout=0.25)
                except queue.Empty:
                    continue

                if command_recognizer is None:
                    if wake_recognizer.AcceptWaveform(data):
                        candidate = self.extract_result(wake_recognizer.Result())
                    else:
                        candidate = self.extract_result(
                            wake_recognizer.PartialResult(), "partial"
                        )

                    if not self.contains_wake_phrase(candidate):
                        continue

                    self.play_activation_sound()
                    self.drain_audio(audio_queue)
                    command_recognizer = self.create_recognizer(
                        model, sample_rate, wake=False
                    )
                    voice_session = VoiceActivitySession(voice_config)
                    transcript = TranscriptAccumulator()
                    self.update_state(error="", mode="activated", partial="")
                    logging.info("Wake word detectada; aguardando início da fala.")
                    continue

                if voice_session is None:
                    raise RuntimeError("Sessão VAD ausente durante a captura do comando.")

                voice_event = voice_session.accept(data)
                accepted_segment = command_recognizer.AcceptWaveform(data)
                if accepted_segment:
                    segment = self.extract_result(command_recognizer.Result())
                    if segment and voice_session.has_started:
                        transcript.add(segment)

                if voice_event is VoiceActivityEvent.START_TIMEOUT:
                    logging.info(
                        "Ativação cancelada após %.1f segundos sem fala.",
                        voice_config.activation_start_timeout,
                    )
                    self.drain_audio(audio_queue)
                    command_recognizer = None
                    voice_session = None
                    transcript = TranscriptAccumulator()
                    wake_recognizer = self.create_recognizer(
                        model, sample_rate, wake=True
                    )
                    self.update_state(mode="wake", partial="")
                    continue

                if voice_event is VoiceActivityEvent.SPEECH_STARTED:
                    self.update_state(mode="listening")
                    logging.info("Início da fala detectado pelo VAD.")

                if voice_session.has_started and not accepted_segment:
                    partial = self.extract_result(
                        command_recognizer.PartialResult(), "partial"
                    )
                    visible_partial = transcript.preview(partial)
                    if visible_partial:
                        self.update_state(partial=visible_partial)

                if voice_event is not VoiceActivityEvent.SPEECH_ENDED:
                    continue

                final_text = self.extract_result(command_recognizer.FinalResult())
                command_text = transcript.finish(final_text)
                logging.info(
                    "Fim da fala detectado após %.1f segundos de silêncio.",
                    voice_config.speech_end_silence,
                )
                if command_text:
                    self.complete_command(command_text, audio_queue)
                else:
                    self.drain_audio(audio_queue)
                    self.update_state(mode="wake", partial="")

                command_recognizer = None
                voice_session = None
                transcript = TranscriptAccumulator()
                wake_recognizer = self.create_recognizer(
                    model, sample_rate, wake=True
                )

    def listen_forever(self) -> None:
        try:
            if not MODEL_DIRECTORY.exists():
                raise RuntimeError(
                    "O modelo de voz não está instalado. Execute INSTALAR_ASSISTENTE.cmd."
                )

            voice_config = VoiceActivityConfig.from_file(VOICE_CONFIG_FILE)
            vosk.SetLogLevel(-1)
            model = vosk.Model(str(MODEL_DIRECTORY))
        except Exception as error:
            logging.exception("Não foi possível preparar o reconhecimento de voz.")
            self.update_state(enabled=False, error=str(error), mode="error", partial="")
            return

        reported_microphone_error = False
        while not self.stop_event.is_set():
            try:
                self.run_audio_session(model, voice_config)
                return
            except Exception as error:
                if self.stop_event.is_set():
                    return

                logging.exception("O microfone foi desconectado ou ficou indisponível.")
                self.update_state(
                    error="Microfone indisponível. Tentando reconectar...",
                    mode="error",
                    partial="",
                )
                if self.icon and not reported_microphone_error:
                    self.icon.notify(str(error), "Falha no microfone")
                reported_microphone_error = True
                self.stop_event.wait(3.0)

    def is_autostart_enabled(self) -> bool:
        return AUTOSTART_FILE.exists() or LEGACY_AUTOSTART_FILE.exists()

    def set_autostart(self, enabled: bool) -> None:
        if not enabled:
            AUTOSTART_FILE.unlink(missing_ok=True)
            LEGACY_AUTOSTART_FILE.unlink(missing_ok=True)
            return

        launcher = PROJECT_DIRECTORY / "INICIAR_ASSISTENTE.vbs"
        command = f'wscript.exe //nologo "{launcher}"'
        escaped_command = command.replace('"', '""')
        AUTOSTART_FILE.parent.mkdir(parents=True, exist_ok=True)
        AUTOSTART_FILE.write_text(
            "Set shell = CreateObject(\"WScript.Shell\")\n"
            f"shell.CurrentDirectory = \"{PROJECT_DIRECTORY}\"\n"
            f"shell.Run \"{escaped_command}\", 0, False\n",
            encoding="utf-8-sig",
        )
        LEGACY_AUTOSTART_FILE.unlink(missing_ok=True)

    def toggle_autostart(self) -> None:
        try:
            self.set_autostart(not self.is_autostart_enabled())
        except OSError:
            logging.exception("Não foi possível alterar a inicialização automática.")

    def shutdown(self) -> None:
        if self.stop_event.is_set():
            return

        self.stop_event.set()
        if self.local_server:
            threading.Thread(
                target=self.local_server.shutdown, daemon=True
            ).start()

        if self.icon:
            self.icon.stop()

        if self.speech_engine:
            try:
                self.speech_engine.stop()
            except RuntimeError:
                pass
            self.speech_engine = None

    def run(self, open_on_start: bool) -> None:
        self.ensure_web_assets()
        self.start_local_server()

        audio_thread = threading.Thread(
            target=self.listen_forever,
            name="continuous-listening",
            daemon=True,
        )
        audio_thread.start()

        self.icon = pystray.Icon(
            "assistente-voz",
            create_tray_image(),
            APP_NAME,
            menu=pystray.Menu(
                pystray.MenuItem(
                    "Abrir Doktor Assistant",
                    lambda _icon, _item: open_app_window(),
                    default=True,
                ),
                pystray.MenuItem(
                    lambda _item: (
                        "Pausar escuta"
                        if self.listening_enabled.is_set()
                        else "Ativar escuta"
                    ),
                    lambda _icon, _item: self.toggle_listening(),
                ),
                pystray.MenuItem(
                    lambda _item: (
                        "Comandos autorizados"
                        if self.permission_store.is_accepted()
                        else "Autorizar comandos"
                    ),
                    lambda _icon, _item: open_app_window(),
                ),
                pystray.MenuItem(
                    "Iniciar com o Windows",
                    lambda _icon, _item: self.toggle_autostart(),
                    checked=lambda _item: self.is_autostart_enabled(),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Encerrar", lambda _icon, _item: self.shutdown()),
            ),
        )

        if open_on_start:
            open_app_window()

        self.icon.notify(
            f'Diga "{WAKE_PHRASE}" para começar.',
            "Escuta contínua ativa",
        )
        try:
            self.icon.run()
        finally:
            self.shutdown()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--console", action="store_true")
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--install-autostart", action="store_true")
    parser.add_argument("--stop", action="store_true")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    configure_logging(arguments.console)

    if arguments.stop:
        return 0 if request_existing_shutdown() else 1

    if arguments.install_autostart:
        AssistantRuntime().set_autostart(True)
        return 0

    mutex_handle, already_running = acquire_single_instance()
    if already_running:
        if arguments.open:
            open_app_window()
        return 0

    runtime = AssistantRuntime()
    try:
        runtime.run(arguments.open)
    except Exception as error:
        logging.exception("O assistente não conseguiu iniciar.")
        if not arguments.console:
            show_startup_error(str(error))
        return 1
    finally:
        if mutex_handle and os.name == "nt":
            ctypes.windll.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            ctypes.windll.kernel32.CloseHandle(mutex_handle)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
