import json
from pathlib import Path

from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import DetectedPeak, detect_peaks
from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces


DATASET = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "oxide_mixture_survey_700ev"


def _reference_assignments(*, charging: bool):
    parsed = parse_structured_txt(DATASET / "spectrum.txt")
    trace = region_to_traces(parsed.regions[0])[0]
    peaks = detect_peaks(trace["x"], trace["y"], prominence_fraction=0.005, min_distance_fraction=0.006)
    # The application treats 0--15 eV as the valence-band region.
    peaks = [peak for peak in peaks if peak.energy > 15.0]
    return match_peaks(
        peaks,
        energy_scale="Binding",
        photon_energy=700.0,
        tolerance_eV=5.0,
        elements={"Ti", "O", "Si", "Al"},
        include_auger=False,
        small_charging_possible=charging,
        sample_mode="Automatic (prefer solids)",
        alternatives=10,
    )


def _accepted(assignments):
    return {assignment.best.label: assignment.peak.energy for assignment in assignments if assignment.best is not None}


def test_reference_survey_metadata_and_header_are_consistent():
    metadata = json.loads((DATASET / "metadata.json").read_text(encoding="utf-8"))
    parsed = parse_structured_txt(DATASET / "spectrum.txt")
    trace = region_to_traces(parsed.regions[0])[0]
    assert metadata["photon_energy_eV"] == 700.0
    assert trace["energy_scale"] == "Binding"
    assert len(trace["x"]) == 1205


def test_charging_mode_recovers_ti_anchor_doublet_and_supporting_lines():
    expected = json.loads((DATASET / "expected.json").read_text(encoding="utf-8"))
    accepted = _accepted(_reference_assignments(charging=True))
    for label in expected["charging_on_required_assignments"]:
        assert label in accepted
        assert abs(accepted[label] - expected["expected_ti_peak_positions_eV"][label]) <= expected["position_tolerance_eV"]


def test_charging_off_does_not_speculate_shifted_ti_doublet():
    accepted = _accepted(_reference_assignments(charging=False))
    assert "Ti 2p3/2" not in accepted
    assert "Ti 2p1/2" not in accepted


def test_unresolved_al_and_si_2p_use_family_labels():
    accepted = _accepted(_reference_assignments(charging=True))
    assert "Al 2p" in accepted
    assert "Si 2p" in accepted
    assert not any(label.startswith("Al 2p1/") or label.startswith("Al 2p3/") for label in accepted)
    assert not any(label.startswith("Si 2p1/") or label.startswith("Si 2p3/") for label in accepted)


def test_isolated_weaker_ti_component_is_rejected_even_in_charging_mode():
    assignments = match_peaks(
        [DetectedPeak(index=0, energy=467.0, intensity=1.0, prominence=1.0)],
        energy_scale="Binding",
        photon_energy=700.0,
        tolerance_eV=5.0,
        elements={"Ti"},
        include_auger=False,
        small_charging_possible=True,
        sample_mode="Automatic (prefer solids)",
    )
    assert all(assignment.best is None for assignment in assignments)


def test_charging_assignments_survive_local_feature_refinement():
    """Regression for GUI path: refinement must not jump shifted Ti labels back to unshifted references."""
    from types import SimpleNamespace

    from maxiv_panda.signal_identification.guided_detection import _refine_assignments_to_local_features

    parsed = parse_structured_txt(DATASET / "spectrum.txt")
    trace = region_to_traces(parsed.regions[0])[0]
    payload = SimpleNamespace(x=trace["x"], y=trace["y"], energy_scale="Binding")
    peaks = detect_peaks(trace["x"], trace["y"], prominence_fraction=0.01, min_distance_fraction=0.006)
    peaks = [peak for peak in peaks if peak.energy > 15.0]

    assignments = match_peaks(
        peaks,
        energy_scale="Binding",
        photon_energy=700.0,
        tolerance_eV=2.0,
        elements={"Ti", "O", "Si", "Al"},
        include_auger=False,
        small_charging_possible=True,
        sample_mode="Automatic (prefer solids)",
        alternatives=10,
    )
    refined = _refine_assignments_to_local_features(assignments, payload, tolerance_eV=2.0)
    accepted = _accepted(refined)

    assert abs(accepted["Ti 2p3/2"] - 461.0) <= 0.6
    assert abs(accepted["Ti 2p1/2"] - 467.0) <= 0.6


def test_gui_identification_pipeline_differs_when_charging_is_enabled():
    """The same real spectrum must produce different accepted Ti labels for OFF and ON."""
    from types import SimpleNamespace

    from maxiv_panda.signal_identification.guided_detection import _refine_assignments_to_local_features

    parsed = parse_structured_txt(DATASET / "spectrum.txt")
    trace = region_to_traces(parsed.regions[0])[0]
    payload = SimpleNamespace(x=trace["x"], y=trace["y"], energy_scale="Binding")
    def run(charging: bool):
        peaks = detect_peaks(
            trace["x"], trace["y"], prominence_fraction=0.01,
            min_distance_fraction=(0.006 if charging else 0.012),
        )
        peaks = [peak for peak in peaks if peak.energy > 15.0]
        assignments = match_peaks(
            peaks,
            energy_scale="Binding",
            photon_energy=700.0,
            tolerance_eV=2.0,
            elements={"Ti", "O", "Si", "Al"},
            include_auger=False,
            small_charging_possible=charging,
            sample_mode="Automatic (prefer solids)",
            alternatives=10,
        )
        return _accepted(_refine_assignments_to_local_features(assignments, payload, tolerance_eV=2.0))

    off = run(False)
    on = run(True)
    assert "Ti 2p3/2" not in off and "Ti 2p1/2" not in off
    assert "Ti 2p3/2" in on and "Ti 2p1/2" in on
    assert on != off


def test_charging_mode_shifts_and_broadens_ti_auger_family_region():
    parsed = parse_structured_txt(DATASET / "spectrum.txt")
    trace = region_to_traces(parsed.regions[0])[0]
    peaks = detect_peaks(trace["x"], trace["y"], prominence_fraction=0.01, min_distance_fraction=0.006)
    peaks = [peak for peak in peaks if peak.energy > 15.0]

    def ti_lmm(charging: bool):
        assignments = match_peaks(
            peaks,
            energy_scale="Binding",
            photon_energy=700.0,
            tolerance_eV=2.0,
            elements={"Ti", "O", "Si", "Al"},
            include_auger=True,
            small_charging_possible=charging,
            sample_mode="Automatic (prefer solids)",
            alternatives=10,
        )
        return [a.best for a in assignments if a.best is not None and a.best.label == "Ti LMM"]

    off = ti_lmm(False)
    on = ti_lmm(True)
    assert off and on
    assert all(candidate.common_shift_eV is None for candidate in off)
    assert all(abs(candidate.common_shift_eV - 7.1) <= 0.3 for candidate in on)
    assert min(candidate.region_min for candidate in on) > min(candidate.region_min for candidate in off) + 6.0
    assert min(candidate.soft_region_min for candidate in on) < min(candidate.region_min for candidate in on) - 9.0
    assert all("broadened charging allowance" in candidate.reason for candidate in on)


def test_broad_auger_detector_uses_pe_anchor_shift_only_when_enabled():
    from types import SimpleNamespace

    from maxiv_panda.signal_identification.auger_detection import _broad_auger_assignments

    parsed = parse_structured_txt(DATASET / "spectrum.txt")
    trace = region_to_traces(parsed.regions[0])[0]
    payload = SimpleNamespace(x=trace["x"], y=trace["y"])
    pe_assignments = _reference_assignments(charging=True)

    off = _broad_auger_assignments(
        pe_assignments,
        payload,
        energy_scale="Binding",
        photon_energy=700.0,
        selected_elements={"Ti", "O", "Si", "Al"},
        small_charging_possible=False,
    )
    on = _broad_auger_assignments(
        pe_assignments,
        payload,
        energy_scale="Binding",
        photon_energy=700.0,
        selected_elements={"Ti", "O", "Si", "Al"},
        small_charging_possible=True,
    )
    off_ti = next(a.best for a in off if a.best is not None and a.best.label == "Ti LMM")
    on_ti = next(a.best for a in on if a.best is not None and a.best.label == "Ti LMM")
    assert off_ti.common_shift_eV is None
    assert abs(on_ti.common_shift_eV - 7.1) <= 0.3
    assert on_ti.auger_subregions != off_ti.auger_subregions
    assert "shifted by PE anchor" in on_ti.reason
    assert all((region.tail_hi - region.tail_lo) >= 20.0 for region in on_ti.auger_subregions)
