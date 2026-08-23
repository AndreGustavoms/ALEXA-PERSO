from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(os.environ.get("DOKTOR_PROJECT_ROOT", Path.cwd())).resolve()
MODEL = ROOT / "runtime/models/vosk-model-small-pt-0.3"
if not (ROOT / "dist/index.html").exists():
    raise SystemExit("Frontend ausente. Execute npm run build antes do PyInstaller.")
if not MODEL.exists():
    raise SystemExit("Modelo Vosk ausente. Execute assistant_runtime/setup_model.py.")

datas = [
    (str(ROOT / "VERSION"), "."),
    (str(ROOT / "dist"), "dist"),
    (str(ROOT / "assets"), "assets"),
    (str(MODEL), "runtime/models/vosk-model-small-pt-0.3"),
    (str(ROOT / "assistant_runtime/voice_config.json"), "assistant_runtime"),
    (str(ROOT / "assistant_runtime/stt_config.json"), "assistant_runtime"),
    (str(ROOT / "assistant_runtime/transcription_vocabulary.txt"), "assistant_runtime"),
]
binaries = []
hiddenimports = ["pyttsx3.drivers", "pyttsx3.drivers.sapi5", "websocket"]
for package in ("vosk", "sounddevice", "pystray", "PIL"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

if sys.platform == "win32":
    hiddenimports += ["pycaw.pycaw", "comtypes", "win32ctypes"]
elif sys.platform == "darwin":
    hiddenimports += ["pyttsx3.drivers.nsss"]
else:
    hiddenimports += ["pyttsx3.drivers.espeak"]

a = Analysis(
    [str(ROOT / "assistant_runtime/main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hooksconfig={},
    hookspath=[str(ROOT / "packaging/hooks")],
    runtime_hooks=[],
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Doktor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets/doktor-assistant.ico") if sys.platform == "win32" else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Doktor",
)
