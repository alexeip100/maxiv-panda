from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_map_normalization_cog_removed_and_combo_can_reopen_settings():
    ui = _read("src/maxiv_panda/ui_processed_data_mixin.py")
    controls = _read("src/maxiv_panda/ui_map_controls_mixin.py")
    assert "btn_map_norm_settings" not in ui
    assert "cb_map_normalization.activated.connect(self._on_map_normalization_activated)" in ui
    assert "def _on_map_normalization_activated" in controls


def test_lines_has_independent_h_and_v_auto_scale_controls():
    src = _read("src/maxiv_panda/ui_map_plot_mixin.py")
    assert '"Auto scale H"' in src
    assert '"Auto scale V"' in src
    assert "_map_lines_auto_scale_h" in src
    assert "_map_lines_auto_scale_v" in src


def test_cross_section_plot_marks_selected_photon_energy_intersections():
    src = _read("src/maxiv_panda/signal_identification/cross_section_reference.py")
    assert "angular_cross_section_at(" in src
    assert 'marker="o"' in src
    assert 'label="_nolegend_"' in src


def test_single_fit_window_has_default_visible_legend_checkbox():
    src = _read("src/maxiv_panda/workflows/peakfit/fit_dialog.py")
    plotting = _read("src/maxiv_panda/workflows/peakfit/fit_plotting.py")
    assert 'QCheckBox("Legend"' in src
    assert "self.cb_fit_legend.setChecked(True)" in src
    assert "def _refresh_fit_legend" in src
    assert 'label="Measured data"' in plotting
    assert 'label="Background"' in plotting
    assert 'label="Total fit"' in plotting
