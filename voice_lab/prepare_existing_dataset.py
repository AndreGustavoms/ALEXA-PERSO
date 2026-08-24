from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from voice_lab.core import read_wav, write_wav


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent

# Silence boundaries plus agreement between local recognizers define these clips.
# The manifest keeps that provenance explicit until a human audits the labels.
CURATED = (
    ("open_youtube_01", 0.35, 2.35, "abrir o youtube", {"kind": "OPEN_YOUTUBE", "target": "youtube"}, "calibration"),
    ("wake_ola_doktor_01", 3.10, 4.35, "ola doktor", None, "calibration"),
    ("open_youtube_02", 4.85, 6.65, "abrir o youtube", {"kind": "OPEN_YOUTUBE", "target": "youtube"}, "validation"),
    ("close_youtube_01", 7.15, 9.15, "fecha o youtube", {"kind": "CLOSE_APPLICATION", "target": "youtube"}, "holdout"),
    ("open_valorant_01", 9.58, 12.15, "abre o valorant", {"kind": "OPEN_APPLICATION", "target": "valorant"}, "holdout"),
    ("open_google_01", 13.15, 15.40, "abre o google", {"kind": "OPEN_URL", "target": "google"}, "validation"),
    ("search_youtube_01", 16.00, 17.75, "pesquisa no youtube", None, "calibration"),
    ("open_console_01", 18.05, 20.40, "abre o console", {"kind": "OPEN_APPLICATION", "target": "console"}, "validation"),
    ("shutdown_01", 20.30, 21.98, "desliga o computador", {"command_id": "system.shutdown"}, "holdout"),
    ("power_on_01", 22.05, 24.85, "", {"kind": "NONE"}, "validation"),
)


def find_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    packages = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    matches = tuple(packages.glob("**/ffmpeg.exe"))
    if not matches:
        raise FileNotFoundError("ffmpeg not found")
    return str(matches[0])


def convert(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            find_ffmpeg(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(target),
        ],
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepara os audios autorizados existentes")
    parser.add_argument(
        "--source-directory",
        type=Path,
        default=PROJECT / "Vozes benchmark",
    )
    args = parser.parse_args()
    recordings = sorted(
        args.source_directory.glob("*.m4a"),
        key=lambda path: path.stat().st_size,
        reverse=True,
    )
    if len(recordings) < 2:
        raise SystemExit("As duas gravacoes M4A nao foram encontradas.")

    sample_dir = ROOT / "samples" / "curated"
    full_command = ROOT / "samples" / "authorized_commands.wav"
    full_stress = ROOT / "samples" / "authorized_stress.wav"
    convert(recordings[0], full_command)
    convert(recordings[1], full_stress)
    audio = read_wav(full_command)
    manifest = ROOT / "manifests" / "local-curated.jsonl"
    records = []
    for name, start, end, expected_text, expected, split in CURATED:
        start_byte = int(start * audio.sample_rate) * 2
        end_byte = int(end * audio.sample_rate) * 2
        output = sample_dir / f"{name}.wav"
        write_wav(output, audio.pcm16[start_byte:end_byte], audio.sample_rate)
        records.append(
            {
                "audio": str(output.relative_to(ROOT)).replace("\\", "/"),
                "expected_text": expected_text,
                "text_labeled": bool(expected_text),
                "action_labeled": expected is not None,
                "expected": expected,
                "expected_wake": True if name.startswith("wake_") else False,
                "category": "wake" if name.startswith("wake_") else "command",
                "condition": "NORMAL_VOICE_NEAR_MIC",
                "split": split,
                "source_range_seconds": [start, end],
                "label_source": "local_stt_consensus_needs_human_audit",
            }
        )

    records.append(
        {
            "audio": str(full_stress.relative_to(ROOT)).replace("\\", "/"),
            "text_labeled": False,
            "action_labeled": True,
            "expected": {"kind": "NONE"},
            "expected_wake": False,
            "category": "negative_continuous_speech",
            "condition": "NORMAL_VOICE_NEAR_MIC",
            "split": "holdout",
            "label_source": "negative_action_label_only",
        }
    )
    manifest.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    metadata = {
        "sources": [
            {
                "name": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
            for path in recordings
        ],
        "records": len(records),
        "privacy": "local-only",
    }
    (ROOT / "manifests" / "local-curated-metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
