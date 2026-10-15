from pathlib import Path


def test_macos_subtraction_toggle_uses_deferred_redraw():
    source = (Path(__file__).resolve().parents[1] / "src/maxiv_panda/ui_map_controls_mixin.py").read_text()
    section = source.split("    def _on_respes_preedge_toggled(", 1)[1].split("    def _seed_respes_preedge_interval", 1)[0]
    assert 'sys.platform == "darwin"' in section
    assert "self._schedule_update_plot_from_selected()" in section
    assert "self._update_plot_from_selected()" in section
    assert "self._sync_respes_controls()" in section
