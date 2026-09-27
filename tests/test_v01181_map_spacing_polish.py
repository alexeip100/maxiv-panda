from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_map_layout_reclaims_left_margin_and_keeps_y_titles_aligned():
    main = (ROOT / "src/maxiv_panda/ui_map_plot_mixin.py").read_text(encoding="utf-8")
    live = (ROOT / "src/maxiv_panda/live_monitor/lines_view.py").read_text(encoding="utf-8")
    assert main.count("_map_left = 0.100") >= 2
    assert "ax_map.yaxis.set_label_coords(-0.075, 0.5" in main
    assert "ax_bottom.yaxis.set_label_coords(-0.075, 0.5" in main
    assert "map_left = 0.100" in live
    assert "self.ax_map.yaxis.set_label_coords(-0.075, 0.5" in live
    assert "self.ax_bottom.yaxis.set_label_coords(-0.075, 0.5" in live


def test_map_toolbar_has_small_tool_gap_and_tighter_fixed_fields():
    main = (ROOT / "src/maxiv_panda/ui_map_plot_mixin.py").read_text(encoding="utf-8")
    live_window = (ROOT / "src/maxiv_panda/live_monitor/window.py").read_text(encoding="utf-8")
    live_lines = (ROOT / "src/maxiv_panda/live_monitor/lines_view.py").read_text(encoding="utf-8")
    assert "label.setContentsMargins(14, 0, 0, 0)" in main
    assert "self.toolbar.locLabel.setContentsMargins(14, 0, 0, 0)" in live_window
    assert 'x_field = f"{x_text:<14}"' in main
    assert 'y_field = f"{y_text:<16}"' in main
    assert 'return f"{x_field}  {y_field}  {intensity_field}"' in main
    assert 'return f"{x_text:<14}  {y_text:<16}  {intensity_text}"' in live_lines


def test_help_describes_compact_map_spacing():
    help_text = (ROOT / "src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
    assert "small inset after the toolbar buttons" in help_text
    assert "compact shared margin" in help_text
