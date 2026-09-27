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


DATASET = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "ir_hbn_contamination_700ev"


def _run_reference_pipeline(prominence_fraction: float):
    metadata = json.loads((DATASET / "metadata.json").read_text(encoding="utf-8"))
    trace = region_to_traces(parse_structured_txt(DATASET / "spectrum.txt").regions[0])[0]
    payload = SimpleNamespace(x=trace["x"], y=trace["y"], energy_scale="Binding")
    elements = set(metadata["elements"])
    photon = float(metadata["photon_energy_eV"])

    detected = [
        peak for peak in detect_peaks(
            trace["x"], trace["y"], prominence_fraction=prominence_fraction,
            min_distance_fraction=float(metadata["min_distance_fraction"]),
        ) if peak.energy > 15.0
    ]
    windows = _expected_core_windows(
        energy_scale="Binding", photon_energy=photon, selected_elements=elements,
        tolerance_eV=float(metadata["tolerance_eV"]), sample_mode=metadata["sample_mode"], vb_cutoff=15.0,
    )
    guided = detect_reference_guided_peaks(
        trace["x"], trace["y"], expected_windows=windows, existing_peaks=detected,
        min_feature_fraction=max(prominence_fraction, 0.001),
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
            small_charging_possible=False, sample_mode=metadata["sample_mode"], alternatives=10,
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

    return apply_element_consistency(
        assignments, payload, selected_elements=elements, energy_scale="Binding",
        photon_energy=photon, sample_mode=metadata["sample_mode"],
    )


def test_weak_c1s_is_recovered_on_ir_hbn_survey():
    expected = json.loads((DATASET / "expected.json").read_text(encoding="utf-8"))
    assignments = _run_reference_pipeline(0.005)
    accepted = {
        assignment.best.label: float(assignment.peak.energy)
        for assignment in assignments if assignment.best is not None and assignment.best.kind == "PE"
    }
    for label, energy in expected["required_assignments"].items():
        assert label in accepted
        assert abs(accepted[label] - float(energy)) <= float(expected["position_tolerance_eV"])


def test_c1s_recovery_is_not_artificially_controlled_by_global_prominence():
    # The weak C 1s is reference-guided. Once the global detector is below the
    # guided minimum floor, changing GUI prominence should not make the real
    # local feature disappear merely because its own slope inflated "noise".
    for prominence in (0.005, 0.002, 0.001):
        assignments = _run_reference_pipeline(prominence)
        accepted = {
            assignment.best.label: float(assignment.peak.energy)
            for assignment in assignments if assignment.best is not None and assignment.best.kind == "PE"
        }
        assert "C 1s" in accepted
        assert abs(accepted["C 1s"] - 284.0) <= 1.0
