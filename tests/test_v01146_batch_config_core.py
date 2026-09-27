from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"

COMMON = {
    "_cell_text",
    "_parse_optional_float",
    "_json_clean_value",
    "_sequence_descriptor_for_batch_config",
    "_anchor_center_index",
    "_clip_guess_to_bounds",
    "_fallback_guess_value",
    "_natural_label_sort_key",
    "_validate_and_build_batch_config",
}


def _defined_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_common_batch_config_helpers_live_only_in_shared_core():
    core = _defined_functions(PEAKFIT / "batch_config_core.py")
    assert COMMON <= core
    for name in ("batch_config.py", "batch_peak_only_config.py"):
        src = (PEAKFIT / name).read_text(encoding="utf-8")
        defined = _defined_functions(PEAKFIT / name)
        assert COMMON.isdisjoint(defined)
        assert "batch_config_core" not in src


def test_path_specific_config_builders_remain_separate():
    doublet = _defined_functions(PEAKFIT / "batch_config.py")
    peak = _defined_functions(PEAKFIT / "batch_peak_only_config.py")
    for name in {
        "_anchor_descriptor_for_batch_config",
        "_validate_batch_parameter_row",
        "_build_batch_config_from_table",
        "_anchor_positions_for_initial_guesses",
        "_interpolated_guess_value",
        "_build_initial_guess_sequence",
    }:
        assert name in doublet
        assert name in peak


def test_shared_core_contains_no_doublet_policy():
    src = (PEAKFIT / "batch_config_core.py").read_text(encoding="utf-8")
    assert "so_doublets" not in src
    assert "doublet_models" not in src
    assert "doublet-aware" not in src
