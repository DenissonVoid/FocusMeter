from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PyQt5.QtCore import QThread, pyqtSignal

from app_rules import AppRulesRepository
from config import Config
from notifier import send_notification
from storage.db import init_db, insert_event
from tracker.active_window import WindowInfo, get_active_window_info
from tracker.input_tracker import InputActivityTracker


@dataclass
class WorkerSnapshot:
    timestamp_utc: datetime
    state: str
    status_text: str
    app_name: str
    window_title: str
    exe_path: str
    user_active: bool
    is_work_app: bool
    is_distracting_app: bool
    is_excluded_app: bool
    idle_seconds: float
    non_productive_seconds: float
    fatigue_score: float
    fatigue_threshold: float
    idle_notify_seconds: float
    seconds_to_break: float
    seconds_to_idle_warning: float
    paused: bool


class FocusWorker(QThread):
    status_updated = pyqtSignal(str)
    started_tracking = pyqtSignal()
    stopped_tracking = pyqtSignal()
    paused_changed = pyqtSignal(bool)
    snapshot_updated = pyqtSignal(object)

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self._stop_flag = False
        self._pause_flag = False
        self._rules_repo: AppRulesRepository | None = None
        self._last_snapshot: WorkerSnapshot | None = None

    def stop(self) -> None:
        self._stop_flag = True

    def pause_tracking(self) -> None:
        self._pause_flag = True

    def resume_tracking(self) -> None:
        self._pause_flag = False

    def reload_rules(self) -> None:
        if self._rules_repo is None:
            return
        self._rules_repo.reload()
        self.status_updated.emit("Правила приложений обновлены.")

    def _sleep_with_checks(self, milliseconds: int) -> None:
        remaining = max(0, milliseconds)
        while remaining > 0 and not self._stop_flag and not self._pause_flag:
            step = min(200, remaining)
            self.msleep(step)
            remaining -= step

    @staticmethod
    def _status_text_for_state(state: str) -> str:
        mapping = {
            "work": "В фокусе",
            "distract": "Отвлекающее приложение",
            "other": "Активность вне правил",
            "excluded": "Исключенное приложение",
            "idle": "Нет активности",
            "paused": "Пауза",
            "stopped": "Остановлено",
        }
        return mapping.get(state, "Ожидание")

    def _emit_snapshot(
        self,
        now: datetime,
        state: str,
        window: WindowInfo | None,
        user_active: bool,
        is_work_app: bool,
        is_distracting_app: bool,
        is_excluded_app: bool,
        idle_seconds: float,
        non_productive_seconds: float,
        fatigue_score: float,
        fatigue_threshold: float,
        idle_notify_seconds: float,
        paused: bool,
    ) -> None:
        app_name = window.process_name if window else ""
        window_title = window.window_title if window else ""
        exe_path = window.exe_path if window else ""

        snapshot = WorkerSnapshot(
            timestamp_utc=now,
            state=state,
            status_text=self._status_text_for_state(state),
            app_name=app_name,
            window_title=window_title,
            exe_path=exe_path,
            user_active=user_active,
            is_work_app=is_work_app,
            is_distracting_app=is_distracting_app,
            is_excluded_app=is_excluded_app,
            idle_seconds=idle_seconds,
            non_productive_seconds=non_productive_seconds,
            fatigue_score=fatigue_score,
            fatigue_threshold=fatigue_threshold,
            idle_notify_seconds=idle_notify_seconds,
            seconds_to_break=max(fatigue_threshold - fatigue_score, 0.0),
            seconds_to_idle_warning=max(
                idle_notify_seconds - non_productive_seconds, 0.0
            ),
            paused=paused,
        )
        self._last_snapshot = snapshot
        self.snapshot_updated.emit(snapshot)

    def run(self) -> None:
        self._stop_flag = False
        self._pause_flag = False
        self.status_updated.emit("Инициализация трекера...")
        init_db(self.config.db_path)

        self._rules_repo = AppRulesRepository(self.config)
        self._rules_repo.apply_to_config(persist=False)

        activity_tracker = InputActivityTracker()
        activity_tracker.start()

        idle_notify_seconds = (
            self.config.idle_warning_minutes * 60
            if self.config.idle_warning_minutes > 0
            else self.config.idle_threshold_seconds
        )
        fatigue_threshold = max(1.0, float(self.config.break_warning_minutes * 60))
        fatigue_recovery_factor = 4.0
        min_break_notify_interval_seconds = 60.0

        fatigue_score = 0.0
        non_productive_seconds = 0.0

        last_idle_notification_time: datetime | None = None
        last_break_notification_time: datetime | None = None
        last_observed_signature: tuple[str, str] | None = None

        self.started_tracking.emit()
        self.paused_changed.emit(False)
        self.status_updated.emit("Трекер запущен.")

        try:
            while not self._stop_flag:
                if self._pause_flag:
                    if (
                        self._last_snapshot is not None
                        and not self._last_snapshot.paused
                    ):
                        self._emit_snapshot(
                            now=datetime.utcnow(),
                            state="paused",
                            window=WindowInfo(
                                process_name=self._last_snapshot.app_name,
                                window_title=self._last_snapshot.window_title,
                                exe_path=self._last_snapshot.exe_path,
                            ),
                            user_active=self._last_snapshot.user_active,
                            is_work_app=self._last_snapshot.is_work_app,
                            is_distracting_app=self._last_snapshot.is_distracting_app,
                            is_excluded_app=self._last_snapshot.is_excluded_app,
                            idle_seconds=self._last_snapshot.idle_seconds,
                            non_productive_seconds=self._last_snapshot.non_productive_seconds,
                            fatigue_score=self._last_snapshot.fatigue_score,
                            fatigue_threshold=self._last_snapshot.fatigue_threshold,
                            idle_notify_seconds=self._last_snapshot.idle_notify_seconds,
                            paused=True,
                        )
                        self.status_updated.emit("Трекинг поставлен на паузу.")
                        self.paused_changed.emit(True)
                    self.msleep(250)
                    continue

                if self._last_snapshot is not None and self._last_snapshot.paused:
                    self.status_updated.emit("Трекинг возобновлен.")
                    self.paused_changed.emit(False)

                now = datetime.utcnow()
                last_input_time, inputs_since_last = activity_tracker.consume_stats()
                idle_seconds = max((now - last_input_time).total_seconds(), 0.0)
                user_active = idle_seconds <= self.config.idle_threshold_seconds

                window = get_active_window_info()
                app_name = window.process_name or ""
                app_name_norm = app_name.lower()

                if app_name_norm:
                    signature = (app_name_norm, window.window_title or "")
                    if signature != last_observed_signature:
                        self._rules_repo.record_observation(
                            process_name=app_name_norm,
                            window_title=window.window_title,
                            exe_path=window.exe_path,
                            observed_at=now,
                        )
                        last_observed_signature = signature

                is_work_app = app_name_norm in self.config.work_apps
                is_distracting_app = app_name_norm in self.config.distracting_apps
                is_excluded_app = (
                    self._rules_repo is not None
                    and app_name_norm in self._rules_repo.state.excluded_apps
                )

                if not user_active:
                    state = "idle"
                elif is_work_app:
                    state = "work"
                elif is_distracting_app:
                    state = "distract"
                elif is_excluded_app:
                    state = "excluded"
                else:
                    state = "other"

                insert_event(
                    db_path=self.config.db_path,
                    timestamp_utc=now,
                    app_name=app_name,
                    window_title=window.window_title or "",
                    is_work_app=is_work_app,
                    is_distracting_app=is_distracting_app,
                    user_active=user_active,
                    idle_seconds=idle_seconds,
                    inputs_since_last=inputs_since_last,
                )

                dt = float(self.config.poll_interval_seconds)
                if state == "work":
                    fatigue_score += dt
                elif state in {"idle", "distract"}:
                    fatigue_score = max(
                        0.0, fatigue_score - dt * fatigue_recovery_factor
                    )

                if state == "idle":
                    non_productive_seconds = idle_seconds
                elif state == "distract":
                    non_productive_seconds += dt
                elif state == "work":
                    non_productive_seconds = 0.0

                self.status_updated.emit(
                    " | ".join(
                        [
                            f"state={state}",
                            f"idle={int(idle_seconds)}s",
                            f"break_in={int(max(fatigue_threshold - fatigue_score, 0.0))}s",
                            f"idle_warn_in={int(max(idle_notify_seconds - non_productive_seconds, 0.0))}s",
                            f"app={app_name or '-'}",
                            f"title={(window.window_title or '')[:48]!r}",
                        ]
                    )
                )

                self._emit_snapshot(
                    now=now,
                    state=state,
                    window=window,
                    user_active=user_active,
                    is_work_app=is_work_app,
                    is_distracting_app=is_distracting_app,
                    is_excluded_app=is_excluded_app,
                    idle_seconds=idle_seconds,
                    non_productive_seconds=non_productive_seconds,
                    fatigue_score=fatigue_score,
                    fatigue_threshold=fatigue_threshold,
                    idle_notify_seconds=idle_notify_seconds,
                    paused=False,
                )

                if (
                    state in {"idle", "distract"}
                    and self.config.notify_on_idle
                    and non_productive_seconds >= idle_notify_seconds
                ):
                    need_notify = False
                    if last_idle_notification_time is None:
                        need_notify = True
                    elif (
                        now - last_idle_notification_time
                    ).total_seconds() >= idle_notify_seconds:
                        need_notify = True

                    if need_notify:
                        send_notification(
                            "Пора вернуться к фокусу",
                            "FocusMeter давно не видит продуктивной активности. Вернитесь к задаче или завершите сессию.",
                        )
                        last_idle_notification_time = now
                        non_productive_seconds = 0.0

                if (
                    state == "work"
                    and self.config.notify_on_break
                    and fatigue_score >= fatigue_threshold
                ):
                    need_notify = False
                    if last_break_notification_time is None:
                        need_notify = True
                    elif (
                        now - last_break_notification_time
                    ).total_seconds() >= min_break_notify_interval_seconds:
                        need_notify = True

                    if need_notify:
                        send_notification(
                            "Пора на короткий перерыв",
                            "Вы долго держите фокус. Небольшая пауза сейчас поможет сохранить темп.",
                        )
                        last_break_notification_time = now
                        fatigue_score = fatigue_threshold * 0.5

                self._sleep_with_checks(int(self.config.poll_interval_seconds * 1000))

        finally:
            activity_tracker.stop()
            self.paused_changed.emit(False)
            self.stopped_tracking.emit()
            self.status_updated.emit("Трекер остановлен.")
