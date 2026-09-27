from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pure_simple_map_skips_generic_scientific_y_formatter():
    text = (ROOT / "src/maxiv_panda/ui.py").read_text(encoding="utf-8")
    assert "_pure_map_view = bool(images and not payloads)" in text
    assert "if not _pure_map_view:" in text


def test_main_map_coordinate_fields_are_compact():
    text = (ROOT / "src/maxiv_panda/ui_map_plot_mixin.py").read_text(encoding="utf-8")
    assert 'x_field = f"{x_text:<14}"' in text
    assert 'y_field = f"{y_text:<16}"' in text
    assert 'return f"{x_field}  {y_field}  {intensity_field}"' in text
    assert "AlignLeft | Qt.AlignmentFlag.AlignVCenter" in text


def test_live_monitor_coordinate_fields_match_compact_layout():
    text = (ROOT / "src/maxiv_panda/live_monitor/lines_view.py").read_text(encoding="utf-8")
    assert 'return f"{x_text:<14}  {y_text:<16}  {intensity_text}"' in text
    window = (ROOT / "src/maxiv_panda/live_monitor/window.py").read_text(encoding="utf-8")
    assert "AlignLeft | Qt.AlignmentFlag.AlignVCenter" in window
