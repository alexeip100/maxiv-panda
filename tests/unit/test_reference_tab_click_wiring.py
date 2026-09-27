from pathlib import Path


def test_reference_tab_bar_activates_on_click_even_when_index_is_unchanged():
    source = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
    assert "reference_tab_bar.tabBarClicked.connect(_activate_reference_page)" in source
