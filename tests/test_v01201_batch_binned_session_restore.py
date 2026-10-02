from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = (ROOT / "src/maxiv_panda/ui_actions_mixin.py").read_text(encoding="utf-8")
BATCH = (ROOT / "src/maxiv_panda/workflows/peakfit/batch_dialog.py").read_text(encoding="utf-8")

def test_batch_reopen_uses_real_main_selected_tree_payload_collector():
    restore = ACTIONS[ACTIONS.index("    def _restore_open_batch_window"):ACTIONS.index("    def _restore_workspace_state")]
    assert "from .workflows.peakfit.fit_dialog import _build_payload_by_key" in restore
    assert "payload_by_key = _build_payload_by_key(self)" in restore

def test_batch_session_captures_prepare_binning_state():
    capture = BATCH[BATCH.index("    def _capture_session_batch_state"):BATCH.index("    def _restore_session_batch_state")]
    assert '"prepare_state": prepare_state' in capture
    assert '"bin_size"' in capture
    assert '"original_checked_keys"' in capture
    assert '"binned_checked_keys"' in capture

def test_build8_binned_sessions_can_infer_bin_size_and_rebuild_synthetic_payloads():
    restore = BATCH[BATCH.index("    def _restore_session_batch_state"):BATCH.index("    def _apply_single_fit_reference_size")]
    assert "Backward compatibility for build-8 sessions" in restore
    assert 're.match(r"^bin:.*:(\\d+):\\d+$", key)' in restore
    assert "self._rebuild_tree_for_current_binning()" in restore
    assert "Use the effective Prepare tree here" in restore
