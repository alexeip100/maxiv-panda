from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = (ROOT / "src/maxiv_panda/ui_actions_mixin.py").read_text(encoding="utf-8")
BATCH = (ROOT / "src/maxiv_panda/workflows/peakfit/batch_dialog.py").read_text(encoding="utf-8")
UI = (ROOT / "src/maxiv_panda/ui.py").read_text(encoding="utf-8")


def test_batch_dialog_is_modeless_and_application_owned():
    assert "self.setModal(False)" in BATCH
    assert 'setattr(mw, "_batch_fit_dialogs", dialogs)' in BATCH
    assert "dlg.finished.connect(_forget_dialog)" in BATCH
    assert "dlg.show()" in BATCH
    assert "dlg.exec()" not in BATCH[BATCH.index("def open_batch_fit_dialog"):]


def test_session_save_snapshots_live_batch_dialog_state():
    fitting = ACTIONS[ACTIONS.index("    def _session_fitting_state"):ACTIONS.index("    def _session_signal_identification_state")]
    assert 'getattr(self, "_batch_fit_dialogs", [])' in fitting
    assert "dlg._capture_session_batch_state()" in fitting
    assert 'batch[signature] = state' in fitting


def test_live_batch_table_edits_are_part_of_session_state():
    capture = BATCH[BATCH.index("    def _capture_session_batch_state"):BATCH.index("    def _restore_session_batch_state")]
    assert '"batch_parameter_table": self._capture_batch_parameter_table_state()' in capture
    assert '"live_preview"' in capture
    assert '"store_all_fit_results"' in capture
    restore = BATCH[BATCH.index("    def _restore_session_batch_state"):BATCH.index("    def _apply_single_fit_reference_size")]
    assert "_restore_batch_parameter_table_state" in restore
    assert "chk_batch_live_preview.setChecked" in restore
    assert "chk_batch_store_all_results.setChecked" in restore


def test_open_batch_window_is_saved_and_reopened_with_geometry():
    workspace = ACTIONS[ACTIONS.index("    def _session_workspace_state"):ACTIONS.index("    def _restore_plotted_workspace")]
    assert 'state["batch_windows"] = batch_windows' in workspace
    assert '"geometry"' in workspace
    assert '"maximized"' in workspace
    restore = ACTIONS[ACTIONS.index("    def _restore_open_batch_window"):ACTIONS.index("    def _save_session")]
    assert "open_batch_fit_dialog(self, items)" in restore
    assert 'saved_batch.get("curve_keys")' in restore
    assert 'state.get("batch_windows")' in restore


def test_clear_and_close_all_close_batch_dialogs():
    close_all = ACTIONS[ACTIONS.index("    def close_all"):ACTIONS.index("    def clear_all")]
    clear_all = ACTIONS[ACTIONS.index("    def clear_all"):ACTIONS.index("    def _session_sources")]
    assert 'getattr(self, "_batch_fit_dialogs", [])' in close_all
    assert 'getattr(self, "_batch_fit_dialogs", [])' in clear_all


def test_main_window_close_closes_top_level_windows_and_quits_app():
    assert "def closeEvent(self, event)" in UI
    body = UI[UI.index("    def closeEvent(self, event)"):UI.index("    def _apply_curve_color_icons", UI.index("    def closeEvent(self, event)"))]
    assert "app.topLevelWidgets()" in body
    assert "widget.close()" in body
    assert "QTimer.singleShot(0, app.quit)" in body
