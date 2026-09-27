from pathlib import Path
import ast


EXPECTED = {
    "_constraint_item", "_bg_constraint_display_map", "_clear_fit_results_tables",
    "_result_item_for_param", "_apply_fit_result_to_widgets",
    "_clear_fit_quality_summary", "_compute_fit_quality_metrics",
    "_update_fit_quality_summary", "_populate_fit_results_tables",
    "_capture_pre_fit_snapshot", "_on_undo_fit", "_update_fit_results_tables",
}


def _methods(path: str, class_name: str) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    return {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}


def test_result_quality_and_undo_methods_live_in_dedicated_mixin():
    results = _methods(
        "src/maxiv_panda/workflows/peakfit/fit_dialog_results_mixin.py",
        "FitDialogResultsMixin",
    )
    fit = _methods(
        "src/maxiv_panda/workflows/peakfit/fit_dialog_fit_mixin.py",
        "FitDialogFitMixin",
    )
    assert EXPECTED <= results
    assert not (EXPECTED & fit)


def test_fit_dialog_wires_results_mixin_before_fit_mixin():
    src = Path("src/maxiv_panda/workflows/peakfit/fit_dialog.py").read_text(encoding="utf-8")
    assert "from .fit_dialog_results_mixin import FitDialogResultsMixin" in src
    class_block = src.split("class FitCoreLevelDialog(", 1)[1].split("):", 1)[0]
    assert "FitDialogResultsMixin" in class_block
    assert class_block.index("FitDialogResultsMixin") < class_block.index("FitDialogFitMixin")
