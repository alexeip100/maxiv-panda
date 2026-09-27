from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src" / "maxiv_panda" / "ui.py").read_text(encoding="utf-8")
LIVE = (ROOT / "src" / "maxiv_panda" / "live_monitor" / "window.py").read_text(encoding="utf-8")
HELP_CONTROLS = (ROOT / "src" / "maxiv_panda" / "docs" / "usage_controls.md").read_text(encoding="utf-8")


def test_palette_hint_uses_qt_five_second_display_time():
    assert "QRect(),\n                5000" in UI
    assert "QRect(),\n                5000" in LIVE
    assert "msecDisplayTime=2500" not in UI
    assert "msecDisplayTime=2500" not in LIVE


def test_shared_map_hit_testing_checks_overlapping_image_axes():
    assert "for ax in self.fig.axes" in UI
    assert 'getattr(ax, "images", None)' in UI
    assert "bbox.contains(x, y)" in UI
    assert "Raw Data and View -> Simple" in UI


def test_help_mentions_five_second_hint_and_simple_raw_right_click():
    assert "about five seconds" in HELP_CONTROLS
    assert "Raw Data" in HELP_CONTROLS
    assert "Simple" in HELP_CONTROLS
    assert "Right-click" in HELP_CONTROLS
