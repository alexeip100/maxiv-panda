import numpy as np

from maxiv_panda.workflows.peakfit.peak_detection import suggest_initial_peaks


def _gauss(x, mu, sigma, amp):
    return amp * np.exp(-0.5 * ((x - mu) / sigma) ** 2)


def test_conservative_detector_finds_clear_resolved_peaks():
    rng = np.random.default_rng(5)
    x = np.linspace(150.0, 170.0, 2001)
    y = 10.0 + _gauss(x, 156.0, 0.22, 80.0) + _gauss(x, 162.0, 0.28, 55.0)
    y += rng.normal(0.0, 0.5, x.size)
    peaks = suggest_initial_peaks(x, y)
    assert len(peaks) == 2
    assert abs(peaks[0].energy - 156.0) < 0.15
    assert abs(peaks[1].energy - 162.0) < 0.15


def test_detector_respects_03ev_separation_and_caps_at_five():
    x = np.linspace(0.0, 10.0, 4001)
    y = np.ones_like(x)
    for mu in (1.0, 1.20, 1.35, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0):
        y += _gauss(x, mu, 0.08, 20.0)
    peaks = suggest_initial_peaks(x, y)
    assert len(peaks) <= 5
    energies = [p.energy for p in peaks]
    assert all(abs(a - b) >= 0.299 for i, a in enumerate(energies) for b in energies[i + 1:])


def test_detector_does_not_treat_rising_edge_as_peak():
    x = np.linspace(0.0, 10.0, 2001)
    y = 2.0 + 0.4 * x + _gauss(x, 5.0, 0.25, 10.0)
    # Strong rise very close to the right boundary must not become a suggestion.
    y += 30.0 * np.exp((x - 10.0) / 0.12)
    peaks = suggest_initial_peaks(x, y)
    assert any(abs(p.energy - 5.0) < 0.15 for p in peaks)
    assert all(p.energy <= 9.5 for p in peaks)


def test_no_convincing_peak_falls_back_to_one_interior_marker():
    x = np.linspace(0.0, 10.0, 1001)
    y = x  # monotonic background only
    peaks = suggest_initial_peaks(x, y)
    assert len(peaks) == 1
    assert 0.5 <= peaks[0].energy <= 9.5


def test_reported_height_is_component_amplitude_not_absolute_signal():
    x = np.linspace(0.0, 10.0, 1001)
    baseline = 2000.0 + 8.0 * x
    y = baseline + _gauss(x, 5.0, 0.25, 500.0)
    peaks = suggest_initial_peaks(x, y)
    assert len(peaks) == 1
    # The initial component amplitude must be of order the peak above background,
    # not the ~2040-count absolute spectrum intensity.
    assert 350.0 < peaks[0].height < 650.0


def test_noisy_background_does_not_seed_ghost_peaks():
    rng = np.random.default_rng(42)
    x = np.linspace(157.0, 171.0, 1401)
    baseline = 1900.0 + 12.0 * (171.0 - x)
    y = baseline + _gauss(x, 164.35, 0.30, 5600.0)
    # Add a modest real shoulder plus realistic high-frequency noise/ripple.
    y += _gauss(x, 165.45, 0.34, 1700.0)
    y += rng.normal(0.0, 65.0, x.size)
    y += 55.0 * np.sin(2.0 * np.pi * x / 0.42)
    peaks = suggest_initial_peaks(x, y)
    assert 1 <= len(peaks) <= 2
    assert all(p.energy > 163.5 for p in peaks)
    assert max(p.height for p in peaks) < 7000.0
