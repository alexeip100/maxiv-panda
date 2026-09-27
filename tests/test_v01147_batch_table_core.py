from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"

COMMON = {
    "_fmt_batch_value",
    "_mode_from_anchor_modes",
    "_presence_pattern",
    "_presence_note",
    "_finite_floats",
    "_suggest_peak_bounds",
    "_suggest_peak_mode",
    "_anchor_presence_kind",
    "_initial_strategy_for_peak_param",
    "_initial_strategy_for_background",
    "_mean_if_fixed",
    "_component_sort_key",
}


def _defined_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_common_batch_table_helpers_live_only_in_shared_core():
    core = _defined_functions(PEAKFIT / "batch_table_core.py")
    assert COMMON <= core
    for name in ("batch_table_builder.py", "batch_peak_only_table.py"):
        src = (PEAKFIT / name).read_text(encoding="utf-8")
        defined = _defined_functions(PEAKFIT / name)
        assert COMMON.isdisjoint(defined)
        assert "batch_table_core" not in src


def test_policy_bearing_table_functions_remain_separate():
    doublet = _defined_functions(PEAKFIT / "batch_table_builder.py")
    peak = _defined_functions(PEAKFIT / "batch_peak_only_table.py")
    for name in {
        "_make_batch_table_item",
        "_build_batch_parameter_rows_from_anchors",
        "_populate_batch_parameter_table",
    }:
        assert name in doublet
        assert name in peak


def test_doublet_specific_table_logic_stays_out_of_shared_core_and_peak_path():
    core = (PEAKFIT / "batch_table_core.py").read_text(encoding="utf-8")
    peak = (PEAKFIT / "batch_peak_only_table.py").read_text(encoding="utf-8")
    assert "so_doublets" not in core
    assert "_doublet_union_model" not in core
    assert "_build_doublet_parameter_rows" not in core
    assert "so_doublets" not in peak
    assert "_doublet_union_model" not in peak
    assert "_build_doublet_parameter_rows" not in peak
