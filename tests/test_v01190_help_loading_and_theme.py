from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "maxiv_panda"
DOCS = PKG / "docs"


def test_help_loading_promotes_drag_drop_and_balances_formats():
    controls = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")

    assert "Recommended:** drag a supported file" in controls
    assert "TXT** - Scienta/SES text exports" in controls
    assert "IBW** - Igor Binary Wave files" in controls
    assert "XY (SPECS Prodigy)** - SPECS/SpecsLab Prodigy `.xy` exports" in controls
    assert "Drag-and-drop is the quickest way to load data" in controls

    assert "### Recommended: drag and drop" in workflows
    assert "### Alternative: Load menu" in workflows
    assert "PANDA detects the format automatically" in workflows
    assert "all three formats use the same PANDA selection and analysis workflow" in workflows


def test_help_theme_uses_palette_derived_accent_without_fixed_blue():
    help_text = (PKG / "utils" / "help_text.py").read_text(encoding="utf-8")
    actions = (PKG / "ui_actions_mixin.py").read_text(encoding="utf-8")

    assert "def _blend_hex" in help_text
    assert "dark_theme = _relative_luma" in help_text
    assert "accent_soft" in help_text
    assert "border-left:0.22em solid {accent}" in help_text
    assert "color: palette(link)" in actions
    assert "border-left: 4px solid palette(link)" in actions
    assert "#174f82" not in actions


def test_help_accent_blend_moves_toward_text_in_both_theme_directions():
    from maxiv_panda.utils.help_text import _blend_hex, _relative_luma

    light_accent = _blend_hex("#2f83c5", "#202020", 0.18)
    dark_accent = _blend_hex("#2f83c5", "#eeeeee", 0.30)
    assert _relative_luma(light_accent) < _relative_luma("#2f83c5")
    assert _relative_luma(dark_accent) > _relative_luma("#2f83c5")
