import numpy as np

from maxiv_panda.workflows.peakfit.fit_plotting import smooth_curve_for_display


def test_shape_preserving_display_smoothing_does_not_overshoot_monotonic_edge():
    x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
    y = np.array([10.0, 10.2, 10.8, 12.0, 15.0])
    xs, ys = smooth_curve_for_display(x, y, num_points=200)
    assert xs.size >= x.size
    assert np.nanmin(ys) >= np.min(y) - 1e-12
    assert np.nanmax(ys) <= np.max(y) + 1e-12
    assert abs(float(ys[0]) - float(y[0])) < 1e-12
    assert abs(float(ys[-1]) - float(y[-1])) < 1e-12
