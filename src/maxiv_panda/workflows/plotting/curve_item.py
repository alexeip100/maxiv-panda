from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QMouseEvent
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QHBoxLayout,
    QApplication, QLabel, QListWidget, QPushButton, QWidget,
)

from ...utils.colors import mpl_color_to_hex
from .model import PlottedCurve


class DragHandle(QLabel):
    """Large, explicit drag target for reordering a plotted curve."""

    drag_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("☰", parent)
        self._press_pos: QPoint | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(30, 30)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self.setToolTip("Drag to move this curve up or down")
        self.setStyleSheet(
            "QLabel { border: 1px solid palette(mid); border-radius: 3px; "
            "background: palette(button); color: palette(button-text); "
            "font-size: 16px; font-weight: bold; }"
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if (
            self._press_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._press_pos).manhattanLength() >= 4
        ):
            self._press_pos = None
            self.drag_requested.emit()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._press_pos = None
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        super().mouseReleaseEvent(event)


class DragNameField(QLabel):
    """Read-only curve name that forwards drags to the native list view."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.setMinimumWidth(150)
        self.setMinimumHeight(28)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self.setStyleSheet(
            "QLabel { background: palette(base); color: palette(text); "
            "border: 1px solid palette(mid); border-radius: 2px; padding: 3px 6px; }"
        )

    def _curve_list(self) -> QListWidget | None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QListWidget):
                return parent
            parent = parent.parentWidget()
        return None

    def _forward_mouse_event(self, event: QMouseEvent) -> bool:
        curve_list = self._curve_list()
        if curve_list is None:
            return False
        viewport = curve_list.viewport()
        viewport_pos = self.mapTo(viewport, event.position().toPoint())
        forwarded = QMouseEvent(
            event.type(),
            QPointF(viewport_pos),
            event.globalPosition(),
            event.button(),
            event.buttons(),
            event.modifiers(),
        )
        QApplication.sendEvent(viewport, forwarded)
        return True

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            if self._forward_mouse_event(event):
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.buttons() & Qt.MouseButton.LeftButton and self._forward_mouse_event(event):
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        if event.button() == Qt.MouseButton.LeftButton and self._forward_mouse_event(event):
            event.accept()
            return
        super().mouseReleaseEvent(event)


class CurveItemWidget(QWidget):
    changed = pyqtSignal()
    remove_requested = pyqtSignal(object)
    drag_requested = pyqtSignal(object)

    _STYLES = [
        ("Solid", "-"),
        ("Dashed", "--"),
        ("Dotted", ":"),
        ("Dash-dot", "-."),
        ("Markers", "None"),
    ]

    def __init__(
        self,
        curve: PlottedCurve,
        parent: QWidget | None = None,
        *,
        legend_mode: str = "Curve name",
    ) -> None:
        super().__init__(parent)
        self.curve = curve
        self.legend_mode = str(legend_mode)
        row = QHBoxLayout(self)
        row.setContentsMargins(3, 4, 3, 4)
        row.setSpacing(5)

        self.drag_handle = DragHandle(self)
        row.addWidget(self.drag_handle)

        self.btn_remove = QPushButton("×", self)
        self.btn_remove.setFixedSize(24, 24)
        self.btn_remove.setToolTip("Remove curve")
        row.addWidget(self.btn_remove)

        self.chk_visible = QCheckBox(self)
        self.chk_visible.setChecked(curve.visible)
        self.chk_visible.setToolTip("Show or hide curve")
        row.addWidget(self.chk_visible)

        self.btn_color = QPushButton("", self)
        self.btn_color.setFixedSize(24, 20)
        self.btn_color.setToolTip("Choose curve color")
        row.addWidget(self.btn_color)

        self.cmb_style = QComboBox(self)
        self.cmb_style.setToolTip("Line style")
        for text, value in self._STYLES:
            self.cmb_style.addItem(text, value)
        idx = max(0, self.cmb_style.findData(curve.linestyle))
        self.cmb_style.setCurrentIndex(idx)
        self.cmb_style.setMaximumWidth(88)
        row.addWidget(self.cmb_style)

        self.spin_width = QDoubleSpinBox(self)
        self.spin_width.setRange(0.5, 8.0)
        self.spin_width.setSingleStep(0.5)
        self.spin_width.setDecimals(1)
        self.spin_width.setValue(curve.linewidth)
        self.spin_width.setSuffix(" pt")
        self.spin_width.setToolTip("Line width or marker size")
        self.spin_width.setMaximumWidth(78)
        row.addWidget(self.spin_width)

        # Keep one uncluttered, immutable original name in every legend mode.
        # The wide name field is also a drag target; custom legend/export names
        # remain visible only in the plot legend and exported CSV header.
        self.edit_name = DragNameField(curve.title or "Curve", self)
        row.addWidget(self.edit_name, 1)

        self.drag_handle.drag_requested.connect(lambda: self.drag_requested.emit(self))
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self))
        self.chk_visible.toggled.connect(self._sync)
        self.btn_color.clicked.connect(self._choose_color)
        self.cmb_style.currentIndexChanged.connect(self._sync)
        self.spin_width.valueChanged.connect(self._sync)
        self._update_color_button()

    def current_export_name(self) -> str:
        if self.legend_mode == "Custom":
            return self.curve.custom_name.strip() or "<select curve name>"
        return (self.curve.title or "Curve").strip() or "Curve"

    def set_legend_mode(self, mode: str) -> None:
        # The curve list deliberately stays unchanged across legend modes.
        self.legend_mode = str(mode)

    def _choose_color(self) -> None:
        initial = QColor(mpl_color_to_hex(self.curve.color or "#1f77b4"))
        color = QColorDialog.getColor(initial, self, "Choose curve color")
        if not color.isValid():
            return
        self.curve.color = color.name()
        self._update_color_button()
        self.changed.emit()

    def _update_color_button(self) -> None:
        color = mpl_color_to_hex(self.curve.color or "#1f77b4")
        self.btn_color.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 1px solid #666; border-radius: 2px; }}"
        )

    def _sync(self, *_args) -> None:
        self.curve.visible = self.chk_visible.isChecked()
        self.curve.linestyle = str(self.cmb_style.currentData())
        self.curve.linewidth = float(self.spin_width.value())
        self.changed.emit()
