from pathlib import Path


UI = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
WINDOW = Path("src/maxiv_panda/live_monitor/window.py").read_text(encoding="utf-8")
CONTROLS = Path("src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
WORKFLOWS = Path("src/maxiv_panda/docs/usage_workflows.md").read_text(encoding="utf-8")


def test_live_monitor_is_hidden_in_file_context_menu_not_main_toolbar():
    assert 'menu.addAction("Open live monitor")' in UI
    assert 'metadata.get("metadata_scope", "")' in UI
    assert '== "file"' in UI
    assert 'file_path.lower().endswith(".ibw")' in UI
    assert 'file_path.lower().endswith(".txt")' in UI
    assert 'QPushButton("Live monitor"' not in UI


def test_live_monitor_window_uses_existing_threaded_controller():
    assert 'LiveFileMonitorController' in WINDOW
    assert 'self._controller.update_ready.connect(self._on_update)' in WINDOW
    assert 'self._controller.timing_changed.connect(self._on_timing_info)' in WINDOW
    assert 'self._controller.shutdown()' in WINDOW


def test_live_monitor_window_exposes_auto_and_fixed_intervals():
    for text in ('("Auto", None)', '("1 s", 1.0)', '("2 s", 2.0)', '("5 s", 5.0)', '("10 s", 10.0)'):
        assert text in WINDOW
    assert 'Checked every' in WINDOW
    assert 'Settle for' in WINDOW
    assert 'New spectrum every' in WINDOW
    assert 'learning spectrum interval…' in WINDOW


def test_live_window_appends_rows_and_resets_without_touching_main_selection():
    assert 'if update.reset or self._spectra is None' in WINDOW
    assert 'np.vstack([self._spectra, new_rows])' in WINDOW
    assert '_update_selected_tree' not in WINDOW
    assert 'setCheckState' not in WINDOW


def test_help_documents_specialized_live_monitor_workflow():
    assert 'Live monitor (specialized online-acquisition tool)' in CONTROLS
    assert 'Open live monitor' in CONTROLS
    assert 'Monitor a growing 2D acquisition file' in WORKFLOWS
    assert 'may still contain only the first spectrum' in WORKFLOWS
    assert 'New spectrum every' in WORKFLOWS
    assert 'Reload latest snapshot' in WORKFLOWS
    assert 'Right-click to change palette' in WORKFLOWS
