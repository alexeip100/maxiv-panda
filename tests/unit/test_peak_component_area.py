import numpy as np

from maxiv_panda.workflows.peakfit import fit_models


def _component(x, *, height=10.0, lfwhm=1.0, gfwhm=0.8, alpha=0.0):
    _total, components = fit_models.build_model_from_values(
        x,
        [{"E": 0.0, "H": height, "L": lfwhm, "G": gfwhm, "A": alpha}],
        "constant",
        {"b0": 0.0},
        energy_scale="Binding Energy",
    )
    return components[0]


def test_component_area_scales_linearly_with_height():
    x = np.linspace(-20.0, 20.0, 20001)
    y1 = _component(x, height=10.0)
    y2 = _component(x, height=25.0)
    a1 = fit_models.integrated_component_area(x, y1)
    a2 = fit_models.integrated_component_area(x, y2)
    assert np.isfinite(a1)
    assert np.isclose(a2 / a1, 2.5, rtol=1e-6)


def test_broader_peak_has_larger_area_at_same_height():
    x = np.linspace(-30.0, 30.0, 30001)
    narrow = _component(x, height=10.0, lfwhm=0.4, gfwhm=0.4)
    broad = _component(x, height=10.0, lfwhm=1.6, gfwhm=1.6)
    assert fit_models.integrated_component_area(x, broad) > fit_models.integrated_component_area(x, narrow)


def test_ds_area_is_finite_window_integral():
    x = np.linspace(-10.0, 10.0, 10001)
    y = _component(x, height=10.0, alpha=0.08)
    area = fit_models.integrated_component_area(x, y)
    assert np.isfinite(area)
    assert area > 0.0
