from __future__ import annotations

import argparse
from array import array
import ctypes
import json
import logging
import os
import queue
import sys
import threading
import time
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

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from .commands import CommandExecutor
    from .permission_store import PermissionStore
    from .replies import create_assistant_reply
    from .stt import STTEventType, SpeechToTextSession, create_stt_provider
    from .voice_activity import (
        VoiceActivityConfig,
        VoiceActivityEvent,
        VoiceActivitySession,
        TranscriptAccumulator,
    )
    from .voice_metrics import VoiceMetrics
    from .app_paths import PATHS
    from .platforms import detect_platform
    from .platforms.system import (
        is_autostart_enabled as platform_autostart_enabled,
        open_desktop_window,
        set_autostart as platform_set_autostart,
    )
    from .version import __version__
    from .health import audio_devices, health_snapshot
    from .settings import SettingsStore
    from .update_service import UpdateService
except ImportError:  # Execucao direta pelo inicializador local.
    from assistant_runtime.commands import CommandExecutor
    from assistant_runtime.permission_store import PermissionStore
    from assistant_runtime.replies import create_assistant_reply
    from assistant_runtime.stt import STTEventType, SpeechToTextSession, create_stt_provider
    from assistant_runtime.voice_activity import (
        TranscriptAccumulator,
        VoiceActivityConfig,
        VoiceActivityEvent,
        VoiceActivitySession,
    )
    from assistant_runtime.voice_metrics import VoiceMetrics
    from assistant_runtime.app_paths import PATHS
    from assistant_runtime.platforms import detect_platform
    from assistant_runtime.platforms.system import (
        is_autostart_enabled as platform_autostart_enabled,
        open_desktop_window,
        set_autostart as platform_set_autostart,
    )
    from assistant_runtime.version import __version__
    from assistant_runtime.health import audio_devices, health_snapshot
    from assistant_runtime.settings import SettingsStore
    from assistant_runtime.update_service import UpdateService

APP_NAME = "Doktor Assistant"
WAKE_PHRASE = "Olá, Doktor"
WAKE_VARIANTS = (
    "ola doutor",
)
WEB_PORT = 3000
WEB_URL = f"http://localhost:{WEB_PORT}/"

DIST_DIRECTORY = PATHS.web
MODEL_DIRECTORY = PATHS.model
LOGS_DIRECTORY = PATHS.logs
LOG_FILE = LOGS_DIRECTORY / "assistant.log"
PERMISSION_FILE = PATHS.config / "permissions.json"
VOICE_CONFIG_FILE = PATHS.voice_config
STT_CONFIG_FILE = PATHS.stt_config
VOICE_METRICS_FILE = PATHS.config / "voice-metrics.json"
TRAY_ICON_PATH = PATHS.assets / "doktor-assistant.png"

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


def open_app_window() -> None:
    try:
        open_desktop_window(WEB_URL)
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
        self.settings_store = SettingsStore(PATHS.config / "settings.json")
        self.update_service = UpdateService(self.settings_store.value().update_channel)
        self.command_executor = CommandExecutor(
            status_callback=lambda mode: self.update_state(mode=mode)
        )
        self.stop_event = threading.Event()
        self.listening_enabled = threading.Event()
        self.listening_enabled.set()
        self.reset_recognizer = threading.Event()
        self.audio_device_changed = threading.Event()
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
            "version": __version__,
            "platform": detect_platform().__dict__,
            "settings": self.settings_store.snapshot(),
            "update": self.update_service.snapshot(),
            "autostart": self.is_autostart_enabled(),
            "audioLevel": 0.0,
        }
        self.icon: pystray.Icon | None = None
        self.local_server: ThreadingHTTPServer | None = None
        self.speech_engine: pyttsx3.Engine | None = None
        self.voice_metrics = VoiceMetrics(VOICE_METRICS_FILE)
        self.last_audio_level_update = 0.0

    def snapshot(self) -> dict[str, Any]:
        with self.state_lock:
            snapshot = dict(self.state)
        snapshot["voiceMetrics"] = self.voice_metrics.snapshot()

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

    def update_audio_level(self, pcm16: bytes) -> None:
        now = time.monotonic()
        if now - self.last_audio_level_update < 0.1:
            return
        samples = array("h")
        samples.frombytes(pcm16)
        if not samples:
            return
        level = round(max(abs(value) for value in samples) / 32768, 3)
        with self.state_lock:
            self.state["audioLevel"] = level
        self.last_audio_level_update = now

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

    def set_settings(self, payload: dict[str, object]) -> None:
        previous_device = self.settings_store.value().microphone_device
        settings = self.settings_store.update(payload)
        if settings.update_channel != self.update_service.channel:
            self.update_service = UpdateService(settings.update_channel)
        self.update_state(settings=self.settings_store.snapshot(), update=self.update_service.snapshot())
        if settings.microphone_device != previous_device:
            self.audio_device_changed.set()
            self.reset_recognizer.set()

    def check_for_updates(self) -> None:
        info = self.update_service.check()
        self.update_state(update=self.update_service.snapshot())
        if info.available and self.icon:
            self.icon.notify(f"Doktor {info.latestVersion} esta disponivel.", "Atualizacao")

    def update_loop(self) -> None:
        if self.stop_event.wait(10.0):
            return
        while not self.stop_event.is_set():
            self.check_for_updates()
            self.stop_event.wait(6 * 60 * 60)

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
                    "/api/settings",
                    "/api/update",
                    "/api/autostart",
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

                if request_path == "/api/audio/devices":
                    try:
                        self.send_json(200, {"devices": audio_devices()})
                    except Exception as error:
                        self.send_json(503, {"error": str(error), "devices": []})
                    return

                if request_path == "/api/health":
                    self.send_json(200, health_snapshot(str(runtime.snapshot().get("sttProvider", ""))))
                    return

                if request_path == "/api/settings":
                    self.send_json(200, runtime.settings_store.snapshot())
                    return

                if request_path == "/api/update":
                    self.send_json(200, runtime.update_service.snapshot())
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

                if request_path not in {"/api/listening", "/api/permission", "/api/settings", "/api/update", "/api/autostart"}:
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

                if request_path == "/api/settings":
                    try:
                        runtime.set_settings(payload)
                    except (OSError, TypeError, ValueError) as error:
                        self.send_json(400, {"error": str(error)})
                        return
                    self.send_json(200, runtime.settings_store.snapshot())
                    return

                if request_path == "/api/update":
                    action = payload.get("action", "check")
                    if action == "check":
                        runtime.check_for_updates()
                    elif action == "install":
                        try:
                            runtime.update_service.download_and_install()
                        except Exception as error:
                            self.send_json(503, {"error": str(error)})
                            return
                    else:
                        self.send_json(400, {"error": "Acao de atualizacao invalida."})
                        return
                    self.send_json(200, runtime.update_service.snapshot())
                    return

                if request_path == "/api/autostart":
                    enabled = payload.get("enabled")
                    if not isinstance(enabled, bool):
                        self.send_json(400, {"error": "Estado de inicializacao invalido."})
                        return
                    try:
                        runtime.set_autostart(enabled)
                    except OSError as error:
                        self.send_json(500, {"error": str(error)})
                        return
                    runtime.update_state(autostart=enabled)
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

    def speak_feedback(self, text: str) -> None:
        """Short phase feedback; failures must never stop microphone capture."""
        try:
            self.speak(text)
        except Exception:
            logging.exception("Falha no feedback de voz: %s", text)

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

    def select_input_sample_rate(self, preferred: int) -> int:
        candidates = tuple(dict.fromkeys((preferred, 16_000, 48_000, 32_000, 8_000)))
        failures: list[str] = []
        for sample_rate in candidates:
            try:
                sd.check_input_settings(
                    device=self.settings_store.value().microphone_device,
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
            self.update_audio_level(bytes(indata))
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
            device=self.settings_store.value().microphone_device,
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
                if self.audio_device_changed.is_set():
                    self.audio_device_changed.clear()
                    return
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
                    # Wait for a final Vosk result so the wake word does not
                    # consume the first words of the actual command.
                    if not wake_recognizer.AcceptWaveform(data):
                        continue
                    candidate = self.extract_result(wake_recognizer.Result())

                    if not self.contains_wake_phrase(candidate):
                        continue

                    self.play_activation_sound()
                    self.update_state(error="", mode="activated", partial="")
                    self.speak_feedback("Sim, pode falar.")
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
                    self.speak_feedback("Entendi, processando.")
                    self.drain_audio(audio_queue)
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

    def run_hybrid_audio_session(
        self,
        model: vosk.Model,
        configured_voice: VoiceActivityConfig,
    ) -> None:
        stt_provider, _stt_config = create_stt_provider(model, STT_CONFIG_FILE)
        sample_rate = self.select_input_sample_rate(stt_provider.preferred_sample_rate)
        voice_config = configured_voice.with_sample_rate(sample_rate)
        audio_queue: queue.Queue[bytes] = queue.Queue(
            maxsize=voice_config.frames_for(10.0)
        )

        def audio_callback(indata: bytes, frames: int, time_info: Any, status: Any):
            del frames, time_info
            if status:
                logging.warning("Estado do microfone: %s", status)
            self.update_audio_level(bytes(indata))
            try:
                audio_queue.put_nowait(bytes(indata))
            except queue.Full:
                try:
                    audio_queue.get_nowait()
                    audio_queue.put_nowait(bytes(indata))
                except queue.Empty:
                    pass

        wake_recognizer = self.create_recognizer(model, sample_rate, wake=True)
        stt_session: SpeechToTextSession | None = None
        voice_session: VoiceActivitySession | None = None
        local_speech_ended = False
        command_started_at = 0.0
        captured_frames = 0
        realtime_partial = ""
        local_endpoint_at = 0.0

        def reset_command_session() -> None:
            nonlocal stt_session, voice_session, local_speech_ended
            nonlocal captured_frames, realtime_partial, wake_recognizer
            nonlocal local_endpoint_at
            if stt_session:
                stt_session.close()
            stt_session = None
            voice_session = None
            local_speech_ended = False
            captured_frames = 0
            realtime_partial = ""
            local_endpoint_at = 0.0
            wake_recognizer = self.create_recognizer(model, sample_rate, wake=True)

        with sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=voice_config.frame_samples,
            device=self.settings_store.value().microphone_device,
            dtype="int16",
            channels=1,
            callback=audio_callback,
        ):
            self.update_state(
                error="",
                mode="wake",
                partial="",
                sttProvider=stt_provider.name,
            )
            logging.info(
                "Pipeline hibrido iniciado em %s Hz; STT=%s.",
                sample_rate,
                stt_provider.name,
            )

            while not self.stop_event.is_set():
                if self.audio_device_changed.is_set():
                    self.audio_device_changed.clear()
                    return
                if self.reset_recognizer.is_set():
                    self.reset_recognizer.clear()
                    self.drain_audio(audio_queue)
                    reset_command_session()

                if not self.listening_enabled.is_set():
                    self.update_state(mode="paused", partial="")
                    self.stop_event.wait(0.2)
                    self.drain_audio(audio_queue)
                    continue

                try:
                    data = audio_queue.get(timeout=0.25)
                except queue.Empty:
                    continue

                if stt_session is None:
                    if not wake_recognizer.AcceptWaveform(data):
                        continue
                    candidate = self.extract_result(wake_recognizer.Result())
                    if not self.contains_wake_phrase(candidate):
                        continue

                    self.voice_metrics.activation()
                    self.update_state(error="", mode="wake_detected", partial="")
                    self.play_activation_sound()
                    self.speak_feedback("Sim, pode falar.")
                    self.drain_audio(audio_queue)
                    stt_session = stt_provider.start_session(sample_rate)
                    voice_session = VoiceActivitySession(voice_config)
                    command_started_at = time.monotonic()
                    captured_frames = 0
                    local_speech_ended = False
                    local_endpoint_at = 0.0
                    realtime_partial = ""
                    self.update_state(
                        error="",
                        mode="activated",
                        partial="",
                        sttProvider=(
                            stt_provider.name
                            if stt_session.is_realtime
                            else "vosk-local"
                        ),
                    )
                    logging.info(
                        "Wake detectada; realtime=%s.", stt_session.is_realtime
                    )
                    continue

                if voice_session is None:
                    raise RuntimeError("Sessao VAD ausente durante a captura.")

                voice_event = VoiceActivityEvent.SPEECH
                if not local_speech_ended:
                    voice_event = voice_session.accept(data)
                captured_frames += 1
                stt_session.send_audio(data)

                completed_text = ""
                cloud_completed = False
                for stt_event in stt_session.poll():
                    if stt_event.type is STTEventType.SPEECH_STARTED:
                        self.update_state(mode="listening")
                    elif stt_event.type is STTEventType.PARTIAL and stt_event.text:
                        if stt_session.is_realtime:
                            realtime_partial += stt_event.text
                            self.update_state(partial=realtime_partial.strip())
                        else:
                            self.update_state(partial=stt_event.text)
                    elif stt_event.type is STTEventType.COMPLETED:
                        completed_text = stt_event.text.strip()
                        cloud_completed = bool(completed_text)
                    elif stt_event.type is STTEventType.ERROR:
                        self.voice_metrics.error()
                        logging.error("Falha no STT Realtime: %s", stt_event.error)

                if voice_event is VoiceActivityEvent.START_TIMEOUT:
                    logging.info("Ativacao cancelada: nenhuma fala detectada.")
                    self.drain_audio(audio_queue)
                    reset_command_session()
                    self.update_state(mode="wake", partial="")
                    continue

                if voice_event is VoiceActivityEvent.SPEECH_STARTED:
                    self.update_state(mode="listening")

                if voice_event is VoiceActivityEvent.SPEECH_ENDED:
                    local_speech_ended = True
                    local_endpoint_at = time.monotonic()
                    logging.info("Endpoint local detectado; aguardando Semantic VAD.")

                if (
                    local_speech_ended
                    and stt_session.is_realtime
                    and time.monotonic() - local_endpoint_at > 10.0
                ):
                    logging.error("Semantic VAD excedeu o limite de recuperacao.")
                    self.voice_metrics.error()
                    stt_session.fallback_to_local()

                should_finish = cloud_completed or (
                    local_speech_ended and not stt_session.is_realtime
                )
                if not should_finish:
                    continue

                command_text = completed_text or stt_session.local_result()
                latency_ms = int((time.monotonic() - command_started_at) * 1_000)
                audio_seconds = (
                    captured_frames * voice_config.frame_duration_ms / 1_000
                )
                provider_name = stt_provider.name if cloud_completed else "vosk-local"
                self.voice_metrics.transcription(
                    provider=provider_name,
                    audio_seconds=audio_seconds,
                    latency_ms=latency_ms,
                    fallback=stt_provider.name != "vosk-local" and not cloud_completed,
                )
                if command_text:
                    self.update_state(mode="processing", partial="")
                    self.speak_feedback("Entendi, processando.")
                    self.drain_audio(audio_queue)
                    self.complete_command(command_text, audio_queue)
                else:
                    self.voice_metrics.error()
                    self.drain_audio(audio_queue)
                    self.update_state(mode="wake", partial="")

                reset_command_session()

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
                self.run_hybrid_audio_session(model, voice_config)
                if self.stop_event.is_set():
                    return
                continue
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
        return platform_autostart_enabled()

    def set_autostart(self, enabled: bool) -> None:
        platform_set_autostart(enabled)

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
        threading.Thread(
            target=self.update_loop,
            name="release-update-check",
            daemon=True,
        ).start()

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
                    "Iniciar com o sistema",
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
