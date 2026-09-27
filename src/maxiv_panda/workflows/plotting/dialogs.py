from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from .settings import AnnotationSettings, LegendSettings


class AnnotationDialog(QDialog):
    def __init__(self, settings: AnnotationSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Plot annotation")
        self._settings = settings
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.edit_text = QLineEdit(settings.text, self)
        form.addRow("Text:", self.edit_text)
        self.chk_visible = QCheckBox("Show annotation", self)
        self.chk_visible.setChecked(settings.visible)
        form.addRow("", self.chk_visible)
        self.spin_size = QSpinBox(self)
        self.spin_size.setRange(6, 48)
        self.spin_size.setValue(settings.fontsize)
        form.addRow("Font size:", self.spin_size)
        style_row = QHBoxLayout()
        self.chk_bold = QCheckBox("Bold", self)
        self.chk_bold.setChecked(settings.bold)
        self.chk_italic = QCheckBox("Italic", self)
        self.chk_italic.setChecked(settings.italic)
        style_row.addWidget(self.chk_bold)
        style_row.addWidget(self.chk_italic)
        style_row.addStretch(1)
        form.addRow("Style:", style_row)
        self.btn_color = QPushButton("Text color", self)
        self._color = settings.color
        self._update_color_button()
        self.btn_color.clicked.connect(self._choose_color)
        form.addRow("Color:", self.btn_color)
        self.chk_background = QCheckBox("White background", self)
        self.chk_background.setChecked(settings.background)
        self.chk_border = QCheckBox("Border", self)
        self.chk_border.setChecked(settings.border)
        box_row = QHBoxLayout()
        box_row.addWidget(self.chk_background)
        box_row.addWidget(self.chk_border)
        box_row.addStretch(1)
        form.addRow("Box:", box_row)
        root.addLayout(form)
        note = QLabel("Drag the annotation directly on the plot to reposition it.", self)
        note.setWordWrap(True)
        root.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _choose_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Choose text color")
        if color.isValid():
            self._color = color.name()
            self._update_color_button()

    def _update_color_button(self) -> None:
        self.btn_color.setStyleSheet(
            f"QPushButton {{ color: {self._color}; border: 1px solid #888; padding: 3px; }}"
        )

    def apply_to(self, settings: AnnotationSettings) -> None:
        settings.text = self.edit_text.text()
        settings.visible = self.chk_visible.isChecked() and bool(settings.text.strip())
        settings.fontsize = self.spin_size.value()
        settings.bold = self.chk_bold.isChecked()
        settings.italic = self.chk_italic.isChecked()
        settings.color = self._color
        settings.background = self.chk_background.isChecked()
        settings.border = self.chk_border.isChecked()


class LegendStyleDialog(QDialog):
    _LOCATIONS = [
        ("Best", "best"), ("Upper right", "upper right"), ("Upper left", "upper left"),
        ("Lower left", "lower left"), ("Lower right", "lower right"),
        ("Centre left", "center left"), ("Centre right", "center right"),
        ("Upper centre", "upper center"), ("Lower centre", "lower center"),
    ]

    def __init__(self, settings: LegendSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Legend style")
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.cmb_location = QComboBox(self)
        for text, value in self._LOCATIONS:
            self.cmb_location.addItem(text, value)
        idx = self.cmb_location.findData(settings.location)
        self.cmb_location.setCurrentIndex(max(0, idx))
        form.addRow("Position:", self.cmb_location)
        self.spin_size = QSpinBox(self)
        self.spin_size.setRange(6, 36)
        self.spin_size.setValue(settings.fontsize)
        form.addRow("Font size:", self.spin_size)
        self.spin_columns = QSpinBox(self)
        self.spin_columns.setRange(1, 6)
        self.spin_columns.setValue(settings.columns)
        form.addRow("Columns:", self.spin_columns)
        self.chk_frame = QCheckBox("Show frame", self)
        self.chk_frame.setChecked(settings.frame)
        form.addRow("", self.chk_frame)
        root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def apply_to(self, settings: LegendSettings) -> None:
        settings.location = str(self.cmb_location.currentData())
        settings.anchor = None
        settings.fontsize = self.spin_size.value()
        settings.columns = self.spin_columns.value()
        settings.frame = self.chk_frame.isChecked()
