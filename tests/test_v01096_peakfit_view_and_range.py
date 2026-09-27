from types import SimpleNamespace
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure

from maxiv_panda.workflows.peakfit import fit_plotting


def test_intermediate_fit_redraw_preserves_current_zoom():
    fig = Figure()
    ax = fig.add_subplot(211)
    ax_res = fig.add_subplot(212)
    ax.set_xlim(175.0, 155.0)
    ax.set_ylim(10.0, 75.0)
    view = fit_plotting.capture_axes_view(ax)

    payload = SimpleNamespace(
        x=np.linspace(100.0, 300.0, 201),
        y=np.linspace(0.0, 100.0, 201),
        xlabel="Binding energy (eV)",
        ylabel="Intensity",
        title="survey",
        energy_scale="binding",
    )
    fit_data = {
        "payload": payload,
        "yu": np.linspace(20.0, 30.0, 21),
    }
    xu = np.linspace(155.0, 175.0, 21)

    class Canvas:
        def draw(self):
            pass

        def draw_idle(self):
            pass

    state = fit_plotting.draw_intermediate_fit(
        ax,
        ax_res,
        Canvas(),
        lambda: None,
        lambda: None,
        lambda: None,
        lambda x, **kwargs: (np.linspace(20.0, 30.0, len(x)), []),
        [],
        xu,
        {},
        "constant",
        fit_data,
        view_state=view,
    )

    assert state is not None
    assert np.allclose(ax.get_xlim(), (175.0, 155.0))
    assert np.allclose(ax.get_ylim(), (10.0, 75.0))
    assert np.allclose(ax_res.get_xlim(), (175.0, 155.0))


def test_new_peak_guess_uses_active_fit_range_source_logic():
    src = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_peak_interaction_mixin.py").read_text(encoding="utf-8")
    assert "fit_rng = self._current_fit_range()" in src
    assert "guess_xmin" in src and "guess_xmax" in src
    assert "(x_arr >= guess_xmin) & (x_arr <= guess_xmax)" in src
    assert "sb_E.setValue(guess_xmid)" in src
