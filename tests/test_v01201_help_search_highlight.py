from pathlib import Path


def test_help_search_uses_visible_yellow_selection_highlight():
    """WebEngine highlights selection in CSS, rather than QTextBrowser's palette."""
    root = Path(__file__).parents[1] / "src" / "maxiv_panda"
    browser = (root / "widgets" / "mathjax_help_browser.py").read_text(encoding="utf-8")
    ui = (root / "ui_actions_mixin.py").read_text(encoding="utf-8")
    assert "::selection{background:#ffeb3b;color:#111111}" in browser
    assert "browser.find_help(term, backward, _result)" in ui
