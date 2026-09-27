from pathlib import Path


def test_intermediate_fit_refreshes_fit_range_boundaries():
    src = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_fit_mixin.py").read_text(encoding="utf-8")
    block = src.split("def _draw_intermediate_fit", 1)[1].split("def _constraint_item", 1)[0]
    assert "self._refresh_fit_range_artists()" in block
    assert "self.canvas.draw()" in block


def test_cancelled_fit_sets_interrupted_title_and_restores_overlays():
    src = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_fit_mixin.py").read_text(encoding="utf-8")
    cancelled = src.split('if isinstance(exc, FitCancelled):', 1)[1].split("else:", 1)[0]
    assert 'self._set_fit_progress("Fit interrupted")' in cancelled
    assert 'fit interrupted' in cancelled
    assert "restore_axes_view" in cancelled
    assert "self._refresh_fit_range_artists()" in cancelled
