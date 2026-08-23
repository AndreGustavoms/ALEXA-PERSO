from __future__ import annotations

import json
import math
from dataclasses import dataclass, fields, replace
from enum import Enum
from pathlib import Path
from typing import Protocol

import webrtcvad


@dataclass(frozen=True)
class VoiceActivityConfig:
    activation_start_timeout: float = 7.0
    speech_end_silence: float = 2.0
    minimum_speech_duration: float = 0.24
    maximum_phrase_duration: None = None
    sample_rate: int = 16_000
    frame_duration_ms: int = 30
    vad_aggressiveness: int = 2

    def __post_init__(self) -> None:
        if not 1.0 <= self.activation_start_timeout <= 30.0:
            raise ValueError("activation_start_timeout deve ficar entre 1 e 30 segundos.")
        if not 0.3 <= self.speech_end_silence <= 10.0:
            raise ValueError("speech_end_silence deve ficar entre 0.3 e 10 segundos.")
        if not 0.06 <= self.minimum_speech_duration <= 3.0:
            raise ValueError("minimum_speech_duration deve ficar entre 0.06 e 3 segundos.")
        if self.maximum_phrase_duration is not None:
            raise ValueError("maximum_phrase_duration deve permanecer null.")
        if self.sample_rate not in (8_000, 16_000, 32_000, 48_000):
            raise ValueError("sample_rate deve ser 8000, 16000, 32000 ou 48000 Hz.")
        if self.frame_duration_ms not in (10, 20, 30):
            raise ValueError("frame_duration_ms deve ser 10, 20 ou 30 ms.")
        if self.vad_aggressiveness not in (0, 1, 2, 3):
            raise ValueError("vad_aggressiveness deve ficar entre 0 e 3.")

    @property
    def frame_samples(self) -> int:
        return self.sample_rate * self.frame_duration_ms // 1_000

    @property
    def frame_bytes(self) -> int:
        return self.frame_samples * 2

    def frames_for(self, seconds: float) -> int:
        return max(1, math.ceil(seconds * 1_000 / self.frame_duration_ms))

    def with_sample_rate(self, sample_rate: int) -> VoiceActivityConfig:
        return replace(self, sample_rate=sample_rate)

    @classmethod
    def from_file(cls, path: Path) -> VoiceActivityConfig:
        if not path.exists():
            return cls()

        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("A configuração de voz deve ser um objeto JSON.")

        allowed = {field.name for field in fields(cls)}
        unknown = set(payload) - allowed
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"Parâmetros de voz desconhecidos: {names}.")
        return cls(**payload)


class VoiceActivityEvent(Enum):
    WAITING = "waiting"
    SPEECH_STARTED = "speech_started"
    SPEECH = "speech"
    SPEECH_ENDED = "speech_ended"
    START_TIMEOUT = "start_timeout"


class SpeechDetector(Protocol):
    def is_speech(self, frame: bytes, sample_rate: int) -> bool: ...


class WebRtcSpeechDetector:
    def __init__(self, aggressiveness: int) -> None:
        self._detector = webrtcvad.Vad(aggressiveness)

    def is_speech(self, frame: bytes, sample_rate: int) -> bool:
        return self._detector.is_speech(frame, sample_rate)


class TranscriptAccumulator:
    def __init__(self) -> None:
        self._segments: list[str] = []

    def add(self, text: str) -> None:
        clean = text.strip()
        if clean:
            self._segments.append(clean)

    def preview(self, partial: str = "") -> str:
        clean_partial = partial.strip()
        return " ".join([*self._segments, clean_partial]).strip()

    def finish(self, final_text: str = "") -> str:
        return self.preview(final_text)


class VoiceActivitySession:
    def __init__(
        self,
        config: VoiceActivityConfig,
        detector: SpeechDetector | None = None,
    ) -> None:
        self.config = config
        self.detector = detector or WebRtcSpeechDetector(config.vad_aggressiveness)
        self.has_started = False
        self._finished = False
        self._elapsed_frames = 0
        self._voiced_frames = 0
        self._silent_frames = 0

    def accept(self, frame: bytes) -> VoiceActivityEvent:
        if self._finished:
            raise RuntimeError("A sessão de fala já foi encerrada.")
        if len(frame) != self.config.frame_bytes:
            raise ValueError(
                f"Frame PCM inválido: esperado {self.config.frame_bytes} bytes, "
                f"recebido {len(frame)}."
            )

        self._elapsed_frames += 1
        contains_speech = self.detector.is_speech(frame, self.config.sample_rate)

        if not self.has_started:
            self._voiced_frames = self._voiced_frames + 1 if contains_speech else 0
            if self._voiced_frames >= self.config.frames_for(
                self.config.minimum_speech_duration
            ):
                self.has_started = True
                self._silent_frames = 0
                return VoiceActivityEvent.SPEECH_STARTED

            if (
                not contains_speech
                and self._elapsed_frames
                >= self.config.frames_for(self.config.activation_start_timeout)
            ):
                self._finished = True
                return VoiceActivityEvent.START_TIMEOUT
            return VoiceActivityEvent.WAITING

        if contains_speech:
            self._silent_frames = 0
            return VoiceActivityEvent.SPEECH

        self._silent_frames += 1
        if self._silent_frames >= self.config.frames_for(
            self.config.speech_end_silence
        ):
            self._finished = True
            return VoiceActivityEvent.SPEECH_ENDED
        return VoiceActivityEvent.SPEECH
