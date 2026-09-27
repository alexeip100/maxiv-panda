from pathlib import Path


def test_respes_panel_does_not_impose_hard_minimum_width():
    ui_source = (Path(__file__).resolve().parents[2] / "src" / "maxiv_panda" / "ui.py").read_text(encoding="utf-8")
    assert "self.respes_side_panel.setMinimumWidth(0)" in ui_source
    assert "QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding" in ui_source
    assert "self.respes_side_panel.setMinimumWidth(150)" not in ui_source
