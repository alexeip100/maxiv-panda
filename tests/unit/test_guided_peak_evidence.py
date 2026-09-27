from __future__ import annotations

import numpy as np

from maxiv_panda.signal_identification.peak_detection import refine_peak_near_reference


def test_reference_guided_detection_rejects_noise_only_window() -> None:
    rng = np.random.default_rng(1234)
    x = np.linspace(630.0, 650.0, 81)
    y = 1000.0 + 1.2 * (x - x.mean()) + rng.normal(0.0, 3.0, x.size)

    peak = refine_peak_near_reference(
        x,
        y,
        target_energy=640.0,
        search_half_width=4.0,
        min_feature_height=0.5,
    )

    assert peak is None


def test_reference_guided_detection_keeps_weak_peak_above_noise() -> None:
    rng = np.random.default_rng(5678)
    x = np.linspace(630.0, 650.0, 161)
    weak_peak = 18.0 * np.exp(-0.5 * ((x - 641.2) / 0.8) ** 2)
    y = 1000.0 + 0.8 * (x - x.mean()) + weak_peak + rng.normal(0.0, 1.2, x.size)

    peak = refine_peak_near_reference(
        x,
        y,
        target_energy=640.0,
        search_half_width=4.0,
        min_feature_height=0.5,
    )

    assert peak is not None
    assert abs(peak.energy - 641.2) <= 0.35


def test_refinement_reports_observed_maximum_not_reference_position() -> None:
    x = np.linspace(770.0, 800.0, 301)
    y = 100.0 + 50.0 * np.exp(-0.5 * ((x - 781.8) / 1.6) ** 2)

    peak = refine_peak_near_reference(
        x,
        y,
        target_energy=780.0,
        search_half_width=3.0,
        min_feature_height=1.0,
    )

    assert peak is not None
    assert abs(peak.energy - 781.8) <= 0.35


def test_reference_guided_detrended_noise_recovers_peak_on_curved_background() -> None:
    rng = np.random.default_rng(9012)
    x = np.linspace(280.0, 290.0, 21)
    background = 1000.0 + 9.0 * (x - 285.0) + 0.5 * (x - 285.0) ** 2
    weak_peak = 40.0 * np.exp(-0.5 * ((x - 284.0) / 0.65) ** 2)
    y = background + weak_peak + rng.normal(0.0, 2.0, x.size)

    peak = refine_peak_near_reference(
        x,
        y,
        target_energy=285.0,
        search_half_width=5.0,
        min_feature_height=5.0,
        detrend_background_noise=True,
    )

    assert peak is not None
    assert abs(peak.energy - 284.0) <= 0.55
