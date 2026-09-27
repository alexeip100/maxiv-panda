from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"
ANALYSIS = PEAKFIT / "batch_analysis.py"
CONSTRAINTS = PEAKFIT / "batch_analysis_constraints.py"
MIXIN = PEAKFIT / "batch_analyze_mixin.py"

MOVED = {
    "_derived_so_minor_peak_indices",
    "_is_derived_so_minor_target",
    "_refresh_smoothing_target_combo",
    "_current_smoothing_target",
    "_target_sort_key",
    "_target_short_label",
    "_collect_trend_points_for_target",
    "_table_bounds_for_target",
    "_fit_selected_smooth_trend",
    "_add_update_next_pass_constraint",
    "_refresh_next_constraints_table",
    "_enabled_next_constraints_from_table",
    "_constraint_compact_list",
    "_next_strategy_pass_number",
    "_prepare_next_constrained_pass",
}


def _functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_constraint_workflow_has_dedicated_module():
    assert CONSTRAINTS.exists()
    assert MOVED <= _functions(CONSTRAINTS)
    assert not (MOVED & _functions(ANALYSIS))


def test_shared_series_identity_has_single_owner_outside_constraints():
    plot = PEAKFIT / "batch_analysis_plot.py"
    assert "_series_key_from_payload" in _functions(plot)
    assert "_series_key_from_payload" not in _functions(CONSTRAINTS)


def test_analyze_mixin_delegates_constraint_workflow_to_new_module():
    source = MIXIN.read_text(encoding="utf-8")
    assert "batch_analysis_constraints" in source
    for name in MOVED:
        assert f"batch_analysis_constraints.{name}(self, *args, **kwargs)" in source


def test_minor_doublet_next_pass_guards_survive_split():
    source = CONSTRAINTS.read_text(encoding="utf-8")
    assert "minor_peak_indices = self._derived_so_minor_peak_indices()" in source
    assert "_is_derived_so_minor_target" in source
    assert "invalid_minor_constraints" in source
    assert "derived SO-doublet minor" in source or "SO-doublet minor" in source
