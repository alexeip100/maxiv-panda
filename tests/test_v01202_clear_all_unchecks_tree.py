from pathlib import Path

ACTIONS = Path("src/maxiv_panda/ui_actions_mixin.py").read_text(encoding="utf-8")


def test_clear_all_unchecks_every_tree_checkbox_postorder():
    body = ACTIONS[ACTIONS.index("    def clear_all("):ACTIONS.index("    def _session_sources(")]
    assert "def _uncheck_postorder" in body
    assert "_uncheck_postorder(item.child(i))" in body
    assert "item.setCheckState(0, Qt.CheckState.Unchecked)" in body
    assert "self.tree.invisibleRootItem()" in body
    assert "self.tree.viewport().update()" in body
