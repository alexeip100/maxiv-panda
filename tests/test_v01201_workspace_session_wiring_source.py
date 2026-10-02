from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"


def test_main_session_wires_plotted_and_workspace_state():
    text = (ROOT / "ui_actions_mixin.py").read_text(encoding="utf-8")
    assert "plotted_state=self._session_plotted_state" not in text  # captured separately before manifest
    assert "plotted_state=plotted_state" in text
    assert "workspace_state=workspace_state" in text
    assert "_restore_plotted_workspace(session_path, manifest)" in text
    assert "_restore_workspace_state(session_path, manifest)" in text


def test_plotted_panel_exposes_session_capture_restore():
    text = (ROOT / "workflows" / "plotting" / "panel.py").read_text(encoding="utf-8")
    assert "def capture_session_state" in text
    assert "def restore_session_state" in text
    assert 'member = f"plotted/curve_{idx:05d}.npz"' in text


def test_trace_window_exposes_session_capture_restore():
    text = (ROOT / "ui_trace_comparison.py").read_text(encoding="utf-8")
    assert "def capture_session_state" in text
    assert "def restore_session_state" in text
    assert 'member = f"trace/trace_{idx:05d}.npz"' in text


def test_open_fit_window_workspace_state_uses_saved_signature():
    text = (ROOT / "workflows" / "peakfit" / "fit_dialog.py").read_text(encoding="utf-8")
    assert "dlg._session_signature = signature" in text
    state = (ROOT / "workflows" / "peakfit" / "fit_dialog_state_mixin.py").read_text(encoding="utf-8")
    assert '"active_right_tab"' in state
