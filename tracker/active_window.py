# tracker/active_window.py

from typing import Tuple, Optional
import platform
import psutil

# Определяем ОС
_SYSTEM = platform.system()

# Попробуем подключить WinAPI для Windows
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

# pygetwindow как запасной вариант (для других ОС)
try:
    import pygetwindow as gw
except ImportError:
    gw = None


def _get_active_window_windows() -> Tuple[Optional[str], Optional[str]]:
    """
    Реализация для Windows через WinAPI:
    - берём HWND активного окна
    - по HWND узнаём PID процесса
    - по PID получаем имя процесса через psutil
    """
    if win32gui is None or win32process is None:
        return None, None

    try:
        hwnd = win32gui.GetForegroundWindow()
    except Exception:
        return None, None

    if not hwnd:
        return None, None

    try:
        title = win32gui.GetWindowText(hwnd) or ""
    except Exception:
        title = ""

    app_name = None
    try:
        _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = psutil.Process(pid)
        app_name = proc.name()
    except Exception:
        pass

    return app_name, title


def _get_active_window_fallback() -> Tuple[Optional[str], Optional[str]]:
    """
    Запасной вариант (для не-Windows или если WinAPI недоступен).
    Здесь мы в лучшем случае узнаём только заголовок окна.
    """
    if gw is None:
        return None, None

    try:
        win = gw.getActiveWindow()
    except Exception:
        return None, None

    if win is None:
        return None, None

    title = getattr(win, "title", "") or ""
    # Процесс определить надёжно не можем — вернём только заголовок
    return None, title


def get_active_window() -> Tuple[Optional[str], Optional[str]]:
    """
    Возвращает (app_name, window_title).

    app_name — имя процесса (например, 'pycharm64.exe', 'chrome.exe')
    window_title — заголовок окна
    """
    if _SYSTEM == "Windows":
        app, title = _get_active_window_windows()
        # если получилось, используем WinAPI-результат
        if app is not None or title:
            return app, title

    # иначе — fallback (другие ОС или если WinAPI не сработал)
    return _get_active_window_fallback()
