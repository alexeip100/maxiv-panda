from pathlib import Path


def test_session_restore_blocks_normalization_widget_signals_and_preserves_override_flag():
    src=(Path(__file__).resolve().parents[1]/'src'/'maxiv_panda'/'ui_actions_mixin.py').read_text(encoding='utf-8')
    assert '"norm_user_override"' in src
    assert 'self._norm_to1_user_override = bool(view.get("norm_user_override", False))' in src
    assert 'sb.blockSignals(True)' in src
    assert 'sb.setValue(float(self._norm_to1_energy))' in src
    assert 'sb.blockSignals(False)' in src
