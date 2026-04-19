from __future__ import annotations

import platform

from PyQt5.QtCore import QSize, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from focus_worker import WorkerSnapshot
from window_chrome import (
    build_window_shell,
    prepare_frameless_window,
    schedule_window_layout_sync,
)

_IS_MACOS = platform.system() == "Darwin"


def format_duration(seconds: float) -> str:
    total_seconds = max(int(seconds), 0)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class FocusWidget(QDialog):
    open_main_requested = pyqtSignal()
    pause_toggled = pyqtSignal()
    compact_mode_changed = pyqtSignal(bool)
    always_on_top_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._compact_mode = False
        self._always_on_top = True
        self._is_running = False
        self._is_paused = False
        self._allow_close = False
        self._screen_sync_connected = False
        self._initial_layout_stabilized = False

        self.setWindowTitle("FocusMeter Widget")
        self.setMinimumSize(320, 170)

        prepare_frameless_window(
            self,
            use_tool=self._widget_use_tool_flag(),
            always_on_top=True,
        )
        self._build_ui()
        self.apply_settings(always_on_top=True, compact_mode=False)
        self.show_idle_state()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        host = QWidget(self)
        _, body_layout, self.title_bar, self.size_grip = build_window_shell(
            host,
            title="Виджет",
            subtitle="Быстрый обзор фокуса",
            show_minimize=False,
            body_margins=(14, 10, 14, 10),
            body_spacing=8,
        )
        root_layout.addWidget(host)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self.status_chip = QLabel("Ожидание")
        self.status_chip.setObjectName("StatusChip")
        header_row.addWidget(self.status_chip)
        header_row.addStretch()

        self.menu_button = QPushButton("⋯")
        self.menu_button.setObjectName("TinyButton")
        header_row.addWidget(self.menu_button)
        body_layout.addLayout(header_row)

        self._build_menu()

        panel = QFrame()
        panel.setObjectName("WidgetPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 12, 14, 12)
        panel_layout.setSpacing(6)

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("HeroTimer")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        panel_layout.addWidget(self.timer_label)

        self.app_label = QLabel("Нет активной сессии")
        self.app_label.setObjectName("HeroTitle")
        self.app_label.setWordWrap(True)
        panel_layout.addWidget(self.app_label)

        self.meta_label = QLabel("Запустите FocusMeter, чтобы видеть таймер и активное приложение.")
        self.meta_label.setObjectName("SecondaryText")
        self.meta_label.setWordWrap(True)
        panel_layout.addWidget(self.meta_label)

        self.details_row = QHBoxLayout()
        self.details_row.setSpacing(10)
        self.break_label = QLabel("Перерыв: --")
        self.break_label.setObjectName("PillLabel")
        self.idle_label = QLabel("До возврата: --")
        self.idle_label.setObjectName("PillLabel")
        self.details_row.addWidget(self.break_label, 1)
        self.details_row.addWidget(self.idle_label, 1)
        panel_layout.addLayout(self.details_row)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("WarningStrip")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        panel_layout.addWidget(self.warning_label)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)
        self.open_button = QPushButton("Открыть")
        self.open_button.setObjectName("GhostButton")
        self.open_button.clicked.connect(self.open_main_requested.emit)
        controls_row.addWidget(self.open_button)

        self.pause_button = QPushButton("Пауза")
        self.pause_button.setObjectName("PrimaryButton")
        self.pause_button.clicked.connect(self.pause_toggled.emit)
        controls_row.addWidget(self.pause_button)
        panel_layout.addLayout(controls_row)

        body_layout.addWidget(panel)

    def _build_menu(self) -> None:
        menu = QMenu(self)

        self.compact_action = menu.addAction("Компактный режим")
        if self.compact_action is None:
            raise RuntimeError("Failed to create compact mode action")
        self.compact_action.setCheckable(True)
        self.compact_action.toggled.connect(self.compact_mode_changed.emit)

        self.topmost_action = menu.addAction("Поверх окон")
        if self.topmost_action is None:
            raise RuntimeError("Failed to create always-on-top action")
        self.topmost_action.setCheckable(True)
        self.topmost_action.toggled.connect(self.always_on_top_changed.emit)

        menu.addSeparator()
        open_action = menu.addAction("Открыть главное окно")
        if open_action is None:
            raise RuntimeError("Failed to create open-main action")
        open_action.triggered.connect(self.open_main_requested.emit)

        self.menu_button.setMenu(menu)

    def _target_size_for_mode(self, compact_mode: bool) -> QSize:
        if compact_mode:
            base_size = QSize(324, 176)
        else:
            base_size = QSize(388, 268)

        if not _IS_MACOS:
            return base_size

        # На macOS системные метрики шрифтов и отступов больше, чем на Windows:
        # фиксируем чуть более высокий/широкий размер только для Darwin,
        # чтобы не ломать верстку Windows, где текущие значения уже стабильны.
        mac_floor = QSize(
            base_size.width() + 24,
            base_size.height() + (26 if compact_mode else 44),
        )

        self.layout().activate()
        hinted = self.sizeHint()
        return hinted.expandedTo(mac_floor)

    @staticmethod
    def _widget_use_tool_flag() -> bool:
        # На macOS Qt.Tool (NSPanel) часто скрывается при деактивации приложения.
        # Для виджета используем обычное окно, чтобы оно не исчезало при переключении.
        # На Windows/других ОС сохраняем прежнее поведение.
        return not _IS_MACOS

    def apply_settings(self, always_on_top: bool, compact_mode: bool) -> None:
        self._always_on_top = always_on_top
        self._compact_mode = compact_mode
        was_visible = self.isVisible()

        if was_visible:
            self.hide()

        self.compact_action.blockSignals(True)
        self.compact_action.setChecked(compact_mode)
        self.compact_action.blockSignals(False)

        self.topmost_action.blockSignals(True)
        self.topmost_action.setChecked(always_on_top)
        self.topmost_action.blockSignals(False)

        prepare_frameless_window(
            self,
            use_tool=self._widget_use_tool_flag(),
            always_on_top=always_on_top,
        )
        self.break_label.setVisible(not compact_mode)
        self.idle_label.setVisible(not compact_mode)
        self.meta_label.setVisible(True)
        self.title_bar.set_title(
            "Виджет",
            "Минимальный обзор" if compact_mode else "Быстрый обзор фокуса",
        )
        self.size_grip.setVisible(False)

        if compact_mode:
            self.meta_label.setVisible(False)
            self.warning_label.setVisible(False)
        else:
            self.meta_label.setVisible(True)

        target_size = self._target_size_for_mode(compact_mode)
        self.setFixedSize(target_size)
        self.resize(target_size)

        if was_visible:
            self.show()
            self.raise_()
            self.activateWindow()
        schedule_window_layout_sync(self, 0)

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

    def _stabilize_initial_layout(self) -> None:
        if not self.isVisible():
            return
        self.updateGeometry()
        schedule_window_layout_sync(self, 0)

    def set_tracking_state(self, is_running: bool, is_paused: bool) -> None:
        self._is_running = is_running
        self._is_paused = is_paused
        if not is_running:
            self.pause_button.setEnabled(False)
            self.pause_button.setText("Пауза")
            self.status_chip.setText("Ожидание")
            return

        self.pause_button.setEnabled(True)
        self.pause_button.setText("Продолжить" if is_paused else "Пауза")

    def show_idle_state(self) -> None:
        self.set_tracking_state(is_running=False, is_paused=False)
        self.timer_label.setText("00:00:00")
        self.app_label.setText("Нет активной сессии")
        self.meta_label.setText("Запустите трекинг, чтобы получить компактный обзор.")
        self.break_label.setText("Перерыв: --")
        self.idle_label.setText("До возврата: --")
        self.break_label.setText("До перерыва: --")
        self.warning_label.hide()

    def update_snapshot(self, snapshot: WorkerSnapshot) -> None:
        self.set_tracking_state(is_running=True, is_paused=snapshot.paused)
        self.status_chip.setText(snapshot.status_text)
        self.timer_label.setText(format_duration(snapshot.fatigue_score))
        self.app_label.setText(snapshot.app_name or "Не удалось определить приложение")

        if self._compact_mode:
            self.meta_label.setText(
                f"Перерыв через {format_duration(snapshot.seconds_to_break)}"
            )
        else:
            self.meta_label.setText(
                snapshot.window_title or "Заголовок окна недоступен."
            )

        self.break_label.setText(
            f"Перерыв: {format_duration(snapshot.seconds_to_break)}"
        )
        self.idle_label.setText(
            f"Idle: {format_duration(snapshot.seconds_to_idle_warning)}"
        )
        self.break_label.setText(
            f"До перерыва: {format_duration(snapshot.seconds_to_break)}"
        )
        self.idle_label.setText(
            f"До возврата: {format_duration(snapshot.seconds_to_idle_warning)}"
        )

        warning_text = ""
        if snapshot.state == "distract" and snapshot.seconds_to_idle_warning <= 60:
            warning_text = "Скоро сработает предупреждение об отвлечении."
        elif snapshot.state == "work" and snapshot.seconds_to_break <= 60:
            warning_text = "Пора готовиться к короткому перерыву."
        elif snapshot.state == "idle":
            warning_text = "FocusMeter не видит недавнюю активность."

        if warning_text:
            self.warning_label.setText(warning_text)
            self.warning_label.show()
        else:
            self.warning_label.hide()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._allow_close:
            event.accept()
            return
        self.hide()
        event.ignore()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._ensure_screen_sync()
        schedule_window_layout_sync(self, 0)
        if not self._initial_layout_stabilized:
            self._initial_layout_stabilized = True
            QTimer.singleShot(120, self._stabilize_initial_layout)

    def shutdown(self) -> None:
        self._allow_close = True
        self.close()
