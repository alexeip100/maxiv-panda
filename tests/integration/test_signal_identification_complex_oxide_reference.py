from pathlib import Path
from types import SimpleNamespace

from maxiv_panda.ibw_parser import parse_ibw
from maxiv_panda.signal_identification.auger_detection import _broad_auger_assignments
from maxiv_panda.signal_identification.element_consistency import apply_element_consistency
from maxiv_panda.signal_identification.guided_detection import (
    _expected_core_windows, _refine_assignments_to_local_features,
)
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import detect_peaks, detect_reference_guided_peaks


def test_complex_oxide_family_consistency_and_o_kll_overlap():
    region = parse_ibw(Path(__file__).with_name("AR_11_7_0001survey_1215.ibw")).regions[0]
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
        elements=elements, include_auger=True, small_charging_possible=True,
        sample_mode="Automatic",
    )
    assignments = _refine_assignments_to_local_features(assignments, payload, tolerance_eV=2.0)
    assignments = apply_element_consistency(
        assignments, payload, selected_elements=elements, energy_scale="Binding",
        photon_energy=1215.0, sample_mode="Automatic",
    )
    labels = {a.best.label for a in assignments if a.best is not None}
    assert {"Ni 2p3/2", "Ni 2p1/2", "Co 2p3/2", "Co 2p1/2", "Cr 2p3/2", "Cr 2p1/2"} <= labels
    assert "Si 2p" in labels
    assert "Ni 3p" in labels
    assert "Co 3s" not in labels
    for label in labels:
        if label.endswith(" 3s"):
            assert label.replace(" 3s", " 3p") in labels
    auger = _broad_auger_assignments(
        assignments, payload, energy_scale="Binding", photon_energy=1215.0,
        selected_elements=elements, small_charging_possible=True,
    )
    auger_labels = {a.best.label for a in auger if a.best is not None}
    assert "O KLL" in auger_labels
