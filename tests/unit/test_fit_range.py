from types import SimpleNamespace

import numpy as np

from maxiv_panda.workflows.peakfit.fit_engine import collect_fit_curve_data


def test_collect_fit_curve_data_uses_only_requested_energy_interval():
    payload = SimpleNamespace(
        x=np.arange(10.0, -0.5, -0.5),
        y=np.arange(21.0),
    )
    data, err = collect_fit_curve_data({"curve": payload}, "curve", fit_range=(3.0, 7.0))
    assert err is None
    assert data is not None
    assert float(data["x"].min()) == 3.0
    assert float(data["x"].max()) == 7.0
    assert data["x"].size == 9
    assert data["fit_range"] == (3.0, 7.0)


def test_collect_fit_curve_data_full_range_is_unchanged_by_default():
    payload = SimpleNamespace(x=np.arange(0.0, 10.0), y=np.arange(0.0, 10.0) ** 2)
    data, err = collect_fit_curve_data({"curve": payload}, "curve")
    assert err is None
    assert data is not None
    assert data["x"].size == 10
    assert data["fit_range"] is None


def test_collect_fit_curve_data_rejects_too_narrow_interval():
    payload = SimpleNamespace(x=np.arange(0.0, 10.0), y=np.arange(0.0, 10.0))
    data, err = collect_fit_curve_data({"curve": payload}, "curve", fit_range=(4.0, 6.0))
    assert data is None
    assert "too few data points" in err.lower()
