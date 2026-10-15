"""Help startup and math-content regressions."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"

def test_white_loading_pane_until_webengine_ready():
    text = (ROOT / "ui_actions_mixin.py").read_text(encoding="utf-8")
    assert 'content_stack.setCurrentWidget(loading_pane)' in text
    assert 'browser.loadFinished.connect' in text
    assert 'content_stack.setCurrentWidget(browser)' in text

def test_cross_section_math_is_real_math_not_code():
    text = (ROOT / "docs" / "usage_controls.md").read_text(encoding="utf-8")
    assert '$$F(' in text and '$$\\sigma_' in text
    assert '`F(β,θ) = ' not in text

def test_macos_fix_is_preserved():
    text = (ROOT / "ui.py").read_text(encoding="utf-8")
    assert 'class MainWindow' in text
