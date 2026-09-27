from PyQt6.QtGui import QDoubleValidator

from maxiv_panda.workflows.peakfit.fit_range import FitRangeDialog


def test_fit_range_dialog_uses_qt6_standard_notation(qapp):
    dlg = FitRangeDialog(150.0, 170.0, 155.0, 165.0)
    validator = dlg.edit_min.validator()
    assert isinstance(validator, QDoubleValidator)
    assert validator.notation() == QDoubleValidator.Notation.StandardNotation
    dlg.close()


def test_fit_range_dialog_is_live_and_compact(qapp):
    calls = []
    dlg = FitRangeDialog(150.0, 170.0, 155.0, 165.0, preview_callback=lambda lo, hi: calls.append((lo, hi)))
    assert dlg.windowTitle() == "Fit range"
    assert dlg.btn_select_mouse.text() == "Select on plot"
    assert dlg.btn_full.text() == "Full"
    assert dlg.btn_close.text() == "Close"
    assert not hasattr(dlg, "buttons")

    dlg.edit_min.setText("156")
    dlg.edit_min.textEdited.emit("156")
    assert calls[-1] == (156.0, 165.0)

    dlg.btn_full.click()
    assert calls[-1] == (150.0, 170.0)
    dlg.close()


def test_select_on_plot_hides_dialog(qapp):
    seen = []
    dlg = FitRangeDialog(150.0, 170.0, 155.0, 165.0, select_callback=lambda d: seen.append(d))
    dlg.show()
    qapp.processEvents()
    dlg.btn_select_mouse.click()
    assert seen == [dlg]
    assert not dlg.isVisible()
    dlg.close()
