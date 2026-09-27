from __future__ import annotations

"""Compact application settings dialog."""

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)

from ..ui_metrics import InterfaceDensity
from ..ui_style import (
    UiConfiguration,
    UiTheme,
    apply_dialog_metrics,
    apply_control_metrics,
    current_ui_metrics,
)


class SettingsDialog(QDialog):
    """Edit lightweight global FlexPES settings."""

    def __init__(self, config: UiConfiguration, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(340)

        root = QVBoxLayout(self)
        apply_dialog_metrics(root)

        group = QGroupBox("Appearance", self)
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        metrics = current_ui_metrics()
        form.setHorizontalSpacing(max(8, metrics.layout_spacing + 4))
        form.setVerticalSpacing(metrics.layout_spacing)

        self.theme_combo = QComboBox(group)
        self.theme_combo.addItem("System", UiTheme.SYSTEM.value)
        self.theme_combo.addItem("Light", UiTheme.LIGHT.value)
        self.theme_combo.addItem("Dark", UiTheme.DARK.value)
        theme_index = self.theme_combo.findData(config.theme.value)
        self.theme_combo.setCurrentIndex(max(0, theme_index))
        self.theme_combo.setToolTip("Choose the application color theme.")
        form.addRow("Theme:", self.theme_combo)

        self.density_combo = QComboBox(group)
        self.density_combo.addItem("Automatic", InterfaceDensity.AUTOMATIC.value)
        self.density_combo.addItem("Standard", InterfaceDensity.STANDARD.value)
        self.density_combo.addItem("Compact", InterfaceDensity.COMPACT.value)
        density_index = self.density_combo.findData(config.density.value)
        self.density_combo.setCurrentIndex(max(0, density_index))
        self.density_combo.setToolTip("Automatic chooses Standard or Compact from the available screen size.")
        form.addRow("Interface density:", self.density_combo)

        self.font_combo = QComboBox(group)
        self.font_combo.addItem("Default (current)", 0)
        self.font_combo.addItem("Larger (+1 pt)", 1)
        self.font_combo.addItem("Largest (+2 pt)", 2)
        font_index = self.font_combo.findData(int(config.font_offset_pt))
        self.font_combo.setCurrentIndex(max(0, font_index))
        self.font_combo.setToolTip("Enlarges the Qt interface font. Plot/figure fonts are unchanged.")
        form.addRow("UI font size:", self.font_combo)

        root.addWidget(group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        apply_control_metrics(self)

    def configuration(self) -> UiConfiguration:
        theme = UiTheme(str(self.theme_combo.currentData()))
        density = InterfaceDensity(str(self.density_combo.currentData()))
        font_offset = int(self.font_combo.currentData())
        return UiConfiguration(density=density, font_offset_pt=font_offset, theme=theme)
