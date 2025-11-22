# focus_worker.py

from datetime import datetime, timedelta
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

from config import Config
from tracker.input_tracker import InputActivityTracker
from tracker.active_window import get_active_window
from storage.db import init_db, insert_event
from notifier import send_notification


class FocusWorker(QThread):
    """
    Поток, который занимается отслеживанием активности,
    записью в БД и отправкой уведомлений.
    """

    status_updated = pyqtSignal(str)     # новая строка лога
    started_tracking = pyqtSignal()      # трекер стартовал
    stopped_tracking = pyqtSignal()      # трекер остановлен

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self._stop_flag = False

    def stop(self):
        """Запрашивает остановку потока."""
        self._stop_flag = True

    def run(self):
        self._stop_flag = False
        self.status_updated.emit("Инициализация трекера...")
        init_db(self.config.db_path)

        activity_tracker = InputActivityTracker()
        activity_tracker.start()

        # Непрерывная работа в рабочих приложениях (для напоминаний о перерыве)
        continuous_work_seconds = 0

        last_idle_notification_time: Optional[datetime] = None
        last_break_notification_time: Optional[datetime] = None

        self.started_tracking.emit()
        self.status_updated.emit("Трекер запущен.")

        # Порог для уведомления о бездействии:
        # если idle_warning_minutes == 0, используем порог бездействия (idle_threshold_seconds)
        if self.config.idle_warning_minutes > 0:
            idle_notify_seconds = self.config.idle_warning_minutes * 60
        else:
            idle_notify_seconds = self.config.idle_threshold_seconds

        try:
            while not self._stop_flag:
                now = datetime.utcnow()

                # --- Ввод (клавиатура/мышь) ---
                last_input_time, inputs_since_last = activity_tracker.consume_stats()
                idle_delta = now - last_input_time
                idle_seconds = idle_delta.total_seconds()

                # Активен ли пользователь по input
                user_active = idle_seconds <= self.config.idle_threshold_seconds

                # --- Активное окно ---
                app_name, window_title = get_active_window()
                app_name_norm = (app_name or "").lower()

                is_work_app = app_name_norm in self.config.work_apps
                is_distracting_app = app_name_norm in self.config.distracting_apps

                # --- Тип состояния (для понимания и логов) ---
                if not user_active:
                    state = "idle"
                elif is_work_app:
                    state = "work"
                elif is_distracting_app:
                    state = "distract"
                else:
                    state = "other"

                # --- Запись события в БД ---
                insert_event(
                    db_path=self.config.db_path,
                    timestamp_utc=now,
                    app_name=app_name or "",
                    window_title=window_title or "",
                    is_work_app=is_work_app,
                    is_distracting_app=is_distracting_app,
                    user_active=user_active,
                    idle_seconds=idle_seconds,
                    inputs_since_last=inputs_since_last,
                )

                # --- Непрерывная работа (только когда активные input + рабочее окно) ---
                if user_active and is_work_app:
                    continuous_work_seconds += self.config.poll_interval_seconds
                else:
                    continuous_work_seconds = 0

                # --- Лог в интерфейс ---
                log_line = (
                    f"state={state} "
                    f"idle={int(idle_seconds)}s "
                    f"inputs={inputs_since_last} "
                    f"app={app_name} "
                    f"work={is_work_app} distract={is_distracting_app} "
                    f"title={(window_title or '')[:40]!r}"
                )
                self.status_updated.emit(log_line)

                # --- Уведомление о бездействии (завязано на idle_seconds) ---
                if self.config.notify_on_idle and state == "idle":
                    if idle_seconds >= idle_notify_seconds:
                        need_notify = False
                        if last_idle_notification_time is None:
                            need_notify = True
                        else:
                            # чтобы не спамить — не чаще, чем раз в idle_notify_seconds
                            if (now - last_idle_notification_time).total_seconds() >= idle_notify_seconds:
                                need_notify = True

                        if need_notify:
                            send_notification(
                                "Похоже, вы бездействуете",
                                "Давно не было активности. Вы отвлеклись или пора завершить работу?",
                            )
                            last_idle_notification_time = now

                # --- Уведомление о необходимости перерыва ---
                if self.config.notify_on_break and state == "work":
                    if continuous_work_seconds >= self.config.break_warning_minutes * 60:
                        need_notify = False
                        if last_break_notification_time is None:
                            need_notify = True
                        else:
                            # перерывы напоминаем реже (например, раз в 10 минут)
                            if (now - last_break_notification_time) >= timedelta(minutes=10):
                                need_notify = True

                        if need_notify:
                            send_notification(
                                "Пора сделать перерыв",
                                "Вы долго работаете без перерыва. Встаньте, пройдитесь, отдохните пару минут.",
                            )
                            last_break_notification_time = now
                            # можно сбросить счётчик, чтобы отсчитывать заново
                            continuous_work_seconds = 0

                # --- Пауза до следующего тика ---
                self.sleep(self.config.poll_interval_seconds)

        finally:
            activity_tracker.stop()
            self.stopped_tracking.emit()
            self.status_updated.emit("Трекер остановлен.")
