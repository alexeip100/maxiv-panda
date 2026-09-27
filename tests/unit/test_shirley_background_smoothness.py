from __future__ import annotations

import numpy as np

from maxiv_panda.workflows.peakfit.fit_models import compute_shirley_background


def test_shirley_background_does_not_follow_downward_noise_spikes():
    # Synthetic binding-energy spectrum with a smooth sloping envelope plus
    # sharp downward noise spikes.  A Shirley integral background may sit above
    # individual noisy samples and must not inherit those pointwise spikes.
    x = np.linspace(159.5, 162.5, 401)
    baseline = 16000.0 + 4500.0 * (x - x.min()) / (x.max() - x.min())
    peak = 9000.0 * np.exp(-0.5 * ((x - 161.9) / 0.20) ** 2)
    y = baseline + peak
    y = y.copy()
    spike_idx = np.array([45, 91, 144, 219, 301, 352])
    y[spike_idx] -= 2500.0

    bg = compute_shirley_background(x, y, "Binding", alpha=1.0)

    assert bg.shape == y.shape
    assert np.all(np.isfinite(bg))
    assert np.all(bg >= 0.0)

    # The defining regression: at least one deliberately low noisy data point
    # is allowed to lie below the smooth background.  The former implementation
    # forcibly clipped bg <= y at every point, creating visible oscillations.
    assert np.any(bg[spike_idx] > y[spike_idx])

    # Shirley construction should remain monotonic apart from tiny numerical
    # round-off when x is ordered from low to high binding energy.
    d = np.diff(bg)
    endpoint_direction = np.sign(bg[-1] - bg[0])
    if endpoint_direction >= 0:
        assert np.min(d) >= -1e-8
    else:
        assert np.max(d) <= 1e-8


def test_shirley_background_preserves_input_order_for_descending_binding_energy():
    x = np.linspace(162.5, 159.5, 301)
    baseline = np.linspace(22000.0, 16000.0, x.size)
    peak = 8000.0 * np.exp(-0.5 * ((x - 161.8) / 0.22) ** 2)
    y = baseline + peak
    bg = compute_shirley_background(x, y, "Binding Energy", alpha=1.0)

    assert bg.shape == x.shape
    assert np.all(np.isfinite(bg))
    # Reversing both axes/data should produce the same physical background.
    bg_rev = compute_shirley_background(x[::-1], y[::-1], "Binding Energy", alpha=1.0)
    np.testing.assert_allclose(bg, bg_rev[::-1], rtol=1e-12, atol=1e-9)
