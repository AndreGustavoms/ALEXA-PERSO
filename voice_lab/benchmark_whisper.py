from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from voice_lab.core import (
    character_error_rate,
    classify_speech_cut,
    compare_entity,
    compare_intent,
    compare_intent_kind,
    intent_result,
    load_jsonl,
    read_wav,
    word_error_rate,
)
from voice_lab.providers import FasterWhisperSTTProvider


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B local com faster-whisper")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", default="base")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "faster-whisper.json")
    args = parser.parse_args()
    provider = FasterWhisperSTTProvider(args.model, beam_size=args.beam_size)
    results = []
    for record in load_jsonl(args.manifest):
        path = ROOT / str(record["audio"])
        audio = read_wav(path)
        result = provider.transcribe(path, audio.duration)
        labeled = bool(
            (record.get("text_labeled") or record.get("labeled"))
            and record.get("expected_text")
        )
        actual_intent = intent_result(
            result.text,
            str(record.get("context", "none")),
            str(record.get("previous_target", "")),
        )
        expected = record.get("expected") if isinstance(record.get("expected"), dict) else None
        action_labeled = bool(record.get("action_labeled", labeled))
        results.append(
            {
                "audio": record["audio"],
                "labeled": labeled,
                "transcription": result.__dict__,
                "wer": (
                    word_error_rate(str(record["expected_text"]), result.text)
                    if labeled
                    else None
                ),
                "cer": (
                    character_error_rate(str(record["expected_text"]), result.text)
                    if labeled
                    else None
                ),
                "speech_cut": (
                    classify_speech_cut(str(record["expected_text"]), result.text)
                    if labeled
                    else None
                ),
                "intent": actual_intent,
                "expected": expected,
                "intent_match": (
                    compare_intent_kind(actual_intent, expected)
                    if action_labeled
                    else None
                ),
                "entity_match": (
                    compare_entity(actual_intent, expected)
                    if action_labeled
                    else None
                ),
                "end_to_end_match": (
                    compare_intent(actual_intent, expected)
                    if action_labeled
                    else None
                ),
                "split": record.get("split"),
            }
        )
        text_results = [item for item in results if item["labeled"]]
        action_results = [
            item for item in results if item["end_to_end_match"] is not None
        ]
        entity_results = [item for item in results if item["entity_match"] is not None]
        intent_results = [item for item in results if item["intent_match"] is not None]
        metrics = {
            "sample_count": len(results),
            "word_error_rate": round(
                sum(item["wer"] for item in text_results) / len(text_results), 4
            ) if text_results else None,
            "character_error_rate": round(
                sum(item["cer"] for item in text_results) / len(text_results), 4
            ) if text_results else None,
            "speech_cut_rate": round(
                sum(item["speech_cut"] in {"START_CUT", "END_CUT"} for item in text_results)
                / len(text_results), 4
            ) if text_results else None,
            "intent_accuracy": round(
                sum(item["intent_match"] for item in intent_results) / len(intent_results), 4
            ) if intent_results else None,
            "entity_accuracy": round(
                sum(item["entity_match"] for item in entity_results) / len(entity_results), 4
            ) if entity_results else None,
            "end_to_end_accuracy": round(
                sum(item["end_to_end_match"] for item in action_results) / len(action_results), 4
            ) if action_results else None,
            "mean_latency_ms": round(
                sum(item["transcription"]["latency_ms"] for item in results) / len(results), 2
            ),
            "mean_realtime_factor": round(
                sum(item["transcription"]["realtime_factor"] for item in results) / len(results), 4
            ),
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "provider": provider.name,
                    "metrics": metrics,
                    "results": results,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"{record['audio']}: {result.text}")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
