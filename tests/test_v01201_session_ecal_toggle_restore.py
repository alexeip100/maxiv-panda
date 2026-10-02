from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = (ROOT / 'src' / 'maxiv_panda' / 'processed_controller.py').read_text(encoding='utf-8')
UI = (ROOT / 'src' / 'maxiv_panda' / 'ui_processed_data_mixin.py').read_text(encoding='utf-8')


def test_ecal_toggle_is_not_gated_by_processed_tab_parent_after_session_restore():
    body = UI.split('def _on_e_cal_toggle', 1)[1].split('def _on_tab_changed', 1)[0]
    assert '_is_processed_tab_active()' not in body
    assert '_update_selected_tree_visibility(show_processed=bool(checked))' in body


def test_ecal_visibility_uses_explicit_source_key_pairing():
    body = PROC.split('def update_selected_tree_visibility', 1)[1].split('def guess_norm_default_energy', 1)[0]
    assert 'processed_sources' in body
    assert 'meta.get("source_key")' in body
    assert 'str(key) in processed_sources' in body
    assert 'it.setHidden(not bool(show_processed))' in body
