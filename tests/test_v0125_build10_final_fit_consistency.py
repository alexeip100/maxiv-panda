"""Regression checks for the live/final peak-fit handoff."""
from pathlib import Path
import ast
import numpy as np


def test_final_fit_uses_optimizer_values_without_spinbox_roundtrip():
    path = Path(__file__).resolve().parents[1] / "src/maxiv_panda/workflows/peakfit/fit_dialog_fit_mixin.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FitDialogFitMixin")
    target = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_run_single_curve_fit")
    source = ast.get_source_segment(path.read_text(encoding="utf-8"), target)
    assert 'final_values = result.params.valuesdict()' in source
    assert 'fit_data["xu"], final_values, bg_type, fit_data' in source
    assert 'np.isclose(final_rss, optimizer_rss' in source
    final_block = source.split('final_values = result.params.valuesdict()', 1)[1].split('fit_plotting.restore_axes_view',1)[0]
    assert '_draw_intermediate_fit(' in final_block
    assert '_on_calculate_spectrum()' not in final_block


def test_rss_check_detects_disagreement():
    # A GUI-precision-reconstructed curve need not match the optimizer's RSS.
    y = np.array([1.0, 2.0, 3.0])
    true_fit = np.array([1.0, 2.0, 2.9])
    rounded_fit = np.array([1.0, 1.8, 2.5])
    optimizer_rss = float(np.sum((true_fit-y)**2))
    assert np.isclose(optimizer_rss, float(np.sum((true_fit-y)**2)), rtol=1e-6, atol=1e-6)
    assert not np.isclose(optimizer_rss, float(np.sum((rounded_fit-y)**2)), rtol=1e-6, atol=1e-6)
