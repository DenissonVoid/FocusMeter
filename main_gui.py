# main_gui.py

from __future__ import annotations

import sys
from datetime import datetime

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
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
    QComboBox,
    QStyleFactory,
)

from config import load_config, save_config, Config
from focus_worker import FocusWorker
from stats_window import StatsWindow


# --------- QSS стили для светлой и тёмной тем ---------

LIGHT_STYLE_SHEET = """
QWidget {
    font-family: "Segoe UI", "Roboto", "Arial";
    font-size: 10pt;
}

/* Главное окно */
QMainWindow {
    background-color: #f5f5f7;
}

/* Группы */
QGroupBox {
    border: 1px solid #d0d0d0;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: transparent;
    font-weight: 600;
}

/* Кнопки */
QPushButton {
    border-radius: 6px;
    padding: 6px 12px;
    border: 1px solid #c0c0c0;
    background-color: #ffffff;
}
QPushButton:hover {
    background-color: #e8f0ff;
    border-color: #5b8def;
}
QPushButton:pressed {
    background-color: #d0e0ff;
}
QPushButton:disabled {
    background-color: #eeeeee;
    color: #999999;
    border-color: #dddddd;
}

/* Поля ввода, спинбоксы, комбобоксы, текстовые поля */
QLineEdit,
QPlainTextEdit,
QTextEdit,
QSpinBox,
QComboBox {
    border-radius: 4px;
    padding: 4px;
    border: 1px solid #c8c8c8;
    background-color: #ffffff;
}
QLineEdit:focus,
QPlainTextEdit:focus,
QTextEdit:focus,
QSpinBox:focus,
QComboBox:focus {
    border-color: #5b8def;
    outline: none;
}

/* Чекбоксы */
QCheckBox {
    spacing: 6px;
}

/* Скроллбары */
QScrollBar:vertical {
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #c0c0c0;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background-color: #a0a0a0;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

DARK_STYLE_SHEET = """
QWidget {
    font-family: "Segoe UI", "Roboto", "Arial";
    font-size: 10pt;
}

/* Главное окно */
QMainWindow {
    background-color: #353535;
}

/* Группы */
QGroupBox {
    border: 1px solid #555555;
    border-radius: 8px;
    margin-top: 16px;
    padding-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: transparent;
    font-weight: 600;
}

/* Кнопки */
QPushButton {
    border-radius: 6px;
    padding: 6px 12px;
    border: 1px solid #555555;
    background-color: #444444;
    color: #ffffff;
}
QPushButton:hover {
    background-color: #505a6b;
    border-color: #7aa2ff;
}
QPushButton:pressed {
    background-color: #3c4454;
}
QPushButton:disabled {
    background-color: #3a3a3a;
    color: #777777;
    border-color: #444444;
}

/* Поля ввода, спинбоксы, комбобоксы, текстовые поля */
QLineEdit,
QPlainTextEdit,
QTextEdit,
QSpinBox,
QComboBox {
    border-radius: 4px;
    padding: 4px;
    border: 1px solid #555555;
    background-color: #3b3b3b;
    color: #ffffff;
}
QLineEdit:focus,
QPlainTextEdit:focus,
QTextEdit:focus,
QSpinBox:focus,
QComboBox:focus {
    border-color: #7aa2ff;
    outline: none;
}

/* Чекбоксы */
QCheckBox {
    spacing: 6px;
}

/* Скроллбары */
QScrollBar:vertical {
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #555555;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background-color: #777777;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("FocusMeter")
        self.resize(1100, 850)

        self.config: Config = load_config()
        self.worker: FocusWorker | None = None
        self.stats_window: StatsWindow | None = None

        self._init_presets()
        self._init_ui()
        self._load_config_to_ui()

    # ---------- пресеты работы/отдыха ----------

    def _init_presets(self):
        self.preset_descriptions: dict[int, str] = {
            0: (
                "Пользовательский режим. Настройте интервалы работы и отдыха вручную ниже. "
                "Параметры сохраняются в config.json."
            ),
            1: (
                "Помодоро 25/5: 25 минут сфокусированной работы, затем 5 минут короткого перерыва. "
                "Напоминание о перерыве ориентируется на ~25 минут реальной работы в рабочих приложениях."
            ),
            2: (
                "Методика 52/17: 52 минуты глубокой работы, затем 17 минут отдыха. "
                "Подходит для задач, требующих высокой концентрации."
            ),
            3: (
                "Профиль 50/10: 50 минут работы, затем 10 минут перерыва. "
                "Универсальный вариант для учебной и офисной деятельности."
            ),
        }

        self.preset_configs: dict[int, dict] = {
            1: {
                "poll_interval_seconds": 1,
                "idle_threshold_seconds": 10,
                "idle_warning_minutes": 10,
                "break_warning_minutes": 25,
            },
            2: {
                "poll_interval_seconds": 1,
                "idle_threshold_seconds": 10,
                "idle_warning_minutes": 10,
                "break_warning_minutes": 52,
            },
            3: {
                "poll_interval_seconds": 1,
                "idle_threshold_seconds": 10,
                "idle_warning_minutes": 10,
                "break_warning_minutes": 50,
            },
        }

    # ---------- UI ----------

    def _init_ui(self):
        # Статус
        self.status_label = QLabel("Трекер остановлен.")
        self.status_label.setAlignment(Qt.AlignLeft)

        # Тема интерфейса (выше пресета)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Тёмная (Fusion)", "dark")
        self.theme_combo.addItem("Светлая (Fusion)", "light")
        self.theme_combo.addItem("Системная", "system")
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)

        # Пресеты работы/отдыха
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Пользовательский")
        self.preset_combo.addItem("Помодоро 25/5")
        self.preset_combo.addItem("52/17")
        self.preset_combo.addItem("50/10")
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)

        self.preset_desc_label = QLabel()
        self.preset_desc_label.setWordWrap(True)

        # Настройки числовые
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 60)

        self.idle_threshold_spin = QSpinBox()
        self.idle_threshold_spin.setRange(5, 600)

        self.idle_warning_spin = QSpinBox()
        self.idle_warning_spin.setRange(0, 240)

        self.break_warning_spin = QSpinBox()
        self.break_warning_spin.setRange(1, 480)

        self.notify_idle_check = QCheckBox("Уведомлять о бездействии/отвлечении")
        self.notify_break_check = QCheckBox("Уведомлять о необходимости перерыва")

        # Списки приложений
        self.work_apps_edit = QPlainTextEdit()
        self.work_apps_edit.setPlaceholderText(
            "Одно имя процесса на строку (например, pycharm64.exe)"
        )
        self.work_apps_edit.setMinimumHeight(80)

        self.distract_apps_edit = QPlainTextEdit()
        self.distract_apps_edit.setPlaceholderText(
            "Одно имя процесса на строку (например, chrome.exe)"
        )
        self.distract_apps_edit.setMinimumHeight(80)

        # Лог
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setObjectName("log_edit")
        self.log_edit.setMinimumHeight(250)

        # Кнопка подробной статистики
        self.stats_details_button = QPushButton("Открыть подробную статистику…")
        self.stats_details_button.clicked.connect(self.on_open_detailed_stats)

        # Кнопки управления
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
        form.addRow("Тема интерфейса:", self.theme_combo)
        form.addRow("Профиль (пресет):", self.preset_combo)
        form.addRow("Интервал опроса (сек):", self.poll_interval_spin)
        form.addRow("Порог бездействия (сек):", self.idle_threshold_spin)
        form.addRow("Напоминать о бездействии (мин):", self.idle_warning_spin)
        form.addRow("Напоминать о перерыве (мин):", self.break_warning_spin)
        form.addRow(self.notify_idle_check)
        form.addRow(self.notify_break_check)
        form.addRow("Рабочие приложения:", self.work_apps_edit)
        form.addRow("Отвлекающие приложения:", self.distract_apps_edit)

        settings_layout = QVBoxLayout()
        settings_layout.addLayout(form)
        # Описание пресета отдельным блоком на всю ширину
        settings_layout.addWidget(self.preset_desc_label)
        settings_group.setLayout(settings_layout)

        # Группа "Статистика"
        stats_group = QGroupBox("Статистика")
        stats_layout = QVBoxLayout()
        stats_layout.addWidget(self.stats_details_button)
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

        # Нижний блок: статистика слева, лог справа (лог шире)
        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(stats_group, 1)
        bottom_layout.addWidget(log_group, 3)

        # Общий layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(settings_group)
        main_layout.addLayout(btn_layout)
        main_layout.addLayout(bottom_layout, 2)

        central = QWidget()
        central.setLayout(main_layout)
        self.setCentralWidget(central)

    # ---------- работа с конфигом ----------

    def _detect_preset_index(self, cfg: Config) -> int:
        """Пытаемся сопоставить текущие настройки одному из пресетов."""
        for idx, preset in self.preset_configs.items():
            if (
                cfg.poll_interval_seconds == preset["poll_interval_seconds"]
                and cfg.idle_threshold_seconds == preset["idle_threshold_seconds"]
                and cfg.idle_warning_minutes == preset["idle_warning_minutes"]
                and cfg.break_warning_minutes == preset["break_warning_minutes"]
            ):
                return idx
        return 0  # пользовательский

    def _load_config_to_ui(self):
        cfg = self.config

        # 1) Определяем пресет по текущим настройкам
        preset_index = self._detect_preset_index(cfg)

        # Если настройки не совпадают ни с одним пресетом –
        # принудительно применяем Помодоро 25/5 как новый стандарт.
        if preset_index == 0:
            pomodoro = self.preset_configs[1]
            cfg.poll_interval_seconds = pomodoro["poll_interval_seconds"]
            cfg.idle_threshold_seconds = pomodoro["idle_threshold_seconds"]
            cfg.idle_warning_minutes = pomodoro["idle_warning_minutes"]
            cfg.break_warning_minutes = pomodoro["break_warning_minutes"]
            save_config(cfg)
            preset_index = 1

        # теперь заполняем поля из cfg
        self.poll_interval_spin.setValue(cfg.poll_interval_seconds)
        self.idle_threshold_spin.setValue(cfg.idle_threshold_seconds)
        self.idle_warning_spin.setValue(cfg.idle_warning_minutes)
        self.break_warning_spin.setValue(cfg.break_warning_minutes)
        self.notify_idle_check.setChecked(cfg.notify_on_idle)
        self.notify_break_check.setChecked(cfg.notify_on_break)
        self.work_apps_edit.setPlainText("\n".join(cfg.work_apps))
        self.distract_apps_edit.setPlainText("\n".join(cfg.distracting_apps))

        # выставляем пресет в комбобоксе
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(preset_index)
        self.preset_combo.blockSignals(False)
        self._update_preset_description(preset_index)

        # тема
        theme_key = getattr(cfg, "theme", "dark")
        idx = self.theme_combo.findData(theme_key)
        if idx == -1:
            idx = 0
            theme_key = self.theme_combo.itemData(0)
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.blockSignals(False)
        self.apply_theme(theme_key)

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

    # ---------- пресеты: обработка выбора ----------

    def _update_preset_description(self, index: int):
        desc = self.preset_descriptions.get(index, "")
        self.preset_desc_label.setText(desc)

    def on_preset_changed(self, index: int):
        self._update_preset_description(index)

        if index == 0:
            # пользовательский режим – значения оставляем как есть
            return

        cfg = self.preset_configs.get(index)
        if not cfg:
            return

        self.poll_interval_spin.setValue(cfg["poll_interval_seconds"])
        self.idle_threshold_spin.setValue(cfg["idle_threshold_seconds"])
        self.idle_warning_spin.setValue(cfg["idle_warning_minutes"])
        self.break_warning_spin.setValue(cfg["break_warning_minutes"])

    # ---------- темы: обработка выбора ----------

    def apply_theme(self, theme_key: str):
        """Применить выбранную тему ко всему приложению."""
        app = QApplication.instance()
        if app is None:
            return

        theme_key = theme_key or "dark"
        app.setStyleSheet("")

        if theme_key == "system":
            app.setStyle(app.style().objectName())
            app.setPalette(app.style().standardPalette())
        elif theme_key == "light":
            app.setStyle(QStyleFactory.create("Fusion"))
            palette = app.style().standardPalette()
            app.setPalette(palette)
            app.setStyleSheet(LIGHT_STYLE_SHEET)
        elif theme_key == "dark":
            app.setStyle(QStyleFactory.create("Fusion"))
            dark_palette = QPalette()
            dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.WindowText, Qt.white)
            dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
            dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
            dark_palette.setColor(QPalette.ToolTipText, Qt.white)
            dark_palette.setColor(QPalette.Text, Qt.white)
            dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
            dark_palette.setColor(QPalette.ButtonText, Qt.white)
            dark_palette.setColor(QPalette.BrightText, Qt.red)
            dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            dark_palette.setColor(QPalette.HighlightedText, Qt.black)
            app.setPalette(dark_palette)
            app.setStyleSheet(DARK_STYLE_SHEET)
        else:
            app.setStyle(QStyleFactory.create("Fusion"))
            app.setPalette(app.style().standardPalette())
            app.setStyleSheet(DARK_STYLE_SHEET)

    def on_theme_changed(self, index: int):
        key = self.theme_combo.itemData(index)
        if not key:
            return
        self.apply_theme(key)
        self.config.theme = key
        save_config(self.config)
        self.append_log(f"Тема интерфейса изменена: {key}")

    # ---------- кнопки ----------

    def on_save_clicked(self):
        self._save_ui_to_config()
        QMessageBox.information(self, "Сохранено", "Настройки сохранены в config.json.")
        self.append_log("Настройки сохранены.")

    def on_start_clicked(self):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(self, "Уже запущен", "Трекер уже работает.")
            return

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
        self.show_today_stats()

    # ---------- подробная статистика ----------

    def on_open_detailed_stats(self):
        self.show_today_stats()

    def show_today_stats(self):
        if self.stats_window is None:
            self.stats_window = StatsWindow(self.config, self)
        else:
            self.stats_window.refresh_for_today()
        self.stats_window.show()
        self.stats_window.raise_()
        self.stats_window.activateWindow()

    # ---------- вспомогательное ----------

    def append_log(self, text: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_edit.appendPlainText(f"[{ts}] {text}")

    def closeEvent(self, event):
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
