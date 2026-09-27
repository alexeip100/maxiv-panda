from pathlib import Path

UI = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
PROCESSED = Path("src/maxiv_panda/ui_processed_data_mixin.py").read_text(encoding="utf-8")
SELECTION = Path("src/maxiv_panda/selection_tree.py").read_text(encoding="utf-8")
PLOT_CONTROLLER = Path("src/maxiv_panda/plot_controller.py").read_text(encoding="utf-8")
LIVE_WINDOW = Path("src/maxiv_panda/live_monitor/window.py").read_text(encoding="utf-8")
LIVE_LINES = Path("src/maxiv_panda/live_monitor/lines_view.py").read_text(encoding="utf-8")
BATCH = Path("src/maxiv_panda/workflows/peakfit/batch_selection_mixin.py").read_text(encoding="utf-8")
CONTROLS = Path("src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")


def test_terrain_is_the_default_map_palette_everywhere():
    assert 'self._cmap = "terrain"' in LIVE_WINDOW
    assert 'self.cmap = "terrain"' in LIVE_LINES
    assert "self.region_cmap.setdefault(key, 'terrain')" in SELECTION
    assert 'else "terrain"' in PLOT_CONTROLLER
    assert 'setdefault(rkey, "terrain")' in BATCH


def test_palette_buttons_are_removed_and_map_right_click_is_the_entry_point():
    assert 'btn_map_palette' not in PROCESSED
    assert 'btn_palette' not in LIVE_WINDOW
    assert 'cmap_btn = QPushButton' not in BATCH
    assert 'map_palette_callback' in UI
    assert '_on_map_palette_right_click' in UI
    assert 'button != 3' in UI
    assert 'getattr(ax, "images", None)' in UI
    assert '_on_map_palette_right_click' in LIVE_WINDOW


def test_palette_discovery_hint_is_five_seconds_and_dwell_controlled():
    assert 'Right-click to change palette' in UI
    assert 'QRect(),\n                5000' in UI
    assert '_map_palette_hint_seen' in UI
    assert 'setInterval(1000)' in UI
    assert 'Right-click to change palette' in LIVE_WINDOW
    assert 'QRect(),\n                5000' in LIVE_WINDOW
    assert '_palette_hint_shown' in LIVE_WINDOW
    assert 'setInterval(1000)' in LIVE_WINDOW


def test_help_documents_new_palette_workflow():
    assert 'All 2D maps use **terrain** by default' in CONTROLS
    assert 'Right-click directly inside the 2D image' in CONTROLS
    assert '**Right-click to change palette**' in CONTROLS
