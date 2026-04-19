from __future__ import annotations

import argparse
import builtins
import time
from datetime import datetime, timedelta


def _safe_console_text(value: str) -> str:
    """Normalize potentially broken surrogate characters from Win32 window titles."""
    return value.encode("utf-16", "surrogatepass").decode("utf-16", "replace")


def safe_print(message: str) -> None:
    try:
        builtins.print(_safe_console_text(message))
    except OSError:
        # Console handle can reject invalid data in edge cases; never crash tracking for logs.
        pass


# Route legacy print() calls through safe output to avoid console encoding crashes.
print = safe_print


def run_cli_tracker() -> None:
    """Run legacy terminal tracker mode."""
    from app_rules import AppRulesRepository
    from config import load_config
    from notifier import send_notification
    from storage.db import init_db, insert_event
    from tracker.active_window import get_active_window_info
    from tracker.input_tracker import InputActivityTracker

    safe_print("=== FocusMeter CLI tracker ===")

    config = load_config()
    rules_repo = AppRulesRepository(config)
    rules_repo.apply_to_config(persist=False)
    init_db(config.db_path)

    print(f"[INFO] Database: {config.db_path}")
    print(f"[INFO] Poll interval: {config.poll_interval_seconds}s")
    print(f"[INFO] Idle threshold: {config.idle_threshold_seconds}s")
    print(f"[INFO] Idle reminder: {config.idle_warning_minutes}m")
    print(f"[INFO] Break reminder: {config.break_warning_minutes}m")
    print("Press Ctrl+C to stop.\n")

    activity_tracker = InputActivityTracker()
    activity_tracker.start()

    continuous_work_seconds = 0
    continuous_idle_seconds = 0

    last_idle_notification_time: datetime | None = None
    last_break_notification_time: datetime | None = None
    last_observed_signature: tuple[str, str] | None = None

    try:
        while True:
            now = datetime.utcnow()

            last_input_time, inputs_since_last = activity_tracker.consume_stats()
            idle_seconds = (now - last_input_time).total_seconds()
            user_active = idle_seconds <= config.idle_threshold_seconds

            window = get_active_window_info()
            app_name = window.process_name or ""
            window_title = window.window_title or ""
            app_name_norm = app_name.lower()

            if app_name_norm:
                signature = (app_name_norm, window_title)
                if signature != last_observed_signature:
                    rules_repo.record_observation(
                        process_name=app_name_norm,
                        window_title=window_title,
                        exe_path=window.exe_path,
                        observed_at=now,
                    )
                    last_observed_signature = signature

            is_work_app = app_name_norm in config.work_apps
            is_distracting_app = app_name_norm in config.distracting_apps

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

            if user_active and is_work_app:
                continuous_work_seconds += config.poll_interval_seconds
                continuous_idle_seconds = 0
            elif not user_active:
                continuous_idle_seconds += config.poll_interval_seconds
                continuous_work_seconds = 0
            else:
                continuous_work_seconds = 0

            safe_print(
                f"[{now.isoformat()}] "
                f"active={int(user_active)} idle={int(idle_seconds)}s "
                f"inputs={inputs_since_last} "
                f"app={app_name} "
                f"work={is_work_app} distract={is_distracting_app} "
                f"title={repr((window_title or '')[:50])}"
            )

            if (
                config.notify_on_idle
                and continuous_idle_seconds >= config.idle_warning_minutes * 60
            ):
                need_notify = False
                if last_idle_notification_time is None:
                    need_notify = True
                elif (now - last_idle_notification_time) >= timedelta(minutes=5):
                    need_notify = True

                if need_notify:
                    send_notification(
                        "Looks like you're idle",
                        "No recent activity detected. Continue work or take a break?",
                    )
                    last_idle_notification_time = now
                    continuous_idle_seconds = 0

            if (
                config.notify_on_break
                and continuous_work_seconds >= config.break_warning_minutes * 60
            ):
                need_notify = False
                if last_break_notification_time is None:
                    need_notify = True
                elif (now - last_break_notification_time) >= timedelta(minutes=10):
                    need_notify = True

                if need_notify:
                    send_notification(
                        "Time for a break",
                        "You've been working for a while. Stand up and rest for a few minutes.",
                    )
                    last_break_notification_time = now
                    continuous_work_seconds = 0

            time.sleep(config.poll_interval_seconds)
    except KeyboardInterrupt:
        print("\n[INFO] Stopped by Ctrl+C.")
    finally:
        activity_tracker.stop()
        print("[INFO] Tracker stopped.")


def run_gui() -> None:
    """Run Qt desktop GUI mode."""
    from main_gui import main as run_gui_main

    run_gui_main()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FocusMeter launcher")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run terminal tracker mode instead of desktop GUI.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if args.cli:
        run_cli_tracker()
    else:
        run_gui()


if __name__ == "__main__":
    main()
