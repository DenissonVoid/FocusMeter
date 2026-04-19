from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta

from PyQt5.QtCore import QDate, QRectF, QTimer, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from config import Config
from storage.db import AppUsageRow, TimeStats, get_time_stats
from window_chrome import (
    build_window_shell,
    prepare_frameless_window,
    schedule_window_layout_sync,
)

NO_PEN = Qt.PenStyle.NoPen
ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter


def format_duration(seconds: float) -> str:
    total_seconds = max(int(seconds), 0)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_percent(value: float) -> str:
    return f"{value * 100:.1f}%"


class MetricCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("KpiCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("KpiTitle")
        layout.addWidget(self.title_label)

        self.value_label = QLabel("00:00:00")
        self.value_label.setObjectName("KpiValue")
        layout.addWidget(self.value_label)

        self.meta_label = QLabel("")
        self.meta_label.setObjectName("MutedLabel")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)

    def set_content(self, value: str, meta: str) -> None:
        self.value_label.setText(value)
        self.meta_label.setText(meta)


class CategoryDistributionWidget(QWidget):
    SEGMENT_COLORS = {
        "Рабочее": QColor("#5BB98C"),
        "Отвлекающее": QColor("#F0A35E"),
        "Прочее": QColor("#6D8EEB"),
        "Бездействие": QColor("#8B909A"),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._segments: list[tuple[str, float]] = []
        self.setMinimumHeight(72)

    def set_segments(self, segments: list[tuple[str, float]]) -> None:
        self._segments = segments
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(8, 10, -8, -10)
        painter.setPen(NO_PEN)
        painter.setBrush(QColor(127, 127, 127, 24))
        painter.drawRoundedRect(rect, 14, 14)

        total = sum(value for _, value in self._segments)
        if total <= 0:
            painter.setPen(QPen(QColor(140, 140, 144)))
            painter.drawText(
                self.rect(),
                int(ALIGN_CENTER),
                "Данные появятся после первой активности.",
            )
            return

        x = rect.x()
        width = rect.width()
        for index, (label, value) in enumerate(self._segments):
            fraction = value / total if total else 0.0
            segment_width = width * fraction
            if index == len(self._segments) - 1:
                segment_width = rect.right() - x + 1
            painter.setBrush(self.SEGMENT_COLORS.get(label, QColor("#808080")))
            painter.drawRoundedRect(
                QRectF(x, rect.y(), segment_width, rect.height()),
                14,
                14,
            )
            x += segment_width


class StatsWindow(QDialog):
    PERIOD_OPTIONS = [
        ("Сегодня", "today"),
        ("Вчера", "yesterday"),
        ("Последние 7 дней", "last7"),
        ("Последние 30 дней", "last30"),
        ("Произвольный период", "custom"),
    ]

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.config = config
        self._stats: TimeStats | None = None
        self._visible_rows: list[AppUsageRow] = []
        self._screen_sync_connected = False
        self._initial_layout_stabilized = False

        self.setWindowTitle("Статистика FocusMeter")
        self.resize(1340, 940)
        self.setMinimumSize(1240, 860)
        prepare_frameless_window(self)

        self._build_ui()
        self._set_default_period()
        self._refresh_stats()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        host = QWidget(self)
        _, main_layout, self.title_bar, _size_grip = build_window_shell(
            host,
            title="Статистика",
            subtitle="Ключевые метрики и распределение времени",
            show_minimize=True,
            body_margins=(18, 14, 18, 16),
            body_spacing=12,
        )
        root_layout.addWidget(host)

        toolbar = QFrame()
        toolbar.setObjectName("StatsPanel")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(14, 14, 14, 14)
        toolbar_layout.setSpacing(10)

        self.period_combo = QComboBox()
        for label, key in self.PERIOD_OPTIONS:
            self.period_combo.addItem(label, key)
        self.period_combo.currentIndexChanged.connect(self._on_period_changed)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd.MM.yyyy")

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd.MM.yyyy")

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Поиск по процессу или заголовку окна")
        self.search_edit.textChanged.connect(self._apply_filters)

        self.category_filter = QComboBox()
        self.category_filter.addItem("Все типы", "all")
        self.category_filter.addItem("Рабочие", "work")
        self.category_filter.addItem("Отвлекающие", "distract")
        self.category_filter.addItem("Прочие", "other")
        self.category_filter.addItem("Смешанные", "mixed")
        self.category_filter.currentIndexChanged.connect(self._apply_filters)

        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.setObjectName("PrimaryButton")
        self.refresh_button.clicked.connect(self._refresh_stats)

        toolbar_layout.addWidget(QLabel("Период"))
        toolbar_layout.addWidget(self.period_combo)
        toolbar_layout.addWidget(QLabel("С"))
        toolbar_layout.addWidget(self.start_date_edit)
        toolbar_layout.addWidget(QLabel("По"))
        toolbar_layout.addWidget(self.end_date_edit)
        toolbar_layout.addWidget(self.search_edit, 1)
        toolbar_layout.addWidget(self.category_filter)
        toolbar_layout.addWidget(self.refresh_button)
        main_layout.addWidget(toolbar)

        cards_layout = QGridLayout()
        cards_layout.setHorizontalSpacing(10)
        cards_layout.setVerticalSpacing(10)
        self.total_card = MetricCard("Под наблюдением")
        self.active_card = MetricCard("Активное время")
        self.work_card = MetricCard("Рабочее время")
        self.distract_card = MetricCard("Отвлекающее")
        self.other_card = MetricCard("Прочее")
        self.idle_card = MetricCard("Бездействие")
        cards = [
            self.total_card,
            self.active_card,
            self.work_card,
            self.distract_card,
            self.other_card,
            self.idle_card,
        ]
        for index, card in enumerate(cards):
            cards_layout.addWidget(card, index // 3, index % 3)
        main_layout.addLayout(cards_layout)

        distribution_panel = QFrame()
        distribution_panel.setObjectName("StatsPanel")
        distribution_layout = QVBoxLayout(distribution_panel)
        distribution_layout.setContentsMargins(16, 16, 16, 16)
        distribution_layout.setSpacing(10)

        distribution_title = QLabel("Распределение времени")
        distribution_title.setObjectName("HeroTitle")
        distribution_layout.addWidget(distribution_title)

        self.distribution_widget = CategoryDistributionWidget()
        distribution_layout.addWidget(self.distribution_widget)

        self.distribution_legend = QLabel("")
        self.distribution_legend.setObjectName("SecondaryText")
        self.distribution_legend.setWordWrap(True)
        distribution_layout.addWidget(self.distribution_legend)
        main_layout.addWidget(distribution_panel)

        self.empty_state = QLabel("Для выбранного периода пока нет данных.")
        self.empty_state.setObjectName("WarningStrip")
        self.empty_state.setAlignment(ALIGN_CENTER)
        self.empty_state.hide()
        main_layout.addWidget(self.empty_state)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        list_panel = QFrame()
        list_panel.setObjectName("StatsPanel")
        list_layout = QVBoxLayout(list_panel)
        list_layout.setContentsMargins(14, 14, 14, 14)
        list_layout.setSpacing(8)

        list_title = QLabel("Приложения")
        list_title.setObjectName("HeroTitle")
        list_layout.addWidget(list_title)

        self.app_list = QListWidget()
        self.app_list.currentItemChanged.connect(self._on_app_changed)
        list_layout.addWidget(self.app_list, 1)
        splitter.addWidget(list_panel)

        details_panel = QFrame()
        details_panel.setObjectName("StatsPanel")
        details_layout = QVBoxLayout(details_panel)
        details_layout.setContentsMargins(14, 14, 14, 14)
        details_layout.setSpacing(10)

        self.detail_app_label = QLabel("Ничего не выбрано")
        self.detail_app_label.setObjectName("HeroTitle")
        self.detail_app_label.setWordWrap(True)
        details_layout.addWidget(self.detail_app_label)

        self.detail_window_label = QLabel(
            "Выберите приложение слева, чтобы увидеть детали."
        )
        self.detail_window_label.setObjectName("SecondaryText")
        self.detail_window_label.setWordWrap(True)
        details_layout.addWidget(self.detail_window_label)

        details_grid = QGridLayout()
        details_grid.setHorizontalSpacing(14)
        details_grid.setVerticalSpacing(8)

        self.detail_type = self._detail_value("—")
        self.detail_active = self._detail_value("00:00:00")
        self.detail_work = self._detail_value("00:00:00")
        self.detail_distract = self._detail_value("00:00:00")
        self.detail_other = self._detail_value("00:00:00")
        self.detail_share = self._detail_value("0.0%")

        details_grid.addWidget(self._detail_label("Тип"), 0, 0)
        details_grid.addWidget(self.detail_type, 0, 1)
        details_grid.addWidget(self._detail_label("Активно"), 1, 0)
        details_grid.addWidget(self.detail_active, 1, 1)
        details_grid.addWidget(self._detail_label("Работа"), 2, 0)
        details_grid.addWidget(self.detail_work, 2, 1)
        details_grid.addWidget(self._detail_label("Отвлекающее"), 3, 0)
        details_grid.addWidget(self.detail_distract, 3, 1)
        details_grid.addWidget(self._detail_label("Прочее"), 4, 0)
        details_grid.addWidget(self.detail_other, 4, 1)
        details_grid.addWidget(self._detail_label("Доля активного"), 5, 0)
        details_grid.addWidget(self.detail_share, 5, 1)
        details_layout.addLayout(details_grid)
        details_layout.addStretch()
        splitter.addWidget(details_panel)

        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([760, 540])
        main_layout.addWidget(splitter, 1)

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

    def _detail_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("DetailLabel")
        return label

    def _detail_value(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("DetailValue")
        label.setWordWrap(True)
        return label

    def _set_default_period(self) -> None:
        today = QDate.currentDate()
        self.period_combo.setCurrentIndex(0)
        self.start_date_edit.setDate(today)
        self.end_date_edit.setDate(today)
        self._sync_date_edit_state()

    def refresh_for_today(self) -> None:
        self.period_combo.setCurrentIndex(0)
        self._refresh_stats()

    def _sync_date_edit_state(self) -> None:
        is_custom = self.period_combo.currentData() == "custom"
        self.start_date_edit.setEnabled(is_custom)
        self.end_date_edit.setEnabled(is_custom)

    def _on_period_changed(self) -> None:
        today = QDate.currentDate()
        key = self.period_combo.currentData()
        if key == "today":
            self.start_date_edit.setDate(today)
            self.end_date_edit.setDate(today)
        elif key == "yesterday":
            yesterday = today.addDays(-1)
            self.start_date_edit.setDate(yesterday)
            self.end_date_edit.setDate(yesterday)
        elif key == "last7":
            self.start_date_edit.setDate(today.addDays(-6))
            self.end_date_edit.setDate(today)
        elif key == "last30":
            self.start_date_edit.setDate(today.addDays(-29))
            self.end_date_edit.setDate(today)
        self._sync_date_edit_state()
        if key != "custom":
            self._refresh_stats()

    def _selected_period_bounds(self) -> tuple[datetime, datetime, date, date]:
        start_date = self.start_date_edit.date().toPyDate()
        end_date = self.end_date_edit.date().toPyDate()
        if end_date < start_date:
            start_date, end_date = end_date, start_date

        offset = datetime.now().astimezone().utcoffset() or timedelta(0)
        start_local = datetime.combine(start_date, dt_time.min)
        end_local = datetime.combine(end_date + timedelta(days=1), dt_time.min)
        return start_local - offset, end_local - offset, start_date, end_date

    def _refresh_stats(self) -> None:
        start_utc, end_utc, start_date, end_date = self._selected_period_bounds()
        self._stats = get_time_stats(
            db_path=self.config.db_path,
            start_utc=start_utc,
            end_utc=end_utc,
            sample_interval_seconds=self.config.poll_interval_seconds,
        )
        self._fill_summary(self._stats, start_date, end_date)
        self._apply_filters()

    def _fill_summary(self, stats: TimeStats, start_date: date, end_date: date) -> None:
        total = stats.total_seconds or 0.0
        active_share = (stats.active_seconds / total) if total else 0.0
        work_share = (stats.work_active_seconds / total) if total else 0.0
        distract_share = (stats.distract_active_seconds / total) if total else 0.0
        other_share = (stats.other_active_seconds / total) if total else 0.0
        idle_share = (stats.idle_seconds / total) if total else 0.0

        self.total_card.set_content(
            format_duration(stats.total_seconds),
            f"{start_date.strftime('%d.%m.%Y')} — {end_date.strftime('%d.%m.%Y')}",
        )
        self.active_card.set_content(
            format_duration(stats.active_seconds),
            f"{format_percent(active_share)} периода",
        )
        self.work_card.set_content(
            format_duration(stats.work_active_seconds),
            f"{format_percent(work_share)} периода",
        )
        self.distract_card.set_content(
            format_duration(stats.distract_active_seconds),
            f"{format_percent(distract_share)} периода",
        )
        self.other_card.set_content(
            format_duration(stats.other_active_seconds),
            f"{format_percent(other_share)} периода",
        )
        self.idle_card.set_content(
            format_duration(stats.idle_seconds),
            f"{format_percent(idle_share)} периода",
        )

        segments = [
            ("Рабочее", stats.work_active_seconds),
            ("Отвлекающее", stats.distract_active_seconds),
            ("Прочее", stats.other_active_seconds),
            ("Бездействие", stats.idle_seconds),
        ]
        self.distribution_widget.set_segments(segments)
        self.distribution_legend.setText(
            "  •  ".join(
                (
                    f"<span style='color: {self.distribution_widget.SEGMENT_COLORS[label].name()};'>●</span> "
                    f"{label}: {format_duration(value)} "
                    f"({format_percent(value / total) if total else '0.0%'})"
                )
                for label, value in segments
            )
        )

    def _match_row(self, row: AppUsageRow) -> bool:
        query = self.search_edit.text().strip().lower()
        if query:
            haystack = " ".join([row.app_name, row.last_window_title]).lower()
            if query not in haystack:
                return False

        filter_key = self.category_filter.currentData()
        if filter_key == "work":
            return row.app_type == "Рабочее"
        if filter_key == "distract":
            return row.app_type == "Отвлекающее"
        if filter_key == "other":
            return row.app_type == "Прочее"
        if filter_key == "mixed":
            return row.app_type == "Смешанное"
        return True

    def _apply_filters(self) -> None:
        stats = self._stats
        if stats is None:
            self._visible_rows = []
            self.app_list.clear()
            self.empty_state.show()
            return

        self._visible_rows = [row for row in stats.by_app if self._match_row(row)]
        self.empty_state.setVisible(stats.total_seconds == 0 or not self._visible_rows)

        previous = self._selected_row()
        previous_key = previous.app_name if previous else ""

        self.app_list.clear()
        for row in self._visible_rows:
            item = QListWidgetItem(
                f"{row.app_name or '<без имени>'}\n"
                f"{row.last_window_title or 'Без заголовка'}\n"
                f"{row.app_type} • {format_duration(row.active_seconds)} • {format_percent(row.share_of_active)}"
            )
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.app_list.addItem(item)

        if self.app_list.count() == 0:
            self._fill_details(None)
            return

        target_index = 0
        for index in range(self.app_list.count()):
            item = self.app_list.item(index)
            if item is None:
                continue
            row = item.data(Qt.ItemDataRole.UserRole)
            if row.app_name == previous_key:
                target_index = index
                break
        self.app_list.setCurrentRow(target_index)

    def _selected_row(self) -> AppUsageRow | None:
        item = self.app_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_app_changed(self, current=None, previous=None) -> None:
        del previous
        row = (
            current.data(Qt.ItemDataRole.UserRole)
            if current is not None
            else self._selected_row()
        )
        self._fill_details(row)

    def _fill_details(self, row: AppUsageRow | None) -> None:
        if row is None:
            self.detail_app_label.setText("Ничего не выбрано")
            self.detail_window_label.setText(
                "Выберите приложение слева, чтобы увидеть детали."
            )
            self.detail_type.setText("—")
            self.detail_active.setText("00:00:00")
            self.detail_work.setText("00:00:00")
            self.detail_distract.setText("00:00:00")
            self.detail_other.setText("00:00:00")
            self.detail_share.setText("0.0%")
            return

        self.detail_app_label.setText(row.app_name or "<без имени>")
        self.detail_window_label.setText(row.last_window_title or "Без заголовка окна.")
        self.detail_type.setText(row.app_type)
        self.detail_active.setText(format_duration(row.active_seconds))
        self.detail_work.setText(format_duration(row.work_active_seconds))
        self.detail_distract.setText(format_duration(row.distract_active_seconds))
        self.detail_other.setText(format_duration(row.other_active_seconds))
        self.detail_share.setText(format_percent(row.share_of_active))

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._ensure_screen_sync()
        schedule_window_layout_sync(self, 0)
        if not self._initial_layout_stabilized:
            self._initial_layout_stabilized = True
            QTimer.singleShot(120, self._stabilize_initial_layout)
