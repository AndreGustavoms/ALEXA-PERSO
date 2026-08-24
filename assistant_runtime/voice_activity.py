from __future__ import annotations

import json
import math
from array import array
from collections import deque
from dataclasses import dataclass, fields, replace
from enum import Enum
from pathlib import Path
from typing import Protocol

import webrtcvad


@dataclass(frozen=True)
class VoiceActivityConfig:
    activation_start_timeout: float = 12.0
    speech_end_silence: float = 1.5
    possible_end_silence: float = 0.3
    minimum_speech_duration: float = 0.06
    pre_roll_duration: float = 0.75
    end_padding_duration: float = 0.24
    watchdog_timeout: float = 45.0
    maximum_phrase_duration: None = None
    sample_rate: int = 16_000
    frame_duration_ms: int = 30
    vad_aggressiveness: int = 0
    sensitivity_preset: str = "VERY_HIGH"
    maximum_input_gain: float = 10.0

    def __post_init__(self) -> None:
        if not 1.0 <= self.activation_start_timeout <= 30.0:
            raise ValueError("activation_start_timeout deve ficar entre 1 e 30 segundos.")
        if not 0.3 <= self.speech_end_silence <= 10.0:
            raise ValueError("speech_end_silence deve ficar entre 0.3 e 10 segundos.")
        if not 0.1 <= self.possible_end_silence < self.speech_end_silence:
            raise ValueError("possible_end_silence deve preceder speech_end_silence.")
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
        if self.sensitivity_preset not in {"NORMAL", "HIGH", "VERY_HIGH"}:
            raise ValueError("sensitivity_preset invalido.")
        if not 1.0 <= self.maximum_input_gain <= 20.0:
            raise ValueError("maximum_input_gain deve ficar entre 1 e 20.")
        if not 0.3 <= self.pre_roll_duration <= 2.0:
            raise ValueError("pre_roll_duration deve ficar entre 0.3 e 2 segundos.")
        if not 0.0 <= self.end_padding_duration <= 1.0:
            raise ValueError("end_padding_duration deve ficar entre 0 e 1 segundo.")
        if not 15.0 <= self.watchdog_timeout <= 120.0:
            raise ValueError("watchdog_timeout deve ficar entre 15 e 120 segundos.")

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


def normalize_pcm16(
    frame: bytes,
    maximum_gain: float,
    target_peak: float = 0.2,
) -> bytes:
    """Lift quiet microphone input while limiting already-loud frames."""
    if maximum_gain <= 1.0 or not frame:
        return frame
    samples = array("h")
    samples.frombytes(frame)
    peak = max((abs(value) for value in samples), default=0)
    if not peak:
        return frame

    target = max(1, min(32_767, int(32_767 * target_peak)))
    gain = min(maximum_gain, max(1.0, target / peak))
    if gain <= 1.0:
        return frame

    for index, value in enumerate(samples):
        samples[index] = max(-32_768, min(32_767, round(value * gain)))
    return samples.tobytes()


class VoiceActivityEvent(Enum):
    WAITING = "waiting"
    SPEECH_STARTED = "speech_started"
    SPEECH = "speech"
    POSSIBLE_END = "possible_end"
    SPEECH_ENDED = "speech_ended"
    START_TIMEOUT = "start_timeout"


class TurnState(Enum):
    WAITING = "waiting"
    POSSIBLE_SPEECH = "possible_speech"
    ACTIVE_SPEECH = "active_speech"
    POSSIBLE_END = "possible_end"
    ENDED = "ended"


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
        if not clean:
            return
        if not self._segments:
            self._segments.append(clean)
            return

        # Vosk can repeat the last words when it closes a segment after a
        # pause. Merge the largest word overlap instead of duplicating it.
        previous_words = self._segments[-1].split()
        current_words = clean.split()
        overlap = 0
        for size in range(1, min(5, len(previous_words), len(current_words)) + 1):
            if [word.casefold() for word in previous_words[-size:]] == [
                word.casefold() for word in current_words[:size]
            ]:
                overlap = size
        self._segments.append(" ".join(current_words[overlap:]) or clean)

    def preview(self, partial: str = "") -> str:
        clean_partial = partial.strip()
        return " ".join([*self._segments, clean_partial]).strip()

    def finish(self, final_text: str = "") -> str:
        return self.preview(final_text)


class TurnManager:
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
        self._possible_end_emitted = False
        self.state = TurnState.WAITING
        self.last_is_speech = False

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
        self.last_is_speech = contains_speech

        if not self.has_started:
            # A single VAD miss must not erase an otherwise valid quiet onset.
            self._voiced_frames = (
                self._voiced_frames + 1
                if contains_speech
                else max(0, self._voiced_frames - 1)
            )
            self.state = (
                TurnState.POSSIBLE_SPEECH
                if self._voiced_frames
                else TurnState.WAITING
            )
            if self._voiced_frames >= self.config.frames_for(
                self.config.minimum_speech_duration
            ):
                self.has_started = True
                self._silent_frames = 0
                self.state = TurnState.ACTIVE_SPEECH
                return VoiceActivityEvent.SPEECH_STARTED

            if (
                not contains_speech
                and self._elapsed_frames
                >= self.config.frames_for(self.config.activation_start_timeout)
            ):
                self._finished = True
                self.state = TurnState.ENDED
                return VoiceActivityEvent.START_TIMEOUT
            return VoiceActivityEvent.WAITING

        if contains_speech:
            self._silent_frames = 0
            self._possible_end_emitted = False
            self.state = TurnState.ACTIVE_SPEECH
            return VoiceActivityEvent.SPEECH

        self._silent_frames += 1
        end_after = self.config.speech_end_silence + self.config.end_padding_duration
        if self._silent_frames >= self.config.frames_for(end_after):
            self._finished = True
            self.state = TurnState.ENDED
            return VoiceActivityEvent.SPEECH_ENDED
        if (
            not self._possible_end_emitted
            and self._silent_frames
            >= self.config.frames_for(self.config.possible_end_silence)
        ):
            self._possible_end_emitted = True
            self.state = TurnState.POSSIBLE_END
            return VoiceActivityEvent.POSSIBLE_END
        return VoiceActivityEvent.SPEECH

    @property
    def elapsed_seconds(self) -> float:
        return self._elapsed_frames * self.config.frame_duration_ms / 1_000

    @property
    def silence_seconds(self) -> float:
        return self._silent_frames * self.config.frame_duration_ms / 1_000


# Compatibility for integrations that used the previous public name.
VoiceActivitySession = TurnManager


@dataclass(frozen=True)
class AudioFrameMetrics:
    raw_rms: float
    processed_rms: float
    peak: float
    noise_floor: float
    gain: float
    clipping: float


class AudioPreprocessor:
    """Stateful, bounded gain control with observable signal metrics."""

    def __init__(self, maximum_gain: float, target_rms: float = 0.055) -> None:
        self.maximum_gain = maximum_gain
        self.target_rms = target_rms
        self.noise_floor = 0.002
        self.gain = min(3.0, maximum_gain)

    @staticmethod
    def _levels(frame: bytes) -> tuple[float, float]:
        samples = array("h")
        samples.frombytes(frame)
        if not samples:
            return 0.0, 0.0
        rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32_768
        peak = max(abs(value) for value in samples) / 32_768
        return rms, peak

    def process(self, frame: bytes) -> tuple[bytes, AudioFrameMetrics]:
        raw_rms, raw_peak = self._levels(frame)
        if raw_rms <= self.noise_floor * 1.8:
            self.noise_floor = 0.98 * self.noise_floor + 0.02 * raw_rms

        signal_floor = max(raw_rms, self.noise_floor * 1.35, 1 / 32_768)
        desired_gain = min(self.maximum_gain, max(1.0, self.target_rms / signal_floor))
        smoothing = 0.28 if desired_gain > self.gain else 0.08
        self.gain += (desired_gain - self.gain) * smoothing

        peak_limited_gain = min(self.gain, 0.92 / raw_peak) if raw_peak else self.gain
        processed = normalize_pcm16(frame, peak_limited_gain, target_peak=0.92)
        processed_rms, processed_peak = self._levels(processed)
        samples = array("h")
        samples.frombytes(processed)
        clipped = sum(abs(value) >= 32_760 for value in samples)
        clipping = clipped / len(samples) if samples else 0.0
        return processed, AudioFrameMetrics(
            raw_rms=raw_rms,
            processed_rms=processed_rms,
            peak=processed_peak,
            noise_floor=self.noise_floor,
            gain=peak_limited_gain,
            clipping=clipping,
        )


class AudioPreRollBuffer:
    def __init__(self, config: VoiceActivityConfig) -> None:
        self._frames: deque[bytes] = deque(
            maxlen=config.frames_for(config.pre_roll_duration)
        )

    def append(self, frame: bytes) -> None:
        self._frames.append(frame)

    def snapshot(self) -> tuple[bytes, ...]:
        return tuple(self._frames)

    def clear(self) -> None:
        self._frames.clear()
