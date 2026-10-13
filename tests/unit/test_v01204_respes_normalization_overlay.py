import numpy as np
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure

from maxiv_panda.ui_map_plot_mixin import MapPlotMixin


class Dummy(MapPlotMixin):
    pass


def _draw(mode, energy_axis, interval):
    obj = Dummy()
    fig = Figure()
    ax = fig.subplots()
    ax.set_xlim(0.0, 20.0)
    ax.set_ylim(0.0, 4.0)
    hv = np.array([570.0, 571.0, 572.0, 573.0])
    obj._draw_respes_normalization_region(
        ax, interval, mode, lambda *_: None,
        photon_energy=hv, rows=4, energy_axis=energy_axis,
        source_axis="be", source_x=np.linspace(0.0, 20.0, 41), work_function=4.5,
    )
    return obj, ax


def test_be_interval_is_vertical_in_be_view():
    obj, _ = _draw("at_be", "be", (3.0, 5.0))
    b1, b2 = obj._map_norm_band_state["boundary_xy"]
    assert np.allclose(b1[0], 3.0)
    assert np.allclose(b2[0], 5.0)


def test_be_interval_is_diagonal_in_ke_view():
    obj, _ = _draw("at_be", "ke", (3.0, 5.0))
    b1, _ = obj._map_norm_band_state["boundary_xy"]
    x, y = b1
    assert x.size == 4 and y.size == 4
    assert np.allclose(np.diff(x), 1.0)


def test_ke_interval_is_diagonal_in_be_view():
    obj, _ = _draw("at_ke", "be", (550.0, 552.0))
    b1, _ = obj._map_norm_band_state["boundary_xy"]
    x, _y = b1
    assert np.allclose(np.diff(x), 1.0)


def test_ke_interval_is_vertical_in_ke_view():
    obj, _ = _draw("at_ke", "ke", (550.0, 552.0))
    b1, b2 = obj._map_norm_band_state["boundary_xy"]
    assert np.allclose(b1[0], 550.0)
    assert np.allclose(b2[0], 552.0)


def test_photon_energy_interval_is_horizontal():
    obj, _ = _draw("at_hv", "be", (570.5, 571.5))
    b1, b2 = obj._map_norm_band_state["boundary_xy"]
    assert np.allclose(b1[1], b1[1][0])
    assert np.allclose(b2[1], b2[1][0])
    assert b1[1][0] < b2[1][0]


def test_opposite_axis_mouse_coordinate_recovers_physical_ke():
    obj, _ = _draw("at_ke", "be", (550.0, 552.0))
    state = obj._map_norm_band_state
    class E: pass
    e = E(); e.xdata = 16.5; e.ydata = 1.5
    # y=1.5 corresponds to hnu=571 eV: KE = 571 - 16.5 - 4.5 = 550 eV.
    assert np.isclose(state["coordinate_from_event"](e), 550.0)


def test_overlay_update_keeps_physical_interval_and_notifies():
    calls = []
    obj = Dummy(); fig = Figure(); ax = fig.subplots(); ax.set_xlim(0, 20); ax.set_ylim(0, 4)
    hv = np.array([570.,571.,572.,573.])
    obj._draw_respes_normalization_region(
        ax, (3.,5.), "at_be", lambda interval, final=False: calls.append((interval, final)),
        photon_energy=hv, rows=4, energy_axis="ke", source_axis="be",
        source_x=np.linspace(0,20,41), work_function=4.5,
    )
    obj._update_map_norm_band_artists(4.0, 6.0, notify=True)
    assert obj._map_norm_band_state["low"] == 4.0
    assert obj._map_norm_band_state["high"] == 6.0
    assert calls[-1] == ((4.0, 6.0), False)


def test_mouse_event_is_recovered_from_pixels_even_if_twin_axes_received_it():
    obj, ax = _draw("at_ke", "be", (550.0, 552.0))
    state = obj._map_norm_band_state
    px, py = ax.transData.transform((16.5, 1.5))
    class E: pass
    e = E(); e.x = px; e.y = py; e.inaxes = object(); e.button = 1
    proxy = obj._map_norm_event_in_main_axes(state, e)
    assert proxy is not None
    assert np.isclose(proxy.xdata, 16.5)
    assert np.isclose(proxy.ydata, 1.5)
    assert np.isclose(state["coordinate_from_event"](proxy), 550.0)


def test_diagonal_normalization_boundary_is_directly_draggable_from_pixels():
    obj, ax = _draw("at_ke", "be", (550.0, 552.0))
    state = obj._map_norm_band_state
    # Pick an exact point on the first diagonal boundary.
    xx, yy = state["boundary_xy"][0]
    i = len(xx) // 2
    px, py = ax.transData.transform((float(xx[i]), float(yy[i])))
    class E: pass
    e = E(); e.x = px; e.y = py; e.inaxes = object(); e.button = 1
    assert obj._map_norm_boundary_hit(e)
    obj._on_map_norm_band_press(e)
    assert obj._map_norm_drag is not None
    assert obj._map_norm_drag["mode"] in {"left", "right"}


def test_respes_cut_yields_when_normalization_boundary_is_hit():
    obj, ax = _draw("at_ke", "be", (550.0, 552.0))
    # Minimal cut state: if priority is wrong the handler would proceed into it.
    obj._respes_cut_state = {"ax": ax, "event_axes": {ax}}
    obj._respes_cut_drag = None
    xx, yy = obj._map_norm_band_state["boundary_xy"][0]
    i = len(xx) // 2
    px, py = ax.transData.transform((float(xx[i]), float(yy[i])))
    class E: pass
    e = E(); e.x = px; e.y = py; e.xdata = float(xx[i]); e.ydata = float(yy[i]); e.inaxes = ax; e.button = 1
    obj._on_respes_cut_press(e)
    assert obj._respes_cut_drag is None


def test_diagonal_edges_resize_from_mid_segment_not_just_vertices():
    # Regression: build 4's arbitration used segment distance, but its drag
    # selector used vertex distance and mistook an edge drag for a band move.
    for index, mode, expected in ((0, "at_ke", "left"), (1, "at_ke", "right"),
                                  (0, "at_be", "left"), (1, "at_be", "right")):
        display = "be" if mode == "at_ke" else "ke"
        interval = (550., 552.) if mode == "at_ke" else (3., 5.)
        obj, ax = _draw(mode, display, interval)
        if mode == "at_be":
            ax.set_xlim(558., 568.)  # KE view of BE=3..5 at hν≈570..573
        xx, yy = obj._map_norm_band_state["boundary_xy"][index]
        # Midpoint between sampled vertices: notably NOT at a vertex.
        px, py = ax.transData.transform((float((xx[1]+xx[2])/2), float((yy[1]+yy[2])/2)))
        class E: pass
        e = E(); e.x = px; e.y = py; e.inaxes = object(); e.button = 1
        assert obj._map_norm_boundary_hit(e)
        obj._on_map_norm_band_press(e)
        assert obj._map_norm_drag is not None
        assert obj._map_norm_drag["mode"] == expected


def test_horizontal_photon_energy_edges_resize_between_endpoints():
    obj, ax = _draw("at_hv", "be", (570.5, 571.5))
    for index, mode in ((0, "left"), (1, "right")):
        xx, yy = obj._map_norm_band_state["boundary_xy"][index]
        px, py = ax.transData.transform((float(np.mean(xx)), float(np.mean(yy))))
        class E: pass
        e = E(); e.x = px; e.y = py; e.inaxes = object(); e.button = 1
        obj._on_map_norm_band_press(e)
        assert obj._map_norm_drag is not None
        assert obj._map_norm_drag["mode"] == mode
        obj._map_norm_drag = None


def test_diagonal_left_edge_drag_really_changes_width():
    obj, ax = _draw("at_ke", "be", (550., 552.))
    obj.canvas = type("Canvas", (), {"draw_idle": lambda self: None})()
    xx, yy = obj._map_norm_band_state["boundary_xy"][0]
    x0, y0 = (float(xx[1]+xx[2])/2, float(yy[1]+yy[2])/2)
    class E: pass
    e = E(); e.x, e.y = ax.transData.transform((x0, y0)); e.button = 1; e.inaxes = ax
    obj._on_map_norm_band_press(e)
    assert obj._map_norm_drag["mode"] == "left"
    e2 = E(); e2.x, e2.y = ax.transData.transform((x0-0.5, y0)); e2.button = 1; e2.inaxes = ax
    obj._on_map_norm_band_motion(e2)
    state = obj._map_norm_band_state
    assert np.isclose(state["low"], 550.5)
    assert np.isclose(state["high"], 552.0)
    obj._on_map_norm_band_release(e2)
    assert obj._map_norm_drag is None


def test_narrow_vertical_interval_selects_nearest_edge_and_resizes():
    obj, ax = _draw("at_be", "be", (4.0, 4.4))
    obj.canvas = type("Canvas", (), {"draw_idle": lambda self: None})()
    class E: pass
    for index, expected in ((0, "left"), (1, "right")):
        xx, yy = obj._map_norm_band_state["boundary_xy"][index]
        e = E(); e.x, e.y = ax.transData.transform((float(xx[0]), 2.0))
        e.inaxes = ax; e.button = 1
        obj._on_map_norm_band_press(e)
        assert obj._map_norm_drag["mode"] == expected
        obj._map_norm_drag = None
