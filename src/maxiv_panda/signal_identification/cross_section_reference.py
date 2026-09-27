from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from .cross_sections import (
    angular_cross_section_curve,
    angular_cross_section_at,
    asymmetry_at,
    available_elements,
    available_subshells,
    cross_section_at,
)
from .dialogs import ElementTileButton
from .reference_data import element_symbols
from .reference_widgets import CoreLevelSelectorBox, FlowLayout, ShellCheckBox
from ..ui_style import register_widget_role


@dataclass(frozen=True)
class CrossSectionSelection:
    element: str
    subshell: str

    @property
    def label(self) -> str:
        return f"{self.element} {self.subshell}"


class CrossSectionReferencePanel(QWidget):
    """Standalone Yeh–Lindau cross-section reference browser."""

    DEFAULT_PHOTON_ENERGY_EV = 1000.0
    DEFAULT_ANGLE_DEG = 48.0

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("crossSectionReferencePanel")
        self.setStyleSheet("""
            QWidget#crossSectionReferencePanel { background: palette(window); }
            QLabel#panelIntro { color: palette(window-text); padding: 2px 4px 5px 4px; }
            QLabel[paneHeading="true"] {
                                font-weight: 600;
                color: palette(window-text);
                padding: 2px 2px 5px 2px;
            }
            QFrame[paneCard="true"] {
                background: palette(alternate-base);
                border: 1px solid palette(mid);
                border-radius: 6px;
            }
            QGroupBox {
                                font-weight: 600;
                color: palette(window-text);
                border: 1px solid palette(mid);
                border-radius: 5px;
                margin-top: 12px;
                padding-top: 9px;
                background: palette(base);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTableWidget {
                background: palette(base);
                alternate-background-color: palette(alternate-base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                gridline-color: palette(mid);
            }
            QHeaderView::section {
                background: palette(button);
                color: palette(button-text);
                font-weight: 600;
                padding: 3px 5px;
                border: 0;
                border-right: 1px solid palette(mid);
                border-bottom: 1px solid palette(mid);
            }
            QPushButton[elementCategory] {
                border: 1px solid palette(mid);
                border-top-width: 4px;
                border-radius: 5px;
                background: palette(base);
                color: palette(button-text);
                                font-weight: 600;
                padding: 2px;
                text-align: center;
            }
            QPushButton[elementCategory]:hover { background: palette(midlight); border-color: palette(mid); }
            QPushButton[elementCategory]:checked {
                background: palette(highlight);
                border-color: palette(highlight);
                color: palette(highlighted-text);
            }
            QPushButton[elementCategory="nonmetal"] { border-top-color: #62a879; }
            QPushButton[elementCategory="halogen"] { border-top-color: #55a7a5; }
            QPushButton[elementCategory="noble"] { border-top-color: #8d83c6; }
            QPushButton[elementCategory="alkali"] { border-top-color: #d3945c; }
            QPushButton[elementCategory="alkaline"] { border-top-color: #d5b85e; }
            QPushButton[elementCategory="metalloid"] { border-top-color: #70a0a0; }
            QPushButton[elementCategory="lanthanide"] { border-top-color: #bf7ba0; }
            QPushButton[elementCategory="actinide"] { border-top-color: #a36f92; }
            QPushButton[elementCategory="posttransition"] { border-top-color: #8199ad; }
            QPushButton[elementCategory="transition"] { border-top-color: #7093b5; }
            QCheckBox#shellChoice {
                background: palette(alternate-base);
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 3px 7px;
                color: palette(text);
            }
            QCheckBox#shellChoice:hover { background: palette(midlight); }
            QCheckBox#shellChoice:checked {
                background: palette(highlight);
                border-color: palette(highlight);
                font-weight: 600;
            }
            QSplitter#referenceSelectorSplitter::handle:vertical {
                height: 5px;
                background: palette(mid);
                border-top: 1px solid palette(light);
                border-bottom: 1px solid palette(mid);
            }
        """)
        self._element_buttons: dict[str, ElementTileButton] = {}
        self._shell_items: dict[tuple[str, str], ShellCheckBox] = {}
        self._photon_marker = None
        self._intersection_markers = []
        self._legend = None
        self._dragging_photon_marker = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(7)

        intro = QLabel(
            "Yeh–Lindau atomic core-level photoionization cross sections. "
            "This reference view is independent of loaded PES data."
        )
        intro.setObjectName("panelIntro")
        intro.setWordWrap(True)
        outer.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, 1)

        left = QFrame(splitter)
        left.setProperty("paneCard", True)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(9, 7, 9, 8)
        left_layout.setSpacing(6)

        elements_heading = QLabel("Elements", left)
        elements_heading.setProperty("paneHeading", True)
        left_layout.addWidget(elements_heading)

        action_row = QHBoxLayout()
        clear_elements = QPushButton("Clear elements", left)
        clear_elements.clicked.connect(self.clear_elements)
        action_row.addWidget(clear_elements)
        action_row.addStretch(1)
        left_layout.addLayout(action_row)

        selector_splitter = QSplitter(Qt.Orientation.Vertical, left)
        selector_splitter.setChildrenCollapsible(False)
        selector_splitter.setObjectName("referenceSelectorSplitter")

        element_area = QWidget(selector_splitter)
        selector_splitter.addWidget(element_area)
        element_layout = QVBoxLayout(element_area)
        element_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(element_area)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget(scroll)
        grid = QGridLayout(host)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        database_elements = set(available_elements())
        columns = 5
        for index, symbol in enumerate(element_symbols()):
            tile = ElementTileButton(symbol, index + 1, host)
            tile.setEnabled(symbol in database_elements)
            if symbol not in database_elements:
                tile.setToolTip(f"No cross-section data available for {symbol}")
            tile.toggled.connect(lambda checked, symbol=symbol: self._on_element_toggled(symbol, checked))
            self._element_buttons[symbol] = tile
            grid.addWidget(tile, index // columns, index % columns)
        for column in range(columns):
            grid.setColumnStretch(column, 1)
        scroll.setWidget(host)
        element_layout.addWidget(scroll, 1)

        self.core_level_selector = CoreLevelSelectorBox(
            selector_splitter, on_select_all=self.select_all_shells, on_clear_all=self.clear_shell_selection
        )
        selector_splitter.addWidget(self.core_level_selector)
        self.shells_box = self.core_level_selector
        self.shell_scroll = self.core_level_selector.scroll
        self.shell_host = self.core_level_selector.host
        self.shell_flow = self.core_level_selector.flow
        self.btn_select_all_shells = self.core_level_selector.select_all_button
        self.btn_clear_all_shells = self.core_level_selector.clear_all_button
        self.btn_select_all_shells.setToolTip("Select every available core level")
        self.btn_clear_all_shells.setToolTip("Clear all core-level selections, the plot, and the values table")
        selector_splitter.setStretchFactor(0, 1)
        selector_splitter.setStretchFactor(1, 0)
        selector_splitter.setSizes([470, 170])
        left_layout.addWidget(selector_splitter, 1)
        self.selector_splitter = selector_splitter
        # Keep the default left pane just wide enough for five element tiles.
        # The splitter remains draggable when the user wants more room.
        left.setMinimumWidth(305)
        register_widget_role(left, "periodic_table_pane")

        right = QFrame(splitter)
        right.setProperty("paneCard", True)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 7, 8, 7)
        right_layout.setSpacing(4)

        controls = QGroupBox("Reference conditions", right)
        self.reference_conditions_box = controls
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(10, 10, 10, 6)
        controls_layout.setSpacing(3)
        condition_row = QHBoxLayout()
        condition_row.setContentsMargins(0, 0, 0, 0)
        condition_row.setSpacing(8)

        photon_label = QLabel("Photon energy:", controls)
        self.sb_photon_energy = QDoubleSpinBox(controls)
        self.sb_photon_energy.setRange(1.0, 100000.0)
        self.sb_photon_energy.setDecimals(2)
        self.sb_photon_energy.setSingleStep(10.0)
        self.sb_photon_energy.setSuffix(" eV")
        self.sb_photon_energy.setValue(self.DEFAULT_PHOTON_ENERGY_EV)
        self.sb_photon_energy.setToolTip("Photon energy marked by the vertical line and used for the values table.")
        self.sb_photon_energy.setMinimumWidth(150)
        self.sb_photon_energy.setMaximumWidth(200)
        condition_row.addWidget(photon_label)
        condition_row.addWidget(self.sb_photon_energy)

        angle_label = QLabel("E-vector–analyzer angle:", controls)
        self.sb_angle = QDoubleSpinBox(controls)
        self.sb_angle.setRange(0.0, 180.0)
        self.sb_angle.setDecimals(1)
        self.sb_angle.setSingleStep(1.0)
        self.sb_angle.setSuffix("°")
        self.sb_angle.setValue(self.DEFAULT_ANGLE_DEG)
        self.sb_angle.setToolTip(
            "Angle between the electric-field vector and analyzer axis. "
            "The plotted geometry-weighted cross section includes the Yeh–Lindau asymmetry parameter."
        )
        self.sb_angle.setMinimumWidth(125)
        self.sb_angle.setMaximumWidth(165)
        condition_row.addWidget(angle_label)
        condition_row.addWidget(self.sb_angle)

        self.cb_legend = QCheckBox("Legend", controls)
        self.cb_legend.setChecked(True)
        self.cb_legend.setToolTip("Show or hide the plot legend. The legend can be dragged with the mouse.")
        condition_row.addWidget(self.cb_legend)
        condition_row.addStretch(1)
        controls_layout.addLayout(condition_row)

        geometry_note = QLabel(
            "σgeom = σ·[1 + β/2·(3cos²θ − 1)]; values remain in Mbarn and guide relative intensities."
        )
        geometry_note.setWordWrap(False)
        geometry_note.setStyleSheet("color: palette(mid);")
        geometry_note.setToolTip(
            "Geometry-weighted atomic cross section. The common 1/(4π) factor is omitted; "
            "analyzer transmission, attenuation, morphology and chemical-state effects are not included."
        )
        controls_layout.addWidget(geometry_note, 0)
        # Let the group box grow with accessibility font size; the previous
        # fixed 82 px cap clipped labels/inputs when the UI font was enlarged.
        controls.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        right_layout.addWidget(controls, 0)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, right)
        right_layout.addWidget(self.toolbar, 0)
        right_layout.addWidget(self.canvas, 1)

        self.values_table = QTableWidget(0, 5, right)
        table_headers = [
            ("Core level", "Selected element and tabulated core level"),
            ("σ atomic (Mb)", "Yeh–Lindau atomic photoionization cross section at the selected photon energy, in megabarns"),
            ("β", "Photoelectron angular-asymmetry parameter interpolated at the selected photon energy"),
            ("Angular factor", "Geometry factor calculated from β and the selected E-vector–analyzer angle"),
            ("σ geometry (Mb)", "Atomic cross section multiplied by the angular factor, in megabarns"),
        ]
        self.values_table.setHorizontalHeaderLabels([label for label, _tooltip in table_headers])
        for column, (_label, tooltip) in enumerate(table_headers):
            header_item = self.values_table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setToolTip(tooltip)
        self.values_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.values_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.values_table.setAlternatingRowColors(True)
        self.values_table.verticalHeader().setVisible(False)
        self.values_table.verticalHeader().setDefaultSectionSize(20)
        self.values_table.horizontalHeader().setMinimumHeight(24)
        header = self.values_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        for column, width in enumerate((110, 145, 70, 115, 150)):
            self.values_table.setColumnWidth(column, width)
        self.values_table.setFixedHeight(116)
        right_layout.addWidget(self.values_table, 0)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([310, 1120])
        self.main_splitter = splitter

        self._clear_plot()

        self.sb_photon_energy.valueChanged.connect(self._on_photon_energy_changed)
        self.sb_angle.valueChanged.connect(self._update_marker_and_values_if_plotted)
        self.cb_legend.toggled.connect(self._set_legend_visible)
        self.canvas.mpl_connect("button_press_event", self._on_plot_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_plot_motion)
        self.canvas.mpl_connect("button_release_event", self._on_plot_release)

    def selected_shells(self) -> list[CrossSectionSelection]:
        selected: list[CrossSectionSelection] = []
        for (element, subshell), checkbox in self._shell_items.items():
            if checkbox.checkState() == Qt.CheckState.Checked:
                selected.append(CrossSectionSelection(element, subshell))
        return sorted(selected, key=lambda item: (item.element, item.subshell))

    def clear_elements(self) -> None:
        for button in self._element_buttons.values():
            button.blockSignals(True)
            button.setChecked(False)
            button.blockSignals(False)
        for checkbox in tuple(self._shell_items.values()):
            self.shell_flow.removeWidget(checkbox)
            checkbox.deleteLater()
        self._shell_items.clear()
        self._refresh_shell_layout()
        self._clear_plot()

    def select_all_shells(self) -> None:
        """Check every shell currently available for the selected elements."""
        for checkbox in self._shell_items.values():
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
        self.plot_selected_cross_sections()

    def clear_shell_selection(self) -> None:
        for checkbox in self._shell_items.values():
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
        self._clear_plot()

    def _on_element_toggled(self, symbol: str, checked: bool) -> None:
        # Capture the symbol explicitly in the signal connection.  This is more
        # reliable than QObject.sender() when the panel is embedded in a tab or
        # signals are delivered through Qt's queued event processing.
        if checked:
            self._append_element_shells(symbol)
        else:
            self._remove_element_shells(symbol)
        self.plot_selected_cross_sections()

    def _append_element_shells(self, element: str) -> None:
        for subshell in available_subshells(element):
            key = (element, subshell)
            if key in self._shell_items:
                continue
            checkbox = ShellCheckBox(f"{element} {subshell}", self.shell_host)
            checkbox.setObjectName("shellChoice")
            checkbox.setToolTip(f"Plot {element} {subshell}")
            checkbox.stateChanged.connect(self._on_shell_item_changed)
            self.shell_flow.addWidget(checkbox)
            self._shell_items[key] = checkbox
        self._refresh_shell_layout()

    def _remove_element_shells(self, element: str) -> None:
        keys = [key for key in self._shell_items if key[0] == element]
        for key in keys:
            checkbox = self._shell_items.pop(key)
            self.shell_flow.removeWidget(checkbox)
            checkbox.deleteLater()
        self._refresh_shell_layout()

    def _refresh_shell_layout(self) -> None:
        """Refresh the dynamically growing wrapped shell selector."""
        self.core_level_selector.refresh_extent()

    def _on_shell_item_changed(self, _state: int) -> None:
        self.plot_selected_cross_sections()

    def _clear_plot(self) -> None:
        self._photon_marker = None
        self._legend = None
        self._dragging_photon_marker = False
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_xlabel("Photon energy (eV)")
        ax.set_ylabel("Geometry-weighted cross section (Mbarn)")
        ax.minorticks_on()
        ax.grid(which="major", linewidth=1.0, alpha=0.68)
        ax.grid(which="minor", linewidth=0.65, alpha=0.38)
        ax.text(
            0.5,
            0.5,
            "Select one or more core levels",
            transform=ax.transAxes,
            ha="center",
            va="center",
        )
        self.values_table.setRowCount(0)
        self.figure.tight_layout(pad=1.0)
        self.canvas.draw_idle()

    def plot_selected_cross_sections(self) -> None:
        selections = self.selected_shells()
        if not selections:
            self._clear_plot()
            return

        angle = float(self.sb_angle.value())
        photon = float(self.sb_photon_energy.value())
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        plotted = 0
        self._intersection_markers = []
        for selection in selections:
            curve = angular_cross_section_curve(selection.element, selection.subshell, angle)
            if curve is None:
                continue
            (line,) = ax.plot(curve.photon_energy_eV, curve.cross_section_mb, label=selection.label)
            # Make the value at the selected photon energy visually explicit.
            # Keep the marker artist so changing photon energy can move it along
            # the already plotted cross-section curve without rebuilding the plot.
            (marker,) = ax.plot(
                [photon], [np.nan], marker="o", linestyle="None",
                markersize=5.0, markerfacecolor=line.get_color(),
                markeredgecolor=line.get_color(), zorder=6, label="_nolegend_",
            )
            marker.set_visible(False)
            try:
                value = angular_cross_section_at(
                    selection.element, selection.subshell, photon, angle
                )
                if value is not None and np.isfinite(value) and float(value) > 0.0:
                    marker.set_data([photon], [float(value)])
                    marker.set_visible(True)
            except Exception:
                pass
            self._intersection_markers.append((selection, marker))
            plotted += 1

        self._photon_marker = ax.axvline(
            photon, linestyle="--", linewidth=1.2, label=f"Selected hν = {photon:g} eV", picker=6
        )
        ax.set_xlabel("Photon energy (eV)")
        ax.set_ylabel("Geometry-weighted cross section (Mbarn)")
        ax.minorticks_on()
        ax.grid(which="major", linewidth=1.0, alpha=0.68)
        ax.grid(which="minor", linewidth=0.65, alpha=0.38)
        if plotted:
            ax.set_yscale("log")
            self._legend = ax.legend(loc="best")
            self._legend.set_draggable(True)
            self._legend.set_visible(self.cb_legend.isChecked())
        else:
            ax.text(0.5, 0.5, "No plottable data for the selected core levels", transform=ax.transAxes, ha="center", va="center")
        self.figure.tight_layout(pad=1.0)
        self._populate_values(selections)
        self.canvas.draw_idle()

    def _populate_values(self, selections: list[CrossSectionSelection]) -> None:
        photon = float(self.sb_photon_energy.value())
        angle = float(self.sb_angle.value())
        self.values_table.setRowCount(len(selections))
        for row, selection in enumerate(selections):
            total = cross_section_at(selection.element, selection.subshell, photon)
            beta = asymmetry_at(selection.element, selection.subshell, photon)
            effective = angular_cross_section_at(selection.element, selection.subshell, photon, angle)
            factor = None
            if beta is not None:
                theta = math.radians(angle)
                factor = 1.0 + 0.5 * beta * (3.0 * math.cos(theta) ** 2 - 1.0)
            values = [
                selection.label,
                self._format_value(total),
                self._format_value(beta, decimals=4),
                self._format_value(factor, decimals=4),
                self._format_value(effective),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.values_table.setItem(row, column, item)
            self.values_table.setRowHeight(row, 20)

    @staticmethod
    def _format_value(value: float | None, *, decimals: int = 6) -> str:
        if value is None or not np.isfinite(value):
            return "N/A"
        magnitude = abs(float(value))
        if magnitude != 0.0 and (magnitude < 1e-4 or magnitude >= 1e4):
            return f"{float(value):.5e}"
        return f"{float(value):.{decimals}g}"

    def _on_photon_energy_changed(self, _value: float | None = None) -> None:
        if not self.selected_shells():
            return
        photon = float(self.sb_photon_energy.value())
        if self._photon_marker is None:
            self.plot_selected_cross_sections()
            return
        self._photon_marker.set_xdata([photon, photon])
        self._photon_marker.set_label(f"Selected hν = {photon:g} eV")
        angle = float(self.sb_angle.value())
        for selection, marker in list(getattr(self, "_intersection_markers", [])):
            if marker is None:
                continue
            try:
                value = angular_cross_section_at(
                    selection.element, selection.subshell, photon, angle
                )
                if value is None or not np.isfinite(value) or float(value) <= 0.0:
                    marker.set_visible(False)
                else:
                    marker.set_data([photon], [float(value)])
                    marker.set_visible(True)
            except Exception:
                marker.set_visible(False)
        if self._legend is not None and self._legend.get_texts():
            # The photon-energy marker is appended after the selected core-level curves.
            self._legend.get_texts()[-1].set_text(f"Selected hν = {photon:g} eV")
        self._populate_values(self.selected_shells())
        self.canvas.draw_idle()

    def _set_legend_visible(self, visible: bool) -> None:
        if self._legend is not None:
            self._legend.set_visible(bool(visible))
            self.canvas.draw_idle()

    def _toolbar_is_active(self) -> bool:
        mode = getattr(self.toolbar, "mode", "")
        return bool(mode)

    def _near_photon_marker(self, event) -> bool:
        if self._photon_marker is None or event.inaxes is None or event.x is None:
            return False
        photon = float(self.sb_photon_energy.value())
        try:
            marker_x = event.inaxes.transData.transform((photon, 1.0))[0]
        except Exception:
            return False
        return abs(float(event.x) - float(marker_x)) <= 8.0

    def _on_plot_press(self, event) -> None:
        if event.button != 1 or self._toolbar_is_active() or not self.selected_shells():
            return
        if self._near_photon_marker(event):
            self._dragging_photon_marker = True

    def _on_plot_motion(self, event) -> None:
        if not self._dragging_photon_marker or event.inaxes is None or event.xdata is None:
            return
        value = min(max(float(event.xdata), self.sb_photon_energy.minimum()), self.sb_photon_energy.maximum())
        self.sb_photon_energy.setValue(value)

    def _on_plot_release(self, _event) -> None:
        self._dragging_photon_marker = False

    def _update_marker_and_values_if_plotted(self) -> None:
        if self.selected_shells():
            self.plot_selected_cross_sections()
