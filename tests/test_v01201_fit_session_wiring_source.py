from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"


def test_single_fit_curve_state_includes_fit_range_and_session_helpers():
    text = (ROOT / "workflows" / "peakfit" / "fit_dialog_state_mixin.py").read_text(encoding="utf-8")
    assert '"fit_range": list(self._current_fit_range())' in text
    assert "def _capture_session_fit_state" in text
    assert "def _restore_session_fit_state" in text


def test_main_session_saves_and_restores_fitting_registry():
    text = (ROOT / "ui_actions_mixin.py").read_text(encoding="utf-8")
    assert "fitting_state=self._session_fitting_state()" in text
    assert '"single": dict(fitting.get("single") or {})' in text
    assert '"batch": dict(fitting.get("batch") or {})' in text


def test_batch_dialog_exposes_session_capture_restore():
    text = (ROOT / "workflows" / "peakfit" / "batch_dialog.py").read_text(encoding="utf-8")
    assert "def _capture_session_batch_state" in text
    assert "def _restore_session_batch_state" in text
    assert 'registry.setdefault("batch", {})[signature]' in text
