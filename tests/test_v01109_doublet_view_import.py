from pathlib import Path


def test_component_display_mixin_imports_so_doublets_helper():
    root = Path(__file__).resolve().parents[1]
    text = (root / "src/maxiv_panda/workflows/peakfit/fit_dialog_component_display_mixin.py").read_text(encoding="utf-8")
    assert "so_doublets" in text
    import_lines = [line for line in text.splitlines() if line.startswith("from . import ")]
    assert any("so_doublets" in line for line in import_lines)
