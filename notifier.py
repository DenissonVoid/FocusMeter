# notifier.py

from datetime import datetime

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    print("[NOTIFIER] plyer не установлен, буду только печатать уведомления в консоль.")


def send_notification(title: str, message: str):
    """
    Отправляет системное уведомление (если возможно) + печатает в консоль.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] NOTIFY: {title} — {message}")

    if not PLYER_AVAILABLE:
        return

    try:
        notification.notify(
            title=title,
            message=message,
            app_name="FocusMeter",
            timeout=10  # секунд
        )
    except Exception as e:
        print(f"[NOTIFIER ERROR] {e}")
