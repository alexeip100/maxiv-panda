from pathlib import Path


def test_help_dialog_is_modeless_and_single_instance():
    source = Path('src/maxiv_panda/ui_actions_mixin.py').read_text(encoding='utf-8')
    start = source.index('    def show_usage_info(')
    end = source.index('\n\n    def _show_not_implemented_dialog', start)
    method = source[start:end]

    assert 'dlg.setModal(False)' in method
    assert 'dlg.show()' in method
    assert 'dlg.exec()' not in method
    assert 'self._help_dialog = dlg' in method
    assert 'QDialog(None, Qt.WindowType.Window)' in method
    assert 'Qt.WindowType.WindowMinimizeButtonHint' in method
    assert 'Qt.WindowType.WindowMaximizeButtonHint' in method
    assert 'QDialog(self)' not in method
    assert 'existing.close()' in method
