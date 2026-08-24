from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from voice_lab.core import write_wav


PHRASES = (
    "Ola Doktor",
    "Ola Doktor abre o YouTube",
    "fecha o YouTube",
    "pode fechar o YouTube pra mim",
    "abre o Chrome",
    "pesquisa GTA 6 no YouTube",
    "abre o primeiro video",
    "volta",
    "fecha isso",
    "abre o Spotify",
    "abaixa o volume",
    "coloca o volume em cinquenta",
)
CONDITIONS = (
    "LOW_VOICE",
    "NORMAL_VOICE",
    "FAST",
    "SLOW",
    "NEAR_MIC",
    "FARTHER_MIC",
    "WITH_KEYBOARD",
    "WITH_BACKGROUND_AUDIO",
)


def record(duration: float, sample_rate: int) -> bytes:
    import sounddevice as sd

    frames = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    return frames.tobytes()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gravador privado do Doktor Voice Lab")
    parser.add_argument("--duration", type=float, default=5.0)
    parser.add_argument("--sample-rate", type=int, default=16_000)
    parser.add_argument("--condition", choices=CONDITIONS)
    parser.add_argument("--phrase", help="grava somente esta frase")
    parser.add_argument("--list", action="store_true", help="lista frases e condicoes")
    args = parser.parse_args()
    if args.list:
        print("Frases:")
        print("\n".join(f"- {phrase}" for phrase in PHRASES))
        print("Condicoes:")
        print("\n".join(f"- {condition}" for condition in CONDITIONS))
        return 0

    condition = args.condition or input(f"Condicao ({', '.join(CONDITIONS)}): ").strip().upper()
    if condition not in CONDITIONS:
        raise SystemExit("Condicao invalida.")
    phrases = (args.phrase,) if args.phrase else PHRASES
    sample_dir = Path(__file__).parent / "samples"
    manifest = Path(__file__).parent / "manifests" / "local-dataset.jsonl"
    manifest.parent.mkdir(parents=True, exist_ok=True)

    for phrase in phrases:
        answer = input(f'ENTER para gravar "{phrase}"; s para pular; q para sair: ').strip().lower()
        if answer == "q":
            break
        if answer == "s":
            continue
        print("Gravando...")
        pcm16 = record(args.duration, args.sample_rate)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        slug = "".join(char if char.isalnum() else "_" for char in phrase.casefold())[:48]
        output = sample_dir / f"{stamp}_{condition.casefold()}_{slug}.wav"
        write_wav(output, pcm16, args.sample_rate)
        record_data = {
            "audio": str(output.relative_to(Path(__file__).parent)).replace("\\", "/"),
            "expected_text": phrase,
            "condition": condition,
            "labeled": True,
        }
        with manifest.open("a", encoding="utf-8") as target:
            target.write(json.dumps(record_data, ensure_ascii=False) + "\n")
        print(f"Salvo localmente: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
