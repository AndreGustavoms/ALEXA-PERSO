from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from voice_lab.core import intent_result, load_jsonl, read_wav, word_error_rate
from voice_lab.providers import FasterWhisperSTTProvider


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="A/B local com faster-whisper")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", default="base")
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "faster-whisper.json")
    args = parser.parse_args()
    provider = FasterWhisperSTTProvider(args.model)
    results = []
    for record in load_jsonl(args.manifest):
        path = ROOT / str(record["audio"])
        audio = read_wav(path)
        result = provider.transcribe(path, audio.duration)
        labeled = bool(record.get("labeled") and record.get("expected_text"))
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
                "intent": intent_result(result.text),
            }
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "provider": provider.name,
                    "results": results,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"{record['audio']}: {result.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
