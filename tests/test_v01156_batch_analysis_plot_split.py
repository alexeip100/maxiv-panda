from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"
ANALYSIS = PEAKFIT / "batch_analysis.py"
PLOT = PEAKFIT / "batch_analysis_plot.py"
MIXIN = PEAKFIT / "batch_analyze_mixin.py"

MOVED = {
    "_on_analyze_parameter_type_changed",
    "_on_analyze_parameter_item_changed",
    "_populate_analyze_parameter_tree",
    "_selected_analyze_series",
    "_value_for_analyze_series",
    "_series_key_from_payload",
    "_update_analyze_trend_plot",
}

def _functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}

def test_plotting_and_series_helpers_have_dedicated_module():
    assert PLOT.exists()
    assert MOVED <= _functions(PLOT)
    assert not (MOVED & _functions(ANALYSIS))

def test_analyze_mixin_delegates_plot_helpers_to_new_module():
    source = MIXIN.read_text(encoding="utf-8")
    assert "batch_analysis_plot" in source
    for name in MOVED - {"_series_key_from_payload"}:
        assert f"batch_analysis_plot.{name}(self, *args, **kwargs)" in source

def test_general_analysis_is_now_orchestration_only():
    funcs = _functions(ANALYSIS)
    assert funcs == {"_available_analyze_parameter_types", "_refresh_analyze_results_tab"}
    assert len(ANALYSIS.read_text(encoding="utf-8").splitlines()) < 220

def test_shared_series_key_importers_follow_new_owner():
    for name in ("batch_analysis_export.py", "batch_analysis_trends.py"):
        text = (PEAKFIT / name).read_text(encoding="utf-8")
        assert "from .batch_analysis_plot import _series_key_from_payload" in text
        assert "from .batch_analysis import _series_key_from_payload" not in text
