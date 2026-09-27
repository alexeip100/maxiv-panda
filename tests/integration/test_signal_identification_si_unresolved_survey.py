from pathlib import Path
from types import SimpleNamespace

from maxiv_panda.signal_identification.element_consistency import apply_element_consistency
from maxiv_panda.signal_identification.guided_detection import (
    _expected_core_windows,
    _refine_assignments_to_local_features,
)
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import detect_peaks, detect_reference_guided_peaks
from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces


def test_unresolved_si_2p_survives_resolved_family_consistency_in_05ev_survey():
    path = Path(__file__).with_name("OCV_0004survey_1215.txt")
    region = parse_structured_txt(path).regions[0]
    trace = region_to_traces(region)[0]
    x, y = trace["x"], trace["y"]
    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")
    photon = 1215.0144573526
    elements = {"Cr", "Mn", "Fe", "Co", "Ni", "Si", "O", "C"}

    detected = detect_peaks(x, y, prominence_fraction=0.005, min_distance_fraction=0.012)
    windows = _expected_core_windows(
        energy_scale="Binding", photon_energy=photon,
        selected_elements=elements, tolerance_eV=5.0,
        sample_mode="Automatic (prefer solids)", vb_cutoff=15.0,
    )
    guided = detect_reference_guided_peaks(
        x, y, expected_windows=windows, existing_peaks=detected,
        min_feature_fraction=0.005,
    )
    peaks = detected + [
        peak for peak in guided
        if all(abs(peak.energy - existing.energy) > 0.4 for existing in detected)
    ]
    assignments = match_peaks(
        peaks, energy_scale="Binding", photon_energy=photon,
        tolerance_eV=5.0, elements=elements, include_auger=True,
        small_charging_possible=False,
        sample_mode="Automatic (prefer solids)", alternatives=10,
    )
    refined = _refine_assignments_to_local_features(assignments, payload, tolerance_eV=5.0)
    consistent = apply_element_consistency(
        refined, payload, selected_elements=elements,
        energy_scale="Binding", photon_energy=photon,
        sample_mode="Automatic (prefer solids)",
    )

    si_2p = [a for a in consistent if a.best is not None and a.best.label == "Si 2p"]
    si_2s = [a for a in consistent if a.best is not None and a.best.label == "Si 2s"]
    assert len(si_2p) == 1
    assert abs(si_2p[0].peak.energy - 102.0) <= 0.5
    assert len(si_2s) >= 1
    assert abs(si_2s[0].peak.energy - 153.5) <= 1.0

    # At 0.5 eV sampling the ~0.5 eV Si 2p spin-orbit splitting is not
    # experimentally resolved; no 2p1/2 or 2p3/2 label should replace the
    # observed unresolved Si 2p feature.
    resolved_si = [
        a for a in consistent
        if a.best is not None and a.best.label in {"Si 2p1/2", "Si 2p3/2"}
    ]
    assert not resolved_si
