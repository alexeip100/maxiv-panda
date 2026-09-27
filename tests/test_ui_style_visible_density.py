from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "maxiv_panda"


def _load_metrics_module():
    spec = importlib.util.spec_from_file_location("flexpes_ui_metrics_test", PKG / "ui_metrics.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_compact_density_is_materially_smaller_without_font_policy():
    m = _load_metrics_module()
    std = m.STANDARD_METRICS
    compact = m.COMPACT_METRICS
    assert compact.panel_margin < std.panel_margin
    assert compact.strip_vertical_margin < std.strip_vertical_margin
    assert compact.strip_spacing < std.strip_spacing
    assert compact.tab_h_padding < std.tab_h_padding
    assert compact.loaded_tree_min_width < std.loaded_tree_min_width
    assert compact.selected_tree_min_width < std.selected_tree_min_width


def test_font_offset_expands_vertical_geometry_only():
    m = _load_metrics_module()
    base = m.STANDARD_METRICS
    enlarged = m.metrics_with_font_offset(base, 2)
    assert enlarged.standard_control_height == base.standard_control_height + 4
    assert enlarged.tab_v_padding == base.tab_v_padding + 2
    assert enlarged.item_v_padding == base.item_v_padding + 2
    assert enlarged.panel_margin == base.panel_margin
    assert enlarged.strip_spacing == base.strip_spacing


def test_main_window_consumes_shared_density_metrics():
    ui = (PKG / "ui.py").read_text(encoding="utf-8")
    raw = (PKG / "ui_raw_data_mixin.py").read_text(encoding="utf-8")
    processed = (PKG / "ui_processed_data_mixin.py").read_text(encoding="utf-8")
    style = (PKG / "ui_style.py").read_text(encoding="utf-8")
    assert "ui_metrics.panel_margin" in ui
    assert "ui_metrics.loaded_tree_min_width" in ui
    assert "metrics.strip_horizontal_margin" in raw
    assert "metrics.strip_spacing" in raw
    assert "metrics.group_margin_h" in processed
    assert "metrics.group_spacing" in processed
    assert "app.setStyleSheet(_application_stylesheet(metrics, font_size_pt=font_size_pt, theme=config.theme))" in style
