from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure

from maxiv_panda.ui_map_plot_mixin import MapPlotMixin

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "src" / "maxiv_panda" / "ui_map_plot_mixin.py"
LIVE_LINES = ROOT / "src" / "maxiv_panda" / "live_monitor" / "lines_view.py"
LIVE_WINDOW = ROOT / "src" / "maxiv_panda" / "live_monitor" / "window.py"
HELP = ROOT / "src" / "maxiv_panda" / "docs" / "usage_controls.md"


class _Dummy(MapPlotMixin):
    @staticmethod
    def _format_map_axis_value(value):
        return f"{float(value):g}"


def test_iteration_only_map_duplicates_iteration_on_left_and_right_axes():
    fig = Figure()
    ax_map = fig.add_subplot(121)
    ax_right = fig.add_subplot(122)
    d = _Dummy()
    d._configure_map_y_axes(ax_map, ax_right, 4, [1, 2, 3, 4], None, "")
    assert ax_map.get_ylabel() == "Iteration"
    assert ax_right.get_ylabel() == "Iteration"
    assert any(t.get_text() for t in ax_map.get_yticklabels())
    assert any(t.get_text() for t in ax_right.get_yticklabels())


def test_physical_y_still_uses_physical_left_and_iteration_right():
    fig = Figure()
    ax_map = fig.add_subplot(121)
    ax_right = fig.add_subplot(122)
    d = _Dummy()
    d._configure_map_y_axes(
        ax_map, ax_right, 4, [1, 2, 3, 4], [700, 710, 720, 730], "Photon Energy [eV]"
    )
    assert ax_map.get_ylabel() == "Photon Energy [eV]"
    assert ax_right.get_ylabel() == "Iteration"


def test_map_and_bottom_trace_use_same_label_coordinate_and_full_margin():
    src = MAP.read_text(encoding="utf-8")
    live = LIVE_LINES.read_text(encoding="utf-8")
    assert 'ax_map.yaxis.set_label_coords(-0.075, 0.5' in src
    assert 'ax_bottom.yaxis.set_label_coords(-0.075, 0.5' in src
    assert src.count('_map_left = 0.100') >= 2
    assert 'self.ax_map.yaxis.set_label_coords(-0.075, 0.5' in live
    assert 'self.ax_bottom.yaxis.set_label_coords(-0.075, 0.5' in live
    assert 'map_left = 0.100' in live


def test_toolbar_uses_system_fixed_font_at_normal_toolbar_size():
    map_src = MAP.read_text(encoding="utf-8")
    live_src = LIVE_WINDOW.read_text(encoding="utf-8")
    for src in (map_src, live_src):
        assert "QFontDatabase.SystemFont.FixedFont" in src
        assert "fixed.setPointSizeF(default.pointSizeF())" in src


def test_help_documents_iteration_mirroring_and_native_fixed_width_font():
    text = HELP.read_text(encoding="utf-8")
    assert "Iteration** is displayed on both the map's **left Y axis**" in text
    assert "Raw Data maps" in text
    assert "system fixed-width font at the normal toolbar text size" in text
