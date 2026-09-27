import numpy as np
import pytest

from maxiv_panda.trace_comparison import ComparisonTrace


def _trace(quantity="binding_energy", unit="eV", label="Binding Energy [eV]"):
    return ComparisonTrace(
        x=np.array([0.0, 1.0, 2.0]),
        y=np.array([10.0, 20.0, 30.0]),
        x_label=label,
        x_quantity=quantity,
        x_unit=unit,
        metadata={"Source": "test"},
    )


def test_trace_snapshots_arrays():
    x = np.array([1.0, 2.0])
    y = np.array([3.0, 4.0])
    t = ComparisonTrace(x=x, y=y, x_label="Iteration", x_quantity="iteration")
    x[0] = 99.0
    y[0] = 88.0
    assert t.x[0] == 1.0
    assert t.y[0] == 3.0
    assert not t.x.flags.writeable
    assert not t.y.flags.writeable


def test_axis_identity_is_not_tied_to_photon_energy():
    be = _trace()
    be_alias = _trace(label="BE [eV]")
    iteration = _trace(quantity="iteration", unit=None, label="Iteration")
    assert be.compatible_with(be_alias)
    assert not be.compatible_with(iteration)


def test_different_sampling_is_compatible_when_quantity_and_unit_match():
    a = _trace(quantity="temperature", unit="K", label="Temperature [K]")
    b = ComparisonTrace(
        x=np.array([100.0, 150.0]), y=np.array([1.0, 2.0]),
        x_label="Sample temperature [K]", x_quantity="temperature", x_unit="K"
    )
    assert a.compatible_with(b)


def test_malformed_trace_is_rejected():
    with pytest.raises(ValueError):
        ComparisonTrace(x=[1, 2], y=[1], x_label="X")
