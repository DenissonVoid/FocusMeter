# tracker/input_tracker.py

from datetime import datetime
import threading

from pynput import keyboard, mouse


class InputActivityTracker:
    """
    Отслеживает глобальные события ввода:
    - любые нажатия клавиатуры
    - движение мыши, клики, скролл

    Хранит:
    - время последней активности
    - сколько событий ввода было с момента последнего опроса (для статистики)
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.last_input_time = datetime.utcnow()
        self.inputs_since_last_poll = 0

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
        self.keyboard_listener.start()
        self.mouse_listener.start()

    def stop(self):
        self.keyboard_listener.stop()
        self.mouse_listener.stop()

    def consume_stats(self):
        """
        Возвращает (last_input_time, inputs_since_last_poll)
        и обнуляет счётчик inputs_since_last_poll.
        """
        with self.lock:
            last_time = self.last_input_time
            count = self.inputs_since_last_poll
            self.inputs_since_last_poll = 0

        return last_time, count
