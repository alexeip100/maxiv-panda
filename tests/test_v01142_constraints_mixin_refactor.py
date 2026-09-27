from pathlib import Path
import ast


EXPECTED = {
    "_constraint_display_text", "_constraint_label", "_constraint_combo_text",
    "_set_constraint_combo_items", "_param_mode", "_parse_tie_target",
    "_tie_kind_for_prefix", "_constraint_tooltip", "_apply_constraint_ui_state",
    "_resolve_tie_root", "_compute_tie_relation",
    "_refresh_all_tied_parameter_values", "_on_constraint_mode_changed",
}


def _methods(path: str, class_name: str) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    return {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}


def test_constraint_methods_live_in_dedicated_mixin():
    constraints = _methods(
        "src/maxiv_panda/workflows/peakfit/fit_dialog_constraints_mixin.py",
        "FitDialogConstraintsMixin",
    )
    fit = _methods(
        "src/maxiv_panda/workflows/peakfit/fit_dialog_fit_mixin.py",
        "FitDialogFitMixin",
    )
    assert EXPECTED <= constraints
    assert not (EXPECTED & fit)


def test_fit_dialog_wires_constraints_mixin():
    src = Path("src/maxiv_panda/workflows/peakfit/fit_dialog.py").read_text(encoding="utf-8")
    assert "from .fit_dialog_constraints_mixin import FitDialogConstraintsMixin" in src
    class_block = src.split("class FitCoreLevelDialog(", 1)[1].split("):", 1)[0]
    assert "FitDialogConstraintsMixin" in class_block
