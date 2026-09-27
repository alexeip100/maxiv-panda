import json
from pathlib import Path
from types import SimpleNamespace

from maxiv_panda.signal_identification.auger_detection import _broad_auger_assignments
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import detect_peaks
from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces


DATASET = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "co_oxide_au_survey_1000ev"


def _auger_assignments():
    metadata = json.loads((DATASET / "metadata.json").read_text(encoding="utf-8"))
    parsed = parse_structured_txt(DATASET / "spectrum.txt")
    trace = region_to_traces(parsed.regions[0])[0]
    peaks = detect_peaks(trace["x"], trace["y"], prominence_fraction=0.005, min_distance_fraction=0.012)
    peaks = [peak for peak in peaks if peak.energy > 15.0]
    pe_assignments = match_peaks(
        peaks,
        energy_scale="Binding",
        photon_energy=metadata["photon_energy_eV"],
        tolerance_eV=2.0,
        elements=set(metadata["expected_elements"]),
        include_auger=False,
        small_charging_possible=False,
        sample_mode="Automatic (prefer solids)",
        alternatives=10,
    )
    payload = SimpleNamespace(x=trace["x"], y=trace["y"])
    return _broad_auger_assignments(
        pe_assignments,
        payload,
        energy_scale="Binding",
        photon_energy=metadata["photon_energy_eV"],
        selected_elements=set(metadata["expected_elements"]),
        small_charging_possible=False,
    )


def test_co_oxide_reference_shows_only_evidence_gated_families():
    assignments = _auger_assignments()
    labels = [assignment.best.label for assignment in assignments if assignment.best is not None]
    assert labels.count("O KLL") == 1
    assert labels.count("Co LMM") == 1
    assert not any(label.startswith("Au ") for label in labels)


def test_co_lmm_has_three_distinct_supported_subregions():
    assignments = _auger_assignments()
    candidate = next(
        assignment.best for assignment in assignments
        if assignment.best is not None and assignment.best.label == "Co LMM"
    )
    assert len(candidate.auger_subregions) == 3
    expected_ranges = [(204, 238), (270, 310), (337, 366)]
    for expected_lo, expected_hi in expected_ranges:
        assert any(
            region.tail_hi >= expected_lo and region.tail_lo <= expected_hi
            for region in candidate.auger_subregions
        )
    assert all(region.tail_hi - region.tail_lo >= 38.0 for region in candidate.auger_subregions)
    assert all(
        region.tail_lo < region.core_lo <= region.peak_energy <= region.core_hi < region.tail_hi
        for region in candidate.auger_subregions
    )


def test_o_kll_region_covers_strong_low_binding_energy_feature():
    assignments = _auger_assignments()
    candidate = next(
        assignment.best for assignment in assignments
        if assignment.best is not None and assignment.best.label == "O KLL"
    )
    assert len(candidate.auger_subregions) == 1
    region = candidate.auger_subregions[0]
    assert 480.0 <= region.peak_energy <= 492.0
    assert region.core_lo <= 488.0 <= region.core_hi
    assert region.tail_lo <= 475.0
    assert region.tail_hi >= 505.0
    assert region.tail_lo < region.core_lo < region.core_hi < region.tail_hi
    assert "EADL" in candidate.reason
