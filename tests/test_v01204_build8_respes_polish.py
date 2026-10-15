"""Source-level protection for ResPES widget/overlay polish (Qt-free)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'src' / 'maxiv_panda'


def test_preedge_uses_independent_label_and_same_physical_band():
    plot = (ROOT / 'ui_map_plot_mixin.py').read_text(encoding='utf8')
    assert 'region_label="Reference" if subtracted else "Norm"' in plot
    assert 'label = ax.text(0.985, 0.5*(ylo+yhi), region_label,' in plot
    assert 'region_label="Norm"' in plot


def test_sidebar_has_clear_labels_and_no_cluttering_instructions():
    text = (ROOT / 'ui_map_controls_mixin.py').read_text(encoding='utf8')
    assert 'pre_form.addWidget(self.lbl_respes_reference_hv, 0, 0)' in text
    assert 'pre_form.addWidget(self.lbl_respes_reference_width, 1, 0)' in text
    assert 'form.addRow("Cut width",' in text
    assert 'QCheckBox("Subtract reference PE\\nspectrum",' in text
    assert 'pre_layout.addWidget(pre_note)' not in text
    assert 'cuts_layout.addWidget(note)' not in text
    assert text.index('QGroupBox("Map energy axis"') < text.index('QGroupBox("Reference subtraction"') < text.index('QGroupBox("ResPES cuts"')
    assert 'setMaximumWidth(270)' in (ROOT / 'ui.py').read_text(encoding='utf8')


def test_map_coordinates_recovered_from_main_axis_pixel_position():
    plot = (ROOT / 'ui_map_plot_mixin.py').read_text(encoding='utf8')
    ui = (ROOT / 'ui.py').read_text(encoding='utf8')
    assert 'ax.transData.inverted().transform((event.x, event.y))' in plot
    assert 'overlay.setText(caption)' in plot
    assert 'layout.addWidget(self.map_coordinate_label)' not in ui
    assert '_refresh_map_coordinate_readout)' in ui


def test_subtraction_map_is_zero_centered_diverging():
    plot = (ROOT / 'ui_map_plot_mixin.py').read_text(encoding='utf8')
    assert 'image_kw = {"vmin": -limit, "vmax": limit}' in plot
    assert 'cmap = str(difference_cmap or "RdBu_r")' in plot
