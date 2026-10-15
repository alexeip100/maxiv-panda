from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / 'src' / 'maxiv_panda'


def test_offline_mathjax_is_packaged_and_required():
    data = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    reqs = data['project']['dependencies']
    assert any(x.startswith('PyQt6-WebEngine') for x in reqs)
    assert any(x.startswith('markdown') for x in reqs)
    assert 'resources/mathjax/*.js' in data['tool']['setuptools']['package-data']['maxiv_panda']
    assert (PKG / 'resources/mathjax/tex-svg-full.js').stat().st_size > 2_000_000
    assert (PKG / 'resources/mathjax/LICENSE-MathJax.txt').is_file()


def test_both_help_windows_use_same_mathjax_viewer():
    ui = (PKG / 'ui_actions_mixin.py').read_text(encoding='utf-8')
    assert 'MathJaxHelpBrowser(md_filename, base_px=17)' in ui
    assert 'browser.find_help(term, backward, _result)' in ui
    assert 'browser.set_base_font(px)' in ui
    assert 'dlg.setModal(False)' in ui
    assert 'browser.setHtml(get_usage_html' not in ui


def test_exact_style_retained_and_offline():
    src = (PKG / 'widgets/mathjax_help_browser.py').read_text(encoding='utf-8')
    assert "files('maxiv_panda')" in src
    assert 'tex-svg-full.js' in src
    assert 'setHtml(document,QUrl.fromLocalFile' in src
    assert "font-family:Arial,sans-serif" in src
    assert 'fontCache:\'local\'' in src
