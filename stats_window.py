# stats_window.py

from datetime import datetime, time as dt_time

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDateEdit,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from config import Config
from storage.db import get_time_stats


class StatsWindow(QDialog):
    """
    Окно с подробной статистикой за выбранную дату.
    Использует get_time_stats и показывает:
    - сводные показатели за день
    - таблицу по приложениям
    """

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config

        self.setWindowTitle("Подробная статистика")
        self.resize(900, 600)

        self._init_ui()
        self._set_default_date()
        self._refresh_stats()

    # ---------- UI ----------

    def _init_ui(self):
        main_layout = QVBoxLayout()

        # блок выбора даты
        date_layout = QHBoxLayout()
        date_label = QLabel("Дата:")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.clicked.connect(self._refresh_stats)

        date_layout.addWidget(date_label)
        date_layout.addWidget(self.date_edit)
        date_layout.addStretch()
        date_layout.addWidget(self.refresh_button)

        # сводка
        self.summary_view = QPlainTextEdit()
        self.summary_view.setReadOnly(True)

        # таблица по приложениям
        self.apps_table = QTableWidget()
        self.apps_table.setColumnCount(5)
        self.apps_table.setHorizontalHeaderLabels(
            [
                "Приложение",
                "Тип",
                "Активное время",
                "Рабочее активное",
                "Отвлекающее активное",
            ]
        )
        header = self.apps_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # имя приложения
        for col in range(1, 5):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)

        main_layout.addLayout(date_layout)
        main_layout.addWidget(QLabel("Сводка за день:"))
        main_layout.addWidget(self.summary_view)
        main_layout.addWidget(QLabel("Распределение по приложениям:"))
        main_layout.addWidget(self.apps_table)

        self.setLayout(main_layout)

    def _set_default_date(self):
        today = QDate.currentDate()
        self.date_edit.setDate(today)

    # ---------- публичный метод для главного окна ----------

    def refresh_for_today(self):
        """Установить сегодняшнюю дату и обновить статистику."""
        self._set_default_date()
        self._refresh_stats()

    # ---------- внутренняя логика ----------

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _refresh_stats(self):
        # локальная дата из виджета
        qdate: QDate = self.date_edit.date()
        date_py = qdate.toPyDate()

        # границы дня в локальном времени
        start_local = datetime.combine(date_py, dt_time.min)
        end_local = datetime.combine(date_py, dt_time.max)

        # оценка смещения локального времени к UTC
        offset = datetime.now() - datetime.utcnow()

        start_utc = start_local - offset
        end_utc = end_local - offset

        # агрегированная статистика за выбранный день
        stats = get_time_stats(
            db_path=self.config.db_path,
            start_utc=start_utc,
            end_utc=end_utc,
            sample_interval_seconds=self.config.poll_interval_seconds,
        )

        self._fill_summary(stats, date_py)
        self._fill_apps_table(stats)

    def _fill_summary(self, stats, date_py):
        if stats.total_seconds == 0:
            self.summary_view.setPlainText(
                f"За {date_py.strftime('%d.%m.%Y')} нет данных в базе."
            )
            return

        lines = []

        lines.append(f"Дата: {date_py.strftime('%d.%m.%Y')}")
        lines.append("")
        lines.append(
            f"Всего времени под наблюдением: {self._format_duration(stats.total_seconds)}"
        )
        lines.append(
            f"Активное время (есть ввод):     {self._format_duration(stats.active_seconds)}"
        )
        lines.append(
            f"Рабочее активное время:         {self._format_duration(stats.work_active_seconds)}"
        )
        lines.append(
            f"Отвлекающее активное время:     {self._format_duration(stats.distract_active_seconds)}"
        )
        lines.append(
            f"Прочее активное время:          {self._format_duration(stats.other_active_seconds)}"
        )
        lines.append(
            f"Время бездействия:              {self._format_duration(stats.idle_seconds)}"
        )
        lines.append("")

        if stats.total_seconds > 0:
            def pct(x: float) -> str:
                return f"{(x / stats.total_seconds * 100):5.1f}%"

            lines.append("Доля от общего времени:")
            lines.append(f"- активное:            {pct(stats.active_seconds)}")
            lines.append(f"- рабочее активное:    {pct(stats.work_active_seconds)}")
            lines.append(f"- отвлекающее активное:{pct(stats.distract_active_seconds)}")
            lines.append(f"- бездействие:         {pct(stats.idle_seconds)}")

        self.summary_view.setPlainText("\n".join(lines))

    def _fill_apps_table(self, stats):
        apps = stats.by_app
        self.apps_table.setRowCount(len(apps))

        for row, app in enumerate(apps):
            app_name = app["app_name"] or "<без имени>"
            active_sec = app["active_seconds"]
            work_sec = app["work_active_seconds"]
            distract_sec = app["distract_active_seconds"]

            # определяем тип приложения по активному времени
            if work_sec > 0 and distract_sec == 0:
                app_type = "Рабочее"
            elif distract_sec > 0 and work_sec == 0:
                app_type = "Отвлекающее"
            elif work_sec == 0 and distract_sec == 0:
                app_type = "Прочее"
            else:
                app_type = "Смешанное"

            self.apps_table.setItem(row, 0, QTableWidgetItem(app_name))
            self.apps_table.setItem(row, 1, QTableWidgetItem(app_type))
            self.apps_table.setItem(
                row, 2, QTableWidgetItem(self._format_duration(active_sec))
            )
            self.apps_table.setItem(
                row, 3, QTableWidgetItem(self._format_duration(work_sec))
            )
            self.apps_table.setItem(
                row, 4, QTableWidgetItem(self._format_duration(distract_sec))
            )

        self.apps_table.resizeRowsToContents()
