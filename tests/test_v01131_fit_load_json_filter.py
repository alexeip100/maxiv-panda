from pathlib import Path


def test_fit_load_dialog_defaults_to_plain_json_filter():
    src = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_io_mixin.py").read_text(encoding="utf-8")
    start = src.index("def _on_load_fit_setup_file")
    end = src.index("def ", start + 4) if "def " in src[start + 4:] else len(src)
    block = src[start:end]
    assert '"JSON files (*.json);;All files (*.*)"' in block
    assert 'FlexPES fit setup (*.fit.json)' not in block


def test_fit_save_dialog_keeps_fit_json_suggestion_filter():
    src = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_io_mixin.py").read_text(encoding="utf-8")
    start = src.index("def _on_save_fit_setup_file")
    end = src.index("def _on_load_fit_setup_file", start)
    block = src[start:end]
    assert 'FlexPES fit setup (*.fit.json)' in block
