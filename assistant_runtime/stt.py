from __future__ import annotations

import base64
import json
import logging
import os
import time
from array import array
from dataclasses import dataclass, fields
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Protocol

import vosk

try:
    from .secret_store import load_secret
    from .app_paths import PATHS
except ImportError:
    from secret_store import load_secret
    from app_paths import PATHS


class STTEventType(Enum):
    SPEECH_STARTED = "speech_started"
    SPEECH_STOPPED = "speech_stopped"
    PARTIAL = "partial"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass(frozen=True)
class STTEvent:
    type: STTEventType
    text: str = ""
    error: str = ""


@dataclass(frozen=True)
class STTConfig:
    provider: str = "auto"
    realtime_model: str = "gpt-4o-transcribe"
    language: str = "pt"
    noise_reduction: str = "near_field"
    semantic_vad_eagerness: str = "low"
    vocabulary_file: str = "transcription_vocabulary.txt"

    def __post_init__(self) -> None:
        if self.provider not in {"auto", "openai_realtime", "local"}:
            raise ValueError("provider deve ser auto, openai_realtime ou local.")
        if self.noise_reduction not in {"near_field", "far_field"}:
            raise ValueError("noise_reduction deve ser near_field ou far_field.")
        if self.semantic_vad_eagerness not in {"low", "medium", "high", "auto"}:
            raise ValueError("semantic_vad_eagerness invalido.")

    @classmethod
    def from_file(cls, path: Path) -> STTConfig:
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("A configuracao STT deve ser um objeto JSON.")
        allowed = {field.name for field in fields(cls)}
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"Parametros STT desconhecidos: {', '.join(sorted(unknown))}.")
        return cls(**payload)


class SpeechToTextSession(Protocol):
    @property
    def is_realtime(self) -> bool: ...

    def send_audio(self, pcm16: bytes) -> None: ...

    def poll(self) -> list[STTEvent]: ...

    def local_result(self) -> str: ...

    def fallback_to_local(self) -> None: ...

    def close(self) -> None: ...


class SpeechToTextProvider(Protocol):
    @property
    def preferred_sample_rate(self) -> int: ...

    @property
    def name(self) -> str: ...

    def start_session(self, source_sample_rate: int) -> SpeechToTextSession: ...


class LocalVoskSession:
    def __init__(self, model: vosk.Model, sample_rate: int) -> None:
        self._recognizer = vosk.KaldiRecognizer(model, sample_rate)
        self._segments: list[str] = []
        self._last_partial = ""

    @property
    def is_realtime(self) -> bool:
        return False

    @staticmethod
    def _field(raw: str, field: str) -> str:
        try:
            return str(json.loads(raw).get(field, "")).strip()
        except (TypeError, ValueError, json.JSONDecodeError):
            return ""

    def send_audio(self, pcm16: bytes) -> None:
        if self._recognizer.AcceptWaveform(pcm16):
            text = self._field(self._recognizer.Result(), "text")
            if text:
                self._segments.append(text)
            self._last_partial = ""
        else:
            self._last_partial = self._field(
                self._recognizer.PartialResult(), "partial"
            )

    def poll(self) -> list[STTEvent]:
        if not self._last_partial:
            return []
        return [STTEvent(STTEventType.PARTIAL, text=self._last_partial)]

    def local_result(self) -> str:
        final = self._field(self._recognizer.FinalResult(), "text")
        return " ".join([*self._segments, final]).strip()

    def fallback_to_local(self) -> None:
        return

    def close(self) -> None:
        return


class LocalVoskSTT:
    def __init__(self, model: vosk.Model) -> None:
        self.model = model

    @property
    def preferred_sample_rate(self) -> int:
        return 16_000

    @property
    def name(self) -> str:
        return "vosk-local"

    def start_session(self, source_sample_rate: int) -> LocalVoskSession:
        return LocalVoskSession(self.model, source_sample_rate)


class OpenAIRealtimeSession:
    TARGET_SAMPLE_RATE = 24_000

    def __init__(
        self,
        *,
        api_key: str,
        config: STTConfig,
        source_sample_rate: int,
        vocabulary: tuple[str, ...],
        websocket_factory: Callable[..., Any] | None = None,
    ) -> None:
        if source_sample_rate != 48_000:
            raise ValueError("OpenAI Realtime requer captura local em 48000 Hz.")
        if websocket_factory is None:
            import websocket

            websocket_factory = websocket.create_connection

        self._socket = websocket_factory(
            f"wss://api.openai.com/v1/realtime?model={config.realtime_model}",
            header=[f"Authorization: Bearer {api_key}"],
            timeout=8,
        )
        self._socket.settimeout(0.001)
        self._closed = False
        self._completed_text = ""
        prompt = (
            "Transcreva comandos em portugues brasileiro para o assistente Doktor. "
            "Preserve nomes de programas, marcas e termos tecnicos. Vocabulário: "
            + ", ".join(vocabulary)
        )
        self._send(
            {
                "type": "session.update",
                "session": {
                    "type": "transcription",
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": 24_000},
                            "noise_reduction": {"type": config.noise_reduction},
                            "transcription": {
                                "model": config.realtime_model,
                                "language": config.language,
                                "prompt": prompt,
                            },
                            "turn_detection": {
                                "type": "semantic_vad",
                                "eagerness": config.semantic_vad_eagerness,
                            },
                        }
                    },
                },
            }
        )

    @property
    def is_realtime(self) -> bool:
        return True

    def _send(self, payload: dict[str, Any]) -> None:
        self._socket.send(json.dumps(payload, ensure_ascii=False))

    @staticmethod
    def _downsample_48k_to_24k(pcm16: bytes) -> bytes:
        samples = array("h")
        samples.frombytes(pcm16)
        return array("h", samples[::2]).tobytes()

    def send_audio(self, pcm16: bytes) -> None:
        audio = self._downsample_48k_to_24k(pcm16)
        self._send(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(audio).decode("ascii"),
            }
        )

    def poll(self) -> list[STTEvent]:
        events: list[STTEvent] = []
        while not self._closed:
            try:
                raw = self._socket.recv()
            except TimeoutError:
                break
            except Exception as error:
                # websocket-client raises WebSocketTimeoutException, which is
                # intentionally imported lazily to keep local mode lightweight.
                if error.__class__.__name__ == "WebSocketTimeoutException":
                    break
                events.append(STTEvent(STTEventType.ERROR, error=str(error)))
                break
            if not raw:
                break
            try:
                payload = json.loads(raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            event_type = payload.get("type")
            if event_type == "input_audio_buffer.speech_started":
                events.append(STTEvent(STTEventType.SPEECH_STARTED))
            elif event_type == "input_audio_buffer.speech_stopped":
                events.append(STTEvent(STTEventType.SPEECH_STOPPED))
            elif event_type == "conversation.item.input_audio_transcription.delta":
                events.append(STTEvent(STTEventType.PARTIAL, text=str(payload.get("delta", ""))))
            elif event_type == "conversation.item.input_audio_transcription.completed":
                self._completed_text = str(payload.get("transcript", "")).strip()
                events.append(STTEvent(STTEventType.COMPLETED, text=self._completed_text))
            elif event_type == "error":
                error = payload.get("error", {})
                message = error.get("message", "Erro desconhecido da OpenAI") if isinstance(error, dict) else str(error)
                events.append(STTEvent(STTEventType.ERROR, error=message))
        return events

    def local_result(self) -> str:
        return self._completed_text

    def fallback_to_local(self) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._socket.close()
        except Exception:
            logging.exception("Falha ao fechar sessao OpenAI Realtime.")


class OpenAIRealtimeSTT:
    def __init__(
        self,
        config: STTConfig,
        vocabulary: tuple[str, ...],
        *,
        api_key: str | None = None,
        websocket_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config
        self.vocabulary = vocabulary
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.websocket_factory = websocket_factory
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY nao configurada.")

    @property
    def preferred_sample_rate(self) -> int:
        return 48_000

    @property
    def name(self) -> str:
        return f"openai-realtime:{self.config.realtime_model}"

    def start_session(self, source_sample_rate: int) -> OpenAIRealtimeSession:
        return OpenAIRealtimeSession(
            api_key=self.api_key,
            config=self.config,
            source_sample_rate=source_sample_rate,
            vocabulary=self.vocabulary,
            websocket_factory=self.websocket_factory,
        )


class FallbackSTTProvider:
    def __init__(
        self,
        primary: SpeechToTextProvider | None,
        fallback: LocalVoskSTT,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.last_fallback_reason = ""

    @property
    def preferred_sample_rate(self) -> int:
        return self.primary.preferred_sample_rate if self.primary else self.fallback.preferred_sample_rate

    @property
    def name(self) -> str:
        return self.primary.name if self.primary else self.fallback.name

    def start_session(self, source_sample_rate: int) -> SpeechToTextSession:
        local_session = self.fallback.start_session(source_sample_rate)
        if self.primary:
            try:
                primary_session = self.primary.start_session(source_sample_rate)
                return MirroredSTTSession(primary_session, local_session)
            except Exception as error:
                self.last_fallback_reason = str(error)
                logging.exception("OpenAI STT indisponivel; usando Vosk local.")
        return local_session


class MirroredSTTSession:
    """Streams to OpenAI and Vosk together so fallback never loses audio."""

    def __init__(
        self,
        primary: SpeechToTextSession,
        fallback: LocalVoskSession,
    ) -> None:
        self.primary: SpeechToTextSession | None = primary
        self.fallback = fallback
        self._primary_result = ""

    @property
    def is_realtime(self) -> bool:
        return self.primary is not None and self.primary.is_realtime

    def send_audio(self, pcm16: bytes) -> None:
        self.fallback.send_audio(pcm16)
        if self.primary:
            try:
                self.primary.send_audio(pcm16)
            except Exception as error:
                logging.exception("Streaming OpenAI falhou; mantendo Vosk local.")
                self.primary.close()
                self.primary = None

    def poll(self) -> list[STTEvent]:
        if not self.primary:
            return self.fallback.poll()
        events = self.primary.poll()
        for event in events:
            if event.type is STTEventType.COMPLETED:
                self._primary_result = event.text
            elif event.type is STTEventType.ERROR:
                self.primary.close()
                self.primary = None
        return events

    def local_result(self) -> str:
        return self._primary_result or self.fallback.local_result()

    def fallback_to_local(self) -> None:
        if self.primary:
            self.primary.close()
            self.primary = None

    def close(self) -> None:
        if self.primary:
            self.primary.close()
            self.primary = None
        self.fallback.close()


def load_vocabulary(config_path: Path, config: STTConfig) -> tuple[str, ...]:
    path = config_path.parent / config.vocabulary_file
    if not path.exists():
        return ()
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def load_contextual_vocabulary(
    config_path: Path,
    config: STTConfig,
    application_discoverer: Callable[[], tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    static_terms = load_vocabulary(config_path, config)
    if application_discoverer is None:
        try:
            from .assistant_commands.context import visible_application_names
        except ImportError:
            from assistant_commands.context import visible_application_names

        application_discoverer = visible_application_names
    try:
        dynamic_terms = application_discoverer()
    except Exception:
        logging.exception("Nao foi possivel gerar vocabulario dos aplicativos visiveis.")
        dynamic_terms = ()

    merged: list[str] = []
    seen: set[str] = set()
    for term in (*static_terms, *dynamic_terms):
        clean = " ".join(str(term).split()).strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            merged.append(clean)
    return tuple(merged[:128])


def create_stt_provider(
    model: vosk.Model,
    config_path: Path,
) -> tuple[FallbackSTTProvider, STTConfig]:
    config = STTConfig.from_file(config_path)
    vocabulary = load_contextual_vocabulary(config_path, config)
    local = LocalVoskSTT(model)
    primary: SpeechToTextProvider | None = None
    key_file = PATHS.config / "openai-key.bin"
    api_key = os.environ.get("OPENAI_API_KEY", "") or load_secret(key_file)
    should_use_openai = config.provider == "openai_realtime" or (
        config.provider == "auto" and bool(api_key)
    )
    if should_use_openai and api_key:
        primary = OpenAIRealtimeSTT(
            config,
            vocabulary,
            api_key=api_key,
        )
    elif should_use_openai:
        logging.warning("OpenAI STT solicitado sem chave; usando Vosk local.")
    return FallbackSTTProvider(primary, local), config
