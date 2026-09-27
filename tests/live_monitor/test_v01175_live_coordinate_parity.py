from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
CONTROLS = (ROOT / "src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
WINDOW = (ROOT / "src/maxiv_panda/live_monitor/window.py").read_text(encoding="utf-8")


def _make_view():
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from maxiv_panda.live_monitor.lines_view import LiveLinesView

    fig = Figure(figsize=(8, 5))
    canvas = FigureCanvasAgg(fig)
    return LiveLinesView(fig, canvas)


def test_live_cursor_labels_match_view_lines_precision_for_energy_axes():
    view = _make_view()
    x = np.linspace(290.0, 282.0, 101)
    z = np.arange(50 * 101, dtype=float).reshape(50, 101)
    phe = np.linspace(700.0, 749.0, 50)
    view.set_data(
        x, z, second_axis=phe, second_axis_label="Photon Energy [eV]",
        xlabel="Binding Energy [eV]", reset=True,
    )

    # Midpoint row is 25 -> 725 eV; View: Lines displays one decimal because
    # the physical Y sample spacing is 1 eV.
    assert view.hlabel.get_text() == "PhE = 725.0 eV"
    assert view.vlabel.get_text() == "BE = 286.000 eV"


def test_live_map_toolbar_coordinates_match_view_lines_format():
    view = _make_view()
    x = np.array([10.0, 9.0, 8.0])
    z = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
    view.set_data(
        x, z, second_axis=np.array([585.0, 586.0]),
        second_axis_label="Photon Energy [eV]", xlabel="Binding Energy [eV]",
        reset=True,
    )

    assert view.ax_map.format_coord(9.11, 1.2) == (
        "BE = 9.1 eV     PhE = 586.0 eV    Intensity = 5.0000e+00"
    )


def test_live_monitor_uses_fixed_width_toolbar_coordinate_font():
    assert "SystemFont.FixedFont" in WINDOW
    assert "toolbar.locLabel.setFont" in WINDOW


def test_help_documents_live_coordinate_parity_with_view_lines():
    assert "toolbar coordinate readout" in CONTROLS
    assert "same formatting as Processed Data **View: Lines**" in CONTROLS
