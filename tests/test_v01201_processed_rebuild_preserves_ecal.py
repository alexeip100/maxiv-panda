from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / 'src' / 'maxiv_panda' / 'ui.py').read_text(encoding='utf-8')


def test_selected_rebuild_preserves_persistent_processed_children():
    body = UI.split('def _rebuild_selected_from_loaded', 1)[1].split('def _add_txt_to_tree', 1)[0]
    assert 'processed_state = []' in body
    assert 'meta.get("processed", False)' in body
    assert 'meta.get("source_key")' in body
    assert 'raw_item = getattr(self, "_selected_by_key", {}).get(row["source_key"])' in body
    assert 'self._selected_tree_manager.add_selected_leaf(' in body
    assert 'restored.setCheckState(0, row["checked"])' in body


def test_selected_rebuild_preserves_ecal_toggle_instead_of_forcing_it_on():
    body = UI.split('def _rebuild_selected_from_loaded', 1)[1].split('def _add_txt_to_tree', 1)[0]
    assert 'ecal_toggle_checked = bool(self.btn_e_cal_toggle.isChecked())' in body
    assert 'show_processed = bool(cur_is_processed_tab and has_processed and ecal_toggle_checked)' in body
    assert 'self.btn_e_cal_toggle.setChecked(True)' not in body
