from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem


class CurveListWidget(QListWidget):
    """Checkable, editable curve list with an easy full-row drag target."""

    def __init__(self, changed_callback: Callable[[], None], parent=None) -> None:
        super().__init__(parent)
        self._changed_callback = changed_callback
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setToolTip(
            "Drag anywhere on a row to change curve order. "
            "Double-click a name to edit it; uncheck a row to hide the curve."
        )
        self.itemChanged.connect(lambda _item: self._changed_callback())
        self.model().rowsMoved.connect(lambda *_args: self._changed_callback())

    def add_curve(self, curve: object, *, checked: bool = True) -> QListWidgetItem:
        title = str(getattr(curve, "title", "")).strip() or "Curve"
        item = QListWidgetItem(f"☰  {title}")
        item.setData(Qt.ItemDataRole.UserRole, curve)
        item.setData(Qt.ItemDataRole.UserRole + 1, title)
        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsDragEnabled
            | Qt.ItemFlag.ItemIsDropEnabled
        )
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        item.setSizeHint(QSize(0, 34))
        self.addItem(item)
        return item

    def curves_in_order(self, *, checked_only: bool = False) -> list[object]:
        curves: list[object] = []
        for row in range(self.count()):
            item = self.item(row)
            if checked_only and item.checkState() != Qt.CheckState.Checked:
                continue
            curve = item.data(Qt.ItemDataRole.UserRole)
            if curve is None:
                continue
            text = item.text().strip()
            if text.startswith("☰"):
                text = text[1:].strip()
            setattr(curve, "title", text)
            item.setData(Qt.ItemDataRole.UserRole + 1, text)
            curves.append(curve)
        return curves
