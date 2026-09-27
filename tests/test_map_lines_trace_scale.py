import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from maxiv_panda.ui_map_plot_mixin import MapPlotMixin


class Dummy(MapPlotMixin):
    pass


def _state():
    fig = plt.figure()
    ax_bottom = fig.add_subplot(121)
    ax_right = fig.add_subplot(122)
    bottom_line = ax_bottom.plot([0, 1, 2], [4, 5, 6])[0]
    right_line = ax_right.plot([7, 8, 9], [0, 1, 2])[0]
    return fig, {
        "ax_bottom": ax_bottom,
        "ax_right": ax_right,
        "bottom_line": bottom_line,
        "right_line": right_line,
        "trace_scale_min": 1.0,
        "trace_scale_max": 20.0,
        "Z": np.array([[1.0, 3.0], [10.0, 20.0]]),
        "set_bottom_scientific_scale": lambda _values: None,
    }


def test_full_range_uses_dataset_min_max_for_both_live_traces():
    obj = Dummy()
    obj._map_lines_trace_scale_mode = "full"
    fig, state = _state()
    try:
        obj._apply_map_lines_trace_scale(state)
        assert np.allclose(state["ax_bottom"].get_ylim(), (1.0, 20.0))
        assert np.allclose(state["ax_right"].get_xlim(), (1.0, 20.0))
    finally:
        plt.close(fig)


def test_auto_rescales_to_current_trace_values():
    obj = Dummy()
    obj._map_lines_trace_scale_mode = "auto"
    fig, state = _state()
    try:
        obj._apply_map_lines_trace_scale(state)
        by0, by1 = state["ax_bottom"].get_ylim()
        rx0, rx1 = state["ax_right"].get_xlim()
        assert by0 < 4.0 and by1 > 6.0
        assert rx0 < 7.0 and rx1 > 9.0
        assert by1 < 20.0
        assert rx1 < 20.0
    finally:
        plt.close(fig)


def test_switching_full_range_back_to_auto_reenables_matplotlib_autoscaling():
    obj = Dummy()
    fig, state = _state()
    try:
        obj._map_lines_trace_scale_mode = "full"
        obj._apply_map_lines_trace_scale(state)
        assert not state["ax_bottom"].get_autoscaley_on()
        assert not state["ax_right"].get_autoscalex_on()

        obj._map_lines_trace_scale_mode = "auto"
        obj._apply_map_lines_trace_scale(state)

        assert state["ax_bottom"].get_autoscaley_on()
        assert state["ax_right"].get_autoscalex_on()
        by0, by1 = state["ax_bottom"].get_ylim()
        rx0, rx1 = state["ax_right"].get_xlim()
        assert by0 < 4.0 and by1 > 6.0 and by1 < 20.0
        assert rx0 < 7.0 and rx1 > 9.0 and rx1 < 20.0
    finally:
        plt.close(fig)


def test_h_and_v_autoscaling_can_be_controlled_independently():
    obj = Dummy()
    fig, state = _state()
    try:
        obj._map_lines_auto_scale_h = False
        obj._map_lines_auto_scale_v = True
        obj._apply_map_lines_trace_scale(state)
        assert np.allclose(state["ax_bottom"].get_ylim(), (1.0, 20.0))
        rx0, rx1 = state["ax_right"].get_xlim()
        assert rx0 < 7.0 and rx1 > 9.0 and rx1 < 20.0

        obj._map_lines_auto_scale_h = True
        obj._map_lines_auto_scale_v = False
        obj._apply_map_lines_trace_scale(state)
        by0, by1 = state["ax_bottom"].get_ylim()
        assert by0 < 4.0 and by1 > 6.0 and by1 < 20.0
        assert np.allclose(state["ax_right"].get_xlim(), (1.0, 20.0))
    finally:
        plt.close(fig)
