"""Ensure default and alternative signed-map palettes are selectable."""
from __future__ import annotations
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "maxiv_panda" / "colormap_dialog.py"

def _palette_names():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "POPULAR_COLORMAPS" for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError("POPULAR_COLORMAPS list missing")

def test_default_subtraction_palette_can_be_reselected():
    names = _palette_names()
    assert "RdBu_r" in names
    assert len(names) == len(set(names))

def test_diverging_palettes_and_reverse_variants_are_listed():
    names = _palette_names()
    for name in ("RdBu", "RdBu_r", "coolwarm", "coolwarm_r", "PiYG", "PiYG_r", "BrBG", "BrBG_r", "Spectral", "Spectral_r"):
        assert name in names
