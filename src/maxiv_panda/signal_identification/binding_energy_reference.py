from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QAbstractItemView, QCheckBox, QDoubleSpinBox, QFrame, QGridLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QRadioButton, QScrollArea, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .binding_energies import (available_binding_elements, available_binding_shells,
    entries_for_selection)
from .reference_widgets import CoreLevelSelectorBox, ShellCheckBox
from .reference_search import candidates_in_be_region
from .dialogs import ElementTileButton
from .reference_data import element_symbols
from ..ui_style import register_widget_role

STYLE = """
QWidget#bindingEnergyReferencePanel { background: palette(window); }
QLabel#panelIntro { color: palette(window-text); padding: 2px 4px 5px 4px; }
QLabel[paneHeading="true"] { font-weight: 600; color: palette(window-text); padding: 2px 2px 5px 2px; }
QFrame[paneCard="true"] { background: palette(alternate-base); border: 1px solid palette(mid); border-radius: 6px; }
QGroupBox { font-weight: 600; color: palette(window-text); border: 1px solid palette(mid); border-radius: 5px; margin-top: 12px; padding-top: 9px; background: palette(base); }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QTableWidget { background: palette(base); alternate-background-color: palette(alternate-base); border: 1px solid palette(mid); border-radius: 4px; gridline-color: palette(mid); }
QHeaderView::section { background: palette(button); color: palette(button-text); font-weight: 600; padding: 3px 5px; border: 0; border-right: 1px solid palette(mid); border-bottom: 1px solid palette(mid); }
QPushButton[elementCategory] { border: 1px solid palette(mid); border-top-width: 4px; border-radius: 5px; background: palette(base); color: palette(button-text); font-weight: 600; padding: 2px; text-align: center; }
QPushButton[elementCategory]:hover { background: palette(midlight); border-color: palette(mid); }
QPushButton[elementCategory]:checked { background: palette(highlight); border-color: palette(highlight); color: palette(highlighted-text); }
QPushButton[elementCategory="nonmetal"] { border-top-color: #62a879; } QPushButton[elementCategory="halogen"] { border-top-color: #55a7a5; } QPushButton[elementCategory="noble"] { border-top-color: #8d83c6; } QPushButton[elementCategory="alkali"] { border-top-color: #d3945c; } QPushButton[elementCategory="alkaline"] { border-top-color: #d5b85e; } QPushButton[elementCategory="metalloid"] { border-top-color: #70a0a0; } QPushButton[elementCategory="lanthanide"] { border-top-color: #bf7ba0; } QPushButton[elementCategory="actinide"] { border-top-color: #a36f92; } QPushButton[elementCategory="posttransition"] { border-top-color: #8199ad; } QPushButton[elementCategory="transition"] { border-top-color: #7093b5; }
QCheckBox#shellChoice { background: palette(alternate-base); border: 1px solid palette(mid); border-radius: 4px; padding: 3px 7px; color: palette(text); }
QCheckBox#shellChoice:hover { background: palette(midlight); } QCheckBox#shellChoice:checked { background: palette(highlight); border-color: palette(highlight); font-weight: 600; }
QSplitter#referenceSelectorSplitter::handle:vertical { height: 5px; background: palette(mid); border-top: 1px solid palette(light); border-bottom: 1px solid palette(mid); }
QFrame#referenceModeBar { background: palette(base); border: 1px solid palette(mid); border-radius: 5px; }
QRadioButton { spacing: 6px; padding: 3px 8px; }
"""

class BindingEnergyReferencePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName("bindingEnergyReferencePanel"); self.setStyleSheet(STYLE)
        self._element_buttons = {}; self._shell_items = {}; self._view_mode = "selection"
        outer = QVBoxLayout(self); outer.setContentsMargins(8,8,8,8); outer.setSpacing(7)
        intro = QLabel("XPS binding-energy references from the LBNL X-Ray Data Booklet and XPS International Handbook. This view is independent of loaded PES data.")
        intro.setObjectName("panelIntro"); intro.setWordWrap(True); outer.addWidget(intro)
        mode_bar = QFrame(self); mode_bar.setObjectName("referenceModeBar")
        mode_row = QHBoxLayout(mode_bar); mode_row.setContentsMargins(9,4,9,4); mode_row.setSpacing(10)
        mode_row.addWidget(QLabel("Method:"))
        self.mode_browse = QRadioButton("Elements / core levels", mode_bar)
        self.mode_search = QRadioButton("BE range", mode_bar)
        self.mode_browse.setToolTip("Browse reference binding energies by selecting elements and core levels.")
        self.mode_search.setToolTip("Find reference signals that fall inside a selected binding-energy range.")
        self.mode_browse.setChecked(True)
        mode_row.addWidget(self.mode_browse); mode_row.addWidget(self.mode_search); mode_row.addStretch(1)
        outer.addWidget(mode_bar, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal, self); splitter.setChildrenCollapsible(False); outer.addWidget(splitter,1)
        left = QFrame(splitter); self.browse_pane = left; left.setProperty("paneCard",True); ll=QVBoxLayout(left); ll.setContentsMargins(9,7,9,8); ll.setSpacing(6)
        h=QLabel("Elements",left); h.setProperty("paneHeading",True); ll.addWidget(h)
        row=QHBoxLayout(); b=QPushButton("Clear elements",left); b.clicked.connect(self.clear_elements); row.addWidget(b); row.addStretch(1); ll.addLayout(row)
        selector_splitter=QSplitter(Qt.Orientation.Vertical,left); selector_splitter.setChildrenCollapsible(False); selector_splitter.setObjectName("referenceSelectorSplitter")
        element_area=QWidget(selector_splitter); selector_splitter.addWidget(element_area); element_layout=QVBoxLayout(element_area); element_layout.setContentsMargins(0,0,0,0)
        scroll=QScrollArea(element_area); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame); host=QWidget(scroll); grid=QGridLayout(host); grid.setContentsMargins(4,4,4,4); grid.setHorizontalSpacing(8); grid.setVerticalSpacing(4)
        available=set(available_binding_elements())
        for i,symbol in enumerate(element_symbols()):
            tile=ElementTileButton(symbol,i+1,host); tile.setEnabled(symbol in available); tile.toggled.connect(lambda checked,s=symbol:self._element_toggled(s,checked)); self._element_buttons[symbol]=tile; grid.addWidget(tile,i//5,i%5)
        for c in range(5): grid.setColumnStretch(c,1)
        scroll.setWidget(host); element_layout.addWidget(scroll,1)
        self.core_level_selector=CoreLevelSelectorBox(selector_splitter,on_select_all=self.select_all_shells,on_clear_all=self.clear_shells); selector_splitter.addWidget(self.core_level_selector)
        self.shell_scroll=self.core_level_selector.scroll
        self.shell_host=self.core_level_selector.host
        self.shell_layout=self.core_level_selector.flow
        self.btn_select_all_shells=self.core_level_selector.select_all_button
        self.btn_clear_all_shells=self.core_level_selector.clear_all_button
        selector_splitter.setStretchFactor(0,1); selector_splitter.setStretchFactor(1,0); selector_splitter.setSizes([470,170])
        ll.addWidget(selector_splitter,1); self.selector_splitter=selector_splitter; left.setMinimumWidth(305); register_widget_role(left, "periodic_table_pane")
        right=QFrame(splitter); right.setProperty("paneCard",True); rl=QVBoxLayout(right); rl.setContentsMargins(8,7,8,7); rl.setSpacing(6)
        search=QGroupBox("Search by BE range",right); self.search_box = search; sr=QHBoxLayout(search)
        sr.addWidget(QLabel("BE from:")); self.be_from=QDoubleSpinBox(search); self.be_from.setRange(-10000,100000); self.be_from.setDecimals(2); self.be_from.setSuffix(" eV"); self.be_from.setValue(500.0); sr.addWidget(self.be_from)
        sr.addWidget(QLabel("to:")); self.be_to=QDoubleSpinBox(search); self.be_to.setRange(-10000,100000); self.be_to.setDecimals(2); self.be_to.setSuffix(" eV"); self.be_to.setValue(550.0); sr.addWidget(self.be_to)
        self.include_auger = QCheckBox("Include Auger signals", search); self.include_auger.setChecked(False); self.include_auger.toggled.connect(self._include_auger_toggled); sr.addWidget(self.include_auger)
        self.photon_energy_label = QLabel("Photon energy:", search); self.photon_energy_label.setEnabled(False); sr.addWidget(self.photon_energy_label); self.photon_energy=QDoubleSpinBox(search); self.photon_energy.setRange(0,100000); self.photon_energy.setDecimals(2); self.photon_energy.setSuffix(" eV"); self.photon_energy.setValue(1000.0); self.photon_energy.setEnabled(False); sr.addWidget(self.photon_energy)
        find=QPushButton("Find",search); find.clicked.connect(self.find_by_energy); sr.addWidget(find); sr.addStretch(1); rl.addWidget(search)
        self.mode_label=QLabel("Select one or more elements, then select core levels.",right); self.mode_label.setStyleSheet("color: palette(mid);"); rl.addWidget(self.mode_label)
        self.table=QTableWidget(0,8,right); self.table.setHorizontalHeaderLabels(["Element","Signal","Level / family","Reference energy","Position on BE scale","Environment / state","Phase","Source"]); self.table.setAlternatingRowColors(True); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setSortingEnabled(True); hdr=self.table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(False)
        for column, width in enumerate((72, 82, 105, 135, 145, 210, 95, 140)):
            self.table.setColumnWidth(column, width)
        rl.addWidget(self.table,1)
        note=QLabel("Core-level browsing uses binding-energy (BE) references only. For an energy-region search, Auger families can optionally be included; their kinetic-energy (KE) regions are converted to apparent BE using hν − KE. Reference energies depend on chemical state and experimental conditions, so matches are candidates rather than unique identifications.",right); note.setWordWrap(True); note.setStyleSheet("color: palette(mid); padding: 3px;"); rl.addWidget(note)
        splitter.setStretchFactor(0,0); splitter.setStretchFactor(1,1); splitter.setSizes([310,1120])
        self.mode_browse.toggled.connect(self._reference_mode_changed)
        self.mode_search.toggled.connect(self._reference_mode_changed)
        self._reference_mode_changed()

    def _reference_mode_changed(self, *_):
        browse = bool(self.mode_browse.isChecked())
        self.browse_pane.setEnabled(browse)
        self.search_box.setEnabled(not browse)
        if browse:
            self.show_selected()
        else:
            self._view_mode = "search"
            self.mode_label.setText("Enter a binding-energy range and press Find.")
            self._populate([])

    def selected_elements(self): return [s for s,b in self._element_buttons.items() if b.isChecked()]
    def selected_shells(self): return [(element, kind, line) for (element, kind, line), b in self._shell_items.items() if b.isChecked()]
    def _element_toggled(self, symbol, checked):
        self._rebuild_shells()
        self.show_selected()
    def clear_elements(self):
        for b in self._element_buttons.values(): b.setChecked(False)
        self._rebuild_shells(); self.show_selected()
    def select_all_shells(self):
        for b in self._shell_items.values():
            b.setChecked(True)
        self.show_selected()

    def clear_shells(self):
        for b in self._shell_items.values():
            b.setChecked(False)
        self.show_selected()
    def _rebuild_shells(self):
        old=set(self.selected_shells())
        while self.shell_layout.count():
            item=self.shell_layout.takeAt(0); w=item.widget(); w.deleteLater() if w else None
        self._shell_items={}
        for element in self.selected_elements():
            for shell in available_binding_shells([element]):
                key = (element, "core", shell)
                cb=ShellCheckBox(f"{element} {shell}",self.shell_host); cb.setObjectName("shellChoice"); cb.setChecked(key in old); cb.toggled.connect(self.show_selected)
                self._shell_items[key]=cb; self.shell_layout.addWidget(cb)
        self.core_level_selector.refresh_extent()

    def _update_shell_scroll_extent(self):
        # Compatibility hook used by tests and older callers.
        self.core_level_selector.refresh_extent()
    def show_selected(self, *_):
        self._view_mode = "selection"
        selected = set(self.selected_shells())
        if not selected:
            if self.selected_elements():
                self.mode_label.setText("Select one or more core levels to show reference values.")
            else:
                self.mode_label.setText("Select one or more elements, then select core levels.")
            self._populate([])
            return
        core_keys = {(element, line) for element, kind, line in selected if kind == "core"}
        rows = []
        for entry in entries_for_selection(self.selected_elements()):
            if (entry.element, entry.transition) in core_keys:
                rows.append(("core", entry, entry.energy_text))
        self.mode_label.setText("Binding-energy reference values for the selected core levels.")
        self._populate(rows)

    def _include_auger_toggled(self, checked):
        enabled = bool(checked)
        self.photon_energy_label.setEnabled(enabled)
        self.photon_energy.setEnabled(enabled)

    def find_by_energy(self):
        if not self.mode_search.isChecked():
            self.mode_search.setChecked(True)
        self._view_mode = "search"
        lo, hi = sorted((float(self.be_from.value()), float(self.be_to.value())))
        include_auger = bool(self.include_auger.isChecked())
        photon = float(self.photon_energy.value()) if include_auger else None
        candidates = candidates_in_be_region(lo, hi, photon, include_auger=include_auger)
        rows = [(candidate.kind, candidate.entry, candidate.be_text) for candidate in candidates]
        if include_auger:
            self.mode_label.setText(
                f"Core-level and Auger candidates in BE {lo:g}–{hi:g} eV at hν = {photon:g} eV, sorted by BE position."
            )
        else:
            self.mode_label.setText(
                f"Core-level candidates in BE {lo:g}–{hi:g} eV, sorted by BE position."
            )
        self._populate(rows)

    def _populate(self, rows):
        self.table.setSortingEnabled(False); self.table.setRowCount(len(rows))
        for r, (kind, entry, be_text) in enumerate(rows):
            if kind == "auger":
                source="XPS International" if "Handbook" in entry.source else "EADL 2025"
                vals=[entry.element,"Auger",entry.family,f"KE {entry.energy_text}",be_text,entry.environment,"—",source]
            else:
                source="LBNL" if "LBNL" in entry.source else "XPS International"
                vals=[entry.element,"PE",entry.transition,f"BE {entry.energy_text}",be_text,entry.environment,entry.phase.replace("_"," "),source]
            for c,v in enumerate(vals):
                item=QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r,c,item)
        self.table.setSortingEnabled(True)
