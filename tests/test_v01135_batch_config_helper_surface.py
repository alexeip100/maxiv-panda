from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"


def _module_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_every_batch_config_helper_called_through_self_is_exposed_by_batch_run_mixin():
    config_path = PEAKFIT / "batch_config.py"
    run_path = PEAKFIT / "batch_run_mixin.py"
    config_source = config_path.read_text(encoding="utf-8")
    run_source = run_path.read_text(encoding="utf-8")

    config_functions = _module_functions(config_path)
    self_calls = set(re.findall(r"self\.(_[A-Za-z0-9_]+)\(", config_source))
    required_wrappers = self_calls & config_functions
    mixin_methods = _module_functions(run_path)

    assert required_wrappers <= mixin_methods, (
        "batch_config helpers invoked through self must be delegated by "
        f"BatchRunMixin; missing: {sorted(required_wrappers - mixin_methods)}"
    )


def test_batch_row_metadata_is_delegated_explicitly():
    run_source = (PEAKFIT / "batch_run_mixin.py").read_text(encoding="utf-8")
    assert "def _batch_row_metadata" in run_source
    assert "return batch_config._batch_row_metadata(self, *args, **kwargs)" in run_source
