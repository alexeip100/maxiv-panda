from pathlib import Path
from types import SimpleNamespace

import numpy as np

from maxiv_panda.signal_identification.element_consistency import apply_element_consistency
from maxiv_panda.signal_identification.guided_detection import (
    _companion_assisted_peaks,
    _expected_core_windows,
    _refine_assignments_to_local_features,
)
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import detect_peaks, detect_reference_guided_peaks


DATA = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "ir_bn_700ev_4f_window.csv"


def _run_ir_window():
    values = np.loadtxt(DATA, delimiter=",", skiprows=1)
    x, y = values[:, 0], values[:, 1]
    payload = SimpleNamespace(x=x, y=y)
    elements = {"Ir", "N", "B"}

    detected = [
        p for p in detect_peaks(x, y, prominence_fraction=0.01, min_distance_fraction=0.012)
        if p.energy > 15.0
    ]
    windows = _expected_core_windows(
        energy_scale="Binding",
        photon_energy=700.0,
        selected_elements=elements,
        tolerance_eV=2.0,
        sample_mode="Automatic (prefer solids)",
        vb_cutoff=15.0,
    )
    guided = detect_reference_guided_peaks(
        x, y,
        expected_windows=windows,
        existing_peaks=detected,
        min_feature_fraction=0.01,
    )
    combined = list(detected) + [
        p for p in guided if all(abs(p.energy - q.energy) > 0.4 for q in detected)
    ]
    combined.sort(key=lambda p: p.energy)

    def assign(peaks):
        assignments = match_peaks(
            peaks,
            energy_scale="Binding",
            photon_energy=700.0,
            tolerance_eV=2.0,
            elements=elements,
            include_auger=False,
            sample_mode="Automatic (prefer solids)",
        )
        return _refine_assignments_to_local_features(assignments, payload, tolerance_eV=2.0)

    assignments = assign(combined)
    companions = _companion_assisted_peaks(
        assignments,
        payload,
        energy_scale="Binding",
        photon_energy=700.0,
        sample_mode="Automatic (prefer solids)",
    )
    if companions:
        combined.extend(
            p for p in companions
            if all(abs(float(p.energy) - float(q.energy)) > 0.4 for q in combined)
        )
        combined.sort(key=lambda p: p.energy)
        assignments = assign(combined)

    return apply_element_consistency(
        assignments,
        payload,
        selected_elements=elements,
        energy_scale="Binding",
        photon_energy=700.0,
        sample_mode="Automatic (prefer solids)",
    )


def test_ir_4f_doublet_wins_over_overlapping_ir_5p1_2():
    assignments = _run_ir_window()
    accepted = {
        assignment.best.label: assignment.peak.energy
        for assignment in assignments
        if assignment.best is not None
    }
    assert abs(accepted["Ir 4f7/2"] - 60.5) <= 0.6
    assert abs(accepted["Ir 4f5/2"] - 63.5) <= 0.6
    assert "Ir 5p1/2" not in accepted
