from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"


def _functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_analytical_trend_helpers_are_owned_by_dedicated_module() -> None:
    analysis = PEAKFIT / "batch_analysis.py"
    trends = PEAKFIT / "batch_analysis_trends.py"
    assert trends.exists()

    moved = {
        "_refresh_trend_fit_target_combo",
        "_current_trend_fit_target",
        "_on_trend_fit_target_changed",
        "_on_trend_fit_model_changed",
        "_set_trend_fit_formula_label",
        "_selected_trend_model_code",
        "_selected_trend_poly_order",
        "_fit_selected_analysis_trend",
        "_accept_trend_analysis_fit",
        "_clear_selected_trend_analysis_fit",
        "_clear_all_trend_analysis_fits",
        "_trend_fit_summary_line",
        "_update_trend_analysis_summary",
    }
    assert moved <= _functions(trends)
    assert not (moved & _functions(analysis))


def test_next_pass_constraint_logic_remains_separate_from_analytical_trends() -> None:
    analysis_functions = _functions(PEAKFIT / "batch_analysis.py")
    trends_functions = _functions(PEAKFIT / "batch_analysis_trends.py")
    constraint_functions = _functions(PEAKFIT / "batch_analysis_constraints.py")
    sensitive = {
        "_derived_so_minor_peak_indices",
        "_is_derived_so_minor_target",
        "_refresh_smoothing_target_combo",
        "_fit_selected_smooth_trend",
        "_add_update_next_pass_constraint",
        "_prepare_next_constrained_pass",
    }
    assert sensitive <= constraint_functions
    assert not (sensitive & trends_functions)
    assert not (sensitive & analysis_functions)


def test_mixin_preserves_analytical_trend_entry_points() -> None:
    text = (PEAKFIT / "batch_analyze_mixin.py").read_text(encoding="utf-8")
    assert "batch_analysis_trends" in text
    for name in (
        "_refresh_trend_fit_target_combo",
        "_on_trend_fit_target_changed",
        "_on_trend_fit_model_changed",
        "_fit_selected_analysis_trend",
        "_accept_trend_analysis_fit",
        "_clear_selected_trend_analysis_fit",
        "_clear_all_trend_analysis_fits",
        "_update_trend_analysis_summary",
    ):
        assert f"return batch_analysis_trends.{name}" in text
        assert f"return batch_analysis.{name}" not in text


def test_batch_analysis_is_smaller_after_trend_split() -> None:
    line_count = len((PEAKFIT / "batch_analysis.py").read_text(encoding="utf-8").splitlines())
    assert line_count < 900
