from __future__ import annotations

import argparse
import json
import platform
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import vosk

from assistant_runtime.app_paths import PATHS
from assistant_runtime.voice_activity import VoiceActivityConfig
from voice_lab.core import (
    classify_speech_cut,
    config_from_dict,
    intent_result,
    json_safe,
    load_jsonl,
    read_wav,
    replay_vad,
    transcribe_vosk,
    word_error_rate,
)


ROOT = Path(__file__).resolve().parent


def load_model() -> vosk.Model:
    vosk.SetLogLevel(-1)
    if not PATHS.model.exists():
        raise FileNotFoundError(f"Vosk model not found: {PATHS.model}")
    return vosk.Model(str(PATHS.model))


def expected_intent(record: dict[str, Any]) -> dict[str, Any] | None:
    expected = record.get("expected")
    return expected if isinstance(expected, dict) else None


def compare_intent(actual: dict[str, Any] | None, expected: dict[str, Any] | None) -> bool | None:
    if expected is None:
        return None
    if actual is None:
        return False
    for key in ("command_id", "kind", "target"):
        if key in expected and str(actual.get(key, "")).casefold() != str(expected[key]).casefold():
            return False
    return True


def compare_intent_kind(actual: dict[str, Any] | None, expected: dict[str, Any] | None) -> bool | None:
    if expected is None:
        return None
    if actual is None:
        return False
    keys = [key for key in ("command_id", "kind") if key in expected]
    if not keys:
        return None
    return all(
        str(actual.get(key, "")).casefold() == str(expected[key]).casefold()
        for key in keys
    )


def compare_entity(actual: dict[str, Any] | None, expected: dict[str, Any] | None) -> bool | None:
    if expected is None or "target" not in expected:
        return None
    if actual is None:
        return False
    return str(actual.get("target", "")).casefold() == str(expected["target"]).casefold()


def evaluate_record(
    record: dict[str, Any],
    config: VoiceActivityConfig,
    model: vosk.Model,
) -> dict[str, Any]:
    audio_path = ROOT / str(record["audio"])
    audio = read_wav(audio_path)
    vad = replay_vad(audio, config)
    transcript, stt_latency = transcribe_vosk(model, audio.pcm16, audio.sample_rate)
    actual_intent = intent_result(transcript)
    labeled = bool(record.get("labeled") and record.get("expected_text"))
    expected_text = str(record.get("expected_text", ""))
    wer = word_error_rate(expected_text, transcript) if labeled else None
    cut = classify_speech_cut(expected_text, transcript) if labeled else None
    expectation = expected_intent(record)
    intent_match = compare_intent_kind(actual_intent, expectation) if labeled else None
    entity_match = compare_entity(actual_intent, expectation) if labeled else None
    end_to_end_match = compare_intent(actual_intent, expectation) if labeled else None
    boundaries = [segment["boundary_risk"] for segment in vad["segments"]]
    return {
        "audio": str(record["audio"]),
        "condition": record.get("condition", "UNLABELED"),
        "labeled": labeled,
        "duration_seconds": round(audio.duration, 3),
        "signal": {key: value for key, value in vad.items() if key not in {"segments"}},
        "segment_count": len(vad["segments"]),
        "segments": [
            {key: value for key, value in segment.items() if key != "pcm16"}
            for segment in vad["segments"]
        ],
        "boundary_risk_count": sum(
            item["start_risk"] or item["end_risk"] for item in boundaries
        ),
        "stt": {
            "provider": "vosk-local",
            "final": transcript,
            "latency_ms": round(stt_latency, 2),
            "realtime_factor": round(stt_latency / max(1, audio.duration * 1_000), 4),
            "wer": wer,
        },
        "speech_cut": cut,
        "intent": actual_intent,
        "intent_match": intent_match,
        "entity_match": entity_match,
        "end_to_end_match": end_to_end_match,
    }


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    labeled = [record for record in records if record["labeled"]]
    wers = [record["stt"]["wer"] for record in labeled if record["stt"]["wer"] is not None]
    intent_matches = [record["intent_match"] for record in labeled if record["intent_match"] is not None]
    entity_matches = [record["entity_match"] for record in labeled if record.get("entity_match") is not None]
    end_to_end_matches = [
        record["end_to_end_match"]
        for record in labeled
        if record.get("end_to_end_match") is not None
    ]
    cuts = [record["speech_cut"] for record in labeled if record["speech_cut"] is not None]
    total_segments = sum(record["segment_count"] for record in records)
    return {
        "sample_count": len(records),
        "labeled_sample_count": len(labeled),
        "total_audio_seconds": round(sum(record["duration_seconds"] for record in records), 3),
        "segment_count": total_segments,
        "boundary_risk_rate_proxy": (
            round(sum(record["boundary_risk_count"] for record in records) / total_segments, 4)
            if total_segments
            else None
        ),
        "word_error_rate": round(sum(wers) / len(wers), 4) if wers else None,
        "speech_cut_rate": (
            round(sum(cut in {"START_CUT", "END_CUT"} for cut in cuts) / len(cuts), 4)
            if cuts
            else None
        ),
        "intent_accuracy": (
            round(sum(bool(value) for value in intent_matches) / len(intent_matches), 4)
            if intent_matches
            else None
        ),
        "entity_accuracy": (
            round(sum(bool(value) for value in entity_matches) / len(entity_matches), 4)
            if entity_matches
            else None
        ),
        "end_to_end_accuracy": (
            round(
                sum(bool(value) for value in end_to_end_matches)
                / len(end_to_end_matches),
                4,
            )
            if end_to_end_matches
            else None
        ),
        "mean_stt_latency_ms": round(
            sum(record["stt"]["latency_ms"] for record in records) / max(1, len(records)), 2
        ),
        "mean_stt_realtime_factor": round(
            sum(record["stt"]["realtime_factor"] for record in records) / max(1, len(records)), 4
        ),
    }


def run(manifest: Path, config: VoiceActivityConfig, output: Path) -> dict[str, Any]:
    model = load_model()
    records = [evaluate_record(record, config, model) for record in load_jsonl(manifest)]
    payload = {
        "schema_version": 1,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": {"platform": platform.platform(), "processor": platform.processor()},
        "provider": "vosk-local",
        "voice_config": asdict(config),
        "metrics": aggregate(records),
        "records": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay offline e seguro do Doktor Voice Lab")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "baseline.json")
    args = parser.parse_args()
    config = VoiceActivityConfig.from_file(Path("assistant_runtime/voice_config.json"))
    if args.config:
        wrapper = json.loads(args.config.read_text(encoding="utf-8"))
        config = config_from_dict(wrapper.get("voiceConfig", wrapper))
    payload = run(args.manifest, config, args.output)
    print(json.dumps(payload["metrics"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
