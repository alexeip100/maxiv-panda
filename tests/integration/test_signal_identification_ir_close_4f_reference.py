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


DATA = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "ir_700ev_close_4f_doublet.txt"
PHOTON = 700.0
ELEMENTS = {"Ir", "B", "O"}
TOLERANCE = 5.0


def _run():
    trace = region_to_traces(parse_structured_txt(DATA).regions[0])[0]
    payload = SimpleNamespace(x=trace["x"], y=trace["y"], energy_scale="Binding")
    detected = [
        peak for peak in detect_peaks(
            trace["x"], trace["y"], prominence_fraction=0.005, min_distance_fraction=0.012,
        ) if peak.energy > 15.0
    ]
    windows = _expected_core_windows(
        energy_scale="Binding", photon_energy=PHOTON, selected_elements=ELEMENTS,
        tolerance_eV=TOLERANCE, sample_mode="solid", vb_cutoff=15.0,
    )
    guided = detect_reference_guided_peaks(
        trace["x"], trace["y"], expected_windows=windows, existing_peaks=detected,
        min_feature_fraction=0.005,
    )
    peaks = list(detected) + [
        peak for peak in guided
        if all(abs(float(peak.energy) - float(existing.energy)) > 0.4 for existing in detected)
    ]

    def assign(current):
        rows = match_peaks(
            current, energy_scale="Binding", photon_energy=PHOTON, tolerance_eV=TOLERANCE,
            elements=ELEMENTS, include_auger=True, include_second_order=False,
            small_charging_possible=False, sample_mode="solid", alternatives=10,
        )
        return _refine_assignments_to_local_features(rows, payload, tolerance_eV=TOLERANCE)

    assignments = assign(peaks)
    companions = _companion_assisted_peaks(
        assignments, payload, energy_scale="Binding", photon_energy=PHOTON, sample_mode="solid",
    )
    new = [
        peak for peak in companions
        if all(abs(float(peak.energy) - float(existing.energy)) > 0.4 for existing in peaks)
    ]
    if new:
        peaks.extend(new)
        assignments = assign(peaks)
    return apply_element_consistency(
        assignments, payload, selected_elements=ELEMENTS, energy_scale="Binding",
        photon_energy=PHOTON, sample_mode="solid",
    )


def test_close_ir_4f_doublet_is_recovered_from_strong_component_geometry():
    assignments = _run()
    accepted = {
        row.best.label: float(row.peak.energy)
        for row in assignments if row.best is not None and row.best.kind == "PE"
    }
    assert abs(accepted["Ir 4f7/2"] - 60.5) <= 0.6
    assert abs(accepted["Ir 4f5/2"] - 63.0) <= 0.6
    assert accepted["Ir 4f5/2"] > accepted["Ir 4f7/2"]
    assert abs(accepted["Ir 5p3/2"] - 47.0) <= 0.8
    assert "Ir 5p1/2" not in accepted
