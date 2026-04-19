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

if _SYSTEM == "Darwin":
    try:
        from AppKit import NSWorkspace
        import Quartz
    except ImportError:
        NSWorkspace = None
        Quartz = None
else:
    NSWorkspace = None
    Quartz = None

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


def _process_details(
    pid: Optional[int],
    fallback_name: str = "",
) -> tuple[str, str]:
    process_name = (fallback_name or "").strip()
    exe_path = ""

    if pid:
        try:
            process = psutil.Process(pid)
            name = process.name() or ""
            if name:
                process_name = name
            try:
                exe_path = process.exe() or ""
            except Exception:
                exe_path = ""
        except Exception:
            pass

    return process_name, exe_path


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

    process_name, exe_path = _process_details(pid)

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


def _window_list_macos() -> list[dict]:
    if Quartz is None:
        return []

    try:
        options = (
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements
        )
        return Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or []
    except Exception:
        return []


def _frontmost_app_pid_and_name_macos() -> tuple[Optional[int], str]:
    if NSWorkspace is None:
        return None, ""

    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
    except Exception:
        return None, ""

    if app is None:
        return None, ""

    pid: Optional[int]
    try:
        pid = int(app.processIdentifier())
    except Exception:
        pid = None

    try:
        app_name = (app.localizedName() or "").strip()
    except Exception:
        app_name = ""

    return pid, app_name


def _active_window_title_macos(pid: Optional[int]) -> str:
    if pid is None:
        return ""

    for window in _window_list_macos():
        owner_pid = window.get(Quartz.kCGWindowOwnerPID) if Quartz is not None else None
        layer = window.get(Quartz.kCGWindowLayer, 1) if Quartz is not None else 1

        try:
            owner_pid = int(owner_pid)
            layer = int(layer)
        except Exception:
            continue

        if owner_pid != pid or layer != 0:
            continue

        title = (window.get(Quartz.kCGWindowName, "") or "").strip()
        if title:
            return title

    return ""


def _get_active_window_macos() -> WindowInfo:
    pid, fallback_name = _frontmost_app_pid_and_name_macos()
    if pid is None and not fallback_name:
        return WindowInfo()

    process_name, exe_path = _process_details(pid, fallback_name=fallback_name)
    title = _active_window_title_macos(pid)

    return WindowInfo(
        process_name=process_name,
        window_title=title,
        pid=pid,
        exe_path=exe_path,
    )


def _list_open_windows_macos(limit: int) -> list[WindowInfo]:
    if Quartz is None:
        return []

    active = _get_active_window_macos()

    seen: set[tuple[str, str]] = set()
    result: list[WindowInfo] = []

    for window in _window_list_macos():
        owner_name = (window.get(Quartz.kCGWindowOwnerName, "") or "").strip()
        title = (window.get(Quartz.kCGWindowName, "") or "").strip()
        layer = window.get(Quartz.kCGWindowLayer, 1)
        owner_pid = window.get(Quartz.kCGWindowOwnerPID)

        try:
            layer = int(layer)
        except Exception:
            layer = 1

        try:
            owner_pid = int(owner_pid)
        except Exception:
            owner_pid = None

        if layer != 0:
            continue
        if not owner_name and not title:
            continue

        process_name, exe_path = _process_details(owner_pid, fallback_name=owner_name)
        info = WindowInfo(
            process_name=process_name,
            window_title=title,
            pid=owner_pid,
            exe_path=exe_path,
        )
        key = (info.process_name.lower(), info.window_title.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(info)

        if len(result) >= limit:
            break

    if active.process_name or active.window_title:
        active_key = (active.process_name.lower(), active.window_title.lower())
        for index, info in enumerate(result):
            if (info.process_name.lower(), info.window_title.lower()) == active_key:
                if index > 0:
                    result.insert(0, result.pop(index))
                break
        else:
            result.insert(0, active)

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

    if _SYSTEM == "Darwin":
        info = _get_active_window_macos()
        if info.process_name or info.window_title:
            return info

    return _get_active_window_fallback()


def list_open_windows(limit: int = 100) -> list[WindowInfo]:
    if _SYSTEM == "Windows":
        windows = _list_open_windows_windows(limit)
        if windows:
            return windows

    if _SYSTEM == "Darwin":
        windows = _list_open_windows_macos(limit)
        if windows:
            return windows

    return _list_open_windows_fallback(limit)


def get_active_window() -> tuple[Optional[str], Optional[str]]:
    info = get_active_window_info()
    return info.process_name or None, info.window_title or None
