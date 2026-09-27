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


DATASET = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "mn_charged_survey_1215ev"


def _load_reference():
    metadata = json.loads((DATASET / "metadata.json").read_text(encoding="utf-8"))
    expected = json.loads((DATASET / "expected.json").read_text(encoding="utf-8"))
    trace = region_to_traces(parse_structured_txt(DATASET / "spectrum.txt").regions[0])[0]
    payload = SimpleNamespace(x=trace["x"], y=trace["y"], energy_scale="Binding")
    return metadata, expected, trace, payload


def _run_reference_pipeline():
    metadata, expected, trace, payload = _load_reference()
    elements = set(metadata["elements"])
    photon = float(metadata["photon_energy_eV"])

    detected = [
        peak for peak in detect_peaks(
            trace["x"], trace["y"],
            prominence_fraction=float(metadata["prominence_fraction"]),
            min_distance_fraction=float(metadata["min_distance_fraction"]),
        )
        if peak.energy > 15.0
    ]
    windows = _expected_core_windows(
        energy_scale="Binding", photon_energy=photon, selected_elements=elements,
        tolerance_eV=float(metadata["tolerance_eV"]), sample_mode=metadata["sample_mode"],
        vb_cutoff=15.0,
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
            include_auger=True, small_charging_possible=bool(metadata["small_charging_possible"]),
            sample_mode=metadata["sample_mode"], alternatives=10,
        )
        return _refine_assignments_to_local_features(
            assignments, payload, tolerance_eV=float(metadata["tolerance_eV"])
        )

    assignments = assign(combined)
    companions = _companion_assisted_peaks(
        assignments, payload, energy_scale="Binding", photon_energy=photon,
        sample_mode=metadata["sample_mode"],
    )
    if companions:
        combined.extend(
            peak for peak in companions
            if all(abs(float(peak.energy) - float(existing.energy)) > 0.4 for existing in combined)
        )
        combined.sort(key=lambda peak: peak.energy)
        assignments = assign(combined)

    consistent = apply_element_consistency(
        assignments, payload, selected_elements=elements, energy_scale="Binding",
        photon_energy=photon, sample_mode=metadata["sample_mode"],
    )
    return metadata, expected, detected, guided, consistent


def test_resolved_mn_guided_search_uses_only_stronger_component_absolute_anchor():
    metadata, _expected, _trace, _payload = _load_reference()
    windows = _expected_core_windows(
        energy_scale="Binding", photon_energy=float(metadata["photon_energy_eV"]),
        selected_elements={"Mn"}, tolerance_eV=float(metadata["tolerance_eV"]),
        sample_mode=metadata["sample_mode"], vb_cutoff=15.0,
    )
    # Mn 2p3/2 has the larger Yeh-Lindau cross section and is the only 2p
    # member allowed an absolute-energy guide window.  The weaker 2p1/2 is
    # recovered later from the measured 2p3/2 anchor plus the family splitting.
    mn_2p_windows = [(center, width) for center, width in windows if 630.0 <= center <= 660.0]
    assert len(mn_2p_windows) == 1
    assert 637.0 <= mn_2p_windows[0][0] <= 643.0


def test_charged_mn_doublet_recovers_real_partner_not_unshifted_shoulder():
    _metadata, expected, detected, guided, consistent = _run_reference_pipeline()

    # Both visible experimental structures survive generic peak detection.
    assert any(641.0 <= float(peak.energy) <= 644.5 for peak in detected)
    assert any(653.0 <= float(peak.energy) <= 656.5 for peak in detected)

    # Strong-first guided detection must not manufacture the old ~650 eV weak
    # component candidate merely because the unshifted 2p1/2 reference is there.
    lo, hi = expected["forbidden_weak_assignment_range_eV"]
    assert not any(lo <= float(peak.energy) <= hi for peak in guided)

    accepted = {
        assignment.best.label: float(assignment.peak.energy)
        for assignment in consistent
        if assignment.best is not None and assignment.best.kind == "PE"
    }
    for label, energy in expected["required_assignments"].items():
        assert label in accepted
        assert abs(accepted[label] - float(energy)) <= float(expected["position_tolerance_eV"])

    split = accepted["Mn 2p1/2"] - accepted["Mn 2p3/2"]
    assert abs(split - float(expected["expected_spin_orbit_splitting_eV"])) <= float(expected["splitting_tolerance_eV"])
    assert not (lo <= accepted["Mn 2p1/2"] <= hi)
    for label in expected.get("forbidden_assignments", []):
        assert label not in accepted
