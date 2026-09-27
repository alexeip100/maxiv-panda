from __future__ import annotations

import math

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt

from maxiv_panda.signal_identification.cross_section_reference import CrossSectionReferencePanel
from maxiv_panda.signal_identification.cross_sections import (
    angular_cross_section_at,
    angular_factor,
    cross_section_at,
)


def test_angular_factor_magic_angle_is_near_one():
    magic = math.degrees(math.acos(1.0 / math.sqrt(3.0)))
    assert angular_factor(1.7, magic) == pytest.approx(1.0, abs=1e-12)


def test_angular_cross_section_uses_beta_factor():
    raw = cross_section_at("Au", "4f7/2", 1000.0)
    weighted = angular_cross_section_at("Au", "4f7/2", 1000.0, 48.0)
    assert raw is not None
    assert weighted is not None
    assert weighted > 0.0
    assert weighted != pytest.approx(raw)


def test_panel_populates_shells_and_checkbox_immediately_plots(qapp):
    panel = CrossSectionReferencePanel()
    au = panel._element_buttons["Au"]
    au.setChecked(True)
    assert any(key[0] == "Au" for key in panel._shell_items)

    key = next(key for key in panel._shell_items if key[0] == "Au" and key[1] == "4f7/2")
    panel._shell_items[key].setCheckState(0, Qt.CheckState.Checked)
    assert panel.values_table.rowCount() == 1
    assert panel.values_table.item(0, 0).text() == "Au 4f7/2"
    assert panel.values_table.item(0, 4).text() != "N/A"


def test_second_element_appends_shells(qapp):
    panel = CrossSectionReferencePanel()
    panel._element_buttons["Au"].setChecked(True)
    au_count = len(panel._shell_items)
    panel._element_buttons["O"].setChecked(True)
    assert len(panel._shell_items) > au_count
    assert any(key[0] == "Au" for key in panel._shell_items)
    assert any(key[0] == "O" for key in panel._shell_items)


def test_clear_shell_selection_also_clears_plot_and_values(qapp):
    panel = CrossSectionReferencePanel()
    panel._element_buttons["Au"].setChecked(True)
    key = next(key for key in panel._shell_items if key == ("Au", "4f7/2"))
    panel._shell_items[key].setCheckState(0, Qt.CheckState.Checked)
    assert panel.values_table.rowCount() == 1
    assert len(panel.figure.axes[0].lines) >= 2

    panel.clear_shell_selection()

    assert panel.values_table.rowCount() == 0
    assert len(panel.figure.axes[0].lines) == 0
    assert "Select one or more" in panel.figure.axes[0].texts[0].get_text()


def test_shell_flow_gets_nonzero_geometry_after_element_selection(qapp):
    panel = CrossSectionReferencePanel()
    panel.resize(1200, 700)
    panel.show()
    qapp.processEvents()

    panel._element_buttons["Au"].click()
    qapp.processEvents()

    assert panel._shell_items
    assert panel.shell_flow.count() == len(panel._shell_items)
    assert panel.shell_host.minimumHeight() > 0
    assert any(box.geometry().width() > 0 for box in panel._shell_items.values())
    assert all(box.isVisible() for box in panel._shell_items.values())


def test_cross_section_element_tiles_keep_category_styling(qapp):
    panel = CrossSectionReferencePanel()
    au = panel._element_buttons["Au"]
    oxygen = panel._element_buttons["O"]
    assert au.property("elementCategory") == "transition"
    assert oxygen.property("elementCategory") == "nonmetal"
    # The panel stylesheet must include the category selectors used by the
    # shared ElementTileButton, not only the identification dialog stylesheet.
    style = panel.styleSheet()
    assert 'elementCategory="transition"' in style
    assert 'elementCategory="nonmetal"' in style


def test_shell_select_all_clear_all_and_table_header_tooltips(qapp):
    panel = CrossSectionReferencePanel()
    panel._element_buttons["Au"].setChecked(True)
    assert panel._shell_items
    assert panel.btn_select_all_shells.text() == "Select all"
    assert panel.btn_clear_all_shells.text() == "Clear all"

    panel.btn_select_all_shells.click()
    assert all(box.isChecked() for box in panel._shell_items.values())
    assert panel.values_table.rowCount() == len(panel._shell_items)

    tooltips = [panel.values_table.horizontalHeaderItem(i).toolTip() for i in range(5)]
    assert all(tooltips)
    assert "megabarns" in tooltips[1]
    assert panel.values_table.columnWidth(0) <= 110

    panel.btn_clear_all_shells.click()
    assert not any(box.isChecked() for box in panel._shell_items.values())
    assert panel.values_table.rowCount() == 0


def test_reference_conditions_share_right_splitter_column(qapp):
    panel = CrossSectionReferencePanel()
    panel.resize(1400, 800)
    panel.show()
    qapp.processEvents()

    assert panel.main_splitter.count() == 2
    left, right = panel.main_splitter.widget(0), panel.main_splitter.widget(1)
    conditions = next(box for box in right.findChildren(__import__("PyQt6.QtWidgets", fromlist=["QGroupBox"]).QGroupBox) if box.title() == "Reference conditions")
    assert conditions.parentWidget() is right
    assert left.height() == right.height()


def test_compact_reference_layout_and_draggable_selector_splitter(qapp):
    panel = CrossSectionReferencePanel()
    panel.resize(1400, 800)
    panel.show()
    qapp.processEvents()

    sizes = panel.main_splitter.sizes()
    assert sizes[0] <= 330
    assert panel.reference_conditions_box.height() <= 82
    assert panel.selector_splitter.orientation() == Qt.Orientation.Vertical
    assert panel.selector_splitter.count() == 2
    assert panel.shell_scroll.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert abs(panel.btn_select_all_shells.width() - panel.btn_clear_all_shells.width()) <= 1

    # The two spin boxes share one horizontal row.
    assert abs(panel.sb_photon_energy.mapTo(panel.reference_conditions_box, panel.sb_photon_energy.rect().topLeft()).y() - panel.sb_angle.mapTo(panel.reference_conditions_box, panel.sb_angle.rect().topLeft()).y()) <= 3


def test_cross_section_table_columns_are_interactive(qapp):
    panel = CrossSectionReferencePanel()
    header = panel.values_table.horizontalHeader()
    from PyQt6.QtWidgets import QHeaderView
    assert all(
        header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive
        for column in range(panel.values_table.columnCount())
    )


def test_photon_energy_marker_is_draggable_and_updates_spinbox(qapp):
    panel = CrossSectionReferencePanel()
    panel._element_buttons["Au"].setChecked(True)
    key = next(key for key in panel._shell_items if key == ("Au", "4f7/2"))
    panel._shell_items[key].setCheckState(0, Qt.CheckState.Checked)
    assert panel._photon_marker is not None

    class Event:
        button = 1
        inaxes = panel.figure.axes[0]
        xdata = 1250.0
        x = panel.figure.axes[0].transData.transform((panel.sb_photon_energy.value(), 1.0))[0]

    event = Event()
    panel._on_plot_press(event)
    assert panel._dragging_photon_marker
    panel._on_plot_motion(event)
    assert panel.sb_photon_energy.value() == pytest.approx(1250.0)
    panel._on_plot_release(event)
    assert not panel._dragging_photon_marker


def test_cross_section_legend_can_be_hidden_and_is_draggable(qapp):
    panel = CrossSectionReferencePanel()
    panel._element_buttons["Au"].setChecked(True)
    key = next(key for key in panel._shell_items if key == ("Au", "4f7/2"))
    panel._shell_items[key].setCheckState(0, Qt.CheckState.Checked)
    assert panel._legend is not None
    assert panel._legend.get_visible()
    assert getattr(panel._legend, "_draggable", None) is not None
    panel.cb_legend.setChecked(False)
    assert not panel._legend.get_visible()


def test_intersection_marker_moves_with_photon_energy(qapp):
    panel = CrossSectionReferencePanel()
    panel._element_buttons["Au"].setChecked(True)
    key = next(key for key in panel._shell_items if key == ("Au", "4f7/2"))
    panel._shell_items[key].setCheckState(0, Qt.CheckState.Checked)
    assert panel._intersection_markers
    _selection, marker = panel._intersection_markers[0]
    old_x = float(marker.get_xdata()[0])
    panel.sb_photon_energy.setValue(old_x + 100.0)
    qapp.processEvents()
    assert float(marker.get_xdata()[0]) == pytest.approx(old_x + 100.0)
    assert marker.get_visible()
