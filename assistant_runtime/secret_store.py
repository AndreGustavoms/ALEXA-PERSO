from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes
from pathlib import Path


class DataBlob(ctypes.Structure):
    _fields_ = (("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_byte)))


def _blob(value: bytes) -> tuple[DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(value)
    return (
        DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))),
        buffer,
    )


def protect_secret(value: str) -> bytes:
    if os.name != "nt":
        raise RuntimeError("O armazenamento protegido requer Windows.")
    plain, buffer = _blob(value.encode("utf-8"))
    encrypted = DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(plain), None, None, None, None, 0, ctypes.byref(encrypted)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(encrypted.data, encrypted.size)
    finally:
        ctypes.windll.kernel32.LocalFree(encrypted.data)


def unprotect_secret(value: bytes) -> str:
    if os.name != "nt":
        raise RuntimeError("O armazenamento protegido requer Windows.")
    protected, buffer = _blob(value)
    plain = DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(protected), None, None, None, None, 0, ctypes.byref(plain)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(plain.data, plain.size).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(plain.data)


def save_secret(path: Path, value: str) -> None:
    if os.name != "nt":
        import keyring

        keyring.set_password("Doktor Assistant", "openai-api-key", value)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64encode(protect_secret(value)))


def load_secret(path: Path) -> str:
    if os.name != "nt":
        try:
            import keyring

            return (keyring.get_password("Doktor Assistant", "openai-api-key") or "").strip()
        except Exception:
            return ""
    try:
        return unprotect_secret(base64.b64decode(path.read_bytes())).strip()
    except (OSError, ValueError):
        return ""
