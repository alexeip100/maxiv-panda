from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QGroupBox, QWidget

from maxiv_panda.workflows.normalization.ui_bits import build_normalization_control


def test_normalization_control_is_compact_and_percentage_based(qapp):
    parent = QWidget()
    widget, checkbox, energy, span, span_ev = build_normalization_control(parent)
    assert isinstance(widget, QGroupBox)
    assert widget.title() == "Normalization"
    assert checkbox.text() == "Norm E:"
    assert energy.suffix().strip() == "eV"
    assert span.value() == 1.0
    assert span.suffix().strip() == "%"
    assert widget.layout().count() == 5
    assert span_ev.text() == ""
