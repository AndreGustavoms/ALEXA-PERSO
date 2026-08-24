from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class WakeWordConfig:
    engine: str = "auto"
    phrase: str = "ola doktor"
    threshold: float = 0.55
    vad_threshold: float = 0.35
    consecutive_frames: int = 2
    model_file: str = "ola_doktor.onnx"

    def __post_init__(self) -> None:
        if self.engine not in {"auto", "openwakeword", "vosk"}:
            raise ValueError("Wake engine invalido.")
        if not 0.05 <= self.threshold <= 0.95:
            raise ValueError("Wake threshold invalido.")
        if not 0.0 <= self.vad_threshold <= 0.95:
            raise ValueError("Wake VAD threshold invalido.")
        if not 1 <= self.consecutive_frames <= 5:
            raise ValueError("consecutive_frames deve ficar entre 1 e 5.")

    @classmethod
    def from_file(cls, path: Path) -> WakeWordConfig:
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        allowed = {item.name for item in fields(cls)}
        if not isinstance(payload, dict) or set(payload) - allowed:
            raise ValueError("Configuracao de wake word invalida.")
        return cls(**payload)


@dataclass(frozen=True)
class WakeWordResult:
    detected: bool
    score: float | None
    engine: str


class WakeWordEngine(Protocol):
    name: str
    score: float | None

    def accept(self, pcm16: bytes, sample_rate: int) -> WakeWordResult: ...


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(
        character
        for character in normalized
        if unicodedata.category(character) != "Mn"
    ).casefold()


class VoskWakeWordEngine:
    def __init__(self, recognizer: Any, variants: tuple[str, ...]) -> None:
        self.recognizer = recognizer
        self.variants = tuple(_normalize(item) for item in variants)
        self.name = "vosk-fallback"
        self.score: float | None = None

    @staticmethod
    def _field(payload: str, key: str) -> str:
        try:
            return str(json.loads(payload).get(key, "")).strip()
        except (TypeError, ValueError, json.JSONDecodeError):
            return ""

    def accept(self, pcm16: bytes, sample_rate: int) -> WakeWordResult:
        del sample_rate
        accepted = self.recognizer.AcceptWaveform(pcm16)
        text = self._field(
            self.recognizer.Result() if accepted else self.recognizer.PartialResult(),
            "text" if accepted else "partial",
        )
        normalized = _normalize(text)
        detected = any(variant in normalized for variant in self.variants)
        return WakeWordResult(detected, None, self.name)


class OpenWakeWordEngine:
    FRAME_SAMPLES = 1_280

    def __init__(
        self,
        config: WakeWordConfig,
        model_path: Path,
        feature_directory: Path,
    ) -> None:
        import numpy as np
        from openwakeword.model import Model

        self._np = np
        self.config = config
        self.name = "openwakeword-0.6.0"
        self.score: float | None = 0.0
        self._hits = 0
        self._pending = np.empty(0, dtype=np.int16)
        self._model = Model(
            wakeword_models=[str(model_path)],
            inference_framework="onnx",
            vad_threshold=config.vad_threshold,
            melspec_model_path=str(feature_directory / "melspectrogram.onnx"),
            embedding_model_path=str(feature_directory / "embedding_model.onnx"),
        )

    def accept(self, pcm16: bytes, sample_rate: int) -> WakeWordResult:
        if sample_rate < 16_000 or sample_rate % 16_000:
            raise ValueError(f"openWakeWord nao suporta {sample_rate} Hz.")
        step = sample_rate // 16_000
        samples = self._np.frombuffer(pcm16, dtype=self._np.int16)[::step]
        self._pending = self._np.concatenate((self._pending, samples))
        detected = False
        while self._pending.size >= self.FRAME_SAMPLES:
            frame = self._pending[: self.FRAME_SAMPLES]
            self._pending = self._pending[self.FRAME_SAMPLES :]
            predictions = self._model.predict(frame)
            self.score = max((float(value) for value in predictions.values()), default=0.0)
            self._hits = self._hits + 1 if self.score >= self.config.threshold else 0
            if self._hits >= self.config.consecutive_frames:
                detected = True
                self._hits = 0
                break
        return WakeWordResult(detected, self.score, self.name)


def create_wake_word_engine(
    config: WakeWordConfig,
    *,
    recognizer: Any,
    variants: tuple[str, ...],
    model_directory: Path,
) -> WakeWordEngine:
    model_path = model_directory / config.model_file
    features = model_directory / "openwakeword"
    resources_ready = all(
        path.exists()
        for path in (
            model_path,
            features / "melspectrogram.onnx",
            features / "embedding_model.onnx",
            features / "silero_vad.onnx",
        )
    )
    if config.engine != "vosk" and resources_ready:
        try:
            return OpenWakeWordEngine(config, model_path, features)
        except (ImportError, OSError, RuntimeError, ValueError):
            if config.engine == "openwakeword":
                raise
    return VoskWakeWordEngine(recognizer, variants)
