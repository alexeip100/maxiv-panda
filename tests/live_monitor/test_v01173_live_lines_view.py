from pathlib import Path
from types import SimpleNamespace

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from maxiv_panda.live_monitor.lines_view import LiveLinesView

ROOT = Path(__file__).resolve().parents[2]
WINDOW = (ROOT / "src" / "maxiv_panda" / "live_monitor" / "window.py").read_text(encoding="utf-8")
CONTROLS = (ROOT / "src" / "maxiv_panda" / "docs" / "usage_controls.md").read_text(encoding="utf-8")
WORKFLOWS = (ROOT / "src" / "maxiv_panda" / "docs" / "usage_workflows.md").read_text(encoding="utf-8")


def _view(rows=10, cols=21):
    fig = Figure(figsize=(8, 6))
    canvas = FigureCanvasAgg(fig)
    view = LiveLinesView(fig, canvas)
    x = np.linspace(170.0, 160.0, cols)
    z = np.arange(rows * cols, dtype=float).reshape(rows, cols)
    view.set_data(
        x, z, second_axis=np.arange(1, rows + 1, dtype=float),
        xlabel="Binding Energy [eV]", title="live", reset=True,
    )
    return view, canvas, x, z


def test_live_lines_layout_and_profiles():
    view, canvas, x, z = _view()
    assert len(view.figure.axes) == 4
    assert view.ax_bottom is not None and view.ax_right is not None
    assert np.asarray(view.bottom_line.get_ydata()).shape == (z.shape[1],)
    assert np.asarray(view.right_line.get_xdata()).shape == (z.shape[0],)
    assert view.vline_bottom is not None and view.hline_right is not None
    canvas.draw()


def test_live_lines_thickness_and_cursor_positions_survive_growth():
    view, canvas, x, z = _view()
    view.set_thickness(3, 5)
    view._set_row(2)
    view._set_col(4)
    old_x = float(view.x[view.col])
    old_y = view._row_coordinate(view.row)
    z2 = np.vstack([z, z[:3] + 1000.0])
    view.set_data(
        x, z2, second_axis=np.arange(1, z2.shape[0] + 1, dtype=float),
        xlabel="Binding Energy [eV]", title="live", reset=False,
    )
    assert view.h_thickness == 3
    assert view.v_thickness == 5
    assert view.hband.get_visible() and view.vband.get_visible()
    assert float(view.x[view.col]) == old_x
    assert view._row_coordinate(view.row) == old_y
    canvas.draw()



def test_live_lines_drag_map_crossing_and_side_guides():
    view, canvas, x, z = _view(rows=10, cols=21)
    canvas.draw()

    # Crossing-point drag moves both cursors.
    x0 = float(view.x[view.col])
    y0 = float(view.row) + 0.5
    px, py = view.ax_map.transData.transform((x0, y0))
    view._on_press(SimpleNamespace(inaxes=view.ax_map, x=px, y=py, xdata=x0, ydata=y0))
    assert view._drag_axis == "both"
    target_col, target_row = 3, 2
    tx = float(view.x[target_col]); ty = float(target_row) + 0.5
    px2, py2 = view.ax_map.transData.transform((tx, ty))
    view._on_motion(SimpleNamespace(inaxes=view.ax_map, x=px2, y=py2, xdata=tx, ydata=ty))
    view._on_release(None)
    assert view.col == target_col and view.row == target_row

    # Bottom trace guide drags the vertical/X cursor.
    guide_x = float(view.x[view.col])
    gx = view.ax_bottom.transData.transform((guide_x, 0.0))[0]
    view._on_press(SimpleNamespace(inaxes=view.ax_bottom, x=gx, y=0.0, xdata=guide_x, ydata=0.0))
    assert view._drag_axis == "x_bottom"
    target_col = 15
    tx = float(view.x[target_col])
    view._on_motion(SimpleNamespace(inaxes=view.ax_bottom, x=gx, y=0.0, xdata=tx, ydata=0.0))
    view._on_release(None)
    assert view.col == target_col

    # Right trace guide drags the horizontal/Y cursor.
    guide_y = float(view.row) + 0.5
    gy = view.ax_right.transData.transform((0.0, guide_y))[1]
    view._on_press(SimpleNamespace(inaxes=view.ax_right, x=0.0, y=gy, xdata=0.0, ydata=guide_y))
    assert view._drag_axis == "y_right"
    target_row = 7
    ty = float(target_row) + 0.5
    view._on_motion(SimpleNamespace(inaxes=view.ax_right, x=0.0, y=gy, xdata=0.0, ydata=ty))
    view._on_release(None)
    assert view.row == target_row

def test_live_monitor_exposes_only_lines_thickness_controls():
    assert 'QLabel("H thickness"' in WINDOW
    assert 'QLabel("V thickness"' in WINDOW
    assert "Animation..." not in WINDOW
    assert "Plot H-trace" not in WINDOW
    assert "Plot V-trace" not in WINDOW


def test_help_describes_live_lines_interactions():
    for text in (CONTROLS, WORKFLOWS):
        assert "H thickness" in text
        assert "V thickness" in text
        assert "crossing point" in text
        assert "trace" in text.lower()
