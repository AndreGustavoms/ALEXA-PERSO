from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*command: str) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def validate_version() -> str:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
        raise SystemExit(f"Versao SemVer invalida: {version}")
    package_version = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    if package_version != version:
        raise SystemExit(f"package.json ({package_version}) difere de VERSION ({version})")
    return version


def main() -> int:
    parser = argparse.ArgumentParser(description="Build desktop reproduzivel do Doktor")
    parser.add_argument("--skip-web", action="store_true")
    parser.add_argument("--skip-model", action="store_true")
    args = parser.parse_args()
    version = validate_version()
    if not args.skip_web:
        run("npm", "ci")
        run("npm", "run", "build")
    if not args.skip_model:
        run(sys.executable, "assistant_runtime/setup_model.py")
    env = {**os.environ, "DOKTOR_PROJECT_ROOT": str(ROOT)}
    subprocess.run(
        (
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(ROOT / "build/pyinstaller"),
            "--workpath",
            str(ROOT / "build/pyinstaller-work"),
            str(ROOT / "packaging/doktor.spec"),
        ),
        cwd=ROOT,
        env=env,
        check=True,
    )
    print(f"Doktor {version}: {ROOT / 'build/pyinstaller/Doktor'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
