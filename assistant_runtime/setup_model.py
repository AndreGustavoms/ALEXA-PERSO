from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

MODEL_NAME = "vosk-model-small-pt-0.3"
MODEL_URL = f"https://alphacephei.com/vosk/models/{MODEL_NAME}.zip"

PROJECT_DIRECTORY = Path(__file__).resolve().parents[1]
MODELS_DIRECTORY = PROJECT_DIRECTORY / "runtime" / "models"
MODEL_DIRECTORY = MODELS_DIRECTORY / MODEL_NAME
ARCHIVE_PATH = MODELS_DIRECTORY / f"{MODEL_NAME}.zip"


def show_progress(block_count: int, block_size: int, total_size: int) -> None:
    downloaded = block_count * block_size
    if total_size <= 0:
        return

    percent = min(100, int(downloaded * 100 / total_size))
    print(f"\rBaixando modelo de voz: {percent:3d}%", end="", flush=True)


def main() -> int:
    if MODEL_DIRECTORY.exists():
        print("Modelo de voz já instalado.")
        return 0

    MODELS_DIRECTORY.mkdir(parents=True, exist_ok=True)

    try:
        urllib.request.urlretrieve(MODEL_URL, ARCHIVE_PATH, show_progress)
        print("\nExtraindo modelo de voz...")

        with zipfile.ZipFile(ARCHIVE_PATH) as archive:
            archive.extractall(MODELS_DIRECTORY)

        if not MODEL_DIRECTORY.exists():
            raise RuntimeError("A pasta esperada do modelo não foi encontrada.")
    except Exception as error:
        if MODEL_DIRECTORY.exists():
            shutil.rmtree(MODEL_DIRECTORY)
        print(f"\nFalha ao instalar o modelo de voz: {error}", file=sys.stderr)
        return 1
    finally:
        ARCHIVE_PATH.unlink(missing_ok=True)

    print("Modelo de voz instalado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
