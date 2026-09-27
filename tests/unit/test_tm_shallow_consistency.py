from types import SimpleNamespace

import numpy as np

from maxiv_panda.signal_identification.element_consistency import (
    _recover_transition_metal_shallow_families,
    _resolve_same_peak_conflicts,
)
from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
from maxiv_panda.signal_identification.peak_detection import DetectedPeak


def _assignment(energy, element, line, expected, *, reliability=85, prominence=1000.0):
    candidate = SignalCandidate(
        element=element,
        line=line,
        kind="PE",
        expected_energy=float(expected),
        delta_e=float(energy) - float(expected),
        score=0.10,
        confident=True,
        reliability=int(reliability),
    )
    peak = DetectedPeak(0, float(energy), 2000.0, float(prominence))
    return PeakAssignment(peak=peak, candidates=[candidate])


def test_tm_3p_conflict_prefers_element_with_coherent_2p_over_shallow_only_support():
    """Deep 2p evidence must dominate an ambiguous neighbouring-metal 3p match."""
    assignments = [
        # At 51 eV Fe 3p is closer to its elemental reference than Mn 3p.
        _assignment(51.0, "Mn", "3p", 47.0, reliability=80, prominence=900.0),
        _assignment(51.0, "Fe", "3p", 52.6, reliability=92, prominence=900.0),
        # Mn, however, is independently established by a complete 2p family.
        _assignment(642.0, "Mn", "2p3/2", 641.6, reliability=90, prominence=5000.0),
        _assignment(654.0, "Mn", "2p1/2", 652.7, reliability=88, prominence=3200.0),
        # Give Fe a shallow companion so this is not a trivial companion-count win.
        _assignment(91.0, "Fe", "3s", 91.0, reliability=92, prominence=700.0),
    ]

    resolved = _resolve_same_peak_conflicts(assignments, photon_energy=1215.0)
    winners = [
        assignment.best.label
        for assignment in resolved
        if assignment.best is not None and abs(float(assignment.peak.energy) - 51.0) < 0.1
    ]
    assert winners == ["Mn 3p"]


def test_missing_2p_does_not_automatically_reject_an_uncontested_tm_3p():
    """The 2p prior is asymmetric: absence removes a bonus, not the assignment."""
    assignment = _assignment(52.5, "Fe", "3p", 52.6, reliability=90, prominence=850.0)
    resolved = _resolve_same_peak_conflicts([assignment], photon_energy=1215.0)
    assert resolved[0].best is not None
    assert resolved[0].best.label == "Fe 3p"


def test_established_mn_2p_recovers_measured_mn_3p():
    """A measured shallow feature is actively sought after Mn is established by 2p."""
    x = np.arange(35.0, 680.0, 0.5)
    y = np.full_like(x, 1000.0)
    for center, amplitude, width in (
        (49.0, 700.0, 1.1),
        (642.0, 4500.0, 1.4),
        (654.0, 2800.0, 1.4),
    ):
        y += amplitude * np.exp(-0.5 * ((x - center) / width) ** 2)
    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")

    assignments = [
        _assignment(642.0, "Mn", "2p3/2", 641.6, reliability=90, prominence=4500.0),
        _assignment(654.0, "Mn", "2p1/2", 652.7, reliability=88, prominence=2800.0),
    ]
    recovered = _recover_transition_metal_shallow_families(
        assignments,
        payload,
        selected_elements={"Mn", "Fe"},
        energy_scale="Binding",
        photon_energy=1215.0,
        sample_mode="Automatic (prefer solids)",
    )
    mn_3p = [
        a for a in recovered
        if a.best is not None and a.best.label == "Mn 3p"
    ]
    assert len(mn_3p) == 1
    assert abs(float(mn_3p[0].peak.energy) - 49.0) <= 1.0


def test_tm_3p_conflict_with_two_established_elements_uses_deep_shift_alignment():
    """When Mn and Fe are both present, 49 eV follows the better deep-core shift."""
    x = np.arange(35.0, 735.0, 0.5)
    y = np.full_like(x, 1000.0)
    for center, amplitude, width in (
        (49.0, 1000.0, 1.1),
        (642.0, 4500.0, 1.4),
        (654.0, 2800.0, 1.4),
        (707.0, 3500.0, 1.4),
        (720.0, 2200.0, 1.4),
    ):
        y += amplitude * np.exp(-0.5 * ((x - center) / width) ** 2)
    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")

    assignments = [
        _assignment(49.0, "Mn", "3p", 47.0, reliability=72, prominence=1000.0),
        _assignment(642.0, "Mn", "2p3/2", 641.6, reliability=90, prominence=4500.0),
        _assignment(654.0, "Mn", "2p1/2", 652.7, reliability=88, prominence=2800.0),
        _assignment(707.0, "Fe", "2p3/2", 707.2, reliability=90, prominence=3500.0),
        _assignment(720.0, "Fe", "2p1/2", 720.4, reliability=88, prominence=2200.0),
    ]

    recovered = _recover_transition_metal_shallow_families(
        assignments,
        payload,
        selected_elements={"Mn", "Fe"},
        energy_scale="Binding",
        photon_energy=1215.0,
        sample_mode="Automatic (prefer solids)",
    )
    near_49 = [
        a for a in recovered
        if a.best is not None and abs(float(a.peak.energy) - 49.0) <= 0.8
    ]
    assert len(near_49) == 1
    assert near_49[0].best.label == "Mn 3p"


def test_tm_2p_partner_reuses_already_detected_sharp_peak_before_broad_search():
    """A sharp Ni 2p1/2 peak already detected at the correct splitting must survive."""
    from maxiv_panda.signal_identification.element_consistency import _recover_transition_metal_2p

    x = np.arange(835.0, 886.0, 0.5)
    y = np.full_like(x, 1000.0)
    y += 1700.0 * np.exp(-0.5 * ((x - 858.5) / 1.2) ** 2)
    # Deliberately sharp weaker partner: broad 4 eV smoothing can attenuate it.
    y += 900.0 * np.exp(-0.5 * ((x - 876.0) / 0.45) ** 2)
    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")

    assignments = [
        _assignment(858.5, "Ni", "2p3/2", 855.4, reliability=84, prominence=500.0),
        PeakAssignment(
            peak=DetectedPeak(0, 876.0, 1900.0, 700.0),
            candidates=[],
        ),
    ]

    recovered = _recover_transition_metal_2p(
        assignments,
        payload,
        selected_elements={"Ni"},
        energy_scale="Binding",
        photon_energy=1215.0,
        sample_mode="Automatic (prefer solids)",
    )
    ni = {
        a.best.line: float(a.peak.energy)
        for a in recovered
        if a.best is not None and a.best.element == "Ni" and a.best.line.startswith("2p")
    }
    assert abs(ni["2p3/2"] - 858.5) <= 0.6
    assert abs(ni["2p1/2"] - 876.0) <= 0.6


def test_relative_2p_intensity_breaks_close_tm_3p_tie_softly():
    """With equally good energy alignment, cleaner/stronger 2p evidence may break the tie."""
    from maxiv_panda.signal_identification.element_consistency import _prefer_tm_shallow_assignment

    mn3p = _assignment(50.0, "Mn", "3p", 47.0, reliability=85, prominence=900.0)
    fe3p = _assignment(50.0, "Fe", "3p", 52.6, reliability=85, prominence=900.0)
    assignments = [
        mn3p, fe3p,
        # Mn deep-core shift = +3.0 eV -> predicted Mn 3p at 50.0 eV.
        _assignment(644.6, "Mn", "2p3/2", 641.6, reliability=92, prominence=6500.0),
        _assignment(655.7, "Mn", "2p1/2", 652.7, reliability=90, prominence=3900.0),
        # Fe deep-core shift = -2.6 eV -> predicted Fe 3p at 50.0 eV.
        # Same-quality doublet but much weaker measured prominence.
        _assignment(704.6, "Fe", "2p3/2", 707.2, reliability=92, prominence=1300.0),
        _assignment(717.75, "Fe", "2p1/2", 720.35, reliability=90, prominence=780.0),
    ]
    winner = _prefer_tm_shallow_assignment(
        fe3p, mn3p, assignments,
        energy_scale="Binding", photon_energy=1215.0,
        sample_mode="Automatic (prefer solids)",
    )
    assert winner.best is not None
    assert winner.best.label == "Mn 3p"


def test_2p_intensity_cannot_override_clearly_better_shallow_energy_match():
    """Even a very large 2p intensity advantage remains secondary to energy/shift agreement."""
    from maxiv_panda.signal_identification.element_consistency import _prefer_tm_shallow_assignment

    mn3p = _assignment(49.0, "Mn", "3p", 47.0, reliability=86, prominence=900.0)
    fe3p = _assignment(49.0, "Fe", "3p", 52.6, reliability=86, prominence=900.0)
    assignments = [
        mn3p, fe3p,
        # Mn shift +2 -> predicted 49 eV (excellent alignment), but weak 2p.
        _assignment(643.6, "Mn", "2p3/2", 641.6, reliability=90, prominence=700.0),
        _assignment(654.7, "Mn", "2p1/2", 652.7, reliability=88, prominence=420.0),
        # Fe shift 0 -> predicted 52.6 eV, but enormous clean 2p signal.
        _assignment(707.2, "Fe", "2p3/2", 707.2, reliability=94, prominence=25000.0),
        _assignment(720.35, "Fe", "2p1/2", 720.35, reliability=92, prominence=15000.0),
    ]
    winner = _prefer_tm_shallow_assignment(
        fe3p, mn3p, assignments,
        energy_scale="Binding", photon_energy=1215.0,
        sample_mode="Automatic (prefer solids)",
    )
    assert winner.best is not None
    assert winner.best.label == "Mn 3p"


def test_implausible_2p_component_ratio_downweights_intensity_prior():
    """A likely masked/distorted 2p family should contribute little intensity evidence."""
    from maxiv_panda.signal_identification.element_consistency import _tm_2p_intensity_evidence

    assignments = [
        _assignment(707.2, "Fe", "2p3/2", 707.2, reliability=90, prominence=10000.0),
        # Coherent position but extremely tiny partner -> suspicious/masked family.
        _assignment(720.35, "Fe", "2p1/2", 720.35, reliability=90, prominence=100.0),
    ]
    strength, confidence = _tm_2p_intensity_evidence(
        assignments, "Fe", photon_energy=1215.0, energy_scale="Binding"
    )
    assert strength is not None and strength > 0.0
    assert confidence < 0.4
