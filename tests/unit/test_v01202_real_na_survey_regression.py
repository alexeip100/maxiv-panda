from pathlib import Path
from types import SimpleNamespace

from maxiv_panda.signal_identification.element_consistency import apply_element_consistency
from maxiv_panda.signal_identification.guided_detection import (
    _companion_assisted_peaks,
    _expected_core_windows,
    _refine_assignments_to_local_features,
)
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import (
    detect_peaks,
    detect_reference_guided_peaks,
)
from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces


_DATA = Path(__file__).resolve().parents[1] / "data" / "signal_identification"
_ELEMENTS = {"Na", "C", "O", "Si"}
_SAMPLE_MODE = "Automatic (prefer solids)"


def _identify_real_txt(path: Path, photon_energy: float):
    """Run the non-GUI part of PANDA's normal signal-identification pipeline."""
    parsed = parse_structured_txt(path)
    assert len(parsed.regions) == 1
    trace = region_to_traces(parsed.regions[0])[0]
    payload = SimpleNamespace(
        x=trace["x"],
        y=trace["y"],
        energy_scale=trace["energy_scale"],
    )

    tolerance_eV = 5.0
    prominence_fraction = 0.005
    vb_cutoff = 15.0

    detected = detect_peaks(
        payload.x,
        payload.y,
        prominence_fraction=prominence_fraction,
        min_distance_fraction=0.012,
    )
    detected = [
        peak for peak in detected
        if not (0.0 <= float(peak.energy) <= vb_cutoff)
    ]

    expected_windows = _expected_core_windows(
        energy_scale="Binding",
        photon_energy=photon_energy,
        selected_elements=_ELEMENTS,
        tolerance_eV=tolerance_eV,
        sample_mode=_SAMPLE_MODE,
        vb_cutoff=vb_cutoff,
    )
    guided = detect_reference_guided_peaks(
        payload.x,
        payload.y,
        expected_windows=expected_windows,
        existing_peaks=detected,
        min_feature_fraction=prominence_fraction,
    )
    combined = list(detected) + [
        peak for peak in guided
        if all(abs(float(peak.energy) - float(old.energy)) > 0.4 for old in detected)
    ]
    combined.sort(key=lambda peak: float(peak.energy))

    assignments = match_peaks(
        combined,
        energy_scale="Binding",
        photon_energy=photon_energy,
        tolerance_eV=tolerance_eV,
        elements=_ELEMENTS,
        include_auger=True,
        include_second_order=False,
        small_charging_possible=False,
        sample_mode=_SAMPLE_MODE,
    )
    assignments = _refine_assignments_to_local_features(
        assignments,
        payload,
        tolerance_eV=tolerance_eV,
    )

    companions = _companion_assisted_peaks(
        assignments,
        payload,
        energy_scale="Binding",
        photon_energy=photon_energy,
        sample_mode=_SAMPLE_MODE,
    )
    new_companions = [
        peak for peak in companions
        if all(abs(float(peak.energy) - float(old.energy)) > 0.4 for old in combined)
    ]
    if new_companions:
        combined.extend(new_companions)
        combined.sort(key=lambda peak: float(peak.energy))
        assignments = match_peaks(
            combined,
            energy_scale="Binding",
            photon_energy=photon_energy,
            tolerance_eV=tolerance_eV,
            elements=_ELEMENTS,
            include_auger=True,
            include_second_order=False,
            small_charging_possible=False,
            sample_mode=_SAMPLE_MODE,
        )
        assignments = _refine_assignments_to_local_features(
            assignments,
            payload,
            tolerance_eV=tolerance_eV,
        )

    return apply_element_consistency(
        assignments,
        payload,
        selected_elements=_ELEMENTS,
        energy_scale="Binding",
        photon_energy=photon_energy,
        sample_mode=_SAMPLE_MODE,
    )


def _accepted_na(assignments):
    return {
        assignment.best.label: float(assignment.peak.energy)
        for assignment in assignments
        if assignment.best is not None
        and assignment.best.kind == "PE"
        and assignment.best.element == "Na"
        and assignment.best.confident
    }


def test_real_1200_ev_na_survey_recovers_na_1s_family():
    assignments = _identify_real_txt(_DATA / "na_survey_1200eV.txt", 1200.0)
    sodium = _accepted_na(assignments)
    assert "Na 2p" in sodium
    assert "Na 2s" in sodium
    assert "Na 1s" in sodium
    assert abs(sodium["Na 1s"] - 1071.0) <= 0.5


def test_real_1160_ev_na_survey_keeps_na_1s_family():
    assignments = _identify_real_txt(_DATA / "na_survey_1160eV.txt", 1160.0)
    sodium = _accepted_na(assignments)
    assert "Na 2p" in sodium
    assert "Na 2s" in sodium
    assert "Na 1s" in sodium
    assert abs(sodium["Na 1s"] - 1071.0) <= 0.5
