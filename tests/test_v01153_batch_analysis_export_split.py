from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"


def _functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


def test_export_helpers_are_owned_by_dedicated_module() -> None:
    analysis = PEAKFIT / "batch_analysis.py"
    export = PEAKFIT / "batch_analysis_export.py"
    assert export.exists()

    moved = {
        "_sanitize_export_name",
        "_result_display_base",
        "_selected_parameter_label_for_filename",
        "_pass_number_fragment",
        "_series_column_name",
        "_pass_sort_number",
        "_constraint_label_list",
        "_binning_metadata_for_pass",
        "_analyze_pass_history_lines",
        "_collect_current_analyze_export_rows",
        "_region_fragment_from_text",
        "_data_file_fragment_for_filename",
        "_suggest_analyze_export_filename",
        "_export_analyze_trends_csv",
        "_suggest_all_fits_zip_filename",
        "_export_all_batch_fits_zip",
    }
    assert moved <= _functions(export)
    assert not (moved & _functions(analysis))


def test_analysis_keeps_shared_series_identity_without_duplication() -> None:
    plot = PEAKFIT / "batch_analysis_plot.py"
    export = PEAKFIT / "batch_analysis_export.py"
    assert "_series_key_from_payload" in _functions(plot)
    assert "_series_key_from_payload" not in _functions(export)
    export_text = export.read_text(encoding="utf-8")
    assert "from .batch_analysis_plot import _series_key_from_payload" in export_text


def test_mixin_preserves_export_entry_points_but_delegates_to_export_module() -> None:
    mixin = (PEAKFIT / "batch_analyze_mixin.py").read_text(encoding="utf-8")
    assert "batch_analysis_export" in mixin
    assert "return batch_analysis_export._export_analyze_trends_csv" in mixin
    assert "return batch_analysis_export._export_all_batch_fits_zip" in mixin
    assert "return batch_analysis._export_analyze_trends_csv" not in mixin
    assert "return batch_analysis._export_all_batch_fits_zip" not in mixin


def test_batch_analysis_is_materially_smaller_after_export_split() -> None:
    line_count = len((PEAKFIT / "batch_analysis.py").read_text(encoding="utf-8").splitlines())
    assert line_count < 1200
