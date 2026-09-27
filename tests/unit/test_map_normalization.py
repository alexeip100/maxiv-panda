import numpy as np
import pytest

from maxiv_panda.workflows.normalization.logic import (
    integrated_intensity_over_interval,
    normalize_map_rows_at_energy,
    normalize_map_rows_by_area,
)


def test_integrated_intensity_uses_interpolated_boundaries():
    x = np.array([0.0, 1.0, 2.0, 3.0])
    y = 2.0 * x + 1.0
    # Integral of 2x+1 from 0.5 to 2.5 = [x^2+x] = 8.0
    assert integrated_intensity_over_interval(x, y, 0.5, 2.5) == pytest.approx(8.0)


def test_at_energy_normalizes_each_map_row_independently_and_keeps_order():
    x = np.array([3.0, 2.0, 1.0, 0.0])  # descending, as BE commonly is displayed
    z = np.array([
        [8.0, 6.0, 4.0, 2.0],
        [16.0, 12.0, 8.0, 4.0],
    ])
    out, interval = normalize_map_rows_at_energy(x, z, centre=1.0, width_ev=0.6)
    assert interval[0] < 1.0 < interval[1]
    assert np.allclose(out[1], out[0])
    # Original column order must be retained.
    assert out[0, 0] > out[0, -1]


def test_area_normalization_makes_requested_area_one_for_each_row():
    x = np.linspace(0.0, 10.0, 101)
    z = np.vstack([2.0 + x, 4.0 + 2.0 * x])
    out = normalize_map_rows_by_area(x, z, 2.0, 8.0)
    for row in out:
        mask = (x >= 2.0) & (x <= 8.0)
        assert np.trapezoid(row[mask], x[mask]) == pytest.approx(1.0, rel=1e-10)


def test_map_normalization_rejects_zero_denominator():
    x = np.linspace(0.0, 1.0, 11)
    z = np.zeros((2, x.size))
    with pytest.raises(ValueError):
        normalize_map_rows_at_energy(x, z, 0.5, 0.2)
    with pytest.raises(ValueError):
        normalize_map_rows_by_area(x, z, 0.0, 1.0)


def test_area_normalization_rejects_limits_outside_energy_axis():
    x = np.linspace(0.0, 10.0, 101)
    z = np.vstack([2.0 + x, 4.0 + 2.0 * x])
    with pytest.raises(ValueError, match="outside"):
        normalize_map_rows_by_area(x, z, -1.0, 8.0)
    with pytest.raises(ValueError, match="outside"):
        normalize_map_rows_by_area(x, z, 2.0, 11.0)


def test_at_energy_rejects_interval_extending_outside_axis():
    x = np.linspace(0.0, 10.0, 101)
    z = np.vstack([2.0 + x, 4.0 + 2.0 * x])
    with pytest.raises(ValueError, match="outside"):
        normalize_map_rows_at_energy(x, z, centre=0.2, width_ev=1.0)
    with pytest.raises(ValueError, match="outside"):
        normalize_map_rows_at_energy(x, z, centre=9.8, width_ev=1.0)
