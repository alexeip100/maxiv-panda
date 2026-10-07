from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_raw_processed_selected_tree_exposes_curve_color_action():
    text = (ROOT / "src/maxiv_panda/ui.py").read_text(encoding="utf-8")
    assert 'customContextMenuRequested.connect(self._show_selected_tree_context_menu)' in text
    assert 'menu.addAction("Choose curve color...")' in text
    assert 'self._curve_color_map[key] = color.name()' in text


def test_processed_to_plotted_preserves_user_selected_color():
    processed = (ROOT / "src/maxiv_panda/ui_processed_data_mixin.py").read_text(encoding="utf-8")
    plotted = (ROOT / "src/maxiv_panda/workflows/plotting/panel.py").read_text(encoding="utf-8")
    assert 'selected_color = getattr(self, "_curve_color_map", {}).get(str(key))' in processed
    assert 'setattr(named, "color", str(selected_color))' in processed
    assert 'preferred_color = getattr(payload, "color", None)' in plotted


def test_raw_processed_curve_colors_are_saved_in_session_view_state():
    text = (ROOT / "src/maxiv_panda/ui_actions_mixin.py").read_text(encoding="utf-8")
    assert '"curve_colors": {' in text
    assert 'dict(getattr(self, "_curve_color_map", {}) or {}).items()' in text
    assert 'saved_colors = view.get("curve_colors", {})' in text
    assert 'self._curve_color_map.update' in text


def test_ecal_derivative_inherits_source_color_initially():
    text = (ROOT / "src/maxiv_panda/workflows/calibration/calibrate_logic.py").read_text(encoding="utf-8")
    assert 'source_color = getattr(mw, "_curve_color_map", {}).get(str(raw_key))' in text
    assert 'mw._curve_color_map[curve_id] = str(source_color)' in text


def test_selected_curve_color_double_click_targets_curve_row_except_checkbox():
    text = (ROOT / "src/maxiv_panda/ui.py").read_text(encoding="utf-8")
    assert "def _selected_tree_checkbox_rect" in text
    assert "SE_ItemViewItemCheckIndicator" in text
    assert "checkbox.contains(pos)" in text
    assert "self._choose_selected_curve_color(item)" in text
    assert "hit = swatch.adjusted(-4, -4, 6, 4)" not in text

