from __future__ import annotations

import socket
from dataclasses import asdict
from typing import Any

import sounddevice as sd

from .app_paths import PATHS
from .platforms import detect_platform
from .version import __version__


def audio_devices() -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    try:
        default_input = int(sd.default.device[0])
    except (IndexError, TypeError, ValueError):
        default_input = None
    for index, raw in enumerate(sd.query_devices()):
        if int(raw.get("max_input_channels", 0)) <= 0:
            continue
        devices.append(
            {
                "id": index,
                "name": str(raw.get("name", f"Microfone {index}")),
                "channels": int(raw.get("max_input_channels", 0)),
                "sampleRate": int(float(raw.get("default_samplerate", 0))),
                "default": index == default_input,
            }
        )
    return devices


def health_snapshot(stt_provider: str = "") -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    try:
        microphones = audio_devices()
        checks["microphone"] = {"ok": bool(microphones), "detail": f"{len(microphones)} entrada(s)"}
    except Exception as error:
        checks["microphone"] = {"ok": False, "detail": str(error)}
    checks["wakeWord"] = {"ok": PATHS.model.exists(), "detail": "Vosk local" if PATHS.model.exists() else "Modelo ausente"}
    checks["stt"] = {"ok": PATHS.model.exists(), "detail": stt_provider or "Aguardando inicializacao"}
    checks["tts"] = {"ok": True, "detail": "Voz do sistema"}
    try:
        socket.getaddrinfo("api.github.com", 443)
        checks["internet"] = {"ok": True, "detail": "DNS disponivel"}
    except OSError as error:
        checks["internet"] = {"ok": False, "detail": str(error)}
    checks["aiProvider"] = {"ok": True, "detail": stt_provider or "Local"}
    info = detect_platform()
    checks["platformAdapter"] = {"ok": bool(info.capabilities), "detail": info.adapter}
    checks["updateService"] = {"ok": True, "detail": "GitHub Releases"}
    return {
        "ok": all(check["ok"] for check in checks.values()),
        "version": __version__,
        "platform": asdict(info),
        "checks": checks,
    }
