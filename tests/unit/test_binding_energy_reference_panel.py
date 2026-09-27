from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHeaderView, QPushButton

from maxiv_panda.signal_identification.binding_energy_reference import BindingEnergyReferencePanel


def test_element_selection_waits_for_core_level_selection(qapp):
    panel = BindingEnergyReferencePanel()
    panel._element_buttons["O"].setChecked(True)
    assert panel._shell_items
    assert panel.table.rowCount() == 0
    assert "Select one or more core levels" in panel.mode_label.text()

    panel._shell_items[("O", "core", "1s")].setChecked(True)
    assert panel.table.rowCount() > 0
    assert all(panel.table.item(row, 0).text() == "O" for row in range(panel.table.rowCount()))


def test_core_level_browser_does_not_expose_auger_families(qapp):
    panel = BindingEnergyReferencePanel()
    panel._element_buttons["O"].setChecked(True)
    assert panel._shell_items
    assert all(kind == "core" for _, kind, _ in panel._shell_items)
    assert not any("Auger" in box.text() for box in panel._shell_items.values())


def test_shell_buttons_and_find_have_distinct_roles(qapp):
    panel = BindingEnergyReferencePanel()
    assert panel.btn_select_all_shells.text() == "Select all"
    assert panel.btn_clear_all_shells.text() == "Clear all"
    button_texts = {button.text() for button in panel.findChildren(QPushButton)}
    assert "Find" in button_texts
    assert "Show selected" not in button_texts

    panel._element_buttons["O"].setChecked(True)
    panel.btn_select_all_shells.click()
    assert all(box.isChecked() for box in panel._shell_items.values())
    assert panel.table.rowCount() > 0
    panel.btn_clear_all_shells.click()
    assert panel.table.rowCount() == 0


def test_binding_energy_table_columns_are_interactive(qapp):
    panel = BindingEnergyReferencePanel()
    header = panel.table.horizontalHeader()
    assert all(
        header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive
        for column in range(panel.table.columnCount())
    )


def test_auger_search_is_optional_and_enables_photon_energy(qapp):
    panel = BindingEnergyReferencePanel()
    assert not panel.include_auger.isChecked()
    assert not panel.photon_energy.isEnabled()

    panel.be_from.setValue(493.0)
    panel.be_to.setValue(526.5)
    panel.find_by_energy()
    assert panel.table.rowCount() > 0
    assert {panel.table.item(row, 1).text() for row in range(panel.table.rowCount())} == {"PE"}

    panel.include_auger.setChecked(True)
    assert panel.photon_energy.isEnabled()
    panel.photon_energy.setValue(1000.0)
    panel.find_by_energy()
    signal_types = {panel.table.item(row, 1).text() for row in range(panel.table.rowCount())}
    assert "Auger" in signal_types
    assert "PE" in signal_types


def test_core_level_choices_scroll_when_many_elements_are_selected(qapp):
    panel = BindingEnergyReferencePanel()
    panel.resize(1200, 720)
    panel.show()
    enabled = [button for button in panel._element_buttons.values() if button.isEnabled()]
    for button in enabled[:12]:
        button.setChecked(True)
    qapp.processEvents()
    panel._update_shell_scroll_extent()
    qapp.processEvents()

    assert panel.shell_scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert panel.shell_scroll.verticalScrollBar().maximum() > 0


def test_binding_energy_selector_uses_draggable_splitter_and_shared_scroll_style(qapp):
    panel = BindingEnergyReferencePanel()
    panel.resize(1200, 720)
    panel.show()
    qapp.processEvents()
    assert panel.selector_splitter.orientation() == Qt.Orientation.Vertical
    assert panel.selector_splitter.count() == 2
    assert panel.shell_scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert abs(panel.btn_select_all_shells.width() - panel.btn_clear_all_shells.width()) <= 1


def test_binding_energy_reference_has_explicit_browse_and_range_modes(qapp):
    panel = BindingEnergyReferencePanel()
    assert panel.mode_browse.isChecked()
    assert panel.browse_pane.isEnabled()
    assert not panel.search_box.isEnabled()

    panel.mode_search.setChecked(True)
    assert panel.mode_search.isChecked()
    assert not panel.browse_pane.isEnabled()
    assert panel.search_box.isEnabled()
    assert "binding-energy range" in panel.mode_label.text()

    panel.mode_browse.setChecked(True)
    assert panel.browse_pane.isEnabled()
    assert not panel.search_box.isEnabled()
