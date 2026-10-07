from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from maxiv_panda.signal_identification.annotation_plotting import draw_signal_annotations


class _Checked:
    def isChecked(self):
        return True


class _Tabs:
    def __init__(self, current):
        self._current = current

    def currentWidget(self):
        return self._current


def _controller(*, current_tab, raw_tab):
    fig, ax = plt.subplots()
    x = np.linspace(20.0, -5.0, 101)
    y = 1.0 + 0.02 * x
    ax.plot(x, y)
    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")
    controller = SimpleNamespace(
        window=SimpleNamespace(
            tabs=_Tabs(current_tab),
            raw_data_tab=raw_tab,
            cb_identify_signals=_Checked(),
            plot_area=SimpleNamespace(ax=ax, canvas=fig.canvas),
        ),
        assignments=[SimpleNamespace(best=None)],
        _active_key="curve",
        settings=SimpleNamespace(valence_band_cutoff_eV=15.0, photon_energy=1000.0),
        current_single_curve=lambda: (payload, {}, "curve"),
        identify=lambda show_messages=False: None,
    )
    return fig, ax, controller


def test_signal_annotations_are_hidden_on_processed_data_without_clearing_cache():
    raw_tab = object()
    processed_tab = object()
    fig, ax, controller = _controller(current_tab=processed_tab, raw_tab=raw_tab)

    assignments_before = controller.assignments
    draw_signal_annotations(controller)

    assert controller.assignments is assignments_before
    assert len(ax.texts) == 0
    assert len(ax.patches) == 0
    assert len(ax.lines) == 1  # spectrum only
    plt.close(fig)


def test_signal_annotations_reappear_on_raw_data_from_same_cached_assignments():
    raw_tab = object()
    fig, ax, controller = _controller(current_tab=raw_tab, raw_tab=raw_tab)

    assignments_before = controller.assignments
    draw_signal_annotations(controller)

    assert controller.assignments is assignments_before
    assert any(text.get_text() == "VB" for text in ax.texts)
    assert len(ax.patches) == 1
    plt.close(fig)
