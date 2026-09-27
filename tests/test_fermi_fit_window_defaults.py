from pathlib import Path


def test_fermi_edge_default_window_and_help_are_documented():
    root = Path(__file__).resolve().parents[1]
    src = (root / "src" / "maxiv_panda" / "workflows" / "calibration" / "calibrate_dialog.py").read_text(encoding="utf-8")
    help_text = (root / "src" / "maxiv_panda" / "docs" / "usage_controls.md").read_text(encoding="utf-8")

    assert "sb_de_from.setValue(-1.0)" in src
    assert "sb_de_to.setValue(+0.4)" in src
    assert "sb_de_to.setValue(+1.0)" in src  # core-level default remains symmetric
    assert "-1.0 to +0.4 eV" in help_text
    assert "valence-band" in help_text
