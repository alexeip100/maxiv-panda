from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / 'src/maxiv_panda/ui.py').read_text(encoding='utf-8')
ACTIONS = (ROOT / 'src/maxiv_panda/ui_actions_mixin.py').read_text(encoding='utf-8')


def test_deferred_selected_rebuild_uses_generation_token():
    assert 'self._selected_rebuild_generation: int = 0' in UI
    assert 'lambda g=generation: self._flush_rebuild_selected_from_loaded(g)' in UI
    assert 'int(generation) != current_generation' in UI
    assert 'A bool alone cannot invalidate a queued callback safely' in UI


def test_session_restore_is_atomic_against_loaded_tree_rebuilds():
    assert 'self._session_restore_in_progress = True' in ACTIONS
    assert 'self._session_restore_in_progress = False' in ACTIONS
    assert 'if bool(getattr(self, "_session_restore_in_progress", False)):' in UI
    assert ACTIONS.count('_selected_rebuild_generation = int(getattr(self, "_selected_rebuild_generation", 0)) + 1') >= 2


def test_session_restore_keeps_raw_visible_until_processed_tab():
    assert 'on_processed_tab = bool(self.tabs.currentIndex() == 1)' in ACTIONS
    assert 'show_processed=bool(ecal_enabled and on_processed_tab)' in ACTIONS
