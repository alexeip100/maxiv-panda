from types import SimpleNamespace

import numpy as np

from maxiv_panda.signal_identification import guided_detection, matcher
from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
from maxiv_panda.signal_identification.peak_detection import DetectedPeak


def test_matcher_builds_resolved_family_context_once_per_identification(monkeypatch):
    calls = 0
    original = matcher._resolved_family_keys

    def counted(records):
        nonlocal calls
        calls += 1
        return original(records)

    monkeypatch.setattr(matcher, "_resolved_family_keys", counted)
    peaks = [
        DetectedPeak(i, energy, 1000.0 + i, 100.0 + i)
        for i, energy in enumerate((49.0, 83.0, 285.0, 531.5, 642.0, 654.0))
    ]
    matcher.match_peaks(
        peaks,
        energy_scale="Binding",
        photon_energy=1215.0,
        tolerance_eV=5.0,
        elements={"C", "O", "Mn", "Fe"},
        include_auger=False,
        include_second_order=False,
        small_charging_possible=False,
        sample_mode="Automatic (prefer solids)",
    )
    assert calls == 1


def test_companion_search_considers_only_observed_resolved_families(monkeypatch):
    calls = []
    original = guided_detection.strongest_component_line

    def counted(element, lines, photon_energy_eV=None):
        calls.append((element, tuple(sorted(lines))))
        return original(element, lines, photon_energy_eV)

    monkeypatch.setattr(guided_detection, "strongest_component_line", counted)

    candidate = SignalCandidate(
        element="Mn",
        line="2p3/2",
        kind="PE",
        expected_energy=641.6,
        delta_e=0.4,
        score=0.1,
        confident=True,
        reliability=90,
    )
    assignment = PeakAssignment(
        peak=DetectedPeak(0, 642.0, 5000.0, 3000.0),
        candidates=[candidate],
    )
    x = np.arange(620.0, 670.0, 0.5)
    y = 1000.0 + 4000.0 * np.exp(-0.5 * ((x - 642.0) / 1.2) ** 2)
    y += 2400.0 * np.exp(-0.5 * ((x - 654.0) / 1.2) ** 2)
    payload = SimpleNamespace(x=x, y=y)

    guided_detection._companion_assisted_peaks(
        [assignment], payload,
        energy_scale="Binding", photon_energy=1215.0,
        sample_mode="Automatic (prefer solids)",
    )

    assert calls
    assert {element for element, _lines in calls} == {"Mn"}
    assert len(calls) == 1
