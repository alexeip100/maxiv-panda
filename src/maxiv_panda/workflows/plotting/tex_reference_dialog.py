from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


_TEX_EXAMPLES = [
    ("Subscript", r"S 2p$_{3/2}$", "S 2p₃⁄₂"),
    ("Superscript", r"Fe$^{3+}$", "Fe³⁺"),
    ("Greek", r"$\alpha$", "α"),
    ("Plus/minus", r"$\pm$", "±"),
    ("Degree", r"$^\circ$", "°"),
    ("Multiply", r"$\times$", "×"),
    ("Math variable", r"$E_F$", "E_F"),
]


class TexReferenceDialog(QDialog):
    """Compact TeX-style legend-label reference.

    When a target line edit is supplied, double-clicking an example inserts its
    syntax at the cursor.  Without a target, the syntax is copied to the
    clipboard instead.
    """

    def __init__(self, parent: QWidget | None = None, *, target: QLineEdit | None = None) -> None:
        super().__init__(parent)
        self._target = target
        self.setWindowTitle("TeX label reference")
        self.setModal(False)
        self.resize(470, 315)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        intro = QLabel(
            "Matplotlib TeX-style notation is supported in custom legend labels. "
            "Double-click an example to insert it." if target is not None else
            "Matplotlib TeX-style notation is supported in custom legend labels. "
            "Double-click an example to copy its syntax."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.table = QTableWidget(len(_TEX_EXAMPLES), 3, self)
        self.table.setHorizontalHeaderLabels(["Format", "Type", "Looks like"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        for row, (label, syntax, rendered) in enumerate(_TEX_EXAMPLES):
            self.table.setItem(row, 0, QTableWidgetItem(label))
            self.table.setItem(row, 1, QTableWidgetItem(syntax))
            self.table.setItem(row, 2, QTableWidgetItem(rendered))
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.resizeSection(0, 105)
        header.resizeSection(1, 180)
        root.addWidget(self.table, 1)

        footer = QHBoxLayout()
        self.lbl_action = QLabel("", self)
        self.lbl_action.setStyleSheet("color: palette(mid);")
        footer.addWidget(self.lbl_action, 1)
        close = QPushButton("Close", self)
        close.clicked.connect(self.close)
        footer.addWidget(close)
        root.addLayout(footer)

        self.table.cellDoubleClicked.connect(self._activate_row)

    def _activate_row(self, row: int, _column: int) -> None:
        if not (0 <= row < len(_TEX_EXAMPLES)):
            return
        syntax = _TEX_EXAMPLES[row][1]
        if self._target is not None:
            self._target.insert(syntax)
            self._target.setFocus(Qt.FocusReason.OtherFocusReason)
            self.lbl_action.setText("Inserted")
        else:
            QApplication.clipboard().setText(syntax)
            self.lbl_action.setText("Copied")


class LegendNameDialog(QDialog):
    """Custom legend-name editor with an inline TeX reference."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Legend name")
        self.setModal(True)
        self._reference_dialog: TexReferenceDialog | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        row = QHBoxLayout()
        self.edit = QLineEdit(self)
        self.edit.setText(text)
        self.edit.setPlaceholderText(r"e.g. S 2p$_{3/2}$")
        self.edit.setToolTip(
            r"Custom legend text. TeX-style notation is supported, e.g. S 2p$_{3/2}$ or Fe$^{3+}$."
        )
        self.btn_help = QPushButton("?", self)
        self.btn_help.setFixedWidth(28)
        self.btn_help.setToolTip("Show a short TeX-style formatting reference")
        row.addWidget(self.edit, 1)
        row.addWidget(self.btn_help)
        root.addLayout(row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        ok = QPushButton("OK", self)
        cancel = QPushButton("Cancel", self)
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(ok)
        buttons.addWidget(cancel)
        root.addLayout(buttons)

        self.btn_help.clicked.connect(self._show_reference)
        self.edit.selectAll()
        self.edit.setFocus()

    def _show_reference(self) -> None:
        if self._reference_dialog is None:
            self._reference_dialog = TexReferenceDialog(self, target=self.edit)
        self._reference_dialog.show()
        self._reference_dialog.raise_()
        self._reference_dialog.activateWindow()

    def text(self) -> str:
        return self.edit.text()
