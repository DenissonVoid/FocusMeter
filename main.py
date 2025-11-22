# main.py

import time
from datetime import datetime, timedelta

from config import load_config
from notifier import send_notification
from tracker.input_tracker import InputActivityTracker
from tracker.active_window import get_active_window
from storage.db import init_db, insert_event


def main():
    print("=== FocusMeter MVP v1 ===")

    config = load_config()
    init_db(config.db_path)

    print(f"[INFO] База данных: {config.db_path}")
    print(f"[INFO] Интервал опроса: {config.poll_interval_seconds} сек")
    print(f"[INFO] Порог бездействия: {config.idle_threshold_seconds} сек")
    print(f"[INFO] Напоминание о бездействии: {config.idle_warning_minutes} мин")
    print(f"[INFO] Напоминание о перерыве: {config.break_warning_minutes} мин")
    print(f"[INFO] Рабочие приложения: {config.work_apps}")
    print(f"[INFO] Отвлекающие приложения: {config.distracting_apps}")
    print("Нажми Ctrl+C, чтобы остановить программу.\n")

    activity_tracker = InputActivityTracker()
    activity_tracker.start()

    # Счётчики для логики уведомлений
    continuous_work_seconds = 0  # непрерывное время работы в "рабочих" приложениях при активности
    continuous_idle_seconds = 0  # непрерывное время бездействия

    last_idle_notification_time: datetime | None = None
    last_break_notification_time: datetime | None = None

    try:
        while True:
            now = datetime.utcnow()

            # Данные по вводу
            last_input_time, inputs_since_last = activity_tracker.consume_stats()
            idle_delta = now - last_input_time
            idle_seconds = idle_delta.total_seconds()

            user_active = idle_seconds <= config.idle_threshold_seconds

            # Текущее активное окно
            app_name, window_title = get_active_window()
            app_name_norm = (app_name or "").lower()

            is_work_app = app_name_norm in config.work_apps
            is_distracting_app = app_name_norm in config.distracting_apps

            # Запись события в БД
            insert_event(
                db_path=config.db_path,
                timestamp_utc=now,
                app_name=app_name or "",
                window_title=window_title or "",
                is_work_app=is_work_app,
                is_distracting_app=is_distracting_app,
                user_active=user_active,
                idle_seconds=idle_seconds,
                inputs_since_last=inputs_since_last,
            )

            # Обновляем счётчики непрерывной работы / бездействия
            if user_active and is_work_app:
                continuous_work_seconds += config.poll_interval_seconds
                continuous_idle_seconds = 0
            elif not user_active:
                continuous_idle_seconds += config.poll_interval_seconds
                continuous_work_seconds = 0
            else:
                # активен, но не в рабочем приложении -> считаем как перерыв/отвлечение
                continuous_work_seconds = 0
                # если хочешь считать "сидит в нерабочем, но двигается" как отдельную метрику, можно потом добавить

            # Лог в консоль (при желании можно выключить/сделать реже)
            print(
                f"[{now.isoformat()}] "
                f"active={int(user_active)} idle={int(idle_seconds)}s "
                f"inputs={inputs_since_last} "
                f"app={app_name} "
                f"work={is_work_app} distract={is_distracting_app} "
                f"title={repr((window_title or '')[:50])}"
            )

            # Уведомление о бездействии
            if config.notify_on_idle and continuous_idle_seconds >= config.idle_warning_minutes * 60:
                need_notify = False
                if last_idle_notification_time is None:
                    need_notify = True
                else:
                    # чтобы не спамить, введём минимальный интервал между уведомлениями, например 5 минут
                    if (now - last_idle_notification_time) >= timedelta(minutes=5):
                        need_notify = True

                if need_notify:
                    send_notification(
                        "Похоже, вы бездействуете",
                        "Давно не было активности. Вы отвлеклись или пора завершить работу?",
                    )
                    last_idle_notification_time = now
                    # можно сбросить счётчик, чтобы ждать следующего длинного периода
                    continuous_idle_seconds = 0

            # Уведомление о необходимости перерыва
            if config.notify_on_break and continuous_work_seconds >= config.break_warning_minutes * 60:
                need_notify = False
                if last_break_notification_time is None:
                    need_notify = True
                else:
                    if (now - last_break_notification_time) >= timedelta(minutes=10):
                        need_notify = True

                if need_notify:
                    send_notification(
                        "Пора сделать перерыв",
                        "Вы долго работаете без перерыва. Встаньте, пройдитесь, отдохните пару минут.",
                    )
                    last_break_notification_time = now
                    continuous_work_seconds = 0

            time.sleep(config.poll_interval_seconds)

    except KeyboardInterrupt:
        print("\n[INFO] Остановка по Ctrl+C...")
    finally:
        activity_tracker.stop()
        print("[INFO] Завершено.")


if __name__ == "__main__":
    main()
