from types import SimpleNamespace

import numpy as np

from maxiv_panda.signal_identification.auger_detection import (
    _BroadFeature,
    _element_pe_evidence,
    _suppress_competing_features,
)
from maxiv_panda.signal_identification.element_consistency import (
    _collapse_duplicate_synthesized_resolved_families,
)
from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
from maxiv_panda.signal_identification.peak_detection import DetectedPeak


def _pe(element: str, line: str, energy: float, prominence: float, reliability: int = 85):
    candidate = SignalCandidate(
        element=element,
        line=line,
        kind="PE",
        expected_energy=energy,
        delta_e=0.0,
        score=0.0,
        confident=True,
        reason="synthetic support",
        reliability=reliability,
    )
    peak = DetectedPeak(0, energy, prominence, prominence)
    return PeakAssignment(peak=peak, candidates=[candidate])


def _feature(center: float, *, strength: float = 2.5, handbook: bool = False):
    return _BroadFeature(
        peak_energy=center,
        peak_intensity=1000.0,
        prominence=500.0,
        core_lo=center - 8.0,
        core_hi=center + 8.0,
        tail_lo=center - 16.0,
        tail_hi=center + 16.0,
        integrated_excess=10000.0,
        significance=2.0,
        broad_scale_ratio=0.7,
        strength=strength,
        reference_centers=(center,),
        sources=("EADL",),
        handbook_supported=handbook,
        summed_probability=1.0,
    )


def test_competing_auger_envelope_prefers_element_with_dominant_pe_evidence():
    # Weak S remains genuinely present, but Yb overwhelmingly dominates the
    # measured PE spectrum.  Both families are allowed to be plausible at the
    # same broad Auger envelope; the envelope must be assigned to Yb first.
    assignments = [
        _pe("Yb", "4d5/2", 184.0, 12000.0),
        _pe("Yb", "4d3/2", 200.0, 9000.0),
        _pe("Yb", "4s", 465.0, 6500.0),
        _pe("S", "2p", 164.0, 650.0),
        _pe("S", "2s", 229.0, 350.0),
    ]
    evidence = _element_pe_evidence(assignments)
    assert evidence["Yb"] > evidence["S"]

    competing = {
        ("S", "LMM"): [_feature(858.0, strength=2.65)],
        ("Yb", "NNN"): [_feature(858.5, strength=2.55)],
    }
    retained = _suppress_competing_features(competing, element_evidence=evidence)
    assert retained[("Yb", "NNN")]
    assert retained[("S", "LMM")] == []


def test_competing_auger_envelope_does_not_remove_s_when_s_is_only_supported_element():
    evidence = _element_pe_evidence([
        _pe("S", "2p", 164.0, 900.0),
        _pe("S", "2s", 229.0, 500.0),
    ])
    competing = {("S", "LMM"): [_feature(853.0)]}
    retained = _suppress_competing_features(competing, element_evidence=evidence)
    assert retained[("S", "LMM")]


def test_synthesized_yb_5p_family_keeps_one_strong_coherent_doublet(monkeypatch):
    import maxiv_panda.signal_identification.element_consistency as ec

    records = (
        {
            "element": "Yb", "transition": "5p3/2",
            "reference_normalization": "condensed anchor + atomic splitting",
        },
        {
            "element": "Yb", "transition": "5p1/2",
            "reference_normalization": "condensed anchor + atomic splitting",
        },
    )
    monkeypatch.setattr(ec, "normalized_core_records", lambda _mode: records)
    monkeypatch.setattr(ec, "family_component_offsets", lambda _e, _f: {"5p3/2": 0.0, "5p1/2": 6.2})
    monkeypatch.setattr(ec, "strongest_component_line", lambda _e, _lines, _hv: "5p3/2")
    monkeypatch.setattr(ec, "family_pair_tolerance", lambda _a, _b: 1.0)

    # Two geometrically plausible doublets.  The 23.5/29.7 pair is much
    # stronger and should be kept as the single synthesized Yb 5p family.
    assignments = [
        _pe("Yb", "5p3/2", 23.5, 5000.0),
        _pe("Yb", "5p1/2", 29.7, 3000.0),
        _pe("Yb", "5p3/2", 25.7, 900.0),
        _pe("Yb", "5p1/2", 31.9, 600.0),
    ]
    result = _collapse_duplicate_synthesized_resolved_families(
        assignments,
        sample_mode="Automatic (prefer solids)",
        energy_scale="Binding",
        photon_energy=1000.0,
    )
    accepted = [a for a in result if a.best is not None]
    assert {(a.best.line, round(a.peak.energy, 1)) for a in accepted} == {
        ("5p3/2", 23.5), ("5p1/2", 29.7)
    }
    rejected = [a for a in result if a.best is None]
    assert len(rejected) == 2
    assert all("Duplicate synthesized Yb 5p family" in a.rejection_reason for a in rejected)


def test_yb_dominant_survey_assigns_shared_high_be_auger_envelope_to_yb_not_s():
    from maxiv_panda.signal_identification.auger_detection import _broad_auger_assignments

    x = np.arange(0.0, 1000.1, 0.5)
    baseline = 15000.0 + 6.0 * (1000.0 - x)
    broad = 85000.0 * np.exp(-0.5 * ((x - 858.0) / 13.0) ** 2)
    y = baseline + broad
    pe_spec = [
        ("Yb", "4d5/2", 184.0, 40000.0),
        ("Yb", "4d3/2", 200.0, 28000.0),
        ("Yb", "4s", 465.0, 15000.0),
        ("S", "2p", 164.0, 3500.0),
        ("S", "2s", 229.0, 1800.0),
    ]
    assignments = []
    for element, line, energy, prominence in pe_spec:
        y += prominence * np.exp(-0.5 * ((x - energy) / 1.2) ** 2)
    for element, line, energy, prominence in pe_spec:
        index = int(np.argmin(np.abs(x - energy)))
        candidate = SignalCandidate(
            element=element, line=line, kind="PE", expected_energy=energy,
            delta_e=0.0, score=0.0, confident=True, reason="synthetic support",
            reliability=90,
        )
        assignments.append(PeakAssignment(
            DetectedPeak(index, float(x[index]), float(y[index]), prominence), [candidate]
        ))

    auger = _broad_auger_assignments(
        assignments, SimpleNamespace(x=x, y=y), energy_scale="Binding",
        photon_energy=1000.0, selected_elements={"Yb", "S"},
        small_charging_possible=False,
    )
    labels = {a.best.label for a in auger if a.best is not None}
    assert any(label.startswith("Yb ") for label in labels)
    assert "S LMM" not in labels
