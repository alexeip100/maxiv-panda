from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_CONTROLS = ROOT / "src" / "maxiv_panda" / "ui_map_controls_mixin.py"
PROCESSED = ROOT / "src" / "maxiv_panda" / "ui_processed_data_mixin.py"


def test_map_control_visibility_is_centralized_and_called_after_silent_simple_reset():
    controls_src = MAP_CONTROLS.read_text(encoding="utf-8")
    processed_src = PROCESSED.read_text(encoding="utf-8")

    assert "def _sync_map_analysis_control_visibility" in controls_src
    assert "trace_controls.setVisible(lines_active or roi_active)" in controls_src
    assert "bin_controls.setVisible(lines_active)" in controls_src
    assert "roi_controls.setVisible(roi_active)" in controls_src
    assert "lines_active, roi_active = self._sync_map_analysis_control_visibility()" in controls_src

    # Fresh Processed-map activation changes the hidden radio state with signals
    # blocked, so it must explicitly call the same visibility synchronizer.
    assert 'sync_visibility = getattr(self, "_sync_map_analysis_control_visibility", None)' in processed_src
    assert "sync_visibility()" in processed_src


def test_simple_visibility_contract_has_no_lines_or_roi_exceptions():
    src = MAP_CONTROLS.read_text(encoding="utf-8")
    start = src.index("def _sync_map_analysis_control_visibility")
    end = src.index("def _on_map_analysis_mode_changed", start)
    helper = src[start:end]

    # Simple is represented by neither Lines nor ROI being active; therefore all
    # representation-specific groups are hidden directly from those booleans.
    assert "setVisible(lines_active or roi_active)" in helper
    assert "setVisible(lines_active)" in helper
    assert "setVisible(roi_active)" in helper
