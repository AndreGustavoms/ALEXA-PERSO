from __future__ import annotations

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


ROOT = Path(os.environ.get("DOKTOR_PROJECT_ROOT", Path.cwd())).resolve()
MODEL = ROOT / "runtime/models/vosk-model-small-pt-0.3"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
VERSION_PARTS = tuple(int(part) for part in VERSION.split("-")[0].split(".")) + (0,)
VERSION_TUPLE = VERSION_PARTS[:4]
VERSION_INFO = ROOT / "build/pyinstaller-work/doktor-version-info.txt"
if not (ROOT / "dist/index.html").exists():
    raise SystemExit("Frontend ausente. Execute npm run build antes do PyInstaller.")
if not MODEL.exists():
    raise SystemExit("Modelo Vosk ausente. Execute assistant_runtime/setup_model.py.")

if sys.platform == "win32":
    VERSION_INFO.parent.mkdir(parents=True, exist_ok=True)
    VERSION_INFO.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={VERSION_TUPLE}, prodvers={VERSION_TUPLE}, mask=0x3f,
    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Doktor'),
      StringStruct('FileDescription', 'Doktor Assistant - assistente de voz local'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('InternalName', 'Doktor'),
      StringStruct('LegalCopyright', 'Copyright (c) 2026 AndreGustavoms'),
      StringStruct('OriginalFilename', 'Doktor.exe'),
      StringStruct('ProductName', 'Doktor Assistant'),
      StringStruct('ProductVersion', '{VERSION}')
    ])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ])
""",
        encoding="utf-8",
    )

datas = [
    (str(ROOT / "VERSION"), "."),
    (str(ROOT / "dist"), "dist"),
    (str(ROOT / "assets"), "assets"),
    (str(ROOT / "licenses"), "licenses"),
    (str(MODEL), "runtime/models/vosk-model-small-pt-0.3"),
    (str(ROOT / "assistant_runtime/voice_config.json"), "assistant_runtime"),
    (str(ROOT / "assistant_runtime/wake_word_config.json"), "assistant_runtime"),
    (str(ROOT / "assistant_runtime/models"), "assistant_runtime/models"),
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
    excludes=[
        "tkinter",
        "pytest",
        "openwakeword",
        "scipy",
        "sklearn",
        "joblib",
        "narwhals",
    ],
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
    version=str(VERSION_INFO) if sys.platform == "win32" else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Doktor",
)
