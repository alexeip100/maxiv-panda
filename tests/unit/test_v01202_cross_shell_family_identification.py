import numpy as np

def test_cross_shell_family_recovery_finds_na_1s_from_na_2p_and_2s():
    """Two established Na families should recover a missed measured Na 1s peak."""
    from types import SimpleNamespace
    import maxiv_panda.signal_identification.element_consistency as ec
    from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    x = np.arange(0.0, 1120.5, 0.5)
    # Broad survey-like background plus three real Na core features.  Add a
    # smaller displaced maximum at 1075 eV to mimic the provisional global
    # peak that previously blocked the reference-guided 1s recovery.
    y = 1000.0 + 0.15 * x
    y += 5000.0 * np.exp(-0.5 * ((x - 30.3) / 0.8) ** 2)
    y += 6500.0 * np.exp(-0.5 * ((x - 63.3) / 0.9) ** 2)
    y += 22000.0 * np.exp(-0.5 * ((x - 1071.0) / 0.7) ** 2)
    y += 2200.0 * np.exp(-0.5 * ((x - 1075.0) / 0.7) ** 2)
    payload = SimpleNamespace(x=x, y=y)

    def accepted(line: str, energy: float, prominence: float):
        idx = int(np.argmin(np.abs(x - energy)))
        peak = DetectedPeak(idx, float(x[idx]), float(y[idx]), prominence)
        candidate = SignalCandidate(
            element="Na", line=line, kind="PE", expected_energy=energy,
            delta_e=0.0, score=-1.0, confident=True, reliability=90,
            reliability_support=0.9,
        )
        return PeakAssignment(peak, [candidate])

    assignments = [
        accepted("2p", 30.3, 4800.0),
        accepted("2s", 63.3, 6200.0),
        # Existing but unassigned displaced provisional peak near Na 1s.
        PeakAssignment(
            DetectedPeak(int(np.argmin(np.abs(x - 1075.0))), 1075.0,
                         float(y[np.argmin(np.abs(x - 1075.0))]), 1800.0),
            [],
        ),
    ]

    result = ec._recover_cross_shell_family_members(
        assignments, payload, selected_elements={"Na"}, energy_scale="Binding",
        photon_energy=1200.0, sample_mode="Automatic (prefer solids)",
    )
    na1s = [a for a in result if a.best is not None and a.best.label == "Na 1s"]
    assert len(na1s) == 1
    assert abs(float(na1s[0].peak.energy) - 1071.0) <= 0.5
    assert "cross-section" in na1s[0].best.reason.lower()


def test_cross_shell_recovery_does_not_bootstrap_from_one_family():
    """A single Na line must not cause reference-guided creation of other shells."""
    from types import SimpleNamespace
    import maxiv_panda.signal_identification.element_consistency as ec
    from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    x = np.arange(0.0, 1120.5, 0.5)
    y = 1000.0 + 4000.0 * np.exp(-0.5 * ((x - 30.3) / 0.8) ** 2)
    # A coincidental large feature near the Na 1s reference must not be enough
    # without independent Na-family support.
    y += 15000.0 * np.exp(-0.5 * ((x - 1071.0) / 0.8) ** 2)
    payload = SimpleNamespace(x=x, y=y)
    idx = int(np.argmin(np.abs(x - 30.3)))
    peak = DetectedPeak(idx, float(x[idx]), float(y[idx]), 3900.0)
    candidate = SignalCandidate(
        element="Na", line="2p", kind="PE", expected_energy=30.3,
        delta_e=0.0, score=-1.0, confident=True, reliability=90,
    )
    result = ec._recover_cross_shell_family_members(
        [PeakAssignment(peak, [candidate])], payload, selected_elements={"Na"},
        energy_scale="Binding", photon_energy=1200.0,
        sample_mode="Automatic (prefer solids)",
    )
    assert not any(a.best is not None and a.best.label == "Na 1s" for a in result)
