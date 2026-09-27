from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QBrush
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
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
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox
from ..ui_style import register_widget_role

from .matcher import PeakAssignment
from .reference_data import element_symbols


_NONMETALS = {"H", "C", "N", "O", "P", "S", "Se"}
_HALOGENS = {"F", "Cl", "Br", "I", "At"}
_NOBLE_GASES = {"He", "Ne", "Ar", "Kr", "Xe", "Rn"}
_ALKALI = {"Li", "Na", "K", "Rb", "Cs", "Fr"}
_ALKALINE_EARTH = {"Be", "Mg", "Ca", "Sr", "Ba", "Ra"}
_METALLOIDS = {"B", "Si", "Ge", "As", "Sb", "Te", "Po"}
_LANTHANIDES = {"La", "Ce", "Pr", "Nd", "Pm", "Sm", "Eu", "Gd", "Tb", "Dy", "Ho", "Er", "Tm", "Yb", "Lu"}
_ACTINIDES = {"Ac", "Th", "Pa", "U", "Np", "Pu", "Am", "Cm", "Bk", "Cf", "Es", "Fm", "Md", "No", "Lr"}
_POST_TRANSITION = {"Al", "Ga", "In", "Sn", "Tl", "Pb", "Bi", "Nh", "Fl", "Mc", "Lv"}


def _reliability_palette(value: float) -> tuple[str, str]:
    """Return subtle background and text colors for a 0..100 factor."""
    score = float(value)
    if score >= 75:
        return "#dff1e3", "#245c31"
    if score >= 55:
        return "#fff2cc", "#6b5600"
    if score >= 35:
        return "#fce4c5", "#7a4300"
    return "#f6d6d6", "#7a2525"


def _factor_html(label: str, value: float) -> str:
    percent = max(0.0, min(100.0, float(value) * 100.0))
    background, foreground = _reliability_palette(percent)
    return (
        "<tr><td style='padding:2px 8px 2px 0'>" + label + "</td>"
        f"<td style='padding:2px 6px;background:{background};color:{foreground};"
        "font-weight:600;text-align:right'>"
        f"{percent:.0f}%</td></tr>"
    )




class SortableTableWidgetItem(QTableWidgetItem):
    """Table item with an explicit sort key independent of displayed text."""

    def __init__(self, text: str, sort_value=None):
        super().__init__(text)
        self._sort_value = text if sort_value is None else sort_value

    def __lt__(self, other):
        if isinstance(other, SortableTableWidgetItem):
            try:
                return self._sort_value < other._sort_value
            except TypeError:
                return str(self._sort_value) < str(other._sort_value)
        return super().__lt__(other)


def _element_category(symbol: str) -> str:
    if symbol in _NONMETALS:
        return "nonmetal"
    if symbol in _HALOGENS:
        return "halogen"
    if symbol in _NOBLE_GASES:
        return "noble"
    if symbol in _ALKALI:
        return "alkali"
    if symbol in _ALKALINE_EARTH:
        return "alkaline"
    if symbol in _METALLOIDS:
        return "metalloid"
    if symbol in _LANTHANIDES:
        return "lanthanide"
    if symbol in _ACTINIDES:
        return "actinide"
    if symbol in _POST_TRANSITION:
        return "posttransition"
    return "transition"


class ElementTileButton(QPushButton):
    """Compact checkable element tile inspired by periodic-table cells."""

    def __init__(self, symbol: str, atomic_number: int, parent: QWidget | None = None):
        super().__init__(parent)
        self.symbol = symbol
        self.atomic_number = atomic_number
        self.setCheckable(True)
        self.setText("")
        self.setAccessibleName(f"{symbol}, atomic number {atomic_number}")
        self.setProperty("elementCategory", _element_category(symbol))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        register_widget_role(self, "element_tile")
        app = QApplication.instance()
        try:
            offset = int(app.property("flexpes_ui_font_offset_pt") or 0) if app is not None else 0
        except Exception:
            offset = 0
        tile_min = 48 + 3 * max(0, offset)
        self.setMinimumSize(tile_min, tile_min)
        self.setMaximumHeight(58 + 3 * max(0, offset))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip(f"{symbol} (atomic number {atomic_number})")

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        colour = self.palette().buttonText().color()
        painter.setPen(colour)

        number_font = self.font()
        number_font.setPointSizeF(max(7.0, self.font().pointSizeF() * 0.72))
        number_font.setBold(False)
        painter.setFont(number_font)
        painter.drawText(QRectF(7.0, 5.0, self.width() - 12.0, 15.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, str(self.atomic_number))

        symbol_font = self.font()
        symbol_font.setPointSizeF(max(12.0, self.font().pointSizeF() * 1.18))
        symbol_font.setBold(True)
        painter.setFont(symbol_font)
        painter.drawText(QRectF(2.0, 11.0, self.width() - 4.0, self.height() - 13.0), Qt.AlignmentFlag.AlignCenter, self.symbol)


@dataclass
class IdentificationSettings:
    photon_energy: float | None = None
    tolerance_eV: float = 5.0
    prominence_fraction: float = 0.005
    include_auger: bool = True
    include_second_order: bool = False
    small_charging_possible: bool = False
    elements: set[str] | None = None
    sample_mode: str = "Automatic (prefer solids)"
    valence_band_cutoff_eV: float = 15.0


class SignalIdentificationDialog(QDialog):
    apply_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None, *, settings: IdentificationSettings, assignments: Iterable[PeakAssignment], energy_scale: str):
        super().__init__(parent)
        self.setWindowTitle("Identify signals")
        # Use logical Qt pixels so the dialog remains well proportioned on
        # ordinary and high-DPI/4K displays.  Cap the initial size to the
        # available screen rather than assuming a particular physical pixel
        # resolution.
        default_width, default_height = 1100, 720
        try:
            screen = self.screen() or (parent.screen() if parent is not None else None)
            if screen is not None:
                available = screen.availableGeometry()
                default_width = min(default_width, max(900, int(available.width() * 0.90)))
                default_height = min(default_height, max(600, int(available.height() * 0.88)))
        except Exception:
            pass
        self.resize(default_width, default_height)
        self.setMinimumSize(860, 580)
        self.setObjectName("identifySignalsDialog")
        self.setStyleSheet("""
            QDialog#identifySignalsDialog { background: palette(window); }
            QLabel#dialogIntro { color: palette(window-text); padding: 2px 4px 6px 4px; }
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
                margin-top: 10px;
                padding-top: 8px;
                background: palette(base);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
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
                padding: 5px;
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
            QSplitter::handle { background: palette(mid); margin: 0 2px; }
            QSplitter::handle:hover { background: palette(highlight); }
        """)
        self._element_checks: dict[str, ElementTileButton] = {}

        outer = QVBoxLayout(self)
        intro = QLabel(
            "Assignments are restricted to the expected elements selected below and are shown only when the matching criteria are satisfied. "
            "Uncertain peaks remain unidentified."
        )
        intro.setWordWrap(True)
        intro.setObjectName("dialogIntro")
        outer.addWidget(intro)

        settings_box = QGroupBox("Identification settings", self)
        settings_columns = QHBoxLayout(settings_box)
        settings_columns.setContentsMargins(10, 12, 10, 8)
        settings_columns.setSpacing(22)
        settings_left = QFormLayout()
        settings_right = QFormLayout()
        for form in (settings_left, settings_right):
            form.setContentsMargins(0, 0, 0, 0)
            form.setHorizontalSpacing(8)
            form.setVerticalSpacing(5)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        settings_columns.addLayout(settings_left, 1)
        settings_columns.addLayout(settings_right, 1)

        self.sb_photon = QDoubleSpinBox(settings_box)
        self.sb_photon.setRange(0.0, 100000.0)
        self.sb_photon.setDecimals(3)
        self.sb_photon.setSingleStep(0.1)
        self.sb_photon.setSuffix(" eV")
        self.sb_photon.setSpecialValueText("Unknown")
        self.sb_photon.setValue(float(settings.photon_energy or 0.0))
        settings_left.addRow("Photon energy:", self.sb_photon)

        self.sb_tolerance = QDoubleSpinBox(settings_box)
        self.sb_tolerance.setRange(0.05, 20.0)
        self.sb_tolerance.setDecimals(2)
        self.sb_tolerance.setSingleStep(0.1)
        self.sb_tolerance.setSuffix(" eV")
        self.sb_tolerance.setValue(float(settings.tolerance_eV))
        settings_left.addRow("Matching tolerance:", self.sb_tolerance)

        self.sb_prominence = QDoubleSpinBox(settings_box)
        self.sb_prominence.setRange(0.1, 50.0)
        self.sb_prominence.setDecimals(1)
        self.sb_prominence.setSingleStep(0.1)
        self.sb_prominence.setSuffix(" % of signal range")
        self.sb_prominence.setValue(float(settings.prominence_fraction) * 100.0)
        settings_left.addRow("Peak prominence:", self.sb_prominence)

        self.sb_vb_cutoff = QDoubleSpinBox(settings_box)
        self.sb_vb_cutoff.setRange(0.0, 30.0)
        self.sb_vb_cutoff.setDecimals(1)
        self.sb_vb_cutoff.setSingleStep(0.1)
        self.sb_vb_cutoff.setSuffix(" eV BE")
        self.sb_vb_cutoff.setValue(float(settings.valence_band_cutoff_eV))
        # Survey-spectrum values occupy only a small numerical range.  Keep
        # the editors compact instead of stretching them across the pane.
        self.sb_photon.setFixedWidth(145)
        self.sb_tolerance.setFixedWidth(125)
        self.sb_prominence.setFixedWidth(180)
        self.sb_vb_cutoff.setFixedWidth(135)
        self.sb_vb_cutoff.setToolTip(
            "Binding energies from 0 eV up to this cutoff are treated as one valence-band region. "
            "No individual atomic-level assignments are made there."
        )
        settings_left.addRow("Valence-band cutoff:", self.sb_vb_cutoff)

        self.cb_auger = QCheckBox("Include Auger lines", settings_box)
        self.cb_auger.setChecked(bool(settings.include_auger))
        settings_right.addRow(self.cb_auger)
        self.cb_second = QCheckBox("Include second-order photoemission", settings_box)
        self.cb_second.setChecked(bool(settings.include_second_order))
        settings_right.addRow(self.cb_second)
        self.cb_small_charging = QCheckBox("Small charging possible", settings_box)
        self.cb_small_charging.setChecked(bool(settings.small_charging_possible))
        self.cb_small_charging.setToolTip(
            "Search up to +10 eV in binding energy only after the strongest resolved "
            "photoelectron feature of an element forms a physically consistent anchor. "
            "Weaker lines must support approximately the same positive shift."
        )
        settings_right.addRow(self.cb_small_charging)
        self.combo_sample = QComboBox(settings_box)
        self.combo_sample.addItems(["Automatic (prefer solids)", "Solid / condensed phase", "Gas phase", "Search both equally"])
        idx = self.combo_sample.findText(str(settings.sample_mode))
        self.combo_sample.setCurrentIndex(max(0, idx))
        self.combo_sample.setMaximumWidth(225)
        settings_right.addRow("Reference mode:", self.combo_sample)
        settings_right.addRow("Energy scale:", QLabel(str(energy_scale), settings_box))
        elements_box = QGroupBox("Select at least one", self)
        elements_outer = QVBoxLayout(elements_box)
        buttons = QHBoxLayout()
        btn_all = QPushButton("Select all", elements_box)
        btn_clear = QPushButton("Clear", elements_box)
        # These are explicit actions, not dialog defaults.  In particular,
        # pressing Enter while editing a numeric field must never select every
        # element accidentally.
        for button in (btn_all, btn_clear):
            button.setAutoDefault(False)
            button.setDefault(False)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        buttons.addWidget(btn_all)
        buttons.addWidget(btn_clear)
        buttons.addStretch(1)
        elements_outer.addLayout(buttons)
        elements_scroll = QScrollArea(elements_box)
        elements_scroll.setWidgetResizable(True)
        elements_scroll.setFrameShape(QFrame.Shape.NoFrame)
        elements_host = QWidget(elements_scroll)
        grid = QGridLayout(elements_host)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(4)
        selected = set(settings.elements or ())
        element_columns = 5
        for index, symbol in enumerate(element_symbols()):
            tile = ElementTileButton(symbol, index + 1, elements_host)
            tile.setChecked(symbol in selected)
            self._element_checks[symbol] = tile
            grid.addWidget(tile, index // element_columns, index % element_columns)
        for column in range(element_columns):
            grid.setColumnStretch(column, 1)
        elements_scroll.setWidget(elements_host)
        elements_outer.addWidget(elements_scroll, 1)
        btn_all.clicked.connect(lambda: self._set_all_elements(True))
        btn_clear.clicked.connect(lambda: self._set_all_elements(False))

        self.table = QTableWidget(0, 7, self)
        headers = [
            ("Peak", "Detected peak position on the displayed energy scale."),
            ("Best assignment", "Highest-ranked accepted PE or Auger assignment."),
            ("Type", "Signal type: photoelectron (PE) or Auger."),
            ("Reference", "Expected position of the selected reference on the displayed scale."),
            ("ΔE", "Peak position minus reference position, in eV."),
            ("Reliability", "Estimated assignment reliability (0–100%)."),
            ("Alternatives / reason", "Other candidate assignments, or the reason why the peak was left unassigned."),
        ]
        self.table.setHorizontalHeaderLabels([label for label, _tip in headers])
        for column, (_label, tooltip) in enumerate(headers):
            header_item = self.table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setToolTip(tooltip)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self._sortable_columns = {0, 2, 5}
        self._sort_column = 0
        self._sort_order = Qt.SortOrder.DescendingOrder
        self._current_assignments = list(assignments)
        header = self.table.horizontalHeader()
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(self._sort_column, self._sort_order)
        header.sectionClicked.connect(self._sort_table_by_column)
        self._populate(self._current_assignments)
        self.table.sortItems(self._sort_column, self._sort_order)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

        left_pane = QFrame(self)
        left_pane.setProperty("paneCard", True)
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(10, 8, 10, 10)
        left_layout.setSpacing(8)
        left_heading = QLabel("Signal identification", left_pane)
        left_heading.setProperty("paneHeading", True)
        results_heading = QLabel("Detected peaks and assignments", left_pane)
        results_heading.setProperty("paneHeading", True)
        self.charging_summary = QLabel(left_pane)
        self.charging_summary.setObjectName("chargingSummary")
        self.charging_summary.setTextFormat(Qt.TextFormat.PlainText)
        self.charging_summary.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.charging_summary.setVisible(False)
        self.charging_summary.setStyleSheet(
            "QLabel#chargingSummary { color: #4b5f6d; padding: 0 2px 2px 2px; }"
        )
        left_layout.addWidget(left_heading)
        left_layout.addWidget(settings_box, 0)
        left_layout.addWidget(results_heading)
        left_layout.addWidget(self.charging_summary, 0)
        left_layout.addWidget(self.table, 1)
        left_pane.setMinimumWidth(540)

        right_pane = QFrame(self)
        right_pane.setProperty("paneCard", True)
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(10, 8, 10, 10)
        right_layout.setSpacing(8)
        right_heading = QLabel("Expected elements", right_pane)
        right_heading.setProperty("paneHeading", True)
        right_layout.addWidget(right_heading)
        right_layout.addWidget(elements_box, 1)
        right_pane.setMinimumWidth(270)
        right_pane.setMaximumWidth(520)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left_pane)
        splitter.addWidget(right_pane)
        splitter.setStretchFactor(0, 64)
        splitter.setStretchFactor(1, 36)
        # Give the periodic-table tiles enough room for five complete columns
        # without requiring the user to move the divider first.
        splitter.setSizes([690, 390])
        splitter.setHandleWidth(6)
        outer.addWidget(splitter, 1)

        buttons_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close, parent=self)
        apply_button = buttons_box.button(QDialogButtonBox.StandardButton.Apply)
        apply_button.setText("Apply and identify")
        apply_button.setAutoDefault(False)
        apply_button.setDefault(False)
        close_button = buttons_box.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.setAutoDefault(False)
            close_button.setDefault(False)
        apply_button.clicked.connect(self._apply)
        buttons_box.rejected.connect(self.reject)
        outer.addWidget(buttons_box)
        self.cb_small_charging.toggled.connect(self._update_charging_summary)
        self._update_charging_summary()
        self.sb_photon.setFocus(Qt.FocusReason.OtherFocusReason)


    def _apply(self) -> None:
        if not any(cb.isChecked() for cb in self._element_checks.values()):
            QMessageBox.warning(
                self,
                "Expected elements required",
                "Select at least one expected element before identification.",
            )
            return
        self.apply_requested.emit()

    def set_assignments(self, assignments: Iterable[PeakAssignment]) -> None:
        """Refresh the result table and compact charging summary in-place."""
        self._current_assignments = list(assignments)
        self.table.setSortingEnabled(False)
        self._populate(self._current_assignments)
        self.table.setSortingEnabled(True)
        self.table.sortItems(self._sort_column, self._sort_order)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        self._update_charging_summary()

    def _update_charging_summary(self) -> None:
        """Show one compact line summarising PE-anchored charging evidence."""
        if not self.cb_small_charging.isChecked():
            self.charging_summary.clear()
            self.charging_summary.setToolTip("")
            self.charging_summary.setVisible(False)
            return

        by_element: dict[str, dict[str, object]] = {}
        for assignment in self._current_assignments:
            best = assignment.best
            if best is None or best.common_shift_eV is None:
                continue
            reason = str(getattr(best, "reason", ""))
            environment = str(getattr(best, "environment", ""))
            charging_supported = (
                "small-charging mode" in reason
                or "PE anchor" in reason
                or "charging-shifted" in environment
            )
            if not charging_supported:
                continue
            entry = by_element.setdefault(
                best.element,
                {"shift": float(best.common_shift_eV), "pe": [], "auger": []},
            )
            if best.kind == "PE":
                entry["pe"].append(best.label)
            elif best.kind == "Auger":
                entry["auger"].append(best.label)

        if not by_element:
            self.charging_summary.setText("Charging: no reliable shift inferred.")
            self.charging_summary.setToolTip(
                "Charging-assisted matching is enabled, but no element has a reliable photoelectron anchor."
            )
            self.charging_summary.setVisible(True)
            return

        parts = []
        details = []
        for element in sorted(by_element):
            entry = by_element[element]
            pe_labels = list(dict.fromkeys(entry["pe"]))
            auger_labels = list(dict.fromkeys(entry["auger"]))
            suffix = f", {len(pe_labels)} PE" if pe_labels else ""
            if auger_labels:
                suffix += ", Auger adjusted"
            parts.append(f"{element} {float(entry['shift']):+.1f} eV ({suffix.lstrip(', ')})" if suffix else f"{element} {float(entry['shift']):+.1f} eV")
            detail = f"{element}: PE anchor/support = {', '.join(pe_labels) or 'not listed'}"
            if auger_labels:
                detail += f"; shifted Auger = {', '.join(auger_labels)}"
            details.append(detail)
        self.charging_summary.setText("Charging: " + "; ".join(parts))
        self.charging_summary.setToolTip("\n".join(details))
        self.charging_summary.setVisible(True)

    def _set_all_elements(self, checked: bool) -> None:
        for cb in self._element_checks.values():
            cb.setChecked(checked)

    def _populate(self, assignments: Iterable[PeakAssignment]) -> None:
        rows = list(assignments)
        self.table.setRowCount(len(rows))
        for row, assignment in enumerate(rows):
            best = assignment.best
            values = [
                f"{assignment.peak.energy:.3f}",
                best.label if best else "Unassigned",
                best.kind if best else "",
                f"{best.expected_energy:.3f}" if best else "",
                f"{best.delta_e:+.3f}" if best else "",
                f"{best.reliability}%" if best else "",
                ("; ".join(candidate.label for candidate in assignment.candidates[1:]) if best else assignment.rejection_reason),
            ]
            if best:
                if best.reliability >= 90:
                    level = "Very strong"
                elif best.reliability >= 75:
                    level = "Strong"
                elif best.reliability >= 55:
                    level = "Plausible"
                elif best.reliability >= 35:
                    level = "Weak"
                else:
                    level = "Uncertain"
                total_bg, total_fg = _reliability_palette(best.reliability)
                details = ""
                if best.common_shift_eV is not None:
                    details += f"<br><b>Common element shift:</b> {best.common_shift_eV:+.2f} eV"
                if best.residual_mismatch_eV is not None:
                    details += f"<br><b>Residual mismatch:</b> {best.residual_mismatch_eV:.2f} eV"
                row_tooltip = (
                    "<div style='white-space:nowrap'>"
                    f"<div style='padding:4px 6px;margin-bottom:5px;background:{total_bg};"
                    f"color:{total_fg};font-weight:700'>Reliability: {best.reliability}% — {level}</div>"
                    "<table cellspacing='2' cellpadding='0'>"
                    + _factor_html("Line-pattern consistency", best.reliability_pattern)
                    + _factor_html("Measured peak evidence", best.reliability_peak)
                    + _factor_html("Element support", best.reliability_support)
                    + _factor_html("Assignment uniqueness", best.reliability_uniqueness)
                    + _factor_html("Absolute-shift plausibility", best.reliability_shift)
                    + _factor_html("Reference quality", best.reliability_reference)
                    + "</table>" + details + "</div>"
                )
            else:
                row_tooltip = assignment.rejection_reason or "No accepted assignment."
            sort_values = [
                float(assignment.peak.energy),
                values[1].casefold(),
                (best.kind.casefold() if best else ""),
                (float(best.expected_energy) if best else float("-inf")),
                (float(best.delta_e) if best else float("-inf")),
                (float(best.reliability) if best else -1.0),
                values[6].casefold(),
            ]
            for col, value in enumerate(values):
                item = SortableTableWidgetItem(value, sort_values[col])
                if col in {0, 3, 4, 5}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setToolTip(row_tooltip)
                if best and col == 5:
                    background, foreground = _reliability_palette(best.reliability)
                    item.setBackground(QBrush(QColor(background)))
                    item.setForeground(QBrush(QColor(foreground)))
                self.table.setItem(row, col, item)

    def _sort_table_by_column(self, column: int) -> None:
        """Sort supported columns and toggle direction on repeated clicks."""
        if column not in self._sortable_columns:
            self.table.horizontalHeader().setSortIndicator(self._sort_column, self._sort_order)
            return
        if column == self._sort_column:
            self._sort_order = (
                Qt.SortOrder.AscendingOrder
                if self._sort_order == Qt.SortOrder.DescendingOrder
                else Qt.SortOrder.DescendingOrder
            )
        else:
            self._sort_column = column
            self._sort_order = Qt.SortOrder.AscendingOrder
        self.table.sortItems(self._sort_column, self._sort_order)
        self.table.horizontalHeader().setSortIndicator(self._sort_column, self._sort_order)

    def settings(self) -> IdentificationSettings:
        elements = {symbol for symbol, cb in self._element_checks.items() if cb.isChecked()}
        photon = float(self.sb_photon.value())
        return IdentificationSettings(
            photon_energy=photon if photon > 0 else None,
            tolerance_eV=float(self.sb_tolerance.value()),
            prominence_fraction=float(self.sb_prominence.value()) / 100.0,
            include_auger=bool(self.cb_auger.isChecked()),
            include_second_order=bool(self.cb_second.isChecked()),
            small_charging_possible=bool(self.cb_small_charging.isChecked()),
            elements=elements,
            sample_mode=str(self.combo_sample.currentText()),
            valence_band_cutoff_eV=float(self.sb_vb_cutoff.value()),
        )
