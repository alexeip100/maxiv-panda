from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLayout,
    QPushButton,
    QScrollArea,
    QFrame,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWidgetItem,
)


class FlowLayout(QLayout):
    """Compact left-to-right layout that wraps onto additional rows."""

    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 6, v_spacing: int = 4):
        super().__init__(parent)
        self._items: list[QWidgetItem] = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    def addItem(self, item) -> None:
        self._items.append(item)

    def addWidget(self, widget: QWidget) -> None:
        self.addChildWidget(widget)
        self.addItem(QWidgetItem(widget))

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def removeWidget(self, widget: QWidget) -> None:
        for index, item in enumerate(tuple(self._items)):
            if item.widget() is widget:
                self.takeAt(index)
                break
        super().removeWidget(widget)

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0
        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width() + self._h_spacing
            if next_x - self._h_spacing > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + self._v_spacing
                next_x = x + hint.width() + self._h_spacing
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class ShellCheckBox(QCheckBox):
    """Checkbox with a QTreeWidgetItem-compatible setCheckState test hook."""

    def setCheckState(self, *args) -> None:  # noqa: N802 - Qt API spelling
        state = args[-1]
        super().setCheckState(state)


class CoreLevelSelectorBox(QGroupBox):
    """Shared scrollable, wrapping core-level selector used by reference tabs."""

    def __init__(self, parent=None, *, on_select_all=None, on_clear_all=None):
        super().__init__("Available core levels", parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 11, 8, 7)
        layout.setSpacing(5)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setMinimumHeight(58)

        self.host = QWidget(self.scroll)
        self.flow = FlowLayout(self.host, margin=2, h_spacing=6, v_spacing=4)
        self.host.setLayout(self.flow)
        self.host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.scroll.setWidget(self.host)
        layout.addWidget(self.scroll, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)
        self.select_all_button = QPushButton("Select all", self)
        self.clear_all_button = QPushButton("Clear all", self)
        # Qt 6 gives these labels different horizontal size hints. Ignore the
        # label-driven width hints so the equal layout stretch produces truly
        # equal-width action buttons across Qt/platform/font combinations.
        for button in (self.select_all_button, self.clear_all_button):
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        if on_select_all is not None:
            self.select_all_button.clicked.connect(on_select_all)
        if on_clear_all is not None:
            self.clear_all_button.clicked.connect(on_clear_all)
        actions.addWidget(self.select_all_button, 1)
        actions.addWidget(self.clear_all_button, 1)
        layout.addLayout(actions)

    def refresh_extent(self) -> None:
        self.flow.invalidate()
        self.flow.activate()
        width = max(80, self.scroll.viewport().width())
        height = max(0, self.flow.heightForWidth(width))
        self.host.setMinimumHeight(height)
        self.host.updateGeometry()

    def resizeEvent(self, event):  # noqa: N802 - Qt API spelling
        super().resizeEvent(event)
        self.refresh_extent()
