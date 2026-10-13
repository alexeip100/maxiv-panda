from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_new_normalization_modes_are_exposed():
    text = (ROOT / "src/maxiv_panda/ui_processed_data_mixin.py").read_text(encoding="utf-8")
    assert 'addItem("BE interval", "at_be")' in text
    assert 'addItem("KE interval", "at_ke")' in text
    assert 'addItem("Spectrum area", "area")' in text
    assert 'addItem("Photon-E interval", "at_hv")' in text


def test_respes_plot_uses_physical_overlay_for_new_interval_modes():
    text = (ROOT / "src/maxiv_panda/ui_map_plot_mixin.py").read_text(encoding="utf-8")
    assert 'norm_mode in {"at_be", "at_ke", "at_hv"}' in text
    assert "_draw_respes_normalization_region(" in text
    assert 'mode == "at_hv"' in text


def test_respes_physical_defaults_precede_raw_x_axis_defaults():
    text = (ROOT / "src/maxiv_panda/ui_map_controls_mixin.py").read_text(encoding="utf-8")
    ensure = text.split("def _ensure_map_normalization_defaults", 1)[1].split("def _current_map_norm_interval", 1)[0]
    assert ensure.index("_respes_normalization_defaults()") < ensure.index("elif default_be is not None")
    assert "Clamp any retained/stale physical settings" in ensure
