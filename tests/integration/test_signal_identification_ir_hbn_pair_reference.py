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
from maxiv_panda.signal_identification.auger_detection import _broad_auger_assignments, _build_family_priors

DATASET = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "ir_hbn_pair_700ev"
ELEMENTS = {"Ir", "N", "B", "C", "O"}
PHOTON = 700.0
TOLERANCE = 5.0


def _run(name: str):
    trace = region_to_traces(parse_structured_txt(DATASET / name).regions[0])[0]
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
    assignments = apply_element_consistency(
        assignments, payload, selected_elements=ELEMENTS, energy_scale="Binding",
        photon_energy=PHOTON, sample_mode="solid",
    )
    auger = _broad_auger_assignments(
        assignments, payload, energy_scale="Binding", photon_energy=PHOTON,
        selected_elements=ELEMENTS, small_charging_possible=False,
    )
    return assignments, auger


def test_weak_and_strong_ir_hbn_surveys_keep_c1s_and_o1s():
    for name in ("strong.txt", "weak.txt"):
        assignments, _auger = _run(name)
        accepted = {
            row.best.label: float(row.peak.energy)
            for row in assignments if row.best is not None and row.best.kind == "PE"
        }
        assert abs(accepted["C 1s"] - 284.0) <= 1.0
        assert abs(accepted["O 1s"] - 531.0) <= 1.0


def test_ir_auger_is_photon_accessible_and_cluster_local_in_both_surveys():
    for name in ("strong.txt", "weak.txt"):
        _assignments, auger = _run(name)
        labels = [row.best.label for row in auger if row.best is not None]
        assert "Ir MMN" not in labels
        ir_noo = next(row.best for row in auger if row.best is not None and row.best.label == "Ir NOO")
        assert len(ir_noo.auger_subregions) == 2
        centers = sorted(float(region.peak_energy) for region in ir_noo.auger_subregions)
        assert 120.0 <= centers[0] <= 140.0
        assert 485.0 <= centers[1] <= 505.0
        assert all((region.tail_hi - region.tail_lo) < 100.0 for region in ir_noo.auger_subregions)


def test_ir_mmn_prior_is_disabled_below_ir_m_shell_threshold():
    priors = _build_family_priors(
        supported={"Ir"}, energy_scale="Binding", photon_energy=PHOTON,
        charging_shifts={}, allow_eadl_only_elements={"Ir"},
    )
    assert ("Ir", "MMN") not in priors
    assert ("Ir", "NOO") in priors


def test_ir_4p_strong_component_survives_when_weak_partner_is_not_measurable():
    """Ir 4p3/2 is a real peak; missing broad/weak 4p1/2 must not erase it."""
    for name in ("strong.txt", "weak.txt", "ir4p_anchor.txt"):
        assignments, _auger = _run(name)
        accepted = {
            row.best.label: float(row.peak.energy)
            for row in assignments if row.best is not None and row.best.kind == "PE"
        }
        assert "Ir 4p3/2" in accepted
        assert abs(accepted["Ir 4p3/2"] - 494.0) <= 1.5
        # Do not manufacture the much weaker/broader partner merely to complete
        # the family.  It should be labelled only when independent local evidence exists.
        assert "Ir 4p1/2" not in accepted


def test_separately_resolved_ir_5p3_2_can_survive_without_obscured_5p1_2():
    assignments, _auger = _run("ir4p_anchor.txt")
    labels = {row.best.label for row in assignments if row.best is not None}
    assert "Ir 5p3/2" in labels
    assert "Ir 5p1/2" not in labels
