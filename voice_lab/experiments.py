from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, replace
from pathlib import Path

from assistant_runtime.voice_activity import VoiceActivityConfig
from voice_lab.benchmark import ROOT
from voice_lab.core import json_safe, load_jsonl, read_wav, replay_vad


def candidates(base: VoiceActivityConfig):
    yield "baseline", base, "baseline"
    yield "vad_webrtc_0", replace(base, vad_engine="webrtc", vad_aggressiveness=0), "vad"
    yield "vad_webrtc_1", replace(base, vad_engine="webrtc", vad_aggressiveness=1), "vad"
    for value in (0.3, 0.4, 0.6, 0.8, 1.0):
        yield f"preroll_{int(value * 1000)}ms", replace(base, pre_roll_duration=value), "pre_roll"
    for value in (0.12, 0.24, 0.4, 0.6):
        yield f"padding_{int(value * 1000)}ms", replace(base, end_padding_duration=value), "end_padding"
    for value in (0.9, 1.2, 1.5, 1.8, 2.1):
        yield f"hangover_{int(value * 1000)}ms", replace(base, speech_end_silence=value), "hangover"
    for value in (1.0, 4.0, 7.0, 10.0):
        yield f"gain_{int(value)}x", replace(base, maximum_input_gain=value), "gain"


def main() -> int:
    parser = argparse.ArgumentParser(description="Busca controlada de uma familia por vez")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "experiments.json")
    args = parser.parse_args()
    base = VoiceActivityConfig.from_file(Path("assistant_runtime/voice_config.json"))
    source_records = load_jsonl(args.manifest)
    completed = []
    started = time.perf_counter()
    for name, config, family in candidates(base):
        records = []
        for record in source_records:
            audio = read_wav(ROOT / str(record["audio"]))
            vad = replay_vad(audio, config)
            segments = vad.pop("segments")
            records.append(
                {
                    "audio": record["audio"],
                    "duration_seconds": round(audio.duration, 3),
                    "segment_count": len(segments),
                    "captured_seconds": round(
                        sum(segment["duration_seconds"] for segment in segments), 3
                    ),
                    "boundary_risk_count": sum(
                        segment["boundary_risk"]["start_risk"]
                        or segment["boundary_risk"]["end_risk"]
                        for segment in segments
                    ),
                    "signal": vad,
                }
            )
        total_segments = sum(record["segment_count"] for record in records)
        total_audio = sum(record["duration_seconds"] for record in records)
        metrics = {
            "sample_count": len(records),
            "total_audio_seconds": round(total_audio, 3),
            "segment_count": total_segments,
            "captured_audio_ratio": round(
                sum(record["captured_seconds"] for record in records) / total_audio, 4
            ),
            "boundary_risk_rate_proxy": (
                round(
                    sum(record["boundary_risk_count"] for record in records)
                    / total_segments,
                    4,
                )
                if total_segments
                else None
            ),
            "mean_vad_realtime_factor": round(
                sum(record["signal"]["realtime_factor"] for record in records)
                / len(records),
                4,
            ),
            "processed_clipping_mean": round(
                sum(record["signal"]["processed_clipping_mean"] for record in records)
                / len(records),
                8,
            ),
        }
        completed.append(
            {
                "name": name,
                "family": family,
                "config": asdict(config),
                "metrics": metrics,
                "records": records,
            }
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(json_safe({"experiments": completed}), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"{name}: {completed[-1]['metrics']}")
    print(f"Concluido em {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
