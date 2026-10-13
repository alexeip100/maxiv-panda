import numpy as np
import pytest

from maxiv_panda.workflows.normalization.logic import (
    integrated_intensity_over_interval,
    mean_intensity_over_interval,
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


def test_ke_interval_normalization_on_measured_be_map_tracks_diagonal():
    from maxiv_panda.workflows.normalization.logic import normalize_respes_rows_at_kinetic_energy

    x_be = np.array([3.0, 2.0, 1.0, 0.0])
    hv = np.array([570.0, 571.0, 572.0])
    # Fixed KE 565.0 eV corresponds to BE 0.5, 1.5, 2.5 eV for the rows.
    z = np.array([
        [40.0, 30.0, 20.0, 10.0],
        [80.0, 60.0, 40.0, 20.0],
        [120.0, 90.0, 60.0, 30.0],
    ])
    out, interval = normalize_respes_rows_at_kinetic_energy(
        x_be, z, hv, centre_ke=565.0, width_ev=0.4, work_function=4.5, source_axis="be"
    )
    assert interval == pytest.approx((564.8, 565.2))
    # Verify the normalized mean is one along the fixed-KE trajectory.
    for row_idx, hnu in enumerate(hv):
        low_be = hnu - 4.5 - interval[1]
        high_be = hnu - 4.5 - interval[0]
        order = np.argsort(x_be)
        assert mean_intensity_over_interval(
            x_be[order], out[row_idx, order], low_be, high_be
        ) == pytest.approx(1.0)


def test_ke_interval_normalization_on_measured_ke_map_is_vertical():
    from maxiv_panda.workflows.normalization.logic import normalize_respes_rows_at_kinetic_energy

    x_ke = np.array([563.0, 564.0, 565.0, 566.0])
    hv = np.array([570.0, 571.0])
    z = np.array([[2.0, 4.0, 6.0, 8.0], [4.0, 8.0, 12.0, 16.0]])
    out, _ = normalize_respes_rows_at_kinetic_energy(
        x_ke, z, hv, centre_ke=565.0, width_ev=0.4, source_axis="ke"
    )
    assert np.allclose(out[1], out[0])
    assert out[0, 2] == pytest.approx(1.0, rel=0.06)


def test_ke_interval_requires_complete_coverage_in_every_row():
    from maxiv_panda.workflows.normalization.logic import normalize_respes_rows_at_kinetic_energy

    x_be = np.linspace(0.0, 2.0, 21)
    hv = np.array([570.0, 571.0])
    z = np.ones((2, x_be.size))
    # At 570 eV, KE~566 eV is available; at 571 eV it maps beyond the BE axis.
    with pytest.raises(ValueError, match="unavailable for at least one row"):
        normalize_respes_rows_at_kinetic_energy(
            x_be, z, hv, centre_ke=565.8, width_ev=0.4, work_function=4.5, source_axis="be"
        )


def test_photon_energy_interval_builds_weighted_reference_with_interpolated_edges():
    from maxiv_panda.workflows.normalization.logic import normalize_map_to_photon_energy_interval

    hv = np.array([570.0, 572.0, 575.0])
    # Each energy channel is linear in photon energy, so the weighted mean over
    # 571..574 eV equals the value at the interval midpoint 572.5 eV.
    z = np.column_stack((2.0 * hv + 1.0, 3.0 * hv - 5.0))
    out, interval, reference = normalize_map_to_photon_energy_interval(
        hv, z, centre_hv=572.5, width_ev=3.0
    )
    assert interval == pytest.approx((571.0, 574.0))
    expected = np.array([2.0 * 572.5 + 1.0, 3.0 * 572.5 - 5.0])
    assert np.allclose(reference, expected)
    # The weighted mean of the normalized rows over the same interval is 1 in
    # each electron-energy channel.
    for col in range(out.shape[1]):
        assert mean_intensity_over_interval(np.sort(hv), out[np.argsort(hv), col], 571.0, 574.0) == pytest.approx(1.0)


def test_photon_energy_interval_rejects_zero_reference_channel():
    from maxiv_panda.workflows.normalization.logic import normalize_map_to_photon_energy_interval

    hv = np.array([570.0, 571.0, 572.0])
    z = np.array([[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]])
    with pytest.raises(ValueError, match="reference spectrum"):
        normalize_map_to_photon_energy_interval(hv, z, centre_hv=571.0, width_ev=1.0)


def test_photon_energy_interval_accepts_descending_scan_order():
    from maxiv_panda.workflows.normalization.logic import normalize_map_to_photon_energy_interval

    hv = np.array([575.0, 572.0, 570.0])
    z = np.column_stack((2.0 * hv + 1.0, 3.0 * hv - 5.0))
    out, interval, reference = normalize_map_to_photon_energy_interval(
        hv, z, centre_hv=572.5, width_ev=3.0
    )
    assert interval == pytest.approx((571.0, 574.0))
    assert np.allclose(reference, [2.0 * 572.5 + 1.0, 3.0 * 572.5 - 5.0])
    order = np.argsort(hv)
    for col in range(out.shape[1]):
        assert mean_intensity_over_interval(hv[order], out[order, col], 571.0, 574.0) == pytest.approx(1.0)


def test_respes_be_normalization_on_ke_source_uses_row_dependent_ke_windows():
    from maxiv_panda.workflows.normalization.logic import normalize_respes_rows_at_binding_energy
    x = np.linspace(410.0, 450.0, 81)
    hv = np.array([484.0, 490.0, 496.0, 502.0])
    phi = 4.5
    centre_be = 55.0
    width = 2.0
    z = np.vstack([
        2.0 + 5.0 * np.exp(-0.5 * ((x - (h - phi - centre_be)) / 0.8) ** 2)
        for h in hv
    ])
    out, interval = normalize_respes_rows_at_binding_energy(
        x, z, hv, centre_be, width, work_function=phi, source_axis="ke"
    )
    assert interval == (54.0, 56.0)
    for i, h in enumerate(hv):
        lo = h - phi - interval[1]
        hi = h - phi - interval[0]
        mask = (x >= lo) & (x <= hi)
        assert np.isclose(np.mean(out[i, mask]), 1.0, atol=0.12)


def test_respes_be_normalization_rejects_interval_not_common_to_all_rows():
    import pytest
    from maxiv_panda.workflows.normalization.logic import normalize_respes_rows_at_binding_energy
    x = np.linspace(410.0, 450.0, 81)
    hv = np.array([484.0, 502.0])
    z = np.ones((2, x.size))
    with pytest.raises(ValueError, match="binding-energy normalization interval is unavailable"):
        normalize_respes_rows_at_binding_energy(
            x, z, hv, centre_be=40.0, width_ev=4.0, work_function=4.5, source_axis="ke"
        )
