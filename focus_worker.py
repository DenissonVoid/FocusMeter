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
    Поток, который отслеживает активность,
    пишет события в БД и управляет уведомлениями.
    """

    status_updated = pyqtSignal(str)     # новые строки лога
    started_tracking = pyqtSignal()      # трекер стартовал
    stopped_tracking = pyqtSignal()      # трекер остановлен

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self._stop_flag = False

    def stop(self):
        """Запрос остановки потока."""
        self._stop_flag = True

    def run(self):
        self._stop_flag = False
        self.status_updated.emit("Инициализация трекера...")
        init_db(self.config.db_path)

        activity_tracker = InputActivityTracker()
        activity_tracker.start()

        # --- Параметры уведомлений ---

        # через сколько секунд бездействия/отвлечения напоминать
        if self.config.idle_warning_minutes > 0:
            idle_notify_seconds = self.config.idle_warning_minutes * 60
        else:
            # специальный режим: напоминать сразу после превышения порога ввода
            idle_notify_seconds = self.config.idle_threshold_seconds

        # порог "усталости" для напоминания о перерыве
        fatigue_threshold = max(1.0, self.config.break_warning_minutes * 60)

        # коэффициент восстановления: насколько быстрее отдых снимает усталость,
        # чем работа её накапливает. 4 означает, что 10 минут отдыха компенсируют
        # примерно 40 минут работы.
        FATIGUE_RECOVERY_FACTOR = 4.0

        # минимальный интервал между напоминаниями о перерыве (секунды),
        # чтобы не спамить при полном игноре рекомендаций
        MIN_BREAK_NOTIFY_INTERVAL_SECONDS = 60

        # --- Состояние для алгоритма ---

        # интегральная "усталость" от работы
        fatigue_score: float = 0.0

        # время непрерывного неблагоприятного состояния
        # (idle ИЛИ активное отвлекающее приложение)
        non_productive_seconds: float = 0.0

        last_idle_notification_time: Optional[datetime] = None
        last_break_notification_time: Optional[datetime] = None

        self.started_tracking.emit()
        self.status_updated.emit("Трекер запущен.")

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

                # --- Определяем состояние для логики ---
                if not user_active:
                    state = "idle"
                elif is_work_app:
                    state = "work"
                elif is_distracting_app:
                    state = "distract"
                else:
                    state = "other"

                # --- Записываем событие в БД ---
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

                # --- Обновляем "усталость" (алгоритм перерывов) ---

                dt = self.config.poll_interval_seconds

                if state == "work":
                    # Работа увеличивает усталость линейно во времени
                    fatigue_score += dt
                else:
                    # Любое состояние, кроме "work", уменьшает усталость
                    fatigue_score = max(
                        0.0, fatigue_score - dt * FATIGUE_RECOVERY_FACTOR
                    )

                # --- Обновляем "непродуктивные" секунды (idle + отвлечения) ---

                # ВАЖНО: здесь мы считаем неблагоприятным как отсутствие ввода,
                # так и активную работу в отвлекающих приложениях.
                if state in ("idle", "distract"):
                    non_productive_seconds += dt
                else:
                    non_productive_seconds = 0.0

                # --- Лог в интерфейс ---
                log_line = (
                    f"state={state} "
                    f"idle={int(idle_seconds)}s "
                    f"non_prod={int(non_productive_seconds)}s "
                    f"fatigue={int(fatigue_score)}/{int(fatigue_threshold)} "
                    f"inputs={inputs_since_last} "
                    f"app={app_name} "
                    f"work={is_work_app} distract={is_distracting_app} "
                    f"title={(window_title or '')[:40]!r}"
                )
                self.status_updated.emit(log_line)

                # --- Уведомление о бездействии/отвлечении ---

                if self.config.notify_on_idle and non_productive_seconds >= idle_notify_seconds:
                    need_notify = False
                    if last_idle_notification_time is None:
                        need_notify = True
                    else:
                        # не чаще, чем раз в тот же интервал
                        if (now - last_idle_notification_time).total_seconds() >= idle_notify_seconds:
                            need_notify = True

                    if need_notify:
                        send_notification(
                            "Похоже, вы отвлеклись или бездействуете",
                            "Давно не было продуктивной активности. "
                            "Вернитесь к рабочим задачам или завершите сессию.",
                        )
                        last_idle_notification_time = now
                        # сбрасываем счётчик неблагоприятного состояния
                        non_productive_seconds = 0.0

                # --- Уведомление о необходимости перерыва ---

                if self.config.notify_on_break and fatigue_score >= fatigue_threshold:
                    need_notify = False
                    if last_break_notification_time is None:
                        need_notify = True
                    else:
                        if (now - last_break_notification_time).total_seconds() >= MIN_BREAK_NOTIFY_INTERVAL_SECONDS:
                            need_notify = True

                    if need_notify:
                        send_notification(
                            "Пора сделать перерыв",
                            "Вы долго работаете в рабочих приложениях. "
                            "Сделайте небольшую паузу и отвлекитесь от экрана.",
                        )
                        last_break_notification_time = now

                        # После уведомления частично "разгружаем" усталость,
                        # чтобы следующая напоминалка не пришла мгновенно,
                        # но при коротком перерыве она появится заметно раньше,
                        # чем через полный интервал.
                        fatigue_score = fatigue_threshold * 0.5

                # --- Пауза между итерациями ---
                self.sleep(self.config.poll_interval_seconds)

        finally:
            activity_tracker.stop()
            self.stopped_tracking.emit()
            self.status_updated.emit("Трекер остановлен.")
