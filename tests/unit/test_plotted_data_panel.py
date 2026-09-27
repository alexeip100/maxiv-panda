from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from maxiv_panda.workflows.plotting import PlottedDataPanel, source_aware_curve_title


@dataclass
class Curve:
    title: str
    x: object
    y: object
    xlabel: str = "Binding Energy [eV]"
    ylabel: str = "Intensity"
    energy_scale: str = "Binding"


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_panel_accepts_independent_curve_snapshots(app):
    panel = PlottedDataPanel()
    x = np.array([0.0, 1.0, 2.0])
    y = np.array([2.0, 3.0, 4.0])
    panel.set_curves([Curve("curve A", x, y)])

    assert len(panel.curves) == 1
    assert len(panel.ax.lines) == 1
    assert panel.ax.xaxis_inverted()

    y[0] = 999.0
    assert float(panel.curves[0].y[0]) == 2.0


def test_panel_replaces_existing_curves(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("A", [0, 1], [1, 2]), Curve("B", [0, 1], [2, 3])])
    assert len(panel.ax.lines) == 2
    panel.set_curves([Curve("C", [0, 1], [4, 5])])
    assert len(panel.curves) == 1
    assert len(panel.ax.lines) == 1


def test_phase1_controls_style_visibility_waterfall_and_grid(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("A", [0, 1, 2], [1, 2, 3]), Curve("B", [0, 1, 2], [2, 3, 4])])

    assert panel.curve_list.count() == 2
    first_widget = panel.curve_list.itemWidget(panel.curve_list.item(0))
    first_widget.chk_visible.setChecked(False)
    assert len(panel.ax.lines) == 1

    first_widget.chk_visible.setChecked(True)
    first_widget.cmb_style.setCurrentIndex(first_widget.cmb_style.findData("--"))
    first_widget.spin_width.setValue(3.0)
    assert panel.ax.lines[0].get_linestyle() == "--"
    assert panel.ax.lines[0].get_linewidth() == 3.0

    panel.chk_waterfall.setChecked(True)
    panel.spin_waterfall.setValue(50.0)
    assert np.allclose(panel.ax.lines[1].get_ydata(), np.array([2, 3, 4]) + 1.5)

    panel.cmb_grid.setCurrentText("Fine")
    assert any(line.get_visible() for line in panel.ax.get_xgridlines())


def test_custom_legend_name_and_clear(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("A", [0, 1], [1, 2])])
    panel.curves[0].custom_name = "Custom A"
    panel.cmb_legend.setCurrentText("Custom (TeX)")
    widget = panel.curve_list.itemWidget(panel.curve_list.item(0))
    assert widget.edit_name.text() == "A"
    assert widget.edit_name.focusPolicy() == 0
    assert widget.edit_name.textInteractionFlags() == Qt.TextInteractionFlag.NoTextInteraction
    assert panel.ax.get_legend().get_texts()[0].get_text() == "Custom A"

    panel.chk_waterfall.setChecked(True)
    panel.clear()
    assert not panel.chk_waterfall.isChecked()
    assert panel.curve_list.count() == 0
    assert len(panel.curves) == 0


def test_add_curves_keeps_existing_plot(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("A", [0, 1], [1, 2])])
    panel.add_curves([Curve("B", [0, 1], [2, 3])])
    assert [curve.title for curve in panel.curves] == ["A", "B"]
    assert len(panel.ax.lines) == 2


def test_export_csv_uses_visible_curves_current_order_and_custom_names(app, tmp_path):
    from maxiv_panda.workflows.plotting import export_visible_curves_csv

    panel = PlottedDataPanel()
    panel.set_curves([
        Curve("A", [0, 1, 2], [10, 11, 12]),
        Curve("B", [5, 6], [20, 21]),
        Curve("C", [7], [30]),
    ])
    panel.curves[0].custom_name = "Sample"
    panel.curves[1].custom_name = "Sample"
    panel.curves[2].visible = False
    panel._curves = [panel._curves[1], panel._curves[0], panel._curves[2]]

    target = tmp_path / "plot.csv"
    assert export_visible_curves_csv(target, panel.curves) == 2
    rows = target.read_text(encoding="utf-8").splitlines()
    assert rows[0] == "Sample - Energy,Sample - Intensity,Sample (2) - Energy,Sample (2) - Intensity"
    assert rows[1] == "5.0,20.0,0.0,10.0"
    assert rows[3] == ",,2.0,12.0"


def test_annotation_and_draggable_legend(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("A", [0, 1, 2], [1, 2, 3])])

    panel.annotation_settings.text = "Sample note"
    panel.annotation_settings.visible = True
    panel.annotation_settings.fontsize = 16
    panel.annotation_settings.bold = True
    panel.legend_settings.location = "upper left"
    panel.legend_settings.fontsize = 13
    panel.redraw()

    assert panel._annotation_artist is not None
    assert panel._annotation_artist.get_text() == "Sample note"
    assert panel._annotation_artist.get_zorder() > max(
        [artist.get_zorder() for artist in panel.ax.lines] +
        [artist.get_zorder() for artist in panel.ax.collections]
    )
    assert panel._legend_artist is not None
    assert panel._legend_artist._draggable is not None
    assert panel.ax.get_legend()._loc == 2  # upper left


def test_annotation_and_legend_positions_are_preserved_after_drag_release(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("A", [0, 1], [1, 2])])
    panel.annotation_settings.text = "Drag me"
    panel.annotation_settings.visible = True
    panel.redraw()
    panel._annotation_artist.set_position((0.35, 0.62))
    panel._legend_artist.set_bbox_to_anchor((0.25, 0.80), transform=panel.ax.transAxes)
    panel.canvas.draw()
    panel._remember_interactive_positions(None)

    assert panel.annotation_settings.x == pytest.approx(0.35)
    assert panel.annotation_settings.y == pytest.approx(0.62)
    assert panel.legend_settings.anchor is not None


def test_custom_legend_defaults_to_invitation(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("A", [0, 1], [1, 2]), Curve("B", [0, 1], [2, 3])])
    panel.cmb_legend.setCurrentText("Custom (TeX)")
    assert [t.get_text() for t in panel.ax.get_legend().get_texts()] == [
        "<select curve name>", "<select curve name>"
    ]


def test_curve_list_stays_static_across_legend_modes(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("Original A", [0, 1], [1, 2])])
    panel.curves[0].custom_name = "Display A"

    widget = panel.curve_list.itemWidget(panel.curve_list.item(0))
    panel.cmb_legend.setCurrentText("Custom (TeX)")
    assert panel.curve_list.itemWidget(panel.curve_list.item(0)) is widget
    assert widget.edit_name.text() == "Original A"
    assert widget.current_export_name() == "Display A"

    panel.cmb_legend.setCurrentText("Curve name")
    assert panel.curve_list.itemWidget(panel.curve_list.item(0)) is widget
    assert widget.edit_name.text() == "Original A"
    assert widget.current_export_name() == "Original A"


def test_finest_grid_is_default_and_duplicate_titles_are_unique(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("[0008] Survey", [0, 1], [1, 2]), Curve("[0008] Survey", [0, 1], [2, 3])])

    assert panel.cmb_grid.currentText() == "Finest"
    assert [curve.title for curve in panel.curves] == ["[0008] Survey", "[0008] Survey (2)"]
    assert not hasattr(panel, "btn_axes")
    assert not hasattr(panel, "btn_export_figure")


def test_source_aware_title_uses_xps_file_number():
    assert source_aware_curve_title("Survey", "/tmp/XPS_0008.txt") == "[0008] Survey"
    assert source_aware_curve_title("[0008] Survey", "/tmp/XPS_0008.txt") == "[0008] Survey"


def test_each_custom_legend_entry_can_be_renamed_and_cancel_rebuilds_cleanly(app, monkeypatch):
    from PyQt6.QtWidgets import QDialog
    import maxiv_panda.workflows.plotting.panel as panel_module

    class AcceptedLegendNameDialog:
        def __init__(self, *args, **kwargs):
            pass
        def exec(self):
            return QDialog.DialogCode.Accepted
        def text(self):
            return "Second curve"

    panel = PlottedDataPanel()
    panel.set_curves([Curve("A", [0, 1], [1, 2]), Curve("B", [0, 1], [2, 3])])
    panel.cmb_legend.setCurrentText("Custom (TeX)")

    monkeypatch.setattr(panel_module, "LegendNameDialog", AcceptedLegendNameDialog)
    panel._rename_custom_legend_entry(1)
    assert panel.curves[0].custom_name == ""
    assert panel.curves[1].custom_name == "Second curve"
    assert [t.get_text() for t in panel.ax.get_legend().get_texts()] == [
        "<select curve name>", "Second curve"
    ]
    assert panel._legend_artist._draggable is not None

    class RejectedLegendNameDialog(AcceptedLegendNameDialog):
        def exec(self):
            return QDialog.DialogCode.Rejected

    legend_before = panel._legend_artist
    monkeypatch.setattr(panel_module, "LegendNameDialog", RejectedLegendNameDialog)
    panel._rename_custom_legend_entry(0)
    assert panel.curves[0].custom_name == ""
    assert panel._legend_artist is not legend_before
    assert panel.ax.get_legend() is panel._legend_artist
    assert panel._legend_artist._draggable is not None


def test_import_csv_roundtrip_pair_columns(tmp_path):
    from maxiv_panda.workflows.plotting import export_visible_curves_csv, import_curves_csv

    curves = [
        Curve("A", [0, 1, 2], [10, 11, 12]),
        Curve("B", [5, 6], [20, 21]),
    ]
    panel = PlottedDataPanel()
    panel.set_curves(curves)
    panel.curves[0].custom_name = "First"
    panel.curves[1].custom_name = "Second"
    target = tmp_path / "roundtrip.csv"
    export_visible_curves_csv(target, panel.curves)

    imported = import_curves_csv(target)
    assert [curve.title for curve in imported] == ["First", "Second"]
    assert [curve.custom_name for curve in imported] == ["First", "Second"]
    assert np.allclose(imported[0].x, [0, 1, 2])
    assert np.allclose(imported[1].y, [20, 21])


def test_import_csv_accepts_shared_energy_column(tmp_path):
    from maxiv_panda.workflows.plotting import import_curves_csv

    target = tmp_path / "shared.csv"
    target.write_text("Binding Energy [eV],Sample A,Sample B\n0,1,3\n1,2,4\n", encoding="utf-8")
    imported = import_curves_csv(target)
    assert [curve.title for curve in imported] == ["Sample A", "Sample B"]
    assert imported[0].xlabel == "Binding Energy [eV]"


def test_curve_rows_have_explicit_large_drag_handle(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("A", [0, 1], [1, 2])])
    widget = panel.curve_list.itemWidget(panel.curve_list.item(0))
    assert widget.drag_handle.width() >= 30
    assert widget.drag_handle.height() >= 30
    assert "Drag" in widget.drag_handle.toolTip()


def test_default_csv_directory_can_follow_loaded_data_folder(app, tmp_path):
    panel = PlottedDataPanel()
    panel.set_default_directory(tmp_path)
    assert panel._default_directory == tmp_path


def test_csv_controls_are_combined_in_one_menu(app):
    panel = PlottedDataPanel()
    assert panel.btn_csv.text() == "Export / Import"
    assert [action.text() for action in panel.csv_menu.actions()] == ["Export CSV", "Import CSV"]
    assert not hasattr(panel, "btn_export")
    assert not hasattr(panel, "btn_import")


def test_export_names_follow_current_curve_list_mode(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("Original A", [0, 1], [1, 2])])
    panel.curves[0].custom_name = "Display A"
    panel.cmb_legend.setCurrentText("Curve name")
    assert panel._export_name_for_curve(panel.curves[0]) == "Original A"
    panel.cmb_legend.setCurrentText("Custom (TeX)")
    assert panel._export_name_for_curve(panel.curves[0]) == "Display A"
    panel.curves[0].custom_name = ""
    assert panel._export_name_for_curve(panel.curves[0]) == "<select curve name>"


def test_waterfall_offset_scale_adapts_to_visible_curve_count(app):
    panel = PlottedDataPanel()
    curves = [Curve(f"C{i}", [0, 1], [i, i + 1]) for i in range(200)]
    panel.set_curves(curves)

    assert panel.spin_waterfall.maximum() == pytest.approx(15.0)
    panel.slider_waterfall.setValue(500)
    assert panel.spin_waterfall.value() == pytest.approx(7.5, abs=0.01)

    for curve in panel.curves[10:]:
        curve.visible = False
    panel.redraw()
    assert panel.spin_waterfall.maximum() == pytest.approx(100.0)


def test_waterfall_adaptive_max_formula(app):
    panel = PlottedDataPanel()
    assert panel._adaptive_waterfall_max_percent(10) == pytest.approx(100.0)
    assert panel._adaptive_waterfall_max_percent(30) == pytest.approx(100.0)
    assert panel._adaptive_waterfall_max_percent(50) == pytest.approx(60.0)
    assert panel._adaptive_waterfall_max_percent(100) == pytest.approx(30.0)
    assert panel._adaptive_waterfall_max_percent(200) == pytest.approx(15.0)
    assert panel._adaptive_waterfall_max_percent(500) == pytest.approx(6.0)
    assert panel._adaptive_waterfall_max_percent(600) == pytest.approx(5.0)


def test_waterfall_slider_defers_expensive_redraw_until_release(app):
    panel = PlottedDataPanel()
    assert panel.slider_waterfall.hasTracking() is False


def test_fixed_width_uses_point_two_step(app):
    panel = PlottedDataPanel()
    assert panel.spin_fixed_width.singleStep() == pytest.approx(0.2)


def test_clear_permanently_removes_annotation_state(app):
    panel = PlottedDataPanel()
    panel.set_curves([Curve("A", [0, 1], [1, 2])])
    panel.annotation_settings.text = "Old note"
    panel.annotation_settings.visible = True
    panel.redraw()
    assert panel._annotation_artist is not None

    panel.clear()
    assert panel.annotation_settings.text == ""
    assert panel.annotation_settings.visible is False
    assert panel._annotation_artist is None

    panel.add_curves([Curve("B", [0, 1], [2, 3])])
    assert panel._annotation_artist is None
