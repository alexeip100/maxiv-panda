from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from maxiv_panda.ui_map_plot_mixin import MapPlotMixin


class DummyMap(MapPlotMixin):
    pass


def _event(ax, x, y):
    px, py = ax.transData.transform((x, y))
    return SimpleNamespace(inaxes=ax, x=float(px), y=float(py), xdata=float(x), ydata=float(y))


def _base():
    fig, ax = plt.subplots()
    ax.set_xlim(0.0, 10.0)
    ax.set_ylim(0.0, 10.0)
    fig.canvas.draw()
    obj = DummyMap()
    obj.canvas = fig.canvas
    obj._respes_cut_drag = None
    obj._map_norm_band_state = None
    obj._map_norm_drag = None
    obj._map_cross_state = None
    obj._map_roi_state = None
    return obj, fig, ax


def test_roi_has_priority_inside_area_normalization_band():
    obj, fig, ax = _base()
    patch = Rectangle((4.0, 4.0), 2.0, 2.0)
    ax.add_patch(patch)
    obj._map_roi_state = {"ax_map": ax, "ax_right": None, "patch": patch, "xidx": np.array([4,5]), "yidx": np.array([4,5])}
    obj._map_roi_drag = None
    obj._draw_map_normalization_band(ax, (2.0, 8.0), "area", lambda *_: None)

    ev = _event(ax, 5.0, 5.0)
    obj._on_map_norm_band_press(ev)
    assert obj._map_norm_drag is None
    obj._on_map_roi_press(ev)
    assert obj._map_roi_drag is not None
    assert obj._map_roi_drag["mode"] == "move"
    obj._map_roi_drag = None

    ev = _event(ax, 3.0, 2.0)
    obj._on_map_norm_band_press(ev)
    assert obj._map_norm_drag is not None
    assert obj._map_norm_drag["mode"] == "move"
    plt.close(fig)


def test_lines_cursor_has_priority_but_area_band_remains_draggable_elsewhere():
    obj, fig, ax = _base()
    obj._map_cross_state = {
        "ax_map": ax,
        "ax_bottom": None,
        "ax_right": None,
        "x": np.arange(10.0),
        "col": 5,
        "row": 6,
    }
    obj._map_drag_axis = None
    obj._draw_map_normalization_band(ax, (2.0, 8.0), "area", lambda *_: None)

    ev = _event(ax, 5.0, 2.0)
    obj._on_map_norm_band_press(ev)
    assert obj._map_norm_drag is None
    obj._on_map_cross_press(ev)
    assert obj._map_drag_axis == "x"
    obj._map_drag_axis = None

    ev = _event(ax, 3.0, 2.0)
    obj._on_map_norm_band_press(ev)
    assert obj._map_norm_drag is not None
    assert obj._map_norm_drag["mode"] == "move"
    plt.close(fig)


def test_normalization_edge_still_resizes_in_lines_view_away_from_cursor():
    obj, fig, ax = _base()
    obj._map_cross_state = {
        "ax_map": ax,
        "x": np.arange(10.0),
        "col": 5,
        "row": 6,
    }
    obj._draw_map_normalization_band(ax, (2.0, 8.0), "area", lambda *_: None)

    ev = _event(ax, 2.0, 2.0)
    obj._on_map_norm_band_press(ev)
    assert obj._map_norm_drag is not None
    assert obj._map_norm_drag["mode"] == "left"
    plt.close(fig)


def test_lines_and_roi_renderers_keep_normalization_callback():
    src = open("src/maxiv_panda/ui_map_plot_mixin.py", encoding="utf-8").read()
    lines_start = src.index("def _plot_single_map_with_cross_sections")
    roi_start = src.index("def _plot_single_map_with_roi")
    respes_start = src.index("def _plot_respes_map") if "def _plot_respes_map" in src else len(src)
    lines = src[lines_start:roi_start]
    roi = src[roi_start:respes_start]
    assert "_draw_map_normalization_band(ax_map, norm_interval, norm_mode, norm_callback)" in lines
    assert "_draw_map_normalization_band(ax_map, norm_interval, norm_mode, norm_callback)" in roi
