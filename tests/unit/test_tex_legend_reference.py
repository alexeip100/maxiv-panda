from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLineEdit

from maxiv_panda.workflows.plotting.panel import PlottedDataPanel
from maxiv_panda.workflows.plotting.tex_reference_dialog import LegendNameDialog, TexReferenceDialog


def _app():
    return QApplication.instance() or QApplication([])


def test_custom_legend_mode_advertises_tex_support():
    _app()
    panel = PlottedDataPanel()
    assert panel.cmb_legend.findText("Custom (TeX)") >= 0
    panel.cmb_legend.setCurrentText("Custom (TeX)")
    assert not hasattr(panel, "btn_tex_help")
    assert "TeX-style" in panel.cmb_legend.toolTip()


def test_legend_name_editor_has_example_and_reference_button():
    _app()
    dialog = LegendNameDialog("")
    assert "S 2p" in dialog.edit.placeholderText()
    assert "TeX-style" in dialog.edit.toolTip()
    assert dialog.btn_help.text() == "?"


def test_reference_double_click_inserts_syntax_into_target():
    _app()
    target = QLineEdit()
    dialog = TexReferenceDialog(target=target)
    dialog._activate_row(0, 1)
    assert target.text() == r"S 2p$_{3/2}$"
