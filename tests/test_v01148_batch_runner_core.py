from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"

COMMON = {
    "_request_stop_batch_fit",
    "_payload_for_batch_spectrum",
    "_collect_fit_data_from_payload",
    "_batch_human_readable_param_name",
    "_resolve_batch_tie_meta",
    "_peak_specs_from_batch_fit_state",
    "_bg_values_from_batch_fit_state",
    "_build_batch_model_from_values",
    "_update_batch_monitor_plot",
    "_result_has_full_plot_data",
    "_selected_run_pass",
    "_refresh_batch_fit_navigation_controls",
    "_on_batch_fit_navigation_changed",
    "_step_batch_fit_navigation",
    "_confirm_run_strategy",
    "_run_selected_batch_strategy",
    "_run_independent_batch_fit",
    "_constraint_value_map",
    "_apply_constraints_to_fit_state",
    "_build_constrained_guesses_from_strategy",
    "_run_constrained_batch_fit",
    "_run_batch_fit_from_guesses",
}


def _defined_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_common_batch_runner_helpers_live_only_in_shared_core():
    core = _defined_functions(PEAKFIT / "batch_runner_core.py")
    assert COMMON <= core
    for name in ("batch_runner.py", "batch_peak_only_runner.py"):
        src = (PEAKFIT / name).read_text(encoding="utf-8")
        defined = _defined_functions(PEAKFIT / name)
        assert COMMON.isdisjoint(defined)
        assert "batch_runner_core" not in src


def test_path_specific_fit_one_spectrum_remains_separate():
    doublet = _defined_functions(PEAKFIT / "batch_runner.py")
    peak = _defined_functions(PEAKFIT / "batch_peak_only_runner.py")
    assert "_fit_one_batch_spectrum" in doublet
    assert "_fit_one_batch_spectrum" in peak


def test_doublet_specific_runner_logic_stays_out_of_shared_core_and_peak_path():
    core = (PEAKFIT / "batch_runner_core.py").read_text(encoding="utf-8")
    peak = (PEAKFIT / "batch_peak_only_runner.py").read_text(encoding="utf-8")
    doublet = (PEAKFIT / "batch_runner.py").read_text(encoding="utf-8")
    assert "so_doublets" not in core
    assert "so_doublets" not in peak
    assert "so_doublets" in doublet
