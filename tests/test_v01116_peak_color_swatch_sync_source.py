from pathlib import Path


def test_peak_color_swatch_prefers_resolved_display_color():
    text = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_component_display_mixin.py").read_text(encoding="utf-8")
    assert 'w.get("_display_color")' in text
    assert "def _sync_peak_display_colors" in text
    assert "self._update_peak_color_button(w)" in text


def test_main_redraw_syncs_display_colors_before_component_plotting():
    text = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_component_display_mixin.py").read_text(encoding="utf-8")
    sync_pos = text.index("self._sync_peak_display_colors()", text.index("def _on_calculate_spectrum"))
    specs_pos = text.index("so_doublets.grouped_component_specs(", sync_pos)
    assert sync_pos < specs_pos


def test_marker_refresh_uses_same_display_color_sync():
    text = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_component_display_mixin.py").read_text(encoding="utf-8")
    start = text.index("def _refresh_peak_markers")
    block = text[start:start + 1200]
    assert "self._sync_peak_display_colors()" in block
