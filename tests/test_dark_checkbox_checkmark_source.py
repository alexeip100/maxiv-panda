from pathlib import Path


def test_dark_theme_uses_custom_checkmark_painter_not_blue_fill():
    src = Path('src/maxiv_panda/ui_style.py').read_text(encoding='utf-8')
    assert 'class FlexPESCheckStyle' in src
    assert 'PE_IndicatorCheckBox' in src
    assert 'PE_IndicatorItemViewItemCheck' in src
    assert 'painter.drawPath(path)' in src
    assert 'background: #4c9bd6' not in src


def test_map_overlay_does_not_override_checkbox_indicator():
    src = Path('src/maxiv_panda/ui_map_plot_mixin.py').read_text(encoding='utf-8')
    block = src[src.index('def _create_map_qt_overlay_checkbox'):]
    block = block[:block.index('def ', 10) if 'def ' in block[10:] else len(block)]
    assert 'QCheckBox::indicator' not in block
