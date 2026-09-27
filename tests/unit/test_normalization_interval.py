from __future__ import annotations

import numpy as np

from maxiv_panda.workflows.normalization.logic import normalization_interval, mean_intensity_over_interval


def test_normalization_interval_is_symmetric_away_from_edges():
    low, high = normalization_interval(0.0, 100.0, 50.0, 10.0)
    assert low == 45.0
    assert high == 55.0


def test_normalization_interval_shifts_inward_near_low_edge():
    low, high = normalization_interval(0.0, 100.0, 3.0, 10.0)
    assert low == 0.0
    assert high == 10.0


def test_normalization_interval_shifts_inward_near_high_edge():
    low, high = normalization_interval(0.0, 100.0, 98.0, 10.0)
    assert low == 90.0
    assert high == 100.0


def test_interval_mean_uses_full_energy_span_not_one_channel():
    x = np.arange(0.0, 11.0, 1.0)
    y = 2.0 + x
    mean = mean_intensity_over_interval(x, y, 2.0, 6.0)
    assert np.isclose(mean, 6.0)
