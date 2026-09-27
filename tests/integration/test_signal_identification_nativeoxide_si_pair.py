from pathlib import Path
from types import SimpleNamespace

from maxiv_panda.signal_identification.element_consistency import apply_element_consistency
from maxiv_panda.signal_identification.guided_detection import (
    _expected_core_windows,
    _refine_assignments_to_local_features,
)
from maxiv_panda.signal_identification.matcher import match_peaks
from maxiv_panda.signal_identification.peak_detection import detect_peaks, detect_reference_guided_peaks
from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces


def test_reference_guided_duplicates_collapse_before_si_pair_consistency():
    path = Path('/mnt/data/nativeoxide_0006.txt')
    if not path.exists():
        return
    trace = region_to_traces(parse_structured_txt(path).regions[0])[0]
    x, y = trace['x'], trace['y']
    payload = SimpleNamespace(x=x, y=y, energy_scale='Binding')
    elements = {'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Si', 'O', 'C'}

    detected = detect_peaks(x, y, prominence_fraction=0.005, min_distance_fraction=0.012)
    windows = _expected_core_windows(
        energy_scale='Binding', photon_energy=1215.037575,
        selected_elements=elements, tolerance_eV=5.0,
        sample_mode='Automatic (prefer solids)', vb_cutoff=15.0,
    )
    guided = detect_reference_guided_peaks(
        x, y, expected_windows=windows, existing_peaks=detected,
        min_feature_fraction=0.005,
    )
    peaks = detected + [
        peak for peak in guided
        if all(abs(peak.energy - existing.energy) > 0.4 for existing in detected)
    ]
    assignments = match_peaks(
        peaks, energy_scale='Binding', photon_energy=1215.037575,
        tolerance_eV=5.0, elements=elements, include_auger=True,
        small_charging_possible=False, sample_mode='Automatic (prefer solids)',
        alternatives=10,
    )
    refined = _refine_assignments_to_local_features(assignments, payload, tolerance_eV=5.0)

    # The raw detector and a guided window both converge onto the same Si 2p
    # maximum.  After refinement there must be one experimental row, not one
    # row per reference window.
    near_102 = [a for a in refined if 101.5 <= a.peak.energy <= 103.0]
    assert len(near_102) == 1
    assert {'Si 2p', 'Co 3s'} <= {candidate.label for candidate in near_102[0].candidates}

    consistent = apply_element_consistency(
        refined, payload, selected_elements=elements, energy_scale='Binding',
        photon_energy=1215.037575, sample_mode='Automatic (prefer solids)',
    )
    labels = {a.best.label for a in consistent if a.best is not None}
    assert {'Si 2p', 'Si 2s'} <= labels
