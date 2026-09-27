from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
WINDOW = (ROOT / "src/maxiv_panda/live_monitor/window.py").read_text(encoding="utf-8")
CONTROLS = (ROOT / "src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")


def test_live_lines_separates_physical_y_from_iteration_y():
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from maxiv_panda.live_monitor.lines_view import LiveLinesView

    fig = Figure(figsize=(8, 5))
    canvas = FigureCanvasAgg(fig)
    view = LiveLinesView(fig, canvas)
    x = np.linspace(290.0, 282.0, 101)
    z = np.arange(50 * 101, dtype=float).reshape(50, 101)
    photon_energy = np.linspace(700.0, 749.0, 50)

    view.set_data(
        x,
        z,
        second_axis=photon_energy,
        second_axis_label="Photon Energy [eV]",
        xlabel="Binding Energy [eV]",
        title="panda_live_map.ibw",
        reset=True,
    )

    assert view.ax_map.get_ylabel() == "Photon Energy [eV]"
    assert view.ax_right.get_ylabel() == "Iteration"
    assert [t.get_text() for t in view.ax_map.get_yticklabels()][:3] == ["700", "705", "710"]
    assert [t.get_text() for t in view.ax_right.get_yticklabels()][:3] == ["1", "6", "11"]
    assert view.hlabel.get_text().startswith("PhE = ")


def test_iteration_second_dimension_is_mirrored_left_and_right():
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from maxiv_panda.live_monitor.lines_view import LiveLinesView

    fig = Figure(figsize=(8, 5))
    canvas = FigureCanvasAgg(fig)
    view = LiveLinesView(fig, canvas)
    x = np.linspace(170.0, 160.0, 51)
    z = np.ones((10, 51), dtype=float)

    view.set_data(
        x,
        z,
        second_axis=np.arange(1.0, 11.0),
        second_axis_label="Seq. Iteration[a.u.]",
        xlabel="Binding Energy [eV]",
        title="test.txt",
        reset=True,
    )

    assert view.ax_map.get_ylabel() == "Iteration"
    assert view.ax_right.get_ylabel() == "Iteration"
    assert view.hlabel.get_text() == "Iteration = 6"


def test_live_monitor_controls_are_above_toolbar_and_diagnostics_at_bottom():
    controls_i = WINDOW.index("layout.addLayout(controls)")
    toolbar_i = WINDOW.index("layout.addWidget(self.toolbar)")
    canvas_i = WINDOW.index("layout.addWidget(self.canvas, 1)")
    info_i = WINDOW.index("layout.addLayout(info_row)")
    assert controls_i < toolbar_i < canvas_i < info_i


def test_help_documents_live_monitor_dual_y_axis_behavior():
    assert "physical second dimension" in CONTROLS
    assert "left Y axis" in CONTROLS
    assert "Iteration" in CONTROLS
    assert "right" in CONTROLS
