from __future__ import annotations

import platform
from dataclasses import dataclass
from typing import Optional

import psutil

_SYSTEM = platform.system()

if _SYSTEM == "Windows":
    try:
        import win32gui
        import win32process
    except ImportError:
        win32gui = None
        win32process = None
else:
    win32gui = None
    win32process = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None


@dataclass(frozen=True)
class WindowInfo:
    process_name: str = ""
    window_title: str = ""
    pid: Optional[int] = None
    exe_path: str = ""
    hwnd: Optional[int] = None


def _build_window_info_windows(hwnd: int) -> WindowInfo | None:
    if win32gui is None or win32process is None:
        return None

    try:
        if not win32gui.IsWindowVisible(hwnd):
            return None
        title = (win32gui.GetWindowText(hwnd) or "").strip()
    except Exception:
        return None

    if not title:
        return None

    try:
        _thread_id, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        pid = None

    process_name = ""
    exe_path = ""
    if pid:
        try:
            process = psutil.Process(pid)
            process_name = process.name() or ""
            exe_path = process.exe() or ""
        except Exception:
            pass

    return WindowInfo(
        process_name=process_name,
        window_title=title,
        pid=pid,
        exe_path=exe_path,
        hwnd=hwnd,
    )


def _get_active_window_windows() -> WindowInfo:
    if win32gui is None:
        return WindowInfo()

    try:
        hwnd = win32gui.GetForegroundWindow()
    except Exception:
        hwnd = 0

    if not hwnd:
        return WindowInfo()

    info = _build_window_info_windows(hwnd)
    if info is not None:
        return info
    return WindowInfo(hwnd=hwnd)


def _list_open_windows_windows(limit: int) -> list[WindowInfo]:
    if win32gui is None:
        return []

    windows: list[WindowInfo] = []
    active_hwnd = None
    try:
        active_hwnd = win32gui.GetForegroundWindow()
    except Exception:
        active_hwnd = None

    def callback(hwnd: int, _extra) -> bool:
        info = _build_window_info_windows(hwnd)
        if info is not None:
            windows.append(info)
        return True

    try:
        win32gui.EnumWindows(callback, None)
    except Exception:
        return []

    deduped: dict[tuple[str, str], WindowInfo] = {}
    for info in windows:
        key = (info.process_name.lower(), info.window_title.lower())
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = info
            continue
        if active_hwnd is not None and info.hwnd == active_hwnd:
            deduped[key] = info

    result = list(deduped.values())
    result.sort(
        key=lambda item: (
            0 if item.hwnd == active_hwnd else 1,
            item.process_name.lower(),
            item.window_title.lower(),
        )
    )
    return result[:limit]


def _get_active_window_fallback() -> WindowInfo:
    if gw is None:
        return WindowInfo()

    try:
        win = gw.getActiveWindow()
    except Exception:
        return WindowInfo()

    if win is None:
        return WindowInfo()

    return WindowInfo(window_title=(getattr(win, "title", "") or "").strip())


def _list_open_windows_fallback(limit: int) -> list[WindowInfo]:
    if gw is None:
        return []

    try:
        titles = gw.getAllTitles()
    except Exception:
        return []

    seen: set[str] = set()
    result: list[WindowInfo] = []
    for title in titles:
        normalized = (title or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(WindowInfo(window_title=normalized))

    return result[:limit]


def get_active_window_info() -> WindowInfo:
    if _SYSTEM == "Windows":
        info = _get_active_window_windows()
        if info.process_name or info.window_title:
            return info
    return _get_active_window_fallback()


def list_open_windows(limit: int = 100) -> list[WindowInfo]:
    if _SYSTEM == "Windows":
        windows = _list_open_windows_windows(limit)
        if windows:
            return windows
    return _list_open_windows_fallback(limit)


def get_active_window() -> tuple[Optional[str], Optional[str]]:
    info = get_active_window_info()
    return info.process_name or None, info.window_title or None
