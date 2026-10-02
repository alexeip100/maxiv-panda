from pathlib import Path


def test_help_search_uses_visible_yellow_selection_highlight():
    src = (Path(__file__).parents[1] / "src" / "maxiv_panda" / "ui_actions_mixin.py").read_text(encoding="utf-8")
    assert "QColor(255, 235, 59)" in src
    assert "ColorRole.HighlightedText, QColor(0, 0, 0)" in src
    assert "browser.setPalette(help_palette)" in src
