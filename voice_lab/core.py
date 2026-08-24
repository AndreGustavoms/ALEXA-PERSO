from __future__ import annotations

import json
import math
import time
import wave
from array import array
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

@dataclass(frozen=True)
class AudioData:
    path: Path
    sample_rate: int
    pcm16: bytes

    @property
    def duration(self) -> float:
        return len(self.pcm16) / (self.sample_rate * 2)


def read_wav(path: Path) -> AudioData:
    with wave.open(str(path), "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError(f"{path} must be mono PCM16 WAV")
        rate = source.getframerate()
        return AudioData(path, rate, source.readframes(source.getnframes()))


def write_wav(path: Path, pcm16: bytes, sample_rate: int = 16_000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(pcm16)


def iter_frames(pcm16: bytes, frame_bytes: int) -> Iterable[bytes]:
    for offset in range(0, len(pcm16) - frame_bytes + 1, frame_bytes):
        yield pcm16[offset : offset + frame_bytes]


def levels(pcm16: bytes) -> tuple[float, float, float]:
    samples = array("h")
    samples.frombytes(pcm16)
    if not samples:
        return 0.0, 0.0, 0.0
    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32_768
    peak = max(abs(value) for value in samples) / 32_768
    clipping = sum(abs(value) >= 32_760 for value in samples) / len(samples)
    return rms, peak, clipping


def normalize_words(text: str) -> list[str]:
    from assistant_runtime.assistant_commands.normalization import normalize_text

    return normalize_text(text).split()


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, expected in enumerate(reference, start=1):
        current = [row]
        for column, actual in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (expected != actual),
                )
            )
        previous = current
    return previous[-1]


def word_error_rate(expected: str, actual: str) -> float | None:
    reference = normalize_words(expected)
    if not reference:
        return None
    return edit_distance(reference, normalize_words(actual)) / len(reference)


def character_error_rate(expected: str, actual: str) -> float | None:
    reference = list(" ".join(normalize_words(expected)))
    if not reference:
        return None
    hypothesis = list(" ".join(normalize_words(actual)))
    return edit_distance(reference, hypothesis) / len(reference)


def classify_speech_cut(expected: str, actual: str) -> str:
    reference = normalize_words(expected)
    hypothesis = normalize_words(actual)
    if not reference or not hypothesis:
        return "UNKNOWN"
    if reference == hypothesis:
        return "NONE"
    if len(reference) > 1 and hypothesis == reference[1:]:
        return "START_CUT"
    if len(reference) > 1 and hypothesis == reference[:-1]:
        return "END_CUT"
    expected_flat = "".join(reference)
    actual_flat = "".join(hypothesis)
    if len(actual_flat) >= 3 and expected_flat.endswith(actual_flat):
        return "START_CUT"
    if len(actual_flat) >= 3 and expected_flat.startswith(actual_flat):
        return "END_CUT"
    return "OTHER_ERROR"


def intent_result(
    text: str,
    context_name: str = "none",
    previous_target: str = "",
) -> dict[str, Any] | None:
    from assistant_runtime.assistant_commands.models import WindowContext
    from assistant_runtime.assistant_commands.parser import IntentParser
    from assistant_runtime.assistant_commands.router import CommandRouter
    from assistant_runtime.intent_benchmark import context_for, resolved_entity

    context = context_for(context_name) if context_name != "none" else WindowContext()
    intents = CommandRouter(IntentParser()).parse(text, context, previous_target)
    if not intents:
        return None
    intent = intents[0]
    target = resolved_entity(intent.parameters)
    return {
        "command_id": intent.spec.id,
        "kind": intent.kind.value,
        "target": str(target),
        "parameters": intent.parameters,
        "confidence": intent.confidence,
    }


def compare_intent(
    actual: dict[str, Any] | None,
    expected: dict[str, Any] | None,
) -> bool | None:
    if expected is None:
        return None
    if expected.get("kind") == "NONE":
        return actual is None
    if actual is None:
        return False
    return all(
        str(actual.get(key, "")).casefold() == str(value).casefold()
        for key, value in expected.items()
        if key in {"command_id", "kind", "target"}
    )


def compare_intent_kind(
    actual: dict[str, Any] | None,
    expected: dict[str, Any] | None,
) -> bool | None:
    if expected is None:
        return None
    if expected.get("kind") == "NONE":
        return actual is None
    if actual is None:
        return False
    keys = [key for key in ("command_id", "kind") if key in expected]
    if not keys:
        return None
    return all(
        str(actual.get(key, "")).casefold() == str(expected[key]).casefold()
        for key in keys
    )


def compare_entity(
    actual: dict[str, Any] | None,
    expected: dict[str, Any] | None,
) -> bool | None:
    if expected is not None and expected.get("kind") == "NONE":
        return None
    if expected is None or "target" not in expected:
        return None
    if actual is None:
        return False
    return str(actual.get("target", "")).casefold() == str(expected["target"]).casefold()


def transcribe_vosk(model: Any, pcm16: bytes, sample_rate: int) -> tuple[str, float]:
    from assistant_runtime.stt import LocalVoskSession

    started = time.perf_counter()
    session = LocalVoskSession(model, sample_rate)
    for frame in iter_frames(pcm16, sample_rate * 2 // 10):
        session.send_audio(frame)
    text = session.local_result()
    return text, (time.perf_counter() - started) * 1_000


def preprocess_audio(
    pcm16: bytes,
    config: Any,
) -> tuple[bytes, dict[str, float]]:
    from assistant_runtime.voice_activity import AudioPreprocessor

    preprocessor = AudioPreprocessor(config.maximum_input_gain)
    processed_frames = []
    clipping = 0.0
    for frame in iter_frames(pcm16, config.frame_bytes):
        processed, metrics = preprocessor.process(frame)
        processed_frames.append(processed)
        clipping += metrics.clipping
    return b"".join(processed_frames), {
        "noise_floor_final": round(preprocessor.noise_floor, 6),
        "gain_final": round(preprocessor.gain, 3),
        "clipping_mean": round(clipping / max(1, len(processed_frames)), 8),
    }


def _boundary_risk(pcm16: bytes, sample_rate: int) -> dict[str, Any]:
    window_bytes = max(2, int(sample_rate * 0.12) * 2)
    whole_rms, _, _ = levels(pcm16)
    start_rms, _, _ = levels(pcm16[:window_bytes])
    end_rms, _, _ = levels(pcm16[-window_bytes:])
    threshold = max(0.008, whole_rms * 0.45)
    return {
        "start_rms": round(start_rms, 6),
        "end_rms": round(end_rms, 6),
        "threshold": round(threshold, 6),
        "start_risk": start_rms >= threshold,
        "end_risk": end_rms >= threshold,
    }


def replay_vad(audio: AudioData, config: Any) -> dict[str, Any]:
    from assistant_runtime.voice_activity import (
        AudioPreprocessor,
        AudioPreRollBuffer,
        TurnManager,
        VoiceActivityEvent,
        create_speech_detector,
    )

    if audio.sample_rate != config.sample_rate:
        raise ValueError("WAV sample rate must match VoiceActivityConfig")

    preprocessor = AudioPreprocessor(config.maximum_input_gain)
    pre_roll = AudioPreRollBuffer(config)
    detector = create_speech_detector(config)
    manager = None
    segments: list[dict[str, Any]] = []
    segment_frames: list[bytes] = []
    frame_metrics = []
    probabilities = []
    elapsed_frames = 0
    speech_start_frame = 0
    started = time.perf_counter()

    manager = TurnManager(config, detector)
    for raw in iter_frames(audio.pcm16, config.frame_bytes):
        elapsed_frames += 1
        processed, metrics = preprocessor.process(raw)
        frame_metrics.append(metrics)
        pre_roll.append(processed)
        event = manager.accept(processed)
        probabilities.append(manager.vad_probability)
        if event is VoiceActivityEvent.SPEECH_STARTED:
            segment_frames = list(pre_roll.snapshot())
            speech_start_frame = elapsed_frames - len(segment_frames) + 1
        elif manager.has_started and event is not VoiceActivityEvent.SPEECH_STARTED:
            segment_frames.append(processed)
        if event is VoiceActivityEvent.SPEECH_ENDED:
            payload = b"".join(segment_frames)
            segments.append(
                {
                    "start_seconds": round(
                        max(0, speech_start_frame - 1)
                        * config.frame_duration_ms
                        / 1_000,
                        3,
                    ),
                    "end_seconds": round(
                        elapsed_frames * config.frame_duration_ms / 1_000, 3
                    ),
                    "duration_seconds": round(
                        len(payload) / (config.sample_rate * 2), 3
                    ),
                    "pcm16": payload,
                    "boundary_risk": _boundary_risk(payload, config.sample_rate),
                }
            )
            detector = create_speech_detector(config)
            manager = TurnManager(config, detector)
            pre_roll.clear()
            segment_frames = []

    if manager.has_started and segment_frames:
        payload = b"".join(segment_frames)
        segments.append(
            {
                "start_seconds": round(
                    max(0, speech_start_frame - 1) * config.frame_duration_ms / 1_000,
                    3,
                ),
                "end_seconds": round(audio.duration, 3),
                "duration_seconds": round(len(payload) / (config.sample_rate * 2), 3),
                "pcm16": payload,
                "boundary_risk": _boundary_risk(payload, config.sample_rate),
            }
        )

    raw_rms, raw_peak, raw_clipping = levels(audio.pcm16)
    latency_ms = (time.perf_counter() - started) * 1_000
    return {
        "engine": manager.vad_engine,
        "raw_rms": round(raw_rms, 6),
        "raw_peak": round(raw_peak, 6),
        "raw_clipping": round(raw_clipping, 8),
        "processed_rms_mean": round(
            sum(item.processed_rms for item in frame_metrics) / max(1, len(frame_metrics)),
            6,
        ),
        "processed_peak_max": round(
            max((item.peak for item in frame_metrics), default=0.0), 6
        ),
        "processed_clipping_mean": round(
            sum(item.clipping for item in frame_metrics) / max(1, len(frame_metrics)),
            8,
        ),
        "noise_floor_final": round(preprocessor.noise_floor, 6),
        "gain_final": round(preprocessor.gain, 3),
        "vad_probability_mean": round(
            sum(probabilities) / max(1, len(probabilities)), 6
        ),
        "replay_latency_ms": round(latency_ms, 2),
        "realtime_factor": round(latency_ms / max(1, audio.duration * 1_000), 4),
        "segments": segments,
    }


def config_from_dict(payload: dict[str, Any]) -> Any:
    from assistant_runtime.voice_activity import VoiceActivityConfig

    base = VoiceActivityConfig()
    allowed = set(asdict(base))
    values = {key: value for key, value in payload.items() if key in allowed}
    return replace(base, **values)


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return f"<{len(value)} PCM bytes>"
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_safe(item) for item in value]
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSONL at {path}:{line_number}: {error}") from error
    return records
