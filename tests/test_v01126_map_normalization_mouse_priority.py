from pathlib import Path


def test_lines_and_roi_normalization_band_remains_wired():
    src = Path("src/maxiv_panda/ui_map_plot_mixin.py").read_text(encoding="utf-8")
    lines_start = src.index("def _plot_single_map_with_cross_sections")
    roi_start = src.index("def _plot_single_map_with_roi")
    respes_start = src.index("def _plot_respes_map") if "def _plot_respes_map" in src else len(src)
    lines = src[lines_start:roi_start]
    roi = src[roi_start:respes_start]
    assert "_draw_map_normalization_band(ax_map, norm_interval, norm_mode, norm_callback)" in lines
    assert "_draw_map_normalization_band(ax_map, norm_interval, norm_mode, norm_callback)" in roi


def test_help_describes_coexisting_mouse_controls():
    controls = Path("src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
    workflows = Path("src/maxiv_panda/docs/usage_workflows.md").read_text(encoding="utf-8")
    assert "Lines" in controls and "ROI" in controls
    assert "take priority" in controls
    assert "Lines" in workflows and "ROI" in workflows and "takes priority" in workflows
