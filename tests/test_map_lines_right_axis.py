import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from maxiv_panda.ui_map_plot_mixin import MapPlotMixin


class _DummyPlot(MapPlotMixin):
    def __init__(self):
        self.fig = Figure(figsize=(8, 6))
        self.canvas = FigureCanvasAgg(self.fig)
        self.ax = self.fig.add_subplot(111)
        self._map_cross_state = None
        self._map_roi_state = None
        self._map_norm_drag = None
        self._map_drag_axis = None
        self._map_roi_drag = None
        self._map_right_y_mode = "iteration"

    def _draw_map_normalization_band(self, *args, **kwargs):
        return None


def _image(with_photon_energy=True):
    x = np.linspace(100.0, 110.0, 11)
    iterations = np.arange(1.0, 7.0)
    z = np.arange(66.0).reshape(6, 11)
    if with_photon_energy:
        secondary = np.linspace(500.0, 505.0, 6)
        label = "Photon Energy [eV]"
    else:
        secondary = None
        label = ""
    return (x, iterations, z, "map", "Binding Energy [eV]", "viridis", secondary, label)


def test_lines_guides_continue_onto_side_traces_with_width():
    plot = _DummyPlot()
    plot._plot_single_map_with_cross_sections(
        [], _image(), False, None, h_thickness=3, v_thickness=5
    )
    state = plot._map_cross_state
    assert state["hline_right"] is not None
    assert state["vline_bottom"] is not None
    assert state["hband_right"].get_height() == 3.0
    assert state["vband_bottom"].get_width() > 0.0


def test_right_trace_can_switch_to_photon_energy():
    plot = _DummyPlot()
    plot._plot_single_map_with_cross_sections([], _image(), False, None)
    state = plot._map_cross_state
    assert state["right_y_mode"] == "iteration"
    assert state["ax_right"].get_ylabel() == "Iteration"

    plot._apply_map_right_trace_y_axis(state, "secondary")
    assert state["right_y_mode"] == "secondary"
    assert state["ax_right"].get_ylabel() == "PhE [eV]"


def test_iteration_only_map_disables_secondary_right_axis():
    plot = _DummyPlot()
    plot._plot_single_map_with_cross_sections([], _image(False), False, None)
    state = plot._map_cross_state
    plot._apply_map_right_trace_y_axis(state, "secondary")
    assert state["right_y_mode"] == "iteration"
    assert state["ax_right"].get_ylabel() == "Iteration"

from types import SimpleNamespace


def _evt(ax, x, y, xdata=None, ydata=None, dblclick=False):
    return SimpleNamespace(inaxes=ax, x=float(x), y=float(y), xdata=xdata, ydata=ydata, dblclick=dblclick)


def test_lines_guides_are_draggable_from_side_traces():
    plot = _DummyPlot()
    plot._plot_single_map_with_cross_sections([], _image(), False, None)
    state = plot._map_cross_state
    plot.canvas.draw()

    # Bottom trace: drag the continued V guide along X.
    xpos = float(state["x"][state["col"]])
    px, py = state["ax_bottom"].transData.transform((xpos, 0.0))
    plot._on_map_cross_press(_evt(state["ax_bottom"], px, py, xdata=xpos, ydata=0.0))
    assert plot._map_drag_axis == "x_bottom"
    target_col = 8
    tx = float(state["x"][target_col])
    tpx, tpy = state["ax_bottom"].transData.transform((tx, 0.0))
    plot._on_map_cross_motion(_evt(state["ax_bottom"], tpx, tpy, xdata=tx, ydata=0.0))
    assert state["col"] == target_col
    plot._on_map_cross_release(None)

    # Right trace: drag the continued H guide along Y.
    ypos = float(state["row"]) + 0.5
    px, py = state["ax_right"].transData.transform((0.0, ypos))
    plot._on_map_cross_press(_evt(state["ax_right"], px, py, xdata=0.0, ydata=ypos))
    assert plot._map_drag_axis == "y_right"
    target_row = 4
    ty = target_row + 0.5
    tpx, tpy = state["ax_right"].transData.transform((0.0, ty))
    plot._on_map_cross_motion(_evt(state["ax_right"], tpx, tpy, xdata=0.0, ydata=ty))
    assert state["row"] == target_row


def test_lines_crossing_drag_moves_both_guides():
    plot = _DummyPlot()
    plot._plot_single_map_with_cross_sections([], _image(), False, None)
    state = plot._map_cross_state
    plot.canvas.draw()

    xpos = float(state["x"][state["col"]])
    ypos = float(state["row"]) + 0.5
    px, py = state["ax_map"].transData.transform((xpos, ypos))
    plot._on_map_cross_press(_evt(state["ax_map"], px, py, xdata=xpos, ydata=ypos))
    assert plot._map_drag_axis == "both"

    target_col = 7
    target_row = 1
    tx = float(state["x"][target_col])
    ty = target_row + 0.5
    tpx, tpy = state["ax_map"].transData.transform((tx, ty))
    plot._on_map_cross_motion(_evt(state["ax_map"], tpx, tpy, xdata=tx, ydata=ty))
    assert state["col"] == target_col
    assert state["row"] == target_row
