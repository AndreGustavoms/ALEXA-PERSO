from __future__ import annotations

import argparse
import json
import random
from array import array
from pathlib import Path

from voice_lab.core import levels, load_jsonl, read_wav, write_wav


ROOT = Path(__file__).resolve().parent
SEED = 20260824


def scale_pcm16(pcm16: bytes, factor: float) -> bytes:
    samples = array("h")
    samples.frombytes(pcm16)
    return array("h", (round(sample * factor) for sample in samples)).tobytes()


def add_white_noise(pcm16: bytes, snr_db: float, seed: int) -> bytes:
    samples = array("h")
    samples.frombytes(pcm16)
    signal_rms, _peak, _clipping = levels(pcm16)
    noise_rms = max(signal_rms, 1 / 32_768) / (10 ** (snr_db / 20))
    sigma = noise_rms * 32_768
    generator = random.Random(seed)
    noisy = array(
        "h",
        (
            max(-32_768, min(32_767, round(sample + generator.gauss(0, sigma))))
            for sample in samples
        ),
    )
    return noisy.tobytes()


def main() -> int:
    parser = argparse.ArgumentParser(description="Aumentacao local e deterministica")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "manifests" / "local-curated.jsonl",
    )
    args = parser.parse_args()
    output_dir = ROOT / "samples" / "augmented"
    records = []
    source_records = [
        record
        for record in load_jsonl(args.manifest)
        if record.get("split") in {"calibration", "validation"}
        and record.get("text_labeled")
    ]
    for index, record in enumerate(source_records):
        audio = read_wav(ROOT / str(record["audio"]))
        stem = Path(str(record["audio"])).stem
        for percent in (50, 35, 25):
            output = output_dir / f"{stem}_volume_{percent}.wav"
            write_wav(output, scale_pcm16(audio.pcm16, percent / 100), audio.sample_rate)
            records.append(
                {
                    **record,
                    "audio": str(output.relative_to(ROOT)).replace("\\", "/"),
                    "condition": f"VOLUME_{percent}",
                    "augmentation": {"type": "volume", "factor": percent / 100},
                    "source_audio": record["audio"],
                }
            )
        for snr_db in (20, 10):
            output = output_dir / f"{stem}_snr_{snr_db}.wav"
            write_wav(
                output,
                add_white_noise(audio.pcm16, snr_db, SEED + index * 100 + snr_db),
                audio.sample_rate,
            )
            records.append(
                {
                    **record,
                    "audio": str(output.relative_to(ROOT)).replace("\\", "/"),
                    "condition": f"WHITE_NOISE_{snr_db}DB",
                    "augmentation": {
                        "type": "white_noise",
                        "snr_db": snr_db,
                        "seed": SEED + index * 100 + snr_db,
                    },
                    "source_audio": record["audio"],
                }
            )
    output_manifest = ROOT / "manifests" / "local-robustness.jsonl"
    output_manifest.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    print(json.dumps({"seed": SEED, "records": len(records)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
