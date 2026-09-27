from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_fit_legend_preserves_dragged_position_and_uses_larger_font():
    src = _read("src/maxiv_panda/workflows/peakfit/fit_dialog.py")
    assert "def _remember_fit_legend_position" in src
    assert 'self._fit_legend_loc = (float(loc[0]), float(loc[1]))' in src
    assert 'loc=getattr(self, "_fit_legend_loc", "best")' in src
    assert "fontsize=9" in src
    assert "legend.set_draggable(True)" in src


def test_peak_label_enter_is_consumed_instead_of_closing_dialog():
    widgets = _read("src/maxiv_panda/workflows/peakfit/fit_widgets.py")
    curve = _read("src/maxiv_panda/workflows/peakfit/fit_dialog_curve_mixin.py")
    assert 'label_edit.setProperty("peak_label_edit", True)' in widgets
    assert "label_edit.installEventFilter(owner)" in widgets
    assert 'isinstance(obj, QLineEdit) and bool(obj.property("peak_label_edit"))' in curve
    assert "return True" in curve


def test_tex_subscript_preview_uses_fraction_slash():
    src = _read("src/maxiv_panda/workflows/plotting/tex_reference_dialog.py")
    assert '("Subscript", r"S 2p$_{3/2}$", "S 2p₃⁄₂")' in src
    assert '"S 2p₃/₂"' not in src
