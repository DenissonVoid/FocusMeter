from __future__ import annotations

from typing import cast

from PyQt5.QtCore import QPoint, QTimer, Qt
from PyQt5.QtGui import QColor, QMouseEvent
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)


def install_shadow(
    widget: QWidget,
    blur_radius: int = 38,
    y_offset: int = 12,
    alpha: int = 70,
) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)


def prepare_frameless_window(
    window: QWidget,
    *,
    use_tool: bool = False,
    always_on_top: bool = False,
) -> None:
    flags = cast(Qt.WindowFlags, Qt.WindowType.FramelessWindowHint)
    flags |= Qt.WindowType.Tool if use_tool else Qt.WindowType.Window
    if always_on_top:
        flags |= Qt.WindowType.WindowStaysOnTopHint
    window.setWindowFlags(flags)
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)


def schedule_window_layout_sync(window: QWidget, delay_ms: int = 0) -> None:
    timer = getattr(window, "_layout_sync_timer", None)
    if not isinstance(timer, QTimer):
        timer = QTimer(window)
        timer.setSingleShot(True)
        setattr(window, "_layout_sync_timer", timer)

        def _sync() -> None:
            if window is None:
                return
            window.ensurePolished()
            _activate_widget_layouts(window)
            window.updateGeometry()
            window.update()

        timer.timeout.connect(_sync)

    timer.start(max(delay_ms, 0))


def _activate_widget_layouts(widget: QWidget) -> None:
    layout = widget.layout()
    if layout is not None:
        layout.invalidate()
        layout.activate()
    for child in widget.findChildren(QWidget):
        child_layout = child.layout()
        if child_layout is not None:
            child_layout.invalidate()
            child_layout.activate()
        child.updateGeometry()


class WindowTitleBar(QFrame):
    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        show_minimize: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self._drag_origin: QPoint | None = None
        self.setObjectName("WindowTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 12, 10)
        layout.setSpacing(10)

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("WindowTitle")
        title_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setObjectName("WindowSubtitle")
        self.subtitle_label.setVisible(bool(subtitle))
        title_layout.addWidget(self.subtitle_label)
        layout.addLayout(title_layout, 1)

        self.minimize_button = QPushButton("–")
        self.minimize_button.setObjectName("ChromeButton")
        self.minimize_button.setVisible(show_minimize)
        self.minimize_button.clicked.connect(self._minimize_window)
        layout.addWidget(self.minimize_button)

        self.close_button = QPushButton("×")
        self.close_button.setObjectName("ChromeCloseButton")
        self.close_button.clicked.connect(self._close_window)
        layout.addWidget(self.close_button)

    def set_title(self, title: str, subtitle: str = "") -> None:
        self.title_label.setText(title)
        self.subtitle_label.setText(subtitle)
        self.subtitle_label.setVisible(bool(subtitle))

    def _window(self) -> QWidget:
        return self.window()

    def _minimize_window(self) -> None:
        self._window().showMinimized()

    def _close_window(self) -> None:
        self._window().close()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPos() - self._window().frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            self._drag_origin is not None
            and bool(event.buttons() & Qt.MouseButton.LeftButton)
        ):
            self._window().move(event.globalPos() - self._drag_origin)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_origin = None
        super().mouseReleaseEvent(event)


def build_window_shell(
    host: QWidget,
    *,
    title: str,
    subtitle: str = "",
    show_minimize: bool = True,
    body_margins: tuple[int, int, int, int] = (16, 14, 16, 14),
    body_spacing: int = 14,
) -> tuple[QWidget, QVBoxLayout, WindowTitleBar, QSizeGrip]:
    outer_layout = QVBoxLayout(host)
    outer_layout.setContentsMargins(10, 10, 10, 10)
    outer_layout.setSpacing(0)

    surface = QFrame()
    surface.setObjectName("WindowSurface")
    install_shadow(surface)
    outer_layout.addWidget(surface)

    surface_layout = QVBoxLayout(surface)
    surface_layout.setContentsMargins(1, 1, 1, 1)
    surface_layout.setSpacing(0)

    title_bar = WindowTitleBar(
        title=title,
        subtitle=subtitle,
        show_minimize=show_minimize,
        parent=surface,
    )
    surface_layout.addWidget(title_bar)

    body = QWidget(surface)
    body.setObjectName("WindowBody")
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(*body_margins)
    body_layout.setSpacing(body_spacing)
    surface_layout.addWidget(body, 1)

    footer_layout = QHBoxLayout()
    footer_layout.setContentsMargins(0, 0, 6, 6)
    footer_layout.addStretch()
    size_grip = QSizeGrip(surface)
    size_grip.setObjectName("WindowSizeGrip")
    footer_layout.addWidget(size_grip, 0, Qt.AlignmentFlag.AlignBottom)
    surface_layout.addLayout(footer_layout)

    return body, body_layout, title_bar, size_grip
