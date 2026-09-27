from pathlib import Path


def _panel_source() -> str:
    return (Path(__file__).parents[2] / "src" / "maxiv_panda" / "workflows" / "plotting" / "panel.py").read_text(encoding="utf-8")


def test_plotted_panel_uses_explicit_margins_not_tight_layout():
    src = _panel_source()
    assert "tight_layout(" not in src
    assert "def _apply_plot_margins" in src


def test_waterfall_has_fixed_color_controls():
    src = _panel_source()
    assert 'QCheckBox("Fixed color:"' in src
    assert "_waterfall_monochrome_enabled" in src
    assert "_choose_waterfall_mono_color" in src
    assert "self.chk_waterfall_mono.setChecked(False)" in src
