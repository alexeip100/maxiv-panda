from pathlib import Path
from types import SimpleNamespace

from maxiv_panda.signal_identification.auger_detection import _broad_auger_assignments
from maxiv_panda.signal_identification.element_consistency import apply_element_consistency
from maxiv_panda.signal_identification.guided_detection import (
    _companion_assisted_peaks,
    _expected_core_windows,
    _refine_assignments_to_local_features,
)
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import detect_peaks, detect_reference_guided_peaks
from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces

_DATA = Path(__file__).resolve().parents[1] / "data" / "signal_identification"
_ELEMENTS = {"Na", "F", "O", "C", "N", "S"}
_MODE = "Automatic (prefer solids)"


def _identify(path: Path):
    parsed = parse_structured_txt(path)
    trace = region_to_traces(parsed.regions[0])[0]
    payload = SimpleNamespace(x=trace["x"], y=trace["y"], energy_scale=trace["energy_scale"])
    photon = 1200.0
    tolerance = 5.0
    prominence = 0.005
    vb_cutoff = 15.0

    detected = detect_peaks(payload.x, payload.y, prominence_fraction=prominence, min_distance_fraction=0.012)
    detected = [peak for peak in detected if not (0.0 <= float(peak.energy) <= vb_cutoff)]
    windows = _expected_core_windows(
        energy_scale="Binding", photon_energy=photon, selected_elements=_ELEMENTS,
        tolerance_eV=tolerance, sample_mode=_MODE, vb_cutoff=vb_cutoff,
    )
    guided = detect_reference_guided_peaks(
        payload.x, payload.y, expected_windows=windows, existing_peaks=detected,
        min_feature_fraction=prominence,
    )
    combined = list(detected) + [
        peak for peak in guided if all(abs(float(peak.energy) - float(old.energy)) > 0.4 for old in detected)
    ]
    combined.sort(key=lambda peak: float(peak.energy))

    assignments = match_peaks(
        combined, energy_scale="Binding", photon_energy=photon, tolerance_eV=tolerance,
        elements=_ELEMENTS, include_auger=True, include_second_order=False,
        small_charging_possible=False, sample_mode=_MODE,
    )
    assignments = _refine_assignments_to_local_features(assignments, payload, tolerance_eV=tolerance)
    companions = _companion_assisted_peaks(
        assignments, payload, energy_scale="Binding", photon_energy=photon, sample_mode=_MODE,
    )
    new_companions = [
        peak for peak in companions
        if all(abs(float(peak.energy) - float(old.energy)) > 0.4 for old in combined)
    ]
    if new_companions:
        combined.extend(new_companions)
        combined.sort(key=lambda peak: float(peak.energy))
        assignments = match_peaks(
            combined, energy_scale="Binding", photon_energy=photon, tolerance_eV=tolerance,
            elements=_ELEMENTS, include_auger=True, include_second_order=False,
            small_charging_possible=False, sample_mode=_MODE,
        )
        assignments = _refine_assignments_to_local_features(assignments, payload, tolerance_eV=tolerance)

    assignments = apply_element_consistency(
        assignments, payload, selected_elements=_ELEMENTS,
        energy_scale="Binding", photon_energy=photon, sample_mode=_MODE,
    )
    broad_auger = _broad_auger_assignments(
        assignments, payload, energy_scale="Binding", photon_energy=photon,
        selected_elements=_ELEMENTS, small_charging_possible=False,
    )
    return assignments, broad_auger


def _accepted(assignments, element):
    return {
        a.best.label: float(a.peak.energy)
        for a in assignments
        if a.best is not None and a.best.kind == "PE" and a.best.confident and a.best.element == element
    }


def test_0021_recovers_na1s_and_s2s_consistently():
    assignments, _auger = _identify(_DATA / "family_auger_0021_1200eV.txt")
    na = _accepted(assignments, "Na")
    sulfur = _accepted(assignments, "S")
    assert {"Na 1s", "Na 2s", "Na 2p"} <= set(na)
    assert abs(na["Na 1s"] - 1070.5) <= 0.5
    assert {"S 2p", "S 2s"} <= set(sulfur)
    assert 231.5 <= sulfur["S 2s"] <= 234.0


def test_0023_keeps_good_family_identification():
    assignments, _auger = _identify(_DATA / "family_auger_0023_1200eV.txt")
    na = _accepted(assignments, "Na")
    sulfur = _accepted(assignments, "S")
    assert {"Na 1s", "Na 2s", "Na 2p"} <= set(na)
    assert {"S 2p", "S 2s"} <= set(sulfur)


def test_0021_na_kll_does_not_borrow_the_s2p_peak():
    _assignments, auger = _identify(_DATA / "family_auger_0021_1200eV.txt")
    na_kll = [a for a in auger if a.best is not None and a.best.element == "Na" and a.best.line == "KLL"]
    assert na_kll
    regions = [region for a in na_kll for region in a.best.auger_subregions]
    assert any(195.0 <= region.peak_energy <= 260.0 for region in regions)
    assert not any(160.0 <= region.peak_energy <= 188.0 for region in regions)


def test_0022_and_0024_keep_family_identification_and_avoid_s2p_as_na_kll():
    for filename in ("family_auger_0022_1200eV.txt", "family_auger_0024_1200eV.txt"):
        assignments, auger = _identify(_DATA / filename)
        na = _accepted(assignments, "Na")
        sulfur = _accepted(assignments, "S")
        assert {"Na 1s", "Na 2s", "Na 2p"} <= set(na)
        assert {"S 2p", "S 2s"} <= set(sulfur)
        na_kll = [a for a in auger if a.best is not None and a.best.element == "Na" and a.best.line == "KLL"]
        assert na_kll
        regions = [region for a in na_kll for region in a.best.auger_subregions]
        assert any(195.0 <= region.peak_energy <= 260.0 for region in regions)
        assert not any(160.0 <= region.peak_energy <= 188.0 for region in regions)
