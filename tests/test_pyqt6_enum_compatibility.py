from pathlib import Path


def test_signal_identification_form_layout_uses_pyqt6_scoped_enum():
    source = Path("src/maxiv_panda/signal_identification/dialogs.py").read_text(encoding="utf-8")
    assert "QFormLayout.FieldsStayAtSizeHint" not in source
    assert "QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint" in source


def test_peak_color_picker_keeps_marker_sync_and_uses_macos_safe_dialog():
    source = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_component_display_mixin.py").read_text(encoding="utf-8")
    assert "QColorDialog.ColorDialogOption.DontUseNativeDialog" in source
    assert "self._refresh_peak_markers()" in source
    assert "self.raise_()" in source
    assert "self.activateWindow()" in source
