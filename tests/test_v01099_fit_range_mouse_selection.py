from pathlib import Path


def test_mouse_fit_range_supports_edge_release_and_two_click_selection():
    src = Path('src/maxiv_panda/workflows/peakfit/fit_range.py').read_text(encoding='utf-8')
    assert 'def _fit_range_event_x' in src
    assert 'self.ax.transData.inverted().transform' in src
    assert '_fit_range_select_awaiting_second_click' in src
    assert 'A plain click-release defines only the first border' in src
    assert 'dragged or awaiting_second' in src
    assert 'self._finish_fit_range_mouse_mode()' in src


def test_mouse_fit_range_tooltip_describes_both_gestures():
    src = Path('src/maxiv_panda/workflows/peakfit/fit_range.py').read_text(encoding='utf-8')
    assert 'Drag across the spectrum plot, or click two positions' in src
