from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"
ANALYSIS = PEAKFIT / "batch_analysis.py"
ANALYZE_MIXIN = PEAKFIT / "batch_analyze_mixin.py"
TRENDS = PEAKFIT / "batch_analysis_trends.py"
CONSTRAINTS = PEAKFIT / "batch_analysis_constraints.py"


def _function_source(name: str) -> str:
    for path in (ANALYSIS, TRENDS, CONSTRAINTS):
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        lines = source.splitlines()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                end = getattr(node, "end_lineno", node.lineno)
                return "\n".join(lines[node.lineno - 1:end])
    raise AssertionError(f"Function {name} not found")


def test_minor_doublet_members_are_excluded_only_from_next_pass_target_combo():
    smoothing = _function_source("_refresh_smoothing_target_combo")
    analytical = _function_source("_refresh_trend_fit_target_combo")
    assert "_derived_so_minor_peak_indices" in smoothing
    assert "minor_peak_indices" in smoothing
    assert "continue" in smoothing
    # General analytical trend fitting remains diagnostic and may still inspect
    # the minor-member trends; only next-pass constraint targeting is restricted.
    assert "_derived_so_minor_peak_indices" not in analytical


def test_minor_target_detection_reads_result_doublet_topology():
    helper = _function_source("_derived_so_minor_peak_indices")
    assert 'fit_state.get("so_doublets")' in helper
    assert 'doublet.get("minor")' in helper


def test_minor_constraint_has_creation_and_execution_backstops():
    smooth_fit = _function_source("_fit_selected_smooth_trend")
    add_constraint = _function_source("_add_update_next_pass_constraint")
    prepare = _function_source("_prepare_next_constrained_pass")
    assert "_is_derived_so_minor_target" in smooth_fit
    assert "_is_derived_so_minor_target" in add_constraint
    assert "invalid_minor_constraints" in prepare
    assert "_is_derived_so_minor_target" in prepare


def test_smoothing_tooltip_explains_minor_omission():
    source = ANALYZE_MIXIN.read_text(encoding="utf-8")
    assert "Derived SO-doublet minor members remain plottable but are omitted here" in source
