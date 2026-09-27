"""Checkpoint guards for the 0.11.40–0.11.44 single-fit dialog refactor."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src/maxiv_panda/workflows/peakfit"

REFRACTORED = (
    "fit_dialog.py",
    "fit_dialog_background_mixin.py",
    "fit_dialog_component_display_mixin.py",
    "fit_dialog_curve_mixin.py",
    "fit_dialog_fit_mixin.py",
    "fit_dialog_peak_interaction_mixin.py",
    "fit_dialog_state_mixin.py",
    "fit_dialog_doublet_mixin.py",
    "fit_dialog_constraints_mixin.py",
    "fit_dialog_io_mixin.py",
    "fit_dialog_results_mixin.py",
)


def _unused_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    unused: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                if bound not in used:
                    unused.append(bound)
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound = alias.asname or alias.name
                if bound not in used:
                    unused.append(bound)
    return unused


def test_refactored_fit_dialog_modules_have_no_stale_imports():
    stale = {}
    for name in REFRACTORED:
        unused = _unused_imports(PEAKFIT / name)
        if unused:
            stale[name] = unused
    assert stale == {}


def test_fit_dialog_composes_all_refactored_responsibilities():
    source = (PEAKFIT / "fit_dialog.py").read_text(encoding="utf-8")
    for mixin in (
        "FitDialogDoubletMixin",
        "FitDialogConstraintsMixin",
        "FitDialogIOMixin",
        "FitDialogStateMixin",
        "FitDialogResultsMixin",
        "FitDialogFitMixin",
    ):
        assert f"    {mixin}," in source
