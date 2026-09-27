from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src" / "maxiv_panda" / "ui.py").read_text(encoding="utf-8")
LIVE = (ROOT / "src" / "maxiv_panda" / "live_monitor" / "window.py").read_text(encoding="utf-8")
MAP_CONTROLS = (ROOT / "src" / "maxiv_panda" / "ui_map_controls_mixin.py").read_text(encoding="utf-8")
PROCESSED = (ROOT / "src" / "maxiv_panda" / "ui_processed_data_mixin.py").read_text(encoding="utf-8")
HELP = (ROOT / "src" / "maxiv_panda" / "docs" / "usage_controls.md").read_text(encoding="utf-8")


def test_palette_hint_requires_one_second_stationary_dwell():
    assert "setInterval(1000)" in UI
    assert "_map_palette_hint_dwell_timer.start()" in UI
    assert "_show_map_palette_hint_after_dwell" in UI
    assert "setInterval(1000)" in LIVE
    assert "_palette_hint_dwell_timer.start()" in LIVE
    assert "_show_palette_hint_after_dwell" in LIVE


def test_palette_hint_remains_visible_for_five_seconds_after_dwell():
    assert "QRect(),\n                5000" in UI
    assert "QRect(),\n                5000" in LIVE


def test_representation_and_tab_changes_start_fresh_hint_visit():
    assert "reset_map_palette_hint_visit" in MAP_CONTROLS
    assert "reset_map_palette_hint_visit" in PROCESSED
    assert "_map_palette_hint_epoch += 1" in UI


def test_help_describes_dwell_and_repeat_per_representation_visit():
    assert "remains still for about one second" in HELP
    assert "once per representation visit" in HELP
    assert "switching between Raw Data, Simple, Lines, ROI" in HELP
