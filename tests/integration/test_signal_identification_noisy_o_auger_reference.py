from pathlib import Path
from types import SimpleNamespace

from maxiv_panda.signal_identification.auger_detection import _broad_auger_assignments
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import detect_peaks
from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces


DATASET = Path(__file__).parents[1] / "data" / "reference" / "signal_identification" / "organic_au_survey_1300ev"


def test_noisy_organic_au_survey_recovers_measured_o_kll():
    parsed = parse_structured_txt(DATASET / "spectrum.txt")
    trace = region_to_traces(parsed.regions[0])[0]
    peaks = detect_peaks(trace["x"], trace["y"], prominence_fraction=0.005, min_distance_fraction=0.012)
    peaks = [peak for peak in peaks if peak.energy > 15.0]
    pe_assignments = match_peaks(
        peaks,
        energy_scale="Binding",
        photon_energy=1300.0,
        tolerance_eV=2.0,
        elements={"Au", "C", "O"},
        include_auger=False,
        small_charging_possible=False,
        sample_mode="Automatic (prefer solids)",
        alternatives=10,
    )
    assignments = _broad_auger_assignments(
        pe_assignments,
        SimpleNamespace(x=trace["x"], y=trace["y"]),
        energy_scale="Binding",
        photon_energy=1300.0,
        selected_elements={"Au", "C", "O"},
        small_charging_possible=False,
    )
    oxygen = next(a.best for a in assignments if a.best is not None and a.best.label == "O KLL")
    assert len(oxygen.auger_subregions) == 1
    region = oxygen.auger_subregions[0]
    assert 789.0 <= region.peak_energy <= 798.0
    assert region.core_lo <= region.peak_energy <= region.core_hi
    assert region.tail_lo <= 790.0
    assert region.tail_hi >= 815.0
