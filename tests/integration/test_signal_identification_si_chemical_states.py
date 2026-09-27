from pathlib import Path
from types import SimpleNamespace

from maxiv_panda.ibw_parser import parse_ibw
from maxiv_panda.signal_identification.element_consistency import apply_element_consistency
from maxiv_panda.signal_identification.guided_detection import (
    _expected_core_windows,
    _refine_assignments_to_local_features,
)
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import detect_peaks, detect_reference_guided_peaks


def test_si_and_siox_pairs_are_kept_as_two_2p_and_two_2s_components():
    region = parse_ibw(Path(__file__).with_name("OCV_0001survey_1215.ibw")).regions[0]
    x, y = region.data[:, 0], region.data[:, 1]
    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")
    elements = {"Cr", "Mn", "Fe", "Co", "Ni", "Si", "O", "C"}

    detected = detect_peaks(x, y, prominence_fraction=0.01, min_distance_fraction=0.006)
    windows = _expected_core_windows(
        energy_scale="Binding", photon_energy=1215.0, selected_elements=elements,
        tolerance_eV=2.0, sample_mode="Automatic", vb_cutoff=15.0,
    )
    guided = detect_reference_guided_peaks(
        x, y, expected_windows=windows, existing_peaks=detected, min_feature_fraction=0.01,
    )
    peaks = detected + [p for p in guided if all(abs(p.energy - q.energy) > 0.4 for q in detected)]
    assignments = match_peaks(
        peaks, energy_scale="Binding", photon_energy=1215.0, tolerance_eV=2.0,
        elements=elements, include_auger=True, small_charging_possible=False,
        sample_mode="Automatic",
    )
    assignments = _refine_assignments_to_local_features(assignments, payload, tolerance_eV=2.0)
    assignments = apply_element_consistency(
        assignments, payload, selected_elements=elements, energy_scale="Binding",
        photon_energy=1215.0, sample_mode="Automatic",
    )

    si_2p = sorted(a.peak.energy for a in assignments if a.best is not None and a.best.label == "Si 2p")
    si_2s = sorted(a.peak.energy for a in assignments if a.best is not None and a.best.label == "Si 2s")
    assert si_2p == [99.0, 102.5]
    assert si_2s == [150.5, 154.0]
    assert abs((si_2p[1] - si_2p[0]) - (si_2s[1] - si_2s[0])) <= 0.5
