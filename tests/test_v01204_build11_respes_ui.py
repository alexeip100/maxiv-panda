"""Regression contract for the compact ResPES reference form (Qt-free)."""
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "src/maxiv_panda/ui_map_controls_mixin.py").read_text(encoding="utf8")

def test_reference_inputs_have_explicit_same_row_labels():
    assert 'pre_form = QGridLayout()' in SOURCE
    for content in (
        'QLabel("Reference PhE", pre_group)',
        'QLabel("Width", pre_group)',
        'pre_form.addWidget(self.lbl_respes_reference_hv, 0, 0)',
        'pre_form.addWidget(self.sb_respes_preedge_center, 0, 1)',
        'pre_form.addWidget(self.lbl_respes_reference_width, 1, 0)',
        'pre_form.addWidget(self.sb_respes_preedge_width, 1, 1)',
    ):
        assert content in SOURCE

def test_native_spinbox_buttons_are_not_overridden_by_stylesheet():
    assert 'spin_frame_style' not in SOURCE
    for group in ('axis_group', 'pre_group', 'cuts_group'):
        assert f'{group}.setStyleSheet(' not in SOURCE
    assert 'QDoubleSpinBox {' not in SOURCE
