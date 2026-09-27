from maxiv_panda.signal_identification.element_consistency import (
    _enforce_s_requires_p,
    _enforce_stronger_spin_orbit,
    _resolve_same_peak_conflicts,
)
from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
from maxiv_panda.signal_identification.peak_detection import DetectedPeak


def _assignment(energy, element, line, *, reliability=80, prominence=100.0):
    peak = DetectedPeak(0, float(energy), 1000.0, float(prominence))
    candidate = SignalCandidate(
        element=element, line=line, kind="PE", expected_energy=float(energy),
        delta_e=0.0, score=0.0, confident=True, reliability=reliability,
    )
    return PeakAssignment(peak=peak, candidates=[candidate])


def test_same_peak_conflict_rejects_label_but_keeps_peak_row():
    a = _assignment(100.0, "A", "3p", reliability=90)
    b = _assignment(100.4, "B", "4f", reliability=70)
    result = _resolve_same_peak_conflicts([a, b], photon_energy=None)
    assert len(result) == 2
    assert sum(item.best is not None for item in result) == 1
    assert any(item.best is None and "Competing assignment" in item.rejection_reason for item in result)


def test_missing_p_companion_does_not_delete_detected_s_peak():
    assignment = _assignment(150.0, "Si", "2s")
    result = _enforce_s_requires_p([assignment])
    assert len(result) == 1
    assert result[0].best is None
    assert "companion" in result[0].rejection_reason


def test_missing_stronger_spin_orbit_partner_does_not_delete_peak():
    assignment = _assignment(65.0, "Ir", "4p1/2")
    result = _enforce_stronger_spin_orbit([assignment])
    assert len(result) == 1
    assert result[0].best is None
    assert "stronger partner" in result[0].rejection_reason


def test_same_peak_conflict_counts_spin_orbit_doublet_as_one_companion_family():
    """Resolved j components must not give two votes to one physical family."""
    si_2p = _assignment(102.0, "Si", "2p", reliability=80, prominence=900.0)
    co_3s = _assignment(102.2, "Co", "3s", reliability=80, prominence=900.0)
    si_2s = _assignment(154.0, "Si", "2s", reliability=80, prominence=500.0)
    co_2p32 = _assignment(780.0, "Co", "2p3/2", reliability=80, prominence=700.0)
    co_2p12 = _assignment(795.0, "Co", "2p1/2", reliability=80, prominence=500.0)

    result = _resolve_same_peak_conflicts(
        [si_2p, co_3s, si_2s, co_2p32, co_2p12],
        photon_energy=1215.0,
    )
    winners = [a.best.label for a in result if a.best is not None and 101.0 <= a.peak.energy <= 103.0]
    assert winners == ["Si 2p"]
