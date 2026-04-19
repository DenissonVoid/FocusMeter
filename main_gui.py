from __future__ import annotations

import sys
from datetime import datetime, time as dt_time, timedelta
from typing import cast

from PyQt5.QtCore import QFileInfo, Qt, QTimer
from PyQt5.QtGui import QColor, QIcon, QPalette
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileIconProvider,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyleFactory,
    QVBoxLayout,
    QWidget,
)

from app_rules import (
    AppHistoryEntry,
    AppRulesRepository,
    RULE_DISTRACTING,
    RULE_EXCLUDED,
    RULE_LABELS,
    RULE_NONE,
    RULE_WORK,
)
from config import Config, load_config, save_config
from focus_widget import FocusWidget, format_duration
from focus_worker import FocusWorker, WorkerSnapshot
from stats_window import StatsWindow
from storage.db import get_time_stats
from tracker.active_window import WindowInfo, list_open_windows
from window_chrome import build_window_shell, prepare_frameless_window
from window_chrome import schedule_window_layout_sync


LIGHT_STYLE_SHEET = """
QWidget {
    font-family: "Segoe UI";
    color: #1F1F21;
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: transparent;
}
QFrame#WindowSurface {
    background: rgba(245, 245, 247, 250);
    border: 1px solid rgba(255, 255, 255, 160);
    border-radius: 24px;
}
QFrame#WindowTitleBar {
    background: rgba(255, 255, 255, 210);
    border: none;
    border-top-left-radius: 24px;
    border-top-right-radius: 24px;
    border-bottom: 1px solid rgba(32, 32, 34, 24);
}
QWidget#WindowBody {
    background: transparent;
}
QLabel#WindowTitle {
    font-size: 11pt;
    font-weight: 700;
    color: #151517;
}
QLabel#WindowSubtitle {
    color: rgba(38, 38, 40, 160);
    font-size: 8.8pt;
}
QPushButton#ChromeButton, QPushButton#ChromeCloseButton {
    background: transparent;
    border: none;
    min-width: 30px;
    max-width: 30px;
    min-height: 28px;
    max-height: 28px;
    border-radius: 14px;
    font-size: 12pt;
}
QPushButton#ChromeButton:hover {
    background: rgba(15, 15, 18, 20);
}
QPushButton#ChromeCloseButton:hover {
    background: rgba(20, 20, 22, 32);
}
QFrame#HeroCard, QFrame#KpiCard, QFrame#WidgetPanel, QFrame#StatsPanel, QFrame#RulesPanel, QFrame#SettingsPanel, QFrame#ActivityPanel {
    background: rgba(255, 255, 255, 236);
    border: 1px solid rgba(32, 32, 34, 26);
    border-radius: 20px;
}
QLabel#HeroEyebrow, QLabel#SectionEyebrow {
    color: rgba(44, 44, 46, 138);
    font-size: 8.8pt;
    font-weight: 600;
    letter-spacing: 0.04em;
}
QLabel#HeroTitle {
    font-size: 14pt;
    font-weight: 700;
    color: #141416;
}
QLabel#HeroTimer {
    font-size: 20pt;
    font-weight: 700;
    color: #141416;
}
QLabel#SecondaryText, QLabel#MutedLabel {
    color: rgba(40, 40, 43, 150);
}
QLabel#StatusChip {
    background: rgba(23, 23, 25, 24);
    color: #1B1B1D;
    border-radius: 999px;
    padding: 6px 12px;
    font-weight: 700;
}
QLabel#PillLabel {
    background: rgba(255, 255, 255, 92);
    border: 1px solid rgba(32, 32, 34, 20);
    border-radius: 12px;
    padding: 7px 10px;
}
QLabel#KpiTitle {
    color: rgba(40, 40, 43, 140);
    font-size: 8.8pt;
    font-weight: 600;
}
QLabel#KpiValue {
    font-size: 16pt;
    font-weight: 700;
}
QLabel#WarningStrip {
    background: rgba(28, 28, 30, 16);
    border: 1px solid rgba(32, 32, 34, 22);
    border-radius: 12px;
    padding: 9px 10px;
    color: #1F1F21;
}
QPushButton {
    background: rgba(255, 255, 255, 112);
    border: 1px solid rgba(32, 32, 34, 24);
    border-radius: 12px;
    padding: 7px 12px;
    min-height: 32px;
    font-weight: 600;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 168);
}
QPushButton#PrimaryButton {
    background: rgba(21, 21, 23, 220);
    color: white;
    border: 1px solid rgba(21, 21, 23, 230);
}
QPushButton#PrimaryButton:hover {
    background: rgba(9, 9, 11, 230);
}
QPushButton#GhostButton, QPushButton#TinyButton {
    background: rgba(255, 255, 255, 88);
}
QPushButton#GhostButton:hover, QPushButton#TinyButton:hover {
    background: rgba(255, 255, 255, 164);
    border-color: rgba(32, 32, 34, 36);
}
QPushButton#TinyButton {
    padding: 5px 10px;
    min-width: 36px;
}
QPushButton#DangerButton {
    background: rgba(30, 30, 33, 42);
    color: #171719;
}
QPushButton#DangerButton:hover {
    background: rgba(30, 30, 33, 68);
    border-color: rgba(32, 32, 34, 34);
}
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox, QTableWidget {
    background: rgba(255, 255, 255, 224);
    border: 1px solid rgba(32, 32, 34, 24);
    border-radius: 14px;
}
QLineEdit, QSpinBox, QComboBox {
    padding: 5px 8px;
    min-height: 32px;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: rgba(22, 22, 24, 90);
}
QComboBox QAbstractItemView {
    background: rgba(249, 249, 250, 248);
    border: 1px solid rgba(32, 32, 34, 32);
    border-radius: 12px;
    padding: 4px;
    selection-background-color: rgba(28, 28, 30, 22);
    selection-color: #141416;
}
QFrame#SegmentBar {
    background: rgba(255, 255, 255, 196);
    border: 1px solid rgba(32, 32, 34, 20);
    border-radius: 18px;
}
QPushButton#SegmentButton {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 8px 16px;
    min-height: 36px;
    min-width: 140px;
    color: rgba(40, 40, 43, 156);
    font-weight: 700;
}
QPushButton#SegmentButton:checked {
    background: rgba(18, 18, 20, 22);
    color: #141416;
}
QPushButton#SegmentButton:hover:!checked {
    background: rgba(18, 18, 20, 10);
}
QStackedWidget#SectionStack {
    background: transparent;
}
QTableWidget {
    gridline-color: rgba(32, 32, 34, 18);
    alternate-background-color: rgba(255, 255, 255, 76);
}
QListWidget {
    background: rgba(255, 255, 255, 214);
    border: 1px solid rgba(32, 32, 34, 24);
    border-radius: 14px;
    padding: 6px;
}
QListWidget::item {
    border-radius: 12px;
    padding: 8px 8px;
    margin: 2px 0;
}
QListWidget::item:selected {
    background: rgba(21, 21, 23, 18);
    color: #141416;
}
QHeaderView::section {
    background: transparent;
    border: none;
    border-bottom: 1px solid rgba(32, 32, 34, 18);
    padding: 8px 8px;
    color: rgba(40, 40, 43, 150);
    font-weight: 700;
}
QCheckBox {
    spacing: 8px;
}
QLabel#SelectionHint {
    color: rgba(40, 40, 43, 150);
}
QLabel#DetailLabel {
    color: rgba(40, 40, 43, 140);
    font-size: 8.8pt;
    font-weight: 600;
}
QLabel#DetailValue {
    color: #161618;
    font-weight: 600;
}
QScrollArea {
    border: none;
    background: transparent;
}
"""


DARK_STYLE_SHEET = """
QWidget {
    font-family: "Segoe UI";
    color: #F0F0F2;
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: transparent;
}
QFrame#WindowSurface {
    background: rgba(22, 22, 24, 248);
    border: 1px solid rgba(255, 255, 255, 28);
    border-radius: 24px;
}
QFrame#WindowTitleBar {
    background: rgba(36, 36, 39, 232);
    border: none;
    border-top-left-radius: 24px;
    border-top-right-radius: 24px;
    border-bottom: 1px solid rgba(255, 255, 255, 18);
}
QWidget#WindowBody {
    background: transparent;
}
QLabel#WindowTitle {
    font-size: 11pt;
    font-weight: 700;
    color: #F6F6F8;
}
QLabel#WindowSubtitle {
    color: rgba(240, 240, 242, 150);
    font-size: 8.8pt;
}
QPushButton#ChromeButton, QPushButton#ChromeCloseButton {
    background: transparent;
    border: none;
    min-width: 30px;
    max-width: 30px;
    min-height: 28px;
    max-height: 28px;
    border-radius: 14px;
    font-size: 12pt;
    color: #F4F4F6;
}
QPushButton#ChromeButton:hover {
    background: rgba(255, 255, 255, 14);
}
QPushButton#ChromeCloseButton:hover {
    background: rgba(255, 255, 255, 18);
}
QFrame#HeroCard, QFrame#KpiCard, QFrame#WidgetPanel, QFrame#StatsPanel, QFrame#RulesPanel, QFrame#SettingsPanel, QFrame#ActivityPanel {
    background: rgba(36, 36, 39, 236);
    border: 1px solid rgba(255, 255, 255, 18);
    border-radius: 20px;
}
QLabel#HeroEyebrow, QLabel#SectionEyebrow {
    color: rgba(240, 240, 242, 124);
    font-size: 8.8pt;
    font-weight: 600;
    letter-spacing: 0.04em;
}
QLabel#HeroTitle {
    font-size: 14pt;
    font-weight: 700;
    color: #FBFBFD;
}
QLabel#HeroTimer {
    font-size: 20pt;
    font-weight: 700;
    color: #FBFBFD;
}
QLabel#SecondaryText, QLabel#MutedLabel {
    color: rgba(240, 240, 242, 138);
}
QLabel#StatusChip {
    background: rgba(255, 255, 255, 10);
    color: #F8F8FA;
    border-radius: 999px;
    padding: 6px 12px;
    font-weight: 700;
}
QLabel#PillLabel {
    background: rgba(255, 255, 255, 6);
    border: 1px solid rgba(255, 255, 255, 12);
    border-radius: 12px;
    padding: 7px 10px;
}
QLabel#KpiTitle {
    color: rgba(240, 240, 242, 132);
    font-size: 8.8pt;
    font-weight: 600;
}
QLabel#KpiValue {
    font-size: 16pt;
    font-weight: 700;
}
QLabel#WarningStrip {
    background: rgba(255, 255, 255, 9);
    border: 1px solid rgba(255, 255, 255, 12);
    border-radius: 12px;
    padding: 9px 10px;
    color: #F4F4F6;
}
QPushButton {
    background: rgba(255, 255, 255, 7);
    border: 1px solid rgba(255, 255, 255, 12);
    border-radius: 12px;
    padding: 7px 12px;
    min-height: 32px;
    font-weight: 600;
}
QPushButton:hover {
    background: rgba(255, 255, 255, 12);
}
QPushButton#PrimaryButton {
    background: rgba(245, 245, 247, 230);
    color: #111113;
    border: 1px solid rgba(255, 255, 255, 110);
}
QPushButton#PrimaryButton:hover {
    background: rgba(255, 255, 247, 245);
}
QPushButton#GhostButton, QPushButton#TinyButton {
    background: rgba(255, 255, 255, 8);
}
QPushButton#GhostButton:hover, QPushButton#TinyButton:hover {
    background: rgba(255, 255, 255, 14);
    border-color: rgba(255, 255, 255, 22);
}
QPushButton#TinyButton {
    padding: 5px 10px;
    min-width: 36px;
}
QPushButton#DangerButton {
    background: rgba(255, 255, 255, 12);
    color: #FAFAFC;
}
QPushButton#DangerButton:hover {
    background: rgba(255, 255, 255, 18);
    border-color: rgba(255, 255, 255, 24);
}
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox, QTableWidget {
    background: rgba(255, 255, 255, 14);
    border: 1px solid rgba(255, 255, 255, 12);
    border-radius: 14px;
}
QLineEdit, QSpinBox, QComboBox {
    padding: 5px 8px;
    min-height: 32px;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: rgba(255, 255, 255, 42);
}
QComboBox QAbstractItemView {
    background: rgba(42, 42, 46, 248);
    border: 1px solid rgba(255, 255, 255, 16);
    border-radius: 12px;
    padding: 4px;
    selection-background-color: rgba(255, 255, 255, 14);
    selection-color: #FBFBFD;
}
QFrame#SegmentBar {
    background: rgba(255, 255, 255, 10);
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 18px;
}
QPushButton#SegmentButton {
    background: transparent;
    border: none;
    border-radius: 12px;
    padding: 8px 16px;
    min-height: 36px;
    min-width: 140px;
    color: rgba(240, 240, 242, 148);
    font-weight: 700;
}
QPushButton#SegmentButton:checked {
    background: rgba(255, 255, 255, 13);
    color: #FBFBFD;
}
QPushButton#SegmentButton:hover:!checked {
    background: rgba(255, 255, 255, 8);
}
QStackedWidget#SectionStack {
    background: transparent;
}
QTableWidget {
    gridline-color: rgba(255, 255, 255, 10);
    alternate-background-color: rgba(255, 255, 255, 4);
}
QListWidget {
    background: rgba(255, 255, 255, 12);
    border: 1px solid rgba(255, 255, 255, 12);
    border-radius: 14px;
    padding: 6px;
}
QListWidget::item {
    border-radius: 12px;
    padding: 8px 8px;
    margin: 2px 0;
}
QListWidget::item:selected {
    background: rgba(255, 255, 255, 10);
    color: #FBFBFD;
}
QHeaderView::section {
    background: transparent;
    border: none;
    border-bottom: 1px solid rgba(255, 255, 255, 10);
    padding: 8px 8px;
    color: rgba(240, 240, 242, 138);
    font-weight: 700;
}
QCheckBox {
    spacing: 8px;
}
QLabel#SelectionHint {
    color: rgba(240, 240, 242, 138);
}
QLabel#DetailLabel {
    color: rgba(240, 240, 242, 132);
    font-size: 8.8pt;
    font-weight: 600;
}
QLabel#DetailValue {
    color: #FBFBFD;
    font-weight: 600;
}
QScrollArea {
    border: none;
    background: transparent;
}
"""


class KpiCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("KpiCard")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(88)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(3)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("KpiTitle")
        self.title_label.setMinimumHeight(20)
        layout.addWidget(self.title_label)

        self.value_label = QLabel("00:00")
        self.value_label.setObjectName("KpiValue")
        self.value_label.setMinimumHeight(24)
        layout.addWidget(self.value_label)

        self.meta_label = QLabel("")
        self.meta_label.setObjectName("MutedLabel")
        self.meta_label.setWordWrap(True)
        self.meta_label.setMinimumHeight(20)
        self.meta_label.setMaximumHeight(22)
        layout.addWidget(self.meta_label)

    def set_content(self, value: str, meta: str) -> None:
        self.value_label.setText(value)
        self.meta_label.setText(meta)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("FocusMeter")
        self.resize(1370, 1100)
        self.setMinimumSize(1370, 1100)
        prepare_frameless_window(self)

        self.config: Config = load_config()
        self.rules_repo = AppRulesRepository(self.config)
        self.worker: FocusWorker | None = None
        self.stats_window: StatsWindow | None = None
        self.widget_window: FocusWidget | None = None
        self.notify_break_check = QCheckBox()

        self._icon_cache: dict[str, QIcon] = {}
        self._open_windows: list[WindowInfo] = []
        self._visible_app_rows: list[dict[str, object]] = []
        self._current_snapshot: WorkerSnapshot | None = None
        self._worker_paused = False
        self._screen_sync_connected = False
        self._initial_layout_stabilized = False

        self._init_presets()
        self._build_window()
        self._load_config_to_ui()
        self._refresh_app_catalog()
        self._refresh_today_overview()

        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop_worker_if_running)

        self.overview_timer = QTimer(self)
        self.overview_timer.timeout.connect(self._refresh_today_overview)
        self.overview_timer.start(30000)

    def _init_presets(self) -> None:
        self.preset_descriptions = {
            0: "Свободный режим: используйте собственные интервалы и уведомления.",
            1: "Помодоро 25/5: короткие рабочие блоки и частые паузы.",
            2: "52/17: длинный рабочий спринт и полноценное восстановление.",
            3: "50/10: спокойный ритм для офиса и учебы.",
        }
        self.preset_configs = {
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
        self.preset_descriptions[0] = (
            "Свободный режим: задайте отдельно момент для перерыва и момент, когда нужно напомнить вернуться к работе."
        )
        self.preset_descriptions[1] = (
            "Помодоро 25/5: напоминание о перерыве через 25 минут работы и напоминание вернуться через 5 минут отдыха или отвлечения."
        )
        self.preset_descriptions[2] = (
            "52/17: длинный рабочий спринт и более длинный интервал восстановления перед напоминанием вернуться."
        )
        self.preset_descriptions[3] = (
            "50/10: спокойный ритм с напоминанием о перерыве через 50 минут и о возврате через 10 минут отдыха."
        )
        self.preset_configs[1]["idle_warning_minutes"] = 5
        self.preset_configs[2]["idle_warning_minutes"] = 17
        self.legacy_preset_configs = {
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
        }

    def _build_window(self) -> None:
        host = QWidget(self)
        self.setCentralWidget(host)
        _, body_layout, self.title_bar, _size_grip = build_window_shell(
            host,
            title="FocusMeter",
            subtitle="Автоматический мониторинг фокус-фактора пользователя",
            show_minimize=True,
            body_margins=(16, 10, 16, 12),
            body_spacing=6,
        )

        self.hero_panel = self._build_hero_panel()
        self.hero_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.hero_panel.setFixedHeight(306)

        self.sections_host = self._build_sections()
        self.sections_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.sections_host.setMinimumHeight(560)

        body_layout.addWidget(self.hero_panel)
        body_layout.addWidget(self.sections_host, 1)

        self._set_worker_controls(is_running=False, paused=False)
        self._update_dashboard_idle_state()

    def _ensure_screen_sync(self) -> None:
        if self._screen_sync_connected:
            return
        handle = self.windowHandle()
        if handle is None:
            return
        handle.screenChanged.connect(self._on_screen_changed)
        self._screen_sync_connected = True

    def _on_screen_changed(self, *_args) -> None:
        schedule_window_layout_sync(self, 0)

    def _repolish_widget_tree(self, root: QWidget) -> None:
        widgets = [root, *root.findChildren(QWidget)]
        for widget in widgets:
            style = widget.style()
            if style is None:
                continue
            style.unpolish(widget)
            style.polish(widget)
            widget.updateGeometry()

    def _stabilize_initial_layout(self) -> None:
        if not self.isVisible():
            return
        self._repolish_widget_tree(self)
        button_heights = [
            self.mark_work_button.sizeHint().height(),
            self.mark_distract_button.sizeHint().height(),
            self.mark_exclude_button.sizeHint().height(),
            self.clear_rule_button.sizeHint().height(),
        ]
        row_height = max(button_heights, default=0)
        if row_height > 0:
            self.rule_actions_host.setMinimumHeight(row_height * 3 + 16)
            self.favorite_button.setMinimumHeight(
                max(self.favorite_button.minimumHeight(), self.favorite_button.sizeHint().height())
            )
            self.rules_detail_panel.setMinimumHeight(
                max(self.rules_detail_panel.minimumHeight(), 320 + row_height * 2)
            )
        central_widget = self.centralWidget()
        if central_widget is not None:
            central_widget.updateGeometry()
        self.sections_host.updateGeometry()
        self.hero_panel.updateGeometry()
        schedule_window_layout_sync(self, 0)

    def _build_hero_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("HeroCard")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(4)
        eyebrow = QLabel("СЕССИЯ")
        eyebrow.setObjectName("HeroEyebrow")
        left.addWidget(eyebrow)

        header_row = QHBoxLayout()
        self.status_chip = QLabel("Остановлено")
        self.status_chip.setObjectName("StatusChip")
        header_row.addWidget(self.status_chip)
        header_row.addStretch()
        left.addLayout(header_row)

        self.current_app_label = QLabel("Фокус ещё не запущен")
        self.current_app_label.setObjectName("HeroTitle")
        self.current_app_label.setWordWrap(True)
        self.current_app_label.setMinimumHeight(32)
        left.addWidget(self.current_app_label)

        self.context_label = QLabel(
            "Главный экран оставляет только текущее состояние, а вся настройка уходит во вкладки ниже."
        )
        self.context_label.setObjectName("SecondaryText")
        self.context_label.setWordWrap(True)
        self.context_label.setMinimumHeight(24)
        left.addWidget(self.context_label)
        top_row.addLayout(left, 3)

        right = QVBoxLayout()
        right.setSpacing(6)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("HeroTimer")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.timer_label.setMinimumHeight(42)
        right.addWidget(self.timer_label)

        self.timer_hint_label = QLabel("Фокус-таймер до следующего перерыва")
        self.timer_hint_label.setObjectName("SecondaryText")
        self.timer_hint_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.timer_hint_label.setMinimumHeight(24)
        right.addWidget(self.timer_hint_label)

        controls_band = QVBoxLayout()
        controls_band.setContentsMargins(0, 6, 0, 6)
        controls_band.setSpacing(0)
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.stats_button = QPushButton("Статистика")
        self.stats_button.setObjectName("GhostButton")
        self.stats_button.clicked.connect(self.on_open_detailed_stats)
        controls_row.addWidget(self.stats_button)

        self.widget_button = QPushButton("Виджет")
        self.widget_button.setObjectName("GhostButton")
        self.widget_button.clicked.connect(self._toggle_widget_visibility)
        controls_row.addWidget(self.widget_button)

        self.start_button = QPushButton("Старт")
        self.start_button.setObjectName("PrimaryButton")
        self.start_button.clicked.connect(self.on_start_clicked)
        controls_row.addWidget(self.start_button)

        self.pause_button = QPushButton("Пауза")
        self.pause_button.clicked.connect(self.on_pause_clicked)
        controls_row.addWidget(self.pause_button)

        self.stop_button = QPushButton("Стоп")
        self.stop_button.setObjectName("DangerButton")
        self.stop_button.clicked.connect(self.on_stop_clicked)
        controls_row.addWidget(self.stop_button)
        controls_band.addLayout(controls_row)
        right.addLayout(controls_band)

        top_row.addLayout(right, 2)
        layout.addLayout(top_row)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(8)

        self.today_active_card = KpiCard("Сегодня активно")
        self.today_work_card = KpiCard("Рабочее время")
        self.today_idle_card = KpiCard("Бездействие")

        summary_row.addWidget(self.today_active_card)
        summary_row.addWidget(self.today_work_card)
        summary_row.addWidget(self.today_idle_card)
        layout.addLayout(summary_row)

        pills_row = QHBoxLayout()
        pills_row.setSpacing(8)
        self.break_eta_label = QLabel("Перерыв: --")
        self.break_eta_label = QLabel("До перерыва: --")
        self.break_eta_label.setObjectName("PillLabel")
        pills_row.addWidget(self.break_eta_label)
        self.idle_eta_label = QLabel("До возврата: --")
        self.idle_eta_label.setObjectName("PillLabel")
        pills_row.addWidget(self.idle_eta_label)
        pills_row.addStretch()
        layout.addLayout(pills_row)
        return panel

    def _build_sections(self) -> QWidget:
        host = QWidget()
        host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        segment_bar = QFrame()
        segment_bar.setObjectName("SegmentBar")
        bar_layout = QHBoxLayout(segment_bar)
        bar_layout.setContentsMargins(6, 6, 6, 6)
        bar_layout.setSpacing(6)

        self.section_stack = QStackedWidget()
        self.section_stack.setObjectName("SectionStack")

        self.section_buttons: list[QPushButton] = []
        sections = [
            ("Правила", self._build_rules_tab()),
            ("Настройки", self._build_settings_tab()),
            ("Активность", self._build_activity_tab()),
        ]
        for index, (title, page) in enumerate(sections):
            button = QPushButton(title)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda checked=False, idx=index: self._set_section(idx)
            )
            self.section_buttons.append(button)
            bar_layout.addWidget(button)
            self.section_stack.addWidget(page)

        layout.addWidget(segment_bar)
        layout.addWidget(self.section_stack, 1)
        self._set_section(0)
        return host

    def _set_section(self, index: int) -> None:
        self.section_stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.section_buttons):
            button.setChecked(button_index == index)

    def _make_detail_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("DetailLabel")
        return label

    def _combo_current_data_str(self, combo: QComboBox) -> str:
        data = combo.currentData()
        return str(data) if data is not None else ""

    def _combo_item_data_str(self, combo: QComboBox, index: int) -> str:
        data = combo.itemData(index)
        return str(data) if data is not None else ""

    def _build_rules_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        panel = QFrame()
        panel.setObjectName("RulesPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(10)

        title = QLabel("Правила приложений")
        title.setObjectName("HeroTitle")
        panel_layout.addWidget(title)

        subtitle = QLabel(
            "Найдите приложение, выберите его слева и назначьте правило без таблицы и лишних колонок."
        )
        subtitle.setObjectName("SecondaryText")
        subtitle.setWordWrap(True)
        panel_layout.addWidget(subtitle)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.app_search_edit = QLineEdit()
        self.app_search_edit.setPlaceholderText("Поиск по процессу или заголовку окна")
        self.app_search_edit.textChanged.connect(self._populate_app_table)
        filters.addWidget(self.app_search_edit, 1)

        self.app_source_combo = QComboBox()
        self.app_source_combo.addItem("Открыты сейчас", "open")
        self.app_source_combo.addItem("Недавние", "recent")
        self.app_source_combo.addItem("Избранные", "favorites")
        self.app_source_combo.addItem("С правилами", "rules")
        self.app_source_combo.currentIndexChanged.connect(self._populate_app_table)
        filters.addWidget(self.app_source_combo)

        self.refresh_apps_button = QPushButton("Обновить")
        self.refresh_apps_button.setObjectName("GhostButton")
        self.refresh_apps_button.clicked.connect(self._refresh_app_catalog)
        filters.addWidget(self.refresh_apps_button)
        panel_layout.addLayout(filters)

        list_side = QFrame()
        list_side.setObjectName("StatsPanel")
        list_side.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        list_layout = QVBoxLayout(list_side)
        list_layout.setContentsMargins(12, 12, 12, 12)
        list_layout.setSpacing(8)
        list_side.setMinimumHeight(320)

        list_title = QLabel("Список приложений")
        list_title.setObjectName("SectionEyebrow")
        list_layout.addWidget(list_title)

        self.app_list = QListWidget()
        self.app_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.app_list.setMinimumHeight(0)
        self.app_list.currentItemChanged.connect(self._update_selection_hint)
        list_layout.addWidget(self.app_list, 1)

        detail_side = QFrame()
        detail_side.setObjectName("StatsPanel")
        detail_side.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.rules_detail_panel = detail_side
        detail_layout = QVBoxLayout(detail_side)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        detail_layout.setSpacing(10)
        detail_side.setMinimumHeight(320)

        detail_title = QLabel("Выбранное приложение")
        detail_title.setObjectName("SectionEyebrow")
        detail_layout.addWidget(detail_title)

        self.selected_process_label = QLabel("Ничего не выбрано")
        self.selected_process_label.setObjectName("HeroTitle")
        self.selected_process_label.setWordWrap(True)
        self.selected_process_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        detail_layout.addWidget(self.selected_process_label)

        self.selected_window_label = QLabel(
            "Выберите приложение слева, чтобы увидеть детали и назначить правило."
        )
        self.selected_window_label.setObjectName("SecondaryText")
        self.selected_window_label.setWordWrap(True)
        self.selected_window_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        detail_layout.addWidget(self.selected_window_label)

        details_grid = QGridLayout()
        details_grid.setHorizontalSpacing(16)
        details_grid.setVerticalSpacing(8)

        self.current_rule_label = QLabel("Без правила")
        self.current_rule_label.setObjectName("DetailValue")
        self.current_history_label = QLabel("—")
        self.current_history_label.setObjectName("DetailValue")
        self.current_favorite_label = QLabel("Нет")
        self.current_favorite_label.setObjectName("DetailValue")

        details_grid.addWidget(self._make_detail_label("Текущее правило"), 0, 0)
        details_grid.addWidget(self.current_rule_label, 0, 1)
        details_grid.addWidget(self._make_detail_label("История"), 1, 0)
        details_grid.addWidget(self.current_history_label, 1, 1)
        details_grid.addWidget(self._make_detail_label("Избранное"), 2, 0)
        details_grid.addWidget(self.current_favorite_label, 2, 1)
        detail_layout.addLayout(details_grid)

        self.rule_actions_host = QWidget()
        self.rule_actions_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        actions = QGridLayout(self.rule_actions_host)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setHorizontalSpacing(8)
        actions.setVerticalSpacing(8)

        self.mark_work_button = QPushButton("Рабочее")
        self.mark_work_button.clicked.connect(
            lambda: self._set_rule_for_selected(RULE_WORK)
        )
        actions.addWidget(self.mark_work_button, 0, 0)

        self.mark_distract_button = QPushButton("Отвлекающее")
        self.mark_distract_button.clicked.connect(
            lambda: self._set_rule_for_selected(RULE_DISTRACTING)
        )
        actions.addWidget(self.mark_distract_button, 0, 1)

        self.mark_exclude_button = QPushButton("Исключить")
        self.mark_exclude_button.clicked.connect(
            lambda: self._set_rule_for_selected(RULE_EXCLUDED)
        )
        actions.addWidget(self.mark_exclude_button, 1, 0)

        self.clear_rule_button = QPushButton("Снять правило")
        self.clear_rule_button.setObjectName("GhostButton")
        self.clear_rule_button.clicked.connect(
            lambda: self._set_rule_for_selected(RULE_NONE)
        )
        actions.addWidget(self.clear_rule_button, 1, 1)
        detail_layout.addWidget(self.rule_actions_host)

        self.favorite_button = QPushButton("Добавить в избранное")
        self.favorite_button.setObjectName("GhostButton")
        self.favorite_button.clicked.connect(self._toggle_favorite_for_selected)
        actions.addWidget(self.favorite_button, 2, 0, 1, 2)

        detail_layout.addStretch(1)

        _notify_idle_label_text = (
            "Напоминать вернуться к работе после отдыха или отвлечения"
        )
        self.notify_break_check.setText("Напоминать сделать перерыв")

        content_row = QHBoxLayout()
        content_row.setSpacing(10)
        content_row.addWidget(list_side, 5)
        content_row.addWidget(detail_side, 4)
        panel_layout.addLayout(content_row, 1)

        self.selection_hint_label = QLabel(
            "Выберите приложение, чтобы назначить правило."
        )
        self.selection_hint_label.setObjectName("SelectionHint")
        self.selection_hint_label.setWordWrap(True)
        panel_layout.addWidget(self.selection_hint_label)

        self.conflict_label = QLabel("")
        self.conflict_label.setObjectName("WarningStrip")
        self.conflict_label.setWordWrap(True)
        self.conflict_label.hide()
        panel_layout.addWidget(self.conflict_label)

        layout.addWidget(panel, 1)
        return tab

    def _build_settings_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        panel = QFrame()
        panel.setObjectName("SettingsPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(10)

        title = QLabel("Настройки")
        title.setObjectName("HeroTitle")
        panel_layout.addWidget(title)

        subtitle = QLabel(
            "Ключевые параметры разделены на два компактных блока, чтобы ничего не схлопывалось и не накладывалось."
        )
        subtitle.setObjectName("SecondaryText")
        subtitle.setWordWrap(True)
        panel_layout.addWidget(subtitle)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Темная", "dark")
        self.theme_combo.addItem("Светлая", "light")
        self.theme_combo.addItem("Системная", "system")
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Свободный режим")
        self.preset_combo.addItem("Помодоро 25/5")
        self.preset_combo.addItem("52/17")
        self.preset_combo.addItem("50/10")
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)

        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(1, 60)
        self.idle_threshold_spin = QSpinBox()
        self.idle_threshold_spin.setRange(5, 600)
        self.idle_warning_spin = QSpinBox()
        self.idle_warning_spin.setRange(0, 240)
        self.break_warning_spin = QSpinBox()
        self.break_warning_spin.setRange(1, 480)

        self.notify_idle_check = QCheckBox("Напоминать о долгом отвлечении или idle")
        self.notify_break_check = QCheckBox("Напоминать о перерыве")
        self.widget_always_on_top_check = QCheckBox("Держать виджет поверх окон")
        self.widget_compact_check = QCheckBox("Открывать виджет в компактном режиме")

        content_row = QHBoxLayout()
        content_row.setSpacing(10)

        basics_panel = QFrame()
        basics_panel.setObjectName("StatsPanel")
        basics_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        basics_layout = QGridLayout(basics_panel)
        basics_layout.setContentsMargins(14, 14, 14, 14)
        basics_layout.setHorizontalSpacing(12)
        basics_layout.setVerticalSpacing(9)

        basics_title = QLabel("Базовые параметры")
        basics_title.setObjectName("SectionEyebrow")
        basics_layout.addWidget(basics_title, 0, 0, 1, 2)
        basics_layout.addWidget(self._make_detail_label("Тема"), 1, 0)
        basics_layout.addWidget(self.theme_combo, 1, 1)
        basics_layout.addWidget(self._make_detail_label("Профиль"), 2, 0)
        basics_layout.addWidget(self.preset_combo, 2, 1)
        basics_layout.addWidget(self._make_detail_label("Опрос, сек"), 3, 0)
        basics_layout.addWidget(self.poll_interval_spin, 3, 1)
        basics_layout.addWidget(self._make_detail_label("Порог idle, сек"), 4, 0)
        basics_layout.addWidget(self.idle_threshold_spin, 4, 1)
        basics_layout.addWidget(self._make_detail_label("Idle warning, мин"), 5, 0)
        basics_layout.addWidget(self.idle_warning_spin, 5, 1)
        basics_layout.addWidget(self._make_detail_label("Перерыв, мин"), 6, 0)
        basics_layout.addWidget(self.break_warning_spin, 6, 1)
        for row, text in {
            4: "Порог бездействия, сек",
            5: "Вернуться к работе, мин",
            6: "Перерыв после работы, мин",
        }.items():
            item = basics_layout.itemAtPosition(row, 0)
            if item is None:
                continue
            label = item.widget()
            if isinstance(label, QLabel):
                label.setText(text)

        widget_panel = QFrame()
        widget_panel.setObjectName("StatsPanel")
        widget_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        widget_layout = QVBoxLayout(widget_panel)
        widget_layout.setContentsMargins(14, 14, 14, 14)
        widget_layout.setSpacing(8)

        widget_title = QLabel("Поведение")
        widget_title.setObjectName("SectionEyebrow")
        widget_layout.addWidget(widget_title)
        widget_layout.addWidget(self.notify_idle_check)
        widget_layout.addWidget(self.notify_break_check)
        widget_layout.addWidget(self.widget_always_on_top_check)
        widget_layout.addWidget(self.widget_compact_check)
        widget_layout.addStretch()
        self.notify_idle_check.setText(
            "Напоминать вернуться к работе после отдыха или отвлечения"
        )
        self.notify_break_check.setText("Напоминать сделать перерыв")

        content_row.addWidget(basics_panel, 6)
        content_row.addWidget(widget_panel, 4)
        panel_layout.addLayout(content_row, 1)

        self.preset_desc_label = QLabel("")
        self.preset_desc_label.setObjectName("MutedLabel")
        self.preset_desc_label.setWordWrap(True)
        panel_layout.addWidget(self.preset_desc_label)

        actions = QHBoxLayout()
        actions.addStretch()
        self.save_button = QPushButton("Сохранить")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.on_save_clicked)
        actions.addWidget(self.save_button)
        panel_layout.addLayout(actions)

        layout.addWidget(panel, 1)
        return tab

    def _build_activity_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        panel = QFrame()
        panel.setObjectName("ActivityPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(10)

        title = QLabel("Лента активности")
        title.setObjectName("HeroTitle")
        panel_layout.addWidget(title)

        subtitle = QLabel(
            "Здесь остаётся только оперативная лента событий. Полная аналитика открывается в отдельном окне статистики."
        )
        subtitle.setObjectName("SecondaryText")
        subtitle.setWordWrap(True)
        panel_layout.addWidget(subtitle)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        open_stats = QPushButton("Открыть статистику")
        open_stats.setObjectName("GhostButton")
        open_stats.clicked.connect(self.on_open_detailed_stats)
        actions.addWidget(open_stats)

        open_widget = QPushButton("Показать виджет")
        open_widget.setObjectName("GhostButton")
        open_widget.clicked.connect(self._toggle_widget_visibility)
        actions.addWidget(open_widget)
        actions.addStretch()
        panel_layout.addLayout(actions)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(0)
        self.log_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        panel_layout.addWidget(self.log_edit, 1)

        layout.addWidget(panel, 1)
        return tab

    def _ensure_widget_window(self) -> FocusWidget:
        if self.widget_window is not None:
            return self.widget_window

        widget = FocusWidget()
        widget.open_main_requested.connect(self._show_main_window)
        widget.pause_toggled.connect(self.on_pause_clicked)
        widget.compact_mode_changed.connect(self._on_widget_compact_changed)
        widget.always_on_top_changed.connect(self._on_widget_topmost_changed)
        widget.apply_settings(
            always_on_top=self.config.widget_always_on_top,
            compact_mode=self.config.widget_compact_mode,
        )

        if self.worker and self.worker.isRunning():
            widget.set_tracking_state(is_running=True, is_paused=self._worker_paused)
            if self._current_snapshot is not None:
                widget.update_snapshot(self._current_snapshot)
        else:
            widget.show_idle_state()

        self.widget_window = widget
        return widget

    def _detect_preset_index(self, cfg: Config) -> int:
        for index, preset in self.preset_configs.items():
            if (
                cfg.poll_interval_seconds == preset["poll_interval_seconds"]
                and cfg.idle_threshold_seconds == preset["idle_threshold_seconds"]
                and cfg.idle_warning_minutes == preset["idle_warning_minutes"]
                and cfg.break_warning_minutes == preset["break_warning_minutes"]
            ):
                return index
        return 0

    def _upgrade_legacy_preset_config(self, cfg: Config) -> None:
        for index, legacy in self.legacy_preset_configs.items():
            if (
                cfg.poll_interval_seconds == legacy["poll_interval_seconds"]
                and cfg.idle_threshold_seconds == legacy["idle_threshold_seconds"]
                and cfg.idle_warning_minutes == legacy["idle_warning_minutes"]
                and cfg.break_warning_minutes == legacy["break_warning_minutes"]
            ):
                cfg.idle_warning_minutes = self.preset_configs[index][
                    "idle_warning_minutes"
                ]
                save_config(cfg)
                return

    def _load_config_to_ui(self) -> None:
        cfg = self.config
        self._upgrade_legacy_preset_config(cfg)
        self.poll_interval_spin.setValue(cfg.poll_interval_seconds)
        self.idle_threshold_spin.setValue(cfg.idle_threshold_seconds)
        self.idle_warning_spin.setValue(cfg.idle_warning_minutes)
        self.break_warning_spin.setValue(cfg.break_warning_minutes)
        self.notify_idle_check.setChecked(cfg.notify_on_idle)
        self.notify_break_check.setChecked(cfg.notify_on_break)
        self.widget_always_on_top_check.setChecked(cfg.widget_always_on_top)
        self.widget_compact_check.setChecked(cfg.widget_compact_mode)

        preset_index = self._detect_preset_index(cfg)
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(preset_index)
        self.preset_combo.blockSignals(False)
        self._update_preset_description(preset_index)

        theme_index = self.theme_combo.findData(cfg.theme)
        if theme_index < 0:
            theme_index = 0
        self.theme_combo.blockSignals(True)
        self.theme_combo.setCurrentIndex(theme_index)
        self.theme_combo.blockSignals(False)
        self.apply_theme(self._combo_current_data_str(self.theme_combo))

        if self.widget_window is not None:
            self.widget_window.apply_settings(
                always_on_top=cfg.widget_always_on_top,
                compact_mode=cfg.widget_compact_mode,
            )

    def _save_ui_to_config(self) -> None:
        self.config.poll_interval_seconds = self.poll_interval_spin.value()
        self.config.idle_threshold_seconds = self.idle_threshold_spin.value()
        self.config.idle_warning_minutes = self.idle_warning_spin.value()
        self.config.break_warning_minutes = self.break_warning_spin.value()
        self.config.notify_on_idle = self.notify_idle_check.isChecked()
        self.config.notify_on_break = self.notify_break_check.isChecked()
        self.config.widget_always_on_top = self.widget_always_on_top_check.isChecked()
        self.config.widget_compact_mode = self.widget_compact_check.isChecked()
        self.rules_repo.apply_to_config(persist=False)
        save_config(self.config)
        if self.widget_window is not None:
            self.widget_window.apply_settings(
                always_on_top=self.config.widget_always_on_top,
                compact_mode=self.config.widget_compact_mode,
            )

    def _show_main_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _toggle_widget_visibility(self) -> None:
        widget = self._ensure_widget_window()
        if widget.isVisible():
            widget.hide()
            return
        widget.show()
        widget.raise_()
        widget.activateWindow()

    def _on_widget_compact_changed(self, value: bool) -> None:
        self.widget_compact_check.setChecked(value)
        self.config.widget_compact_mode = value
        save_config(self.config)
        if self.widget_window is not None:
            self.widget_window.apply_settings(
                always_on_top=self.config.widget_always_on_top,
                compact_mode=value,
            )

    def _on_widget_topmost_changed(self, value: bool) -> None:
        self.widget_always_on_top_check.setChecked(value)
        self.config.widget_always_on_top = value
        save_config(self.config)
        if self.widget_window is not None:
            self.widget_window.apply_settings(
                always_on_top=value,
                compact_mode=self.config.widget_compact_mode,
            )

    def _update_preset_description(self, index: int) -> None:
        self.preset_desc_label.setText(self.preset_descriptions.get(index, ""))

    def on_preset_changed(self, index: int) -> None:
        self._update_preset_description(index)
        if index == 0:
            return
        preset = self.preset_configs.get(index)
        if not preset:
            return
        self.poll_interval_spin.setValue(preset["poll_interval_seconds"])
        self.idle_threshold_spin.setValue(preset["idle_threshold_seconds"])
        self.idle_warning_spin.setValue(preset["idle_warning_minutes"])
        self.break_warning_spin.setValue(preset["break_warning_minutes"])

    def apply_theme(self, theme_key: str) -> None:
        app = QApplication.instance()
        if app is None:
            return
        qt_app = cast(QApplication, app)

        qt_app.setStyle(QStyleFactory.create("Fusion"))
        qt_app.setStyleSheet("")

        if theme_key == "light":
            style = qt_app.style()
            if style is not None:
                qt_app.setPalette(style.standardPalette())
            qt_app.setStyleSheet(LIGHT_STYLE_SHEET)
            return

        if theme_key == "system":
            palette = qt_app.palette()
            is_dark = palette.color(QPalette.ColorRole.Window).lightness() < 128
            qt_app.setStyleSheet(DARK_STYLE_SHEET if is_dark else LIGHT_STYLE_SHEET)
            return

        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(18, 18, 20))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 242))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(22, 22, 24))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(32, 32, 34))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(22, 22, 24))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(240, 240, 242))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 242))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(32, 32, 34))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(240, 240, 242))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(220, 220, 224))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(18, 18, 20))
        qt_app.setPalette(dark_palette)
        qt_app.setStyleSheet(DARK_STYLE_SHEET)

    def on_theme_changed(self, index: int) -> None:
        theme_key = self._combo_item_data_str(self.theme_combo, index)
        if not theme_key:
            return
        self.apply_theme(theme_key)
        self.config.theme = theme_key
        save_config(self.config)
        self.append_log(f"Тема интерфейса: {theme_key}")

    def on_save_clicked(self) -> None:
        self._save_ui_to_config()
        if self.worker and self.worker.isRunning():
            self.worker.reload_rules()
        self.append_log("Настройки сохранены.")
        QMessageBox.information(self, "FocusMeter", "Настройки и правила сохранены.")

    def on_start_clicked(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.warning(self, "FocusMeter", "Трекинг уже запущен.")
            return

        self._save_ui_to_config()
        self.rules_repo.reload()

        self.worker = FocusWorker(self.config)
        self.worker.status_updated.connect(self.on_worker_status)
        self.worker.started_tracking.connect(self.on_worker_started)
        self.worker.stopped_tracking.connect(self.on_worker_stopped)
        self.worker.paused_changed.connect(self.on_worker_paused_changed)
        self.worker.snapshot_updated.connect(self.on_worker_snapshot)
        self.worker.start()
        self.append_log("Запуск трекинга...")

    def on_pause_clicked(self) -> None:
        if not self.worker or not self.worker.isRunning():
            return
        if self._worker_paused:
            self.worker.resume_tracking()
        else:
            self.worker.pause_tracking()

    def on_stop_clicked(self) -> None:
        if self.worker and self.worker.isRunning():
            self.append_log("Остановка трекинга...")
            self.worker.stop()
            self.worker.wait()
        else:
            self.append_log("Трекинг уже остановлен.")

    def on_worker_status(self, text: str) -> None:
        self.append_log(text)

    def on_worker_started(self) -> None:
        self.status_chip.setText("В работе")
        self._set_worker_controls(is_running=True, paused=False)
        if self.widget_window is not None:
            self.widget_window.set_tracking_state(is_running=True, is_paused=False)

    def on_worker_stopped(self) -> None:
        self.status_chip.setText("Остановлено")
        self._worker_paused = False
        self._set_worker_controls(is_running=False, paused=False)
        if self.widget_window is not None:
            self.widget_window.show_idle_state()
        self._current_snapshot = None
        self._update_dashboard_idle_state()
        self._refresh_today_overview()
        self._refresh_app_catalog()

    def on_worker_paused_changed(self, is_paused: bool) -> None:
        self._worker_paused = is_paused
        self.status_chip.setText("На паузе" if is_paused else "В работе")
        self._set_worker_controls(is_running=True, paused=is_paused)
        if self.widget_window is not None:
            self.widget_window.set_tracking_state(is_running=True, is_paused=is_paused)

    def on_worker_snapshot(self, snapshot: WorkerSnapshot) -> None:
        self._current_snapshot = snapshot
        self.current_app_label.setText(
            snapshot.app_name or "Не удалось определить приложение"
        )
        self.context_label.setText(
            snapshot.window_title
            or (
                "Трекинг поставлен на паузу."
                if snapshot.paused
                else "Заголовок окна недоступен."
            )
        )
        self.timer_label.setText(format_duration(snapshot.fatigue_score))
        self.timer_hint_label.setText(
            "Сессия на паузе."
            if snapshot.paused
            else "Фокус-таймер до следующего перерыва"
        )
        self.break_eta_label.setText(
            f"Перерыв: {format_duration(snapshot.seconds_to_break)}"
        )
        self.idle_eta_label.setText(
            f"Idle: {format_duration(snapshot.seconds_to_idle_warning)}"
        )
        self.break_eta_label.setText(
            f"До перерыва: {format_duration(snapshot.seconds_to_break)}"
        )
        self.idle_eta_label.setText(
            f"До возврата: {format_duration(snapshot.seconds_to_idle_warning)}"
        )
        if self.widget_window is not None:
            self.widget_window.update_snapshot(snapshot)

    def _set_worker_controls(self, is_running: bool, paused: bool) -> None:
        self.start_button.setEnabled(not is_running)
        self.stop_button.setEnabled(is_running)
        self.pause_button.setEnabled(is_running)
        self.pause_button.setText("Продолжить" if paused else "Пауза")

    def _update_dashboard_idle_state(self) -> None:
        self.current_app_label.setText("Фокус ещё не запущен")
        self.context_label.setText(
            "Запустите трекинг, а правила, настройки и журнал доступны ниже в отдельных разделах."
        )
        self.timer_label.setText("00:00:00")
        self.timer_hint_label.setText("Фокус-таймер до следующего перерыва")
        self.break_eta_label.setText("Перерыв: --")
        self.idle_eta_label.setText("Idle: --")
        self.break_eta_label.setText("До перерыва: --")
        self.idle_eta_label.setText("До возврата: --")

    def _refresh_today_overview(self) -> None:
        today = datetime.now().date()
        offset = datetime.now().astimezone().utcoffset() or timedelta(0)
        start_local = datetime.combine(today, dt_time.min)
        end_local = datetime.combine(today + timedelta(days=1), dt_time.min)
        stats = get_time_stats(
            db_path=self.config.db_path,
            start_utc=start_local - offset,
            end_utc=end_local - offset,
            sample_interval_seconds=self.config.poll_interval_seconds,
        )
        self.today_active_card.set_content(
            format_duration(stats.active_seconds),
            "За сегодня",
        )
        self.today_work_card.set_content(
            format_duration(stats.work_active_seconds),
            "Рабочие приложения",
        )
        self.today_idle_card.set_content(
            format_duration(stats.idle_seconds),
            "Без ввода",
        )

    def on_open_detailed_stats(self) -> None:
        if self.stats_window is None:
            self.stats_window = StatsWindow(self.config, self)
        else:
            self.stats_window.refresh_for_today()
        self.stats_window.show()
        self.stats_window.raise_()
        self.stats_window.activateWindow()

    def _refresh_app_catalog(self) -> None:
        self.rules_repo.reload()
        self._open_windows = list_open_windows(limit=200)
        self._populate_app_table()
        self._update_rule_conflicts()

    def _history_summary(self, entry: AppHistoryEntry | None) -> str:
        if entry is None:
            return "Новый"
        if entry.last_seen_utc:
            try:
                moment = datetime.fromisoformat(entry.last_seen_utc)
                last_seen_text = moment.strftime("%d.%m %H:%M")
            except ValueError:
                last_seen_text = "недавно"
        else:
            last_seen_text = "недавно"
        return f"{entry.seen_count} раз • {last_seen_text}"

    def _build_app_rows(self) -> list[dict[str, object]]:
        source = self._combo_current_data_str(self.app_source_combo)
        rows: list[dict[str, object]] = []

        if source == "open":
            for window in self._open_windows:
                key = (window.process_name or "").lower()
                entry = self.rules_repo.state.history.get(key)
                rows.append(
                    {
                        "process_name": window.process_name or "",
                        "window_title": window.window_title or "",
                        "exe_path": window.exe_path or "",
                        "rule": self.rules_repo.get_rule(key),
                        "history": self._history_summary(entry),
                        "favorite": key in self.rules_repo.state.favorites,
                    }
                )
        elif source in {"recent", "favorites"}:
            entries = self.rules_repo.get_recent_apps(
                limit=200,
                favorites_only=(source == "favorites"),
            )
            for entry in entries:
                rows.append(
                    {
                        "process_name": entry.process_name,
                        "window_title": entry.window_title,
                        "exe_path": entry.exe_path,
                        "rule": self.rules_repo.get_rule(entry.process_name),
                        "history": self._history_summary(entry),
                        "favorite": entry.process_name
                        in self.rules_repo.state.favorites,
                    }
                )
        else:
            names = (
                self.rules_repo.state.work_apps
                | self.rules_repo.state.distracting_apps
                | self.rules_repo.state.excluded_apps
            )
            for process_name in sorted(names):
                entry = self.rules_repo.state.history.get(process_name)
                rows.append(
                    {
                        "process_name": process_name,
                        "window_title": entry.window_title if entry else "",
                        "exe_path": entry.exe_path if entry else "",
                        "rule": self.rules_repo.get_rule(process_name),
                        "history": self._history_summary(entry),
                        "favorite": process_name in self.rules_repo.state.favorites,
                    }
                )

        query = self.app_search_edit.text().strip().lower()
        if query:
            rows = [
                row
                for row in rows
                if query in str(row["process_name"]).lower()
                or query in str(row["window_title"]).lower()
            ]
        return rows

    def _icon_for_path(self, exe_path: str) -> QIcon:
        path = (exe_path or "").strip()
        if not path:
            return QIcon()
        icon = self._icon_cache.get(path)
        if icon is None:
            provider = QFileIconProvider()
            icon = provider.icon(QFileInfo(path))
            self._icon_cache[path] = icon
        return icon

    def _populate_app_table(self) -> None:
        previous = self._selected_row_payload()
        previous_key = ""
        if previous is not None:
            previous_key = str(previous["process_name"])

        self._visible_app_rows = self._build_app_rows()
        self.app_list.clear()

        for row in self._visible_app_rows:
            rule_label = RULE_LABELS.get(str(row["rule"]), RULE_LABELS[RULE_NONE])
            favorite_prefix = "★ " if bool(row["favorite"]) else ""
            title = str(row["window_title"]) or "Без активного заголовка"
            summary = f"{rule_label} • {row['history']}"
            item = QListWidgetItem(
                f"{favorite_prefix}{row['process_name']} · {rule_label}\n{title}"
            )
            item.setIcon(self._icon_for_path(str(row["exe_path"])))
            item.setData(Qt.ItemDataRole.UserRole, row)
            item.setToolTip(f"{title}\n{summary}")
            self.app_list.addItem(item)

        if self.app_list.count() == 0:
            self._update_selection_hint()
            return

        target_index = 0
        for index in range(self.app_list.count()):
            item = self.app_list.item(index)
            if item is None:
                continue
            payload = cast(dict[str, object], item.data(Qt.ItemDataRole.UserRole))
            if str(payload["process_name"]) == previous_key:
                target_index = index
                break

        self.app_list.setCurrentRow(target_index)
        self._update_selection_hint()

    def _selected_row_payload(self) -> dict[str, object] | None:
        item = self.app_list.currentItem()
        if item is None:
            return None
        return cast(dict[str, object], item.data(Qt.ItemDataRole.UserRole))

    def _update_selection_hint(self, current=None, previous=None) -> None:
        del previous
        if current is not None:
            payload = cast(dict[str, object], current.data(Qt.ItemDataRole.UserRole))
        else:
            payload = self._selected_row_payload()
        if payload is None:
            self.selected_process_label.setText("Ничего не выбрано")
            self.selected_window_label.setText(
                "Выберите приложение слева, чтобы увидеть детали и назначить правило."
            )
            self.current_rule_label.setText("Без правила")
            self.current_history_label.setText("—")
            self.current_favorite_label.setText("Нет")
            self.favorite_button.setText("Добавить в избранное")
            self.selection_hint_label.setText(
                "Выберите приложение в списке, чтобы назначить правило."
            )
            return

        process_name = str(payload["process_name"])
        rule = RULE_LABELS.get(str(payload["rule"]), RULE_LABELS[RULE_NONE])
        favorite = "в избранном" if bool(payload["favorite"]) else "не в избранном"
        self.selected_process_label.setText(process_name or "Без имени")
        self.selected_window_label.setText(
            str(payload["window_title"]) or "Нет активного заголовка окна."
        )
        self.current_rule_label.setText(rule)
        self.current_history_label.setText(str(payload["history"]))
        self.current_favorite_label.setText(
            "Да" if bool(payload["favorite"]) else "Нет"
        )
        self.favorite_button.setText(
            "Убрать из избранного"
            if bool(payload["favorite"])
            else "Добавить в избранное"
        )
        self.selection_hint_label.setText(
            f"{process_name}: {rule}, {payload['history']}, {favorite}."
        )

    def _set_rule_for_selected(self, rule: str) -> None:
        payload = self._selected_row_payload()
        if payload is None:
            QMessageBox.information(self, "FocusMeter", "Сначала выберите приложение.")
            return

        process_name = str(payload["process_name"])
        self.rules_repo.set_rule(process_name, rule)
        if self.worker and self.worker.isRunning():
            self.worker.reload_rules()
        self._refresh_app_catalog()
        self.append_log(
            f"Правило для {process_name}: {RULE_LABELS.get(rule, RULE_LABELS[RULE_NONE])}"
        )

    def _toggle_favorite_for_selected(self) -> None:
        payload = self._selected_row_payload()
        if payload is None:
            QMessageBox.information(self, "FocusMeter", "Сначала выберите приложение.")
            return

        process_name = str(payload["process_name"])
        is_favorite = self.rules_repo.toggle_favorite(process_name)
        self._refresh_app_catalog()
        self.append_log(
            f"{process_name} {'добавлено в избранное' if is_favorite else 'убрано из избранного'}."
        )

    def _update_rule_conflicts(self) -> None:
        conflicts = self.rules_repo.find_conflicts()
        if not conflicts:
            self.conflict_label.hide()
            return
        self.conflict_label.setText(
            "Конфликт правил: " + ", ".join(conflicts[:6]) + ". Уберите дубликаты."
        )
        self.conflict_label.show()

    def append_log(self, text: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_edit.appendPlainText(f"[{timestamp}] {text}")

    def _stop_worker_if_running(self) -> None:
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker and self.worker.isRunning():
            buttons = cast(
                QMessageBox.StandardButtons,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            reply = QMessageBox.question(
                self,
                "FocusMeter",
                "Трекинг сейчас работает. Остановить его и закрыть приложение?",
                buttons,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self._stop_worker_if_running()

        if self.stats_window is not None:
            self.stats_window.close()
        if self.widget_window is not None:
            self.widget_window.shutdown()
        app = QApplication.instance()
        if app is not None:
            app.quit()
        event.accept()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._ensure_screen_sync()
        schedule_window_layout_sync(self, 0)
        if not self._initial_layout_stabilized:
            self._initial_layout_stabilized = True
            QTimer.singleShot(120, self._stabilize_initial_layout)
            QTimer.singleShot(320, self._stabilize_initial_layout)


def main() -> None:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
