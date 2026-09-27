import json
from pathlib import Path
from types import SimpleNamespace

from maxiv_panda.signal_identification.guided_detection import (
    _companion_assisted_peaks,
    _expected_core_windows,
    _refine_assignments_to_local_features,
)
from maxiv_panda.signal_identification.element_consistency import apply_element_consistency
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import (
    detect_peaks,
    detect_reference_guided_peaks,
)
from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces


DATASET = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "carbon_au_survey_1000ev"


def _run_reference_pipeline():
    parsed = parse_structured_txt(DATASET / "spectrum.txt")
    trace = region_to_traces(parsed.regions[0])[0]
    payload = SimpleNamespace(x=trace["x"], y=trace["y"], energy_scale="Binding")

    detected = detect_peaks(
        trace["x"], trace["y"], prominence_fraction=0.01, min_distance_fraction=0.012
    )
    detected = [peak for peak in detected if peak.energy > 15.0]
    windows = _expected_core_windows(
        energy_scale="Binding",
        photon_energy=1000.0,
        selected_elements={"Au", "C"},
        tolerance_eV=2.0,
        sample_mode="Automatic (prefer solids)",
        vb_cutoff=15.0,
    )
    guided = detect_reference_guided_peaks(
        trace["x"],
        trace["y"],
        expected_windows=windows,
        existing_peaks=detected,
        min_feature_fraction=0.01,
    )
    combined = list(detected) + [
        peak for peak in guided
        if all(abs(float(peak.energy) - float(existing.energy)) > 0.4 for existing in detected)
    ]
    combined.sort(key=lambda peak: peak.energy)
    def assign(peaks):
        assignments = match_peaks(
            peaks,
            energy_scale="Binding",
            photon_energy=1000.0,
            tolerance_eV=2.0,
            elements={"Au", "C"},
            include_auger=False,
            small_charging_possible=False,
            sample_mode="Automatic (prefer solids)",
            alternatives=10,
        )
        return _refine_assignments_to_local_features(assignments, payload, tolerance_eV=2.0)

    assignments = assign(combined)
    companions = _companion_assisted_peaks(
        assignments, payload, energy_scale="Binding", photon_energy=1000.0,
        sample_mode="Automatic (prefer solids)",
    )
    if companions:
        combined.extend(
            peak for peak in companions
            if all(abs(float(peak.energy) - float(existing.energy)) > 0.4 for existing in combined)
        )
        combined.sort(key=lambda peak: peak.energy)
        assignments = assign(combined)

    assignments = apply_element_consistency(
        assignments, payload, selected_elements={"Au", "C"}, energy_scale="Binding",
        photon_energy=1000.0, sample_mode="Automatic (prefer solids)",
    )
    return trace, assignments


def _accepted(assignments):
    return {
        assignment.best.label: float(assignment.peak.energy)
        for assignment in assignments
        if assignment.best is not None
    }


def test_au_reference_metadata_and_grid():
    metadata = json.loads((DATASET / "metadata.json").read_text(encoding="utf-8"))
    trace, _assignments = _run_reference_pipeline()
    assert metadata["photon_energy_eV"] == 1000.0
    assert trace["energy_scale"] == "Binding"
    assert len(trace["x"]) == 1290
    assert abs(abs(float(trace["x"][1]) - float(trace["x"][0])) - 0.7) < 1e-9


def test_resolved_au_4f_components_use_their_own_peak_positions():
    expected = json.loads((DATASET / "expected.json").read_text(encoding="utf-8"))
    _trace, assignments = _run_reference_pipeline()
    accepted = _accepted(assignments)

    for label, energy in expected["required_assignments"].items():
        assert label in accepted
        assert abs(accepted[label] - energy) <= expected["position_tolerance_eV"]

    split = accepted["Au 4f5/2"] - accepted["Au 4f7/2"]
    assert abs(split - expected["expected_spin_orbit_splitting_eV"]) <= expected["splitting_tolerance_eV"]


def test_au_4f5_2_is_not_placed_in_the_doublet_valley():
    expected = json.loads((DATASET / "expected.json").read_text(encoding="utf-8"))
    _trace, assignments = _run_reference_pipeline()
    accepted = _accepted(assignments)
    lo, hi = expected["forbidden_component_position_range_eV"]
    assert not (lo <= accepted["Au 4f5/2"] <= hi)
