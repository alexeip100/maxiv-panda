from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from maxiv_panda.signal_identification.annotation_plotting import draw_signal_annotations


class _Checked:
    def isChecked(self):
        return True


def test_vb_label_is_centered_and_uses_distinct_color():
    fig, ax = plt.subplots()
    x = np.linspace(20.0, -5.0, 101)
    y = 1.0 + 0.02 * x
    ax.plot(x, y)

    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")
    controller = SimpleNamespace(
        window=SimpleNamespace(
            cb_identify_signals=_Checked(),
            plot_area=SimpleNamespace(ax=ax, canvas=fig.canvas),
        ),
        assignments=[SimpleNamespace(best=None)],
        _active_key="curve",
        settings=SimpleNamespace(valence_band_cutoff_eV=15.0, photon_energy=1000.0),
        current_single_curve=lambda: (payload, {}, "curve"),
        identify=lambda show_messages=False: None,
    )

    draw_signal_annotations(controller)

    vb_text = next(text for text in ax.texts if text.get_text() == "VB")
    assert vb_text.get_position()[0] == 7.5
    assert vb_text.get_color() == "tab:purple"

    vb_lines = [line for line in ax.lines[1:] if line.get_linestyle() == ":"]
    assert len(vb_lines) == 1
    assert np.allclose(vb_lines[0].get_xdata(), [7.5, 7.5])
    assert vb_lines[0].get_color() == "tab:purple"

    # The VB span is the only patch and uses the same purple hue.
    assert len(ax.patches) == 1
    assert ax.patches[0].get_facecolor()[-1] > 0
    plt.close(fig)


def test_vb_annotation_extracts_photon_energy_from_metadata_when_setting_is_unset():
    fig, ax = plt.subplots()
    x = np.linspace(700.0, 680.0, 101)
    y = 1.0 + 0.01 * (x - 680.0)
    ax.plot(x, y)

    payload = SimpleNamespace(x=x, y=y, energy_scale="Kinetic")
    controller = SimpleNamespace(
        window=SimpleNamespace(
            cb_identify_signals=_Checked(),
            plot_area=SimpleNamespace(ax=ax, canvas=fig.canvas),
        ),
        assignments=[SimpleNamespace(best=None)],
        _active_key="curve",
        settings=SimpleNamespace(valence_band_cutoff_eV=15.0, photon_energy=None),
        current_single_curve=lambda: (
            payload,
            {"source_metadata": {"Excitation Energy": "700.0"}},
            "curve",
        ),
        identify=lambda show_messages=False: None,
    )

    draw_signal_annotations(controller)

    vb_text = next(text for text in ax.texts if text.get_text() == "VB")
    assert vb_text.get_position()[0] == 692.5
    assert len(ax.patches) == 1
    plt.close(fig)
