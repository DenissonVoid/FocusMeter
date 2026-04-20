# tracker/input_tracker.py

from datetime import datetime, timedelta
import platform
import threading

_SYSTEM = platform.system()

if _SYSTEM == "Darwin":
    try:
        import Quartz
    except ImportError:
        Quartz = None
else:
    Quartz = None

if _SYSTEM != "Darwin":
    try:
        from pynput import keyboard, mouse
    except ImportError:
        keyboard = None
        mouse = None
else:
    keyboard = None
    mouse = None


class InputActivityTracker:
    """
    Отслеживает глобальные события ввода:
    - на Windows/Linux: через pynput listeners
    - на macOS: через polling idle времени (Quartz), без listener-потоков

    Хранит:
    - время последней активности
    - сколько событий ввода было с момента последнего опроса (для статистики)
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.last_input_time = datetime.utcnow()
        self.inputs_since_last_poll = 0

        self._use_macos_polling = _SYSTEM == "Darwin" and Quartz is not None
        self._last_polled_idle_seconds = None

        self.keyboard_listener = None
        self.mouse_listener = None

        if not self._use_macos_polling and keyboard is not None and mouse is not None:
            self.keyboard_listener = keyboard.Listener(on_press=self._on_input)
            self.mouse_listener = mouse.Listener(
                on_move=self._on_input,
                on_click=self._on_input,
                on_scroll=self._on_input,
            )

    def _on_input(self, *args, **kwargs):
        with self.lock:
            self.last_input_time = datetime.utcnow()
            self.inputs_since_last_poll += 1

    def start(self):
        if self._use_macos_polling:
            return

        if self.keyboard_listener is not None:
            self.keyboard_listener.start()
        if self.mouse_listener is not None:
            self.mouse_listener.start()

    def stop(self):
        if self._use_macos_polling:
            return

        if self.keyboard_listener is not None:
            self.keyboard_listener.stop()
        if self.mouse_listener is not None:
            self.mouse_listener.stop()

    def _consume_stats_macos_polling(self):
        now = datetime.utcnow()
        idle_seconds = None

        try:
            idle_seconds = float(
                Quartz.CGEventSourceSecondsSinceLastEventType(
                    Quartz.kCGEventSourceStateCombinedSessionState,
                    Quartz.kCGAnyInputEventType,
                )
            )
            if idle_seconds < 0:
                idle_seconds = 0.0
        except Exception:
            idle_seconds = None

        with self.lock:
            if idle_seconds is not None:
                self.last_input_time = now - timedelta(seconds=idle_seconds)

                # Если idle уменьшился относительно прошлого опроса,
                # значит был хотя бы один новый ввод.
                if (
                    self._last_polled_idle_seconds is not None
                    and idle_seconds + 1e-3 < self._last_polled_idle_seconds
                ):
                    self.inputs_since_last_poll += 1

                self._last_polled_idle_seconds = idle_seconds

            last_time = self.last_input_time
            count = self.inputs_since_last_poll
            self.inputs_since_last_poll = 0

        return last_time, count

    def consume_stats(self):
        """
        Возвращает (last_input_time, inputs_since_last_poll)
        и обнуляет счётчик inputs_since_last_poll.
        """
        if self._use_macos_polling:
            return self._consume_stats_macos_polling()

        with self.lock:
            last_time = self.last_input_time
            count = self.inputs_since_last_poll
            self.inputs_since_last_poll = 0

        return last_time, count
