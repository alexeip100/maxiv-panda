from pathlib import Path


WINDOW = Path("src/maxiv_panda/live_monitor/window.py").read_text(encoding="utf-8")
UI = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
RELOAD = Path("src/maxiv_panda/ui_source_reload_mixin.py").read_text(encoding="utf-8")
CONTROLS = Path("src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")


def test_live_monitor_uses_normal_window_semantics_for_backgrounding():
    assert "Qt.WindowType.WindowMinimizeButtonHint" in WINDOW
    assert "Qt.WindowType.WindowMaximizeButtonHint" in WINDOW
    assert "Qt.WidgetAttribute.WA_QuitOnClose, False" in WINDOW
    assert "window = LiveMapWindow(" in UI
    assert "LiveMapWindow(path, self)" not in UI


def test_live_monitor_uses_clear_timing_language():
    assert "Checked every" in WINDOW
    assert "Settle for" in WINDOW
    assert "New spectrum every" in WINDOW
    assert "Auto: check" not in WINDOW
    assert "Fixed: check" not in WINDOW
    assert "stable wait" not in WINDOW
    assert " · cadence " not in WINDOW


def test_live_monitor_reuses_map_palette_chooser_and_preserves_choice():
    assert "from ..colormap_dialog import choose_colormap" in WINDOW
    assert 'self.btn_palette' not in WINDOW
    assert "choose_colormap(self, current=self._cmap)" in WINDOW
    assert "_on_map_palette_right_click" in WINDOW
    assert "Right-click to change palette" in WINDOW
    assert "self._lines_view.set_cmap(self._cmap)" in WINDOW
    assert "self._lines_view.cmap = self._cmap" in WINDOW


def test_reload_latest_snapshot_delegates_to_general_reload_policy():
    assert 'QPushButton("Reload latest snapshot", self)' in WINDOW
    assert "reload_latest_callback=lambda p=path: self._reload_source_path_with_policy(p)" in UI
    assert "def _reload_source_path_with_policy" in RELOAD
    body = RELOAD.split("def _reload_source_path_with_policy", 1)[1].split("def _reload_loaded_file_item", 1)[0]
    assert "_loaded_file_item_for_path(path)" in body
    assert "_reload_loaded_file_item(item)" in body
    assert "standard provenance-aware reload policy" in CONTROLS
