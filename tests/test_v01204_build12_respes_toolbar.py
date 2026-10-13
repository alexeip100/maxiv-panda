"""Protect the compact ResPES toolbar and Windows-native spinbox rendering."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / "src/maxiv_panda"
UI = (ROOT / "ui.py").read_text(encoding="utf8")
PLOT = (ROOT / "ui_map_plot_mixin.py").read_text(encoding="utf8")
CONTROLS = (ROOT / "ui_map_controls_mixin.py").read_text(encoding="utf8")

def test_coordinates_overlay_map_without_new_layout_row():
    assert 'self.map_coordinate_label = QLabel(self.canvas)' in UI
    assert 'WA_TransparentForMouseEvents' in UI
    assert 'overlay.move(' in PLOT
    assert 'overlay.show()' in PLOT
    assert 'layout.addWidget(self.map_coordinate_label)' not in UI
    assert 'compact_respes=True' in PLOT
    assert 'ax.transData.inverted().transform((event.x, event.y))' in PLOT
    assert 'native.setVisible(not is_respes)' in PLOT

def test_step_buttons_use_native_windows_style():
    assert 'spin_frame_style' not in CONTROLS
    assert 'QDoubleSpinBox {' not in CONTROLS
