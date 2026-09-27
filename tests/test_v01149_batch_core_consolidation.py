from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                names.add(f"{module}:{alias.name}")
    return names


def test_path_modules_do_not_reexport_shared_core_helpers():
    pairs = [
        ("batch_config.py", "batch_config_core"),
        ("batch_peak_only_config.py", "batch_config_core"),
        ("batch_table_builder.py", "batch_table_core"),
        ("batch_peak_only_table.py", "batch_table_core"),
        ("batch_runner.py", "batch_runner_core"),
        ("batch_peak_only_runner.py", "batch_runner_core"),
    ]
    for filename, core_name in pairs:
        src = (PEAKFIT / filename).read_text(encoding="utf-8")
        assert f"from .{core_name} import" not in src


def test_mixins_delegate_shared_helpers_directly_to_cores():
    prepare = (PEAKFIT / "batch_prepare_setup_mixin.py").read_text(encoding="utf-8")
    run = (PEAKFIT / "batch_run_mixin.py").read_text(encoding="utf-8")
    assert "batch_table_core._fmt_batch_value" in prepare
    assert "batch_table_core._component_sort_key" in prepare
    assert "batch_config_core._cell_text" in run
    assert "batch_config_core._validate_and_build_batch_config" in run
    assert "batch_runner_core._request_stop_batch_fit" in run
    assert "batch_runner_core._run_batch_fit_from_guesses" in run


def test_only_policy_bearing_calls_route_through_path_modules():
    prepare = (PEAKFIT / "batch_prepare_setup_mixin.py").read_text(encoding="utf-8")
    run = (PEAKFIT / "batch_run_mixin.py").read_text(encoding="utf-8")
    assert "module._make_batch_table_item" in prepare
    assert "module._build_batch_parameter_rows_from_anchors" in prepare
    assert "module._populate_batch_parameter_table" in prepare
    assert "module._anchor_descriptor_for_batch_config" in run
    assert "module._validate_batch_parameter_row" in run
    assert "module._build_batch_config_from_table" in run
    assert "module._anchor_positions_for_initial_guesses" in run
    assert "module._interpolated_guess_value" in run
    assert "module._build_initial_guess_sequence" in run
    assert "module._fit_one_batch_spectrum" in run


def test_stale_reload_workaround_removed_from_table_policies():
    for filename in ("batch_table_builder.py", "batch_peak_only_table.py"):
        src = (PEAKFIT / filename).read_text(encoding="utf-8")
        assert 'globals()["re"]' not in src
        assert "import re as _re" not in src
