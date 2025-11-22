# main_gui.py

import sys
from datetime import datetime, time as dt_time

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QGroupBox,
    QFormLayout,
    QMessageBox,
    QCheckBox,
)

from config import load_config, save_config, Config
from focus_worker import FocusWorker
from storage.db import get_time_stats


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("FocusMeter v2 — трекинг фокуса")
        self.resize(900, 700)

        self.config: Config = load_config()
        self.worker: FocusWorker | None = None

        self._init_ui()
        self._load_config_to_ui()

    # ---------- UI ----------

    def _init_ui(self):
        # Статус
        self.status_label = QLabel("Трекер остановлен.")
        self.status_label.setAlignment(Qt.AlignLeft)

        # Настройки числовые
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 60)

        self.idle_threshold_spin = QSpinBox()
        self.idle_threshold_spin.setRange(5, 600)

        self.idle_warning_spin = QSpinBox()
        self.idle_warning_spin.setRange(0, 240)   # можно 0 минут

        self.break_warning_spin = QSpinBox()
        self.break_warning_spin.setRange(1, 480)  # минимум 1 минута

        self.notify_idle_check = QCheckBox("Уведомлять о бездействии")
        self.notify_break_check = QCheckBox("Уведомлять о необходимости перерыва")

        # Списки приложений
        self.work_apps_edit = QPlainTextEdit()
        self.work_apps_edit.setPlaceholderText("Одно имя процесса на строку (например, pycharm64.exe)")

        self.distract_apps_edit = QPlainTextEdit()
        self.distract_apps_edit.setPlaceholderText("Одно имя процесса на строку (например, chrome.exe)")

        # Лог
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)

        # Статистика
        self.stats_view = QPlainTextEdit()
        self.stats_view.setReadOnly(True)
        self.stats_refresh_button = QPushButton("Обновить статистику за сегодня")
        self.stats_refresh_button.clicked.connect(self.on_refresh_stats_today)

        # Кнопки
        self.save_button = QPushButton("Сохранить настройки")
        self.start_button = QPushButton("Запустить трекинг")
        self.stop_button = QPushButton("Остановить")
        self.stop_button.setEnabled(False)

        self.save_button.clicked.connect(self.on_save_clicked)
        self.start_button.clicked.connect(self.on_start_clicked)
        self.stop_button.clicked.connect(self.on_stop_clicked)

        # Группа "Настройки"
        settings_group = QGroupBox("Настройки")
        form = QFormLayout()
        form.addRow("Интервал опроса (сек):", self.poll_interval_spin)
        form.addRow("Порог бездействия (сек):", self.idle_threshold_spin)
        form.addRow("Напоминать о бездействии (мин):", self.idle_warning_spin)
        form.addRow("Напоминать о перерыве (мин):", self.break_warning_spin)
        form.addRow(self.notify_idle_check)
        form.addRow(self.notify_break_check)
        form.addRow("Рабочие приложения:", self.work_apps_edit)
        form.addRow("Отвлекающие приложения:", self.distract_apps_edit)
        settings_group.setLayout(form)

        # Группа "Статистика"
        stats_group = QGroupBox("Статистика (сегодня)")
        stats_layout = QVBoxLayout()
        stats_layout.addWidget(self.stats_refresh_button)
        stats_layout.addWidget(self.stats_view)
        stats_group.setLayout(stats_layout)

        # Группа "Лог"
        log_group = QGroupBox("Лог")
        log_layout = QVBoxLayout()
        log_layout.addWidget(self.log_edit)
        log_group.setLayout(log_layout)

        # Панель кнопок
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.save_button)
        btn_layout.addStretch()
        btn_layout.addWidget(self.start_button)
        btn_layout.addWidget(self.stop_button)

        # Общий layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(settings_group)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(stats_group)
        main_layout.addWidget(log_group)

        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

    # ---------- работа с конфигом ----------

    def _load_config_to_ui(self):
        cfg = self.config
        self.poll_interval_spin.setValue(cfg.poll_interval_seconds)
        self.idle_threshold_spin.setValue(cfg.idle_threshold_seconds)
        self.idle_warning_spin.setValue(cfg.idle_warning_minutes)
        self.break_warning_spin.setValue(cfg.break_warning_minutes)
        self.notify_idle_check.setChecked(cfg.notify_on_idle)
        self.notify_break_check.setChecked(cfg.notify_on_break)
        self.work_apps_edit.setPlainText("\n".join(cfg.work_apps))
        self.distract_apps_edit.setPlainText("\n".join(cfg.distracting_apps))

    @staticmethod
    def _text_to_list(text: str) -> list[str]:
        lines: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if line:
                lines.append(line)
        return lines

    def _save_ui_to_config(self):
        cfg = self.config
        cfg.poll_interval_seconds = self.poll_interval_spin.value()
        cfg.idle_threshold_seconds = self.idle_threshold_spin.value()
        cfg.idle_warning_minutes = self.idle_warning_spin.value()
        cfg.break_warning_minutes = self.break_warning_spin.value()
        cfg.notify_on_idle = self.notify_idle_check.isChecked()
        cfg.notify_on_break = self.notify_break_check.isChecked()
        cfg.work_apps = self._text_to_list(self.work_apps_edit.toPlainText())
        cfg.distracting_apps = self._text_to_list(self.distract_apps_edit.toPlainText())
        save_config(cfg)

    # ---------- кнопки ----------

    def on_save_clicked(self):
        self._save_ui_to_config()
        QMessageBox.information(self, "Сохранено", "Настройки сохранены в config.json.")
        self.append_log("Настройки сохранены.")

    def on_start_clicked(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(self, "Уже запущен", "Трекер уже работает.")
            return

        # Перед запуском ещё раз сохранить текущие значения в конфиг
        self._save_ui_to_config()

        self.append_log("Запуск трекинга...")
        self.worker = FocusWorker(self.config)
        self.worker.status_updated.connect(self.on_worker_status)
        self.worker.started_tracking.connect(self.on_worker_started)
        self.worker.stopped_tracking.connect(self.on_worker_stopped)
        self.worker.start()

    def on_stop_clicked(self):
        if self.worker and self.worker.isRunning():
            self.append_log("Остановка трекинга...")
            self.worker.stop()
            self.worker.wait()
        else:
            self.append_log("Трекер уже остановлен.")

    # ---------- сигналы от потока ----------

    def on_worker_status(self, text: str):
        self.append_log(text)

    def on_worker_started(self):
        self.status_label.setText("Трекер ЗАПУЩЕН.")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def on_worker_stopped(self):
        self.status_label.setText("Трекер остановлен.")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    # ---------- статистика ----------

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def on_refresh_stats_today(self):
        try:
            text = self._get_today_stats_text()
            self.stats_view.setPlainText(text)
            self.append_log("Статистика за сегодня обновлена.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось обновить статистику: {e}")

    def _get_today_stats_text(self) -> str:
        """
        Статистика за текущий день по локальному времени.
        В БД время хранится в UTC, поэтому переводим границы дня в UTC.
        """
        # локальное сейчас
        now_local = datetime.now()
        # границы дня в локальном
        start_local = datetime.combine(now_local.date(), dt_time.min)
        end_local = datetime.combine(now_local.date(), dt_time.max)

        # оценка смещения локального времени относительно UTC
        offset = datetime.now() - datetime.utcnow()

        # переводим границы дня в "UTC-наивное"
        start_utc = start_local - offset
        end_utc = end_local - offset

        stats = get_time_stats(
            db_path=self.config.db_path,
            start_utc=start_utc,
            end_utc=end_utc,
            sample_interval_seconds=self.config.poll_interval_seconds,
        )

        if stats.total_seconds == 0:
            return "За сегодня пока нет данных."

        lines: list[str] = []

        lines.append(
            f"Период (UTC): {stats.period_start.isoformat()} — {stats.period_end.isoformat()}"
        )
        lines.append("")
        lines.append(f"Всего времени под наблюдением: {self._format_duration(stats.total_seconds)}")
        lines.append(f"Активное время (есть ввод):     {self._format_duration(stats.active_seconds)}")
        lines.append(
            f"Активное время в рабочих приложениях:     {self._format_duration(stats.work_active_seconds)}"
        )
        lines.append(
            f"Активное время в отвлекающих приложениях: {self._format_duration(stats.distract_active_seconds)}"
        )
        lines.append(
            f"Активное время в прочих приложениях:      {self._format_duration(stats.other_active_seconds)}"
        )
        lines.append(f"Время бездействия:                        {self._format_duration(stats.idle_seconds)}")
        lines.append("")

        # Доли
        if stats.total_seconds > 0:
            def pct(x: float) -> str:
                return f"{(x / stats.total_seconds * 100):5.1f}%"

            lines.append("Доля от общего времени:")
            lines.append(f"- Активное:            {pct(stats.active_seconds)}")
            lines.append(f"- Рабочее активное:    {pct(stats.work_active_seconds)}")
            lines.append(f"- Отвлекающее активное:{pct(stats.distract_active_seconds)}")
            lines.append(f"- Бездействие:         {pct(stats.idle_seconds)}")
            lines.append("")

        # Топ приложений
        lines.append("Топ приложений по активному времени:")
        for i, app in enumerate(stats.by_app[:5], start=1):
            app_name = app["app_name"] or "<без имени>"
            dur = self._format_duration(app["active_seconds"])
            lines.append(f"{i}. {app_name} — {dur}")

        return "\n".join(lines)

    # ---------- вспомогательное ----------

    def append_log(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_edit.appendPlainText(f"[{ts}] {text}")

    def closeEvent(self, event):
        # аккуратно останавливаем трекер при закрытии окна
        if self.worker and self.worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Выход",
                "Трекер сейчас работает. Остановить и выйти?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
            self.worker.stop()
            self.worker.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
