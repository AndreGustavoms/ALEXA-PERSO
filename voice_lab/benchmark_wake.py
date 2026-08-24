from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import vosk

from assistant_runtime.app_paths import PATHS
from assistant_runtime.main import WAKE_VARIANTS
from assistant_runtime.wake_word import VoskWakeWordEngine, WakeWordConfig
from voice_lab.core import iter_frames, load_jsonl, read_wav


ROOT = Path(__file__).resolve().parent


def evaluate_vosk(model: vosk.Model, record: dict[str, Any]) -> dict[str, Any]:
    audio = read_wav(ROOT / str(record["audio"]))
    grammar = json.dumps([*WAKE_VARIANTS, "[unk]"], ensure_ascii=False)
    engine = VoskWakeWordEngine(
        vosk.KaldiRecognizer(model, audio.sample_rate, grammar), WAKE_VARIANTS
    )
    detections = 0
    first_detection_ms = None
    frame_bytes = audio.sample_rate * 2 * 30 // 1_000
    for index, frame in enumerate(iter_frames(audio.pcm16, frame_bytes), start=1):
        if engine.accept(frame, audio.sample_rate).detected:
            detections += 1
            if first_detection_ms is None:
                first_detection_ms = index * 30
    expected_wake = record.get("expected_wake")
    return {
        "audio": record["audio"],
        "expected_wake": expected_wake if isinstance(expected_wake, bool) else None,
        "detected": detections > 0,
        "detection_count": detections,
        "first_detection_ms": first_detection_ms,
    }


def supervised_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    labeled = [record for record in records if record["expected_wake"] is not None]
    positives = [record for record in labeled if record["expected_wake"]]
    negatives = [record for record in labeled if not record["expected_wake"]]
    true_positives = sum(record["detected"] for record in positives)
    false_positives = sum(record["detected"] for record in negatives)
    return {
        "labeled_sample_count": len(labeled),
        "wake_recall": round(true_positives / len(positives), 4) if positives else None,
        "false_reject_rate": (
            round(1 - true_positives / len(positives), 4) if positives else None
        ),
        "false_accept_rate": (
            round(false_positives / len(negatives), 4) if negatives else None
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark offline de wake word")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "wake.json")
    args = parser.parse_args()
    vosk.SetLogLevel(-1)
    model = vosk.Model(str(PATHS.model))
    records = [evaluate_vosk(model, record) for record in load_jsonl(args.manifest)]
    configured = WakeWordConfig.from_file(Path("assistant_runtime/wake_word_config.json"))
    custom_model = PATHS.voice_models / configured.model_file
    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "active_provider": "vosk-fallback",
        "openwakeword": {
            "status": "not_run" if not custom_model.exists() else "model_available",
            "reason": None if custom_model.exists() else f"custom model absent: {custom_model}",
        },
        "metrics": supervised_metrics(records),
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
