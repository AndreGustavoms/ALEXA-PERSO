from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Exclui somente os dados privados do Voice Lab")
    parser.add_argument("--yes", action="store_true", help="confirma a exclusao")
    args = parser.parse_args()
    if not args.yes:
        raise SystemExit("Use --yes para confirmar.")
    for directory in (ROOT / "samples", ROOT / "results"):
        for path in directory.iterdir():
            if path.name == ".gitkeep" or path.name == "final-report.md":
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    for pattern in ("local-*.json", "local-*.jsonl"):
        for path in (ROOT / "manifests").glob(pattern):
            path.unlink()
    print("Dataset e resultados privados excluidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
