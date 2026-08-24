from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from .models import WindowContext

BROWSER_PROCESSES = {
    "brave.exe": "Brave",
    "chrome.exe": "Chrome",
    "firefox.exe": "Firefox",
    "msedge.exe": "Edge",
    "opera.exe": "Opera",
}
EXPLORER_PROCESSES = {"explorer.exe": "Explorador de Arquivos"}
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def process_name_for_pid(process_id: int) -> str:
    if os.name != "nt" or not process_id:
        return ""
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, process_id)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return os.path.basename(buffer.value).lower()
    finally:
        kernel32.CloseHandle(handle)


def visible_application_names(limit: int = 48) -> tuple[str, ...]:
    """Return local app names only; window titles and document names stay private."""
    if os.name != "nt":
        return ()
    names: list[str] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def collect(handle: int, _parameter: int) -> bool:
        if len(names) >= limit or not ctypes.windll.user32.IsWindowVisible(handle):
            return True
        process_id = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
        process_name = process_name_for_pid(process_id.value)
        if not process_name:
            return True
        label = (
            BROWSER_PROCESSES.get(process_name)
            or EXPLORER_PROCESSES.get(process_name)
            or process_name.removesuffix(".exe").replace("_", " ").strip().title()
        )
        if label and label.casefold() not in {name.casefold() for name in names}:
            names.append(label)
        return True

    ctypes.windll.user32.EnumWindows(callback_type(collect), 0)
    return tuple(names)


class WindowContextProvider:
    def current(self) -> WindowContext:
        if os.name != "nt":
            return WindowContext()
        user32 = ctypes.windll.user32
        handle = int(user32.GetForegroundWindow())
        if not handle:
            return WindowContext()

        title_length = user32.GetWindowTextLengthW(handle)
        title_buffer = ctypes.create_unicode_buffer(max(1, title_length + 1))
        user32.GetWindowTextW(handle, title_buffer, len(title_buffer))
        process_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
        process_name = process_name_for_pid(process_id.value)

        if process_name in BROWSER_PROCESSES:
            kind = "browser"
            application = BROWSER_PROCESSES[process_name]
        elif process_name in EXPLORER_PROCESSES:
            kind = "explorer"
            application = EXPLORER_PROCESSES[process_name]
        else:
            kind = "application" if process_name else "unknown"
            application = process_name.removesuffix(".exe").replace("_", " ").title()

        return WindowContext(
            handle=handle,
            process_id=process_id.value,
            process_name=process_name,
            title=title_buffer.value.strip(),
            application=application,
            kind=kind,
        )
