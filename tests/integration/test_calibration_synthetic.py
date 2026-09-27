import numpy as np
import pytest

from maxiv_panda.workflows.calibration.fitters import _fit_fermi_edge


def test_fermi_edge_fit_recovers_known_binding_energy():
    x = np.linspace(-1.0, 1.0, 1201)
    ef = 0.12
    width = 0.055
    y = 0.3 + 2.5 / (1.0 + np.exp(-(x - ef) / width))
    result = _fit_fermi_edge(x, y, expected_ef=ef, energy_scale="Binding", x_min=-0.6, x_max=0.7)
    assert result["E_meas"] == pytest.approx(ef, abs=0.01)
    assert result["quality"]["status"] in {"OK", "WARN"}
    assert result["quality"]["r2"] > 0.999
