from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dark_spinbox_arrows_use_explicit_packaged_images():
    src = (ROOT / 'src/maxiv_panda/ui_style.py').read_text(encoding='utf-8')
    assert 'QSpinBox::up-arrow' in src
    assert 'QDoubleSpinBox::down-arrow' in src
    assert 'spin_up_light.png' in src
    assert 'spin_down_light.png' in src
    assert 'def drawComplexControl' not in src
    for name in ('spin_up_light.png', 'spin_down_light.png'):
        icon = ROOT / 'src/maxiv_panda/data' / name
        assert icon.exists() and icon.stat().st_size > 0


def test_raw_plot_canvas_accepts_file_drops_via_existing_loader():
    src = (ROOT / 'src/maxiv_panda/ui.py').read_text(encoding='utf-8')
    assert 'self.canvas.setAcceptDrops(True)' in src
    assert 'self.canvas.installEventFilter(self)' in src
    assert 'self.plot_area.file_drop_callback = self._load_dropped_files' in src
    assert 'self.plot_area.file_drop_enabled_callback = lambda: not self._is_processed_tab_active()' in src
    assert "LoadedFilesTreeWidget._extract_supported_paths(event)" in src


def test_plot_drop_does_not_directly_trigger_plot_redraw():
    src = (ROOT / 'src/maxiv_panda/ui.py').read_text(encoding='utf-8')
    start = src.index('    def eventFilter(self, watched, event):')
    end = src.index('    def _on_intensity_axis_double_click', start)
    block = src[start:end]
    assert '_update_plot_from_selected' not in block
    assert 'callback(paths)' in block
