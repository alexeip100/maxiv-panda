from pathlib import Path

import numpy as np

from maxiv_panda.ui_map_plot_mixin import MapPlotMixin


class Dummy(MapPlotMixin):
    pass


def test_lines_position_memory_uses_physical_coordinates():
    obj = Dummy()
    obj._map_lines_position_memory = {}
    state = {
        "title": "map A",
        "xlabel": "Binding Energy [eV]",
        "x": np.array([10.0, 9.0, 8.0, 7.0]),
        "y_labels": [1.0, 2.0, 3.0],
        "cols": 4,
        "rows": 3,
        "col": 1,
        "row": 1,
        "animation_v_position": 1.5,
        "animation_h_position": 0.5,
    }
    obj._remember_map_lines_state(state)
    saved = obj._map_lines_position_memory[("map A", "Binding Energy [eV]")]
    assert saved["x"] == 8.5
    assert saved["y"] == 1.5


def test_plot_many_saves_lines_position_before_clearing_transient_state():
    source = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
    remember = source.index("self._remember_map_lines_state()")
    clear = source.index("self._map_cross_state = None", remember)
    assert remember < clear


def test_help_describes_cursor_position_persistence():
    controls = Path("src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
    assert "Lines cursor positions are remembered for each map" in controls
    assert "palette changes" in controls
    assert "Raw/Processed Data tabs" in controls


def test_lines_memory_key_ignores_display_only_binning_suffix():
    key_plain = Dummy._map_lines_memory_key("XPS_026 (map)", "Kinetic Energy [eV]")
    key_binned = Dummy._map_lines_memory_key("XPS_026 (map) — binned by 5", "Kinetic Energy [eV]")
    assert key_plain == key_binned
