from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"


def test_generic_control_metrics_do_not_shrink_feature_minima():
    style = (PKG / "ui_style.py").read_text(encoding="utf-8")
    assert 'flexpes_original_min_height' in style
    assert 'max(int(original), target_height)' in style


def test_element_tiles_have_live_accessibility_role():
    dialogs = (PKG / "signal_identification" / "dialogs.py").read_text(encoding="utf-8")
    style = (PKG / "ui_style.py").read_text(encoding="utf-8")
    assert 'register_widget_role(self, "element_tile")' in dialogs
    assert 'role == "element_tile"' in style
    assert 'tile_min = 48 + 3 * max(0, offset)' in style


def test_reference_conditions_are_not_fixed_height():
    source = (PKG / "signal_identification" / "cross_section_reference.py").read_text(encoding="utf-8")
    assert 'controls.setMaximumHeight(82)' not in source
    assert 'controls.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)' in source


def test_reference_panels_do_not_pin_ui_font_sizes():
    for name in ("cross_section_reference.py", "binding_energy_reference.py"):
        source = (PKG / "signal_identification" / name).read_text(encoding="utf-8")
        assert 'font-size: 11pt' not in source
        assert 'font-size: 13pt' not in source
