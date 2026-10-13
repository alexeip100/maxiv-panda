"""Regression for independent ResPES pre-edge subtraction."""
from pathlib import Path
import ast
import numpy as np
import pytest
from maxiv_panda.workflows.normalization.logic import subtract_map_photon_energy_reference


def test_subtraction_linear_photon_dependence():
    hv = np.array([103., 101., 100., 102.])  # deliberately reversed/nonmonotonic
    original = np.vstack([np.array([0., 10., 50.]) + h * np.array([2., -1., 0.5]) for h in hv])
    sub, interval, reference = subtract_map_photon_energy_reference(hv, original, 100.5, 1.0)
    assert interval == pytest.approx((100., 101.))
    np.testing.assert_allclose(reference, [201., -90.5, 100.25])
    np.testing.assert_allclose(sub, (hv[:, None] - 100.5) * [2., -1., 0.5])


def test_reference_may_equal_zero_without_division():
    hv = np.array([0., 1., 2.])
    z = np.array([[-1., 10.], [1., 20.], [3., 30.]])
    sub, _, ref = subtract_map_photon_energy_reference(hv, z, 0.5, 1.0)
    assert ref[0] == pytest.approx(0.)
    np.testing.assert_allclose(sub[:, 0], [-1., 1., 3.])


def test_out_of_range_refused():
    with pytest.raises(ValueError):
        subtract_map_photon_energy_reference([10., 11.], np.ones((2, 3)), 13., 1.)


def test_ui_wiring_and_no_cut_branch_exist():
    base = Path(__file__).resolve().parents[1] / 'src/maxiv_panda'
    controls = (base / 'ui_map_controls_mixin.py').read_text()
    plot = (base / 'ui_map_plot_mixin.py').read_text()
    main = (base / 'ui.py').read_text()
    assert 'QGroupBox("Reference subtraction"' in controls
    assert controls.index('QGroupBox("Map energy axis"') < controls.index('QGroupBox("Reference subtraction"') < controls.index('QGroupBox("ResPES cuts"')
    assert 'self.cb_respes_cut_type.addItem("None", "none")' in controls
    assert 'if cut_type == "none":' in plot
    assert 'self._respes_cut_state = None' in plot
    assert 'subtract_map_photon_energy_reference' in controls
    assert '_on_respes_preedge_interval_from_plot' in main
    for file in (base/'ui_map_controls_mixin.py', base/'ui_map_plot_mixin.py', base/'ui.py'):
        ast.parse(file.read_text())
