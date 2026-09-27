from pathlib import Path


def test_inactive_main_tab_bar_skips_hidden_reference_tabs():
    source = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
    assert 'not self.isTabVisible(index)' in source
    assert 'option.rect.isEmpty()' in source
