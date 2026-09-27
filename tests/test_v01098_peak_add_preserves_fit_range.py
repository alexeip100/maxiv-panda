from pathlib import Path


def test_peak_rebuild_preserves_custom_fit_range_before_new_peak_defaults():
    src = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_state_mixin.py").read_text(encoding="utf-8")
    block = src.split("def _rebuild_peak_widgets", 1)[1]

    capture = "_saved_fit_range = self._current_fit_range()"
    restore = "self._fit_range = _saved_fit_range"
    defaults = "self._apply_peak_defaults_from_ranges(only_new=True, update_existing_defaults=False)"

    assert capture in block
    assert restore in block
    assert defaults in block
    # The protected range must be restored before the automatic guess for the
    # newly appended peak is calculated.
    assert block.index(restore) < block.index(defaults)
    # Keep an explicit final guard after the live redraw as well.
    assert block.rfind(restore) > block.index("self._refresh_live_calculated_spectrum()")
    assert "self._refresh_fit_range_artists()" in block
