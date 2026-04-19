from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AppUsageRow:
    app_name: str
    last_window_title: str
    active_seconds: float
    work_active_seconds: float
    distract_active_seconds: float
    other_active_seconds: float
    share_of_total: float
    share_of_active: float

    @property
    def app_type(self) -> str:
        if self.work_active_seconds > 0 and self.distract_active_seconds == 0:
            return "Рабочее"
        if self.distract_active_seconds > 0 and self.work_active_seconds == 0:
            return "Отвлекающее"
        if self.work_active_seconds == 0 and self.distract_active_seconds == 0:
            return "Прочее"
        return "Смешанное"


@dataclass
class TimeStats:
    period_start: datetime
    period_end: datetime
    total_seconds: float
    active_seconds: float
    work_active_seconds: float
    distract_active_seconds: float
    other_active_seconds: float
    idle_seconds: float
    by_app: list[AppUsageRow]


def _connect(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(db_path, timeout=5.0)


def init_db(db_path: str) -> None:
    conn = _connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            app_name TEXT,
            window_title TEXT,
            is_work_app INTEGER NOT NULL,
            is_distracting_app INTEGER NOT NULL,
            user_active INTEGER NOT NULL,
            idle_seconds REAL NOT NULL,
            inputs_since_last INTEGER NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def insert_event(
    db_path: str,
    timestamp_utc: datetime,
    app_name: str,
    window_title: str,
    is_work_app: bool,
    is_distracting_app: bool,
    user_active: bool,
    idle_seconds: float,
    inputs_since_last: int,
) -> None:
    conn = _connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO events (
            timestamp_utc,
            app_name,
            window_title,
            is_work_app,
            is_distracting_app,
            user_active,
            idle_seconds,
            inputs_since_last
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            timestamp_utc.isoformat(),
            app_name or "",
            window_title or "",
            1 if is_work_app else 0,
            1 if is_distracting_app else 0,
            1 if user_active else 0,
            float(idle_seconds),
            int(inputs_since_last),
        ),
    )
    conn.commit()
    conn.close()


def get_time_stats(
    db_path: str,
    start_utc: datetime,
    end_utc: datetime,
    sample_interval_seconds: float,
) -> TimeStats:
    init_db(db_path)

    start_iso = start_utc.isoformat()
    end_iso = end_utc.isoformat()

    conn = _connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            COUNT(*) AS total_rows,
            SUM(CASE WHEN user_active = 1 THEN 1 ELSE 0 END) AS active_rows,
            SUM(CASE WHEN user_active = 1 AND is_work_app = 1 THEN 1 ELSE 0 END) AS work_rows,
            SUM(CASE WHEN user_active = 1 AND is_distracting_app = 1 THEN 1 ELSE 0 END) AS distract_rows,
            SUM(CASE WHEN user_active = 0 THEN 1 ELSE 0 END) AS idle_rows
        FROM events
        WHERE timestamp_utc >= ? AND timestamp_utc < ?;
        """,
        (start_iso, end_iso),
    )
    row = cur.fetchone() or (0, 0, 0, 0, 0)

    total_rows = row[0] or 0
    active_rows = row[1] or 0
    work_rows = row[2] or 0
    distract_rows = row[3] or 0
    idle_rows = row[4] or 0

    total_seconds = total_rows * sample_interval_seconds
    active_seconds = active_rows * sample_interval_seconds
    work_active_seconds = work_rows * sample_interval_seconds
    distract_active_seconds = distract_rows * sample_interval_seconds
    idle_seconds = idle_rows * sample_interval_seconds
    other_active_seconds = max(
        active_seconds - work_active_seconds - distract_active_seconds,
        0.0,
    )

    cur.execute(
        """
        SELECT
            app_name,
            COALESCE(MAX(NULLIF(window_title, '')), '') AS last_window_title,
            SUM(CASE WHEN user_active = 1 THEN 1 ELSE 0 END) AS active_rows,
            SUM(CASE WHEN user_active = 1 AND is_work_app = 1 THEN 1 ELSE 0 END) AS work_rows,
            SUM(CASE WHEN user_active = 1 AND is_distracting_app = 1 THEN 1 ELSE 0 END) AS distract_rows
        FROM events
        WHERE timestamp_utc >= ? AND timestamp_utc < ?
        GROUP BY app_name
        HAVING SUM(CASE WHEN user_active = 1 THEN 1 ELSE 0 END) > 0
        ORDER BY active_rows DESC, app_name ASC;
        """,
        (start_iso, end_iso),
    )

    by_app: list[AppUsageRow] = []
    for app_name, last_window_title, active_rows, work_rows, distract_rows in cur.fetchall():
        active_rows = active_rows or 0
        work_rows = work_rows or 0
        distract_rows = distract_rows or 0

        app_active_seconds = active_rows * sample_interval_seconds
        app_work_seconds = work_rows * sample_interval_seconds
        app_distract_seconds = distract_rows * sample_interval_seconds
        app_other_seconds = max(
            app_active_seconds - app_work_seconds - app_distract_seconds,
            0.0,
        )
        by_app.append(
            AppUsageRow(
                app_name=app_name or "",
                last_window_title=last_window_title or "",
                active_seconds=app_active_seconds,
                work_active_seconds=app_work_seconds,
                distract_active_seconds=app_distract_seconds,
                other_active_seconds=app_other_seconds,
                share_of_total=(app_active_seconds / total_seconds) if total_seconds else 0.0,
                share_of_active=(app_active_seconds / active_seconds) if active_seconds else 0.0,
            )
        )

    conn.close()

    return TimeStats(
        period_start=start_utc,
        period_end=end_utc,
        total_seconds=total_seconds,
        active_seconds=active_seconds,
        work_active_seconds=work_active_seconds,
        distract_active_seconds=distract_active_seconds,
        other_active_seconds=other_active_seconds,
        idle_seconds=idle_seconds,
        by_app=by_app,
    )
