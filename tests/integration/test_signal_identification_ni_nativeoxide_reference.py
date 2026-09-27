import json
from pathlib import Path
from types import SimpleNamespace

from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces
from maxiv_panda.signal_identification.peak_detection import detect_peaks, detect_reference_guided_peaks
from maxiv_panda.signal_identification.guided_detection import (
    _companion_assisted_peaks,
    _expected_core_windows,
    _refine_assignments_to_local_features,
)
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.element_consistency import apply_element_consistency


DATASET = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "ni_nativeoxide_survey_1215ev"


def _run_reference_pipeline():
    metadata = json.loads((DATASET / "metadata.json").read_text(encoding="utf-8"))
    expected = json.loads((DATASET / "expected.json").read_text(encoding="utf-8"))
    trace = region_to_traces(parse_structured_txt(DATASET / "spectrum.txt").regions[0])[0]
    payload = SimpleNamespace(x=trace["x"], y=trace["y"], energy_scale="Binding")
    elements = set(metadata["elements"])
    photon = float(metadata["photon_energy_eV"])

    detected = [
        peak for peak in detect_peaks(
            trace["x"], trace["y"],
            prominence_fraction=float(metadata["prominence_fraction"]),
            min_distance_fraction=float(metadata["min_distance_fraction"]),
        ) if peak.energy > 15.0
    ]
    windows = _expected_core_windows(
        energy_scale="Binding", photon_energy=photon, selected_elements=elements,
        tolerance_eV=float(metadata["tolerance_eV"]), sample_mode=metadata["sample_mode"], vb_cutoff=15.0,
    )
    guided = detect_reference_guided_peaks(
        trace["x"], trace["y"], expected_windows=windows, existing_peaks=detected,
        min_feature_fraction=float(metadata["prominence_fraction"]),
    )
    combined = list(detected) + [
        peak for peak in guided
        if all(abs(float(peak.energy) - float(existing.energy)) > 0.4 for existing in detected)
    ]
    combined.sort(key=lambda peak: peak.energy)

    def assign(peaks):
        assignments = match_peaks(
            peaks, energy_scale="Binding", photon_energy=photon,
            tolerance_eV=float(metadata["tolerance_eV"]), elements=elements,
            include_auger=True, include_second_order=False,
            small_charging_possible=bool(metadata["small_charging_possible"]),
            sample_mode=metadata["sample_mode"], alternatives=10,
        )
        return _refine_assignments_to_local_features(assignments, payload, tolerance_eV=float(metadata["tolerance_eV"]))

    assignments = assign(combined)
    companions = _companion_assisted_peaks(
        assignments, payload, energy_scale="Binding", photon_energy=photon,
        sample_mode=metadata["sample_mode"],
    )
    new_companions = [
        peak for peak in companions
        if all(abs(float(peak.energy) - float(existing.energy)) > 0.4 for existing in combined)
    ]
    if new_companions:
        combined.extend(new_companions)
        combined.sort(key=lambda peak: peak.energy)
        assignments = assign(combined)

    consistent = apply_element_consistency(
        assignments, payload, selected_elements=elements, energy_scale="Binding",
        photon_energy=photon, sample_mode=metadata["sample_mode"],
    )
    return expected, consistent


def test_nativeoxide_ni_2p_prefers_coherent_853_870_family_over_855_shoulder():
    expected, consistent = _run_reference_pipeline()
    accepted = {
        assignment.best.label: float(assignment.peak.energy)
        for assignment in consistent
        if assignment.best is not None and assignment.best.kind == "PE"
    }
    for label, energy in expected["required_assignments"].items():
        assert label in accepted
        assert abs(accepted[label] - float(energy)) <= float(expected["position_tolerance_eV"])

    split = accepted["Ni 2p1/2"] - accepted["Ni 2p3/2"]
    assert abs(split - float(expected["ni_splitting_eV"])) <= float(expected["ni_splitting_tolerance_eV"])

    lo, hi = expected["forbidden_ni_2p3_2_window_eV"]
    assert not any(
        assignment.best is not None
        and assignment.best.label == "Ni 2p3/2"
        and lo <= float(assignment.peak.energy) <= hi
        for assignment in consistent
    )
