from pathlib import Path

UI = (Path(__file__).parents[1] / "src" / "maxiv_panda" / "ui.py").read_text(encoding="utf-8")


def test_intensity_tooltip_uses_explicit_qtooltip():
    assert "QToolTip.showText" in UI
    assert "QToolTip.hideText" in UI
    assert 'mpl_connect("figure_leave_event", self._hide_intensity_axis_tooltip)' in UI
    assert "self.canvas.mapToGlobal(QPoint" in UI


def test_intensity_tooltip_instruction_kept():
    assert "Double-click the Intensity axis title to select Counts or CPS." in UI
