from types import SimpleNamespace

import numpy as np

from maxiv_panda.signal_identification.core_reference_families import (
    normalized_core_records,
    resolved_family_keys,
)
from maxiv_panda.signal_identification.guided_detection import _refine_assignments_to_local_features
from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
from maxiv_panda.signal_identification.peak_detection import (
    DetectedPeak,
    detect_reference_guided_peaks,
)


def test_phosphorus_2p_is_unresolved_for_survey_matching():
    rows = normalized_core_records("Automatic (prefer solids)")
    p_2p = [
        row for row in rows
        if row.get("element") == "P" and str(row.get("transition", "")).startswith("2p")
    ]
    assert [row["transition"] for row in p_2p] == ["2p"]
    assert ("P", "2p") not in resolved_family_keys(rows)


def test_reference_guided_detector_does_not_duplicate_existing_peak_in_window():
    x = np.arange(180.0, 196.0, 0.5)
    y = 100.0 + 900.0 * np.exp(-0.5 * ((x - 189.0) / 0.8) ** 2)
    existing = [DetectedPeak(index=13, energy=186.5, intensity=150.0, prominence=120.0)]
    guided = detect_reference_guided_peaks(
        x,
        y,
        expected_windows=[(189.0, 2.5)],
        existing_peaks=existing,
        min_feature_fraction=0.005,
    )
    assert guided == []


def test_2s_refinement_can_reach_raw_apex_displaced_by_survey_smoothing():
    # Shape modelled on the P 2s region of the reported survey: the broad
    # detector may seed near 186.5 eV while the raw narrow apex is at 189 eV.
    x = np.arange(180.0, 195.5, 0.5)
    baseline = 30000.0 + 300.0 * (x - 180.0)
    peak = 22000.0 * np.exp(-0.5 * ((x - 189.0) / 0.65) ** 2)
    y = baseline + peak
    idx = int(np.argmin(np.abs(x - 186.5)))
    assignment = PeakAssignment(
        peak=DetectedPeak(idx, 186.5, float(y[idx]), 13000.0),
        candidates=[SignalCandidate(
            element="P", line="2s", kind="PE", expected_energy=189.0,
            delta_e=-2.5, score=-0.2, confident=True,
            reason="Accepted: close reference match with companion/uniqueness support",
        )],
    )
    refined = _refine_assignments_to_local_features(
        [assignment], SimpleNamespace(x=x, y=y, energy_scale="Binding"), tolerance_eV=5.0
    )
    assert refined[0].best is not None
    assert refined[0].best.label == "P 2s"
    assert abs(refined[0].peak.energy - 189.0) <= 0.5
