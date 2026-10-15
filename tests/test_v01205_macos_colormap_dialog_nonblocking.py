"""Regression checks for the native macOS colormap-dialog event-loop issue."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / 'src' / 'maxiv_panda'

def test_map_selector_opens_without_exec():
    code = (ROOT / 'ui.py').read_text()
    section = code.split('    def _choose_region_cmap(', 1)[1].split('    def _on_region_map_toggled(', 1)[0]
    assert 'open_colormap(self, current, _apply)' in section
    assert 'choose_colormap(self, current)' not in section

def test_subtraction_selector_opens_without_exec():
    code = (ROOT / 'ui_processed_data_mixin.py').read_text()
    section = code.split('    def _choose_active_map_cmap(', 1)[1].split('    def _on_map_view_combo_changed(', 1)[0]
    assert 'open_colormap(self, str(getattr(self, "_respes_difference_cmap", "RdBu_r")), _apply)' in section
    assert 'choose_colormap(self,' not in section

def test_dialog_cleanup_and_deferred_callback():
    code = (ROOT / 'colormap_dialog.py').read_text()
    section = code.split('def open_colormap(', 1)[1]
    assert 'dialog.open()' in section
    assert 'dialog.exec()' not in section
    assert 'dialog.finished.connect(_finished)' in section
    assert 'dialog.deleteLater()' in section
    assert 'QTimer.singleShot(0,' in section
    assert 'if result == int(QDialog.DialogCode.Accepted)' in section
