from maxiv_panda.signal_identification.element_consistency import (
    _collapse_unbalanced_resolved_family_duplicates,
)
from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
from maxiv_panda.signal_identification.peak_detection import DetectedPeak


def _pe(element, line, energy, prominence, reliability=90):
    candidate = SignalCandidate(
        element=element, line=line, kind="PE", expected_energy=energy,
        delta_e=0.0, score=0.0, confident=True, reason="synthetic", reliability=reliability,
    )
    return PeakAssignment(DetectedPeak(0, energy, prominence, prominence), [candidate])


def test_one_partner_cannot_support_two_sn_3d32_duplicates(monkeypatch):
    import maxiv_panda.signal_identification.element_consistency as ec
    monkeypatch.setattr(ec, "family_component_offsets", lambda _e, _f: {"3d5/2": 0.0, "3d3/2": 8.4})
    monkeypatch.setattr(ec, "strongest_component_line", lambda _e, _lines, _hv: "3d5/2")
    monkeypatch.setattr(ec, "family_pair_tolerance", lambda _a, _b: 1.6)

    assignments = [
        _pe("Sn", "3d5/2", 486.6, 5000),
        _pe("Sn", "3d3/2", 495.0, 3800),   # correct partner
        _pe("Sn", "3d3/2", 497.1, 800),    # nearby shoulder/duplicate
    ]
    out = _collapse_unbalanced_resolved_family_duplicates(
        assignments, energy_scale="Binding", photon_energy=700.0
    )
    accepted = [(a.best.line, round(a.peak.energy, 1)) for a in out if a.best is not None]
    assert accepted == [("3d5/2", 486.6), ("3d3/2", 495.0)]
    rejected = [a for a in out if a.best is None]
    assert len(rejected) == 1
    assert "same spin-orbit partner" in rejected[0].rejection_reason


def test_two_disjoint_sn_3d_doublets_are_preserved(monkeypatch):
    import maxiv_panda.signal_identification.element_consistency as ec
    monkeypatch.setattr(ec, "family_component_offsets", lambda _e, _f: {"3d5/2": 0.0, "3d3/2": 8.4})
    monkeypatch.setattr(ec, "strongest_component_line", lambda _e, _lines, _hv: "3d5/2")
    monkeypatch.setattr(ec, "family_pair_tolerance", lambda _a, _b: 1.2)

    assignments = [
        _pe("Sn", "3d5/2", 486.6, 5000), _pe("Sn", "3d3/2", 495.0, 3800),
        _pe("Sn", "3d5/2", 488.8, 2200), _pe("Sn", "3d3/2", 497.2, 1700),
    ]
    out = _collapse_unbalanced_resolved_family_duplicates(
        assignments, energy_scale="Binding", photon_energy=700.0
    )
    assert sum(a.best is not None for a in out) == 4
