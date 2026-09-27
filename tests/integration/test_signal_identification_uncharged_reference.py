import json
from pathlib import Path

from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import detect_peaks
from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces


DATASET = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "graphene_ir_survey_750ev"


def _run(*, charging: bool):
    parsed = parse_structured_txt(DATASET / "spectrum.txt")
    trace = region_to_traces(parsed.regions[0])[0]
    peaks = detect_peaks(
        trace["x"], trace["y"], prominence_fraction=0.01,
        min_distance_fraction=(0.006 if charging else 0.012),
    )
    peaks = [peak for peak in peaks if peak.energy > 15.0]
    return match_peaks(
        peaks,
        energy_scale="Binding",
        photon_energy=750.0,
        tolerance_eV=2.0,
        elements={"Ir", "C"},
        include_auger=False,
        small_charging_possible=charging,
        sample_mode="Automatic (prefer solids)",
        alternatives=10,
    )


def _accepted(assignments):
    return {assignment.best.label: assignment.best for assignment in assignments if assignment.best is not None}


def test_uncharged_reference_metadata_declares_no_charging():
    metadata = json.loads((DATASET / "metadata.json").read_text(encoding="utf-8"))
    expected = json.loads((DATASET / "expected.json").read_text(encoding="utf-8"))
    assert metadata["photon_energy_eV"] == 750.0
    assert metadata["expected_elements"] == ["Ir", "C"]
    assert expected["charging_shift_expected"] is False


def test_charging_mode_does_not_override_valid_unshifted_ir_anchor():
    off = _accepted(_run(charging=False))
    on = _accepted(_run(charging=True))

    for label in ("Ir 4d5/2", "Ir 4d3/2", "C 1s"):
        assert label in off
        assert label in on

    assert not any("small-charging mode" in candidate.reason for candidate in on.values())
    assert not any(
        candidate.element == "Ir" and candidate.common_shift_eV not in (None, 0.0)
        for candidate in on.values()
    )


def test_charging_fallback_preserves_uncharged_ir_assignments():
    off = _accepted(_run(charging=False))
    on = _accepted(_run(charging=True))
    for label in ("Ir 4d5/2", "Ir 4d3/2", "Ir 5s", "C 1s"):
        assert label in off and label in on
        assert abs(off[label].expected_energy - on[label].expected_energy) < 1e-9
