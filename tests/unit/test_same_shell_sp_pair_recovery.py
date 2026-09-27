from types import SimpleNamespace

import numpy as np

from maxiv_panda.signal_identification.element_consistency import _recover_same_shell_sp_pairs
from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
from maxiv_panda.signal_identification.peak_detection import DetectedPeak


def test_ambiguous_p_line_is_rescued_by_independent_same_shell_s_companion():
    # Use Al rather than the reported Si spectrum to verify that the rule is
    # family-generic.  Apply a common +3 eV shift to both lines; the pair
    # separation should remain diagnostic even though either line alone can be
    # ambiguous in a survey.
    x = np.arange(40.0, 150.5, 0.5)
    baseline = 1000.0 + 0.8 * x
    p_energy = 72.9 + 3.0
    s_energy = 117.9 + 3.0
    y = (
        baseline
        + 900.0 * np.exp(-0.5 * ((x - p_energy) / 0.8) ** 2)
        + 450.0 * np.exp(-0.5 * ((x - s_energy) / 1.0) ** 2)
    )
    p_idx = int(np.argmin(np.abs(x - p_energy)))
    provisional = SignalCandidate(
        element="Al", line="2p", kind="PE", expected_energy=72.9,
        delta_e=3.0, score=0.4, confident=False,
    )
    assignments = [PeakAssignment(
        peak=DetectedPeak(p_idx, float(x[p_idx]), float(y[p_idx]), 850.0),
        candidates=[provisional],
        rejection_reason="Rejected as ambiguous or insufficiently supported",
    )]
    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")

    recovered = _recover_same_shell_sp_pairs(
        assignments, payload, selected_elements=set(), energy_scale="Binding",
        photon_energy=1215.0, sample_mode="Automatic",
    )

    labels = {a.best.label for a in recovered if a.best is not None}
    assert {"Al 2p", "Al 2s"} <= labels


def test_same_shell_pair_rule_does_not_create_missing_companion():
    x = np.arange(40.0, 150.5, 0.5)
    p_energy = 72.9 + 3.0
    y = 1000.0 + 900.0 * np.exp(-0.5 * ((x - p_energy) / 0.8) ** 2)
    p_idx = int(np.argmin(np.abs(x - p_energy)))
    assignments = [PeakAssignment(
        peak=DetectedPeak(p_idx, float(x[p_idx]), float(y[p_idx]), 850.0),
        candidates=[SignalCandidate(
            element="Al", line="2p", kind="PE", expected_energy=72.9,
            delta_e=3.0, score=0.4, confident=False,
        )],
    )]
    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")

    recovered = _recover_same_shell_sp_pairs(
        assignments, payload, selected_elements=set(), energy_scale="Binding",
        photon_energy=1215.0, sample_mode="Automatic",
    )

    assert not any(a.best is not None for a in recovered)


def test_same_shell_pair_can_rescue_nonleading_p_candidate():
    x = np.arange(40.0, 170.5, 0.5)
    p_energy = 102.0
    s_energy = 153.5
    y = (
        1000.0
        + 1200.0 * np.exp(-0.5 * ((x - p_energy) / 0.9) ** 2)
        + 650.0 * np.exp(-0.5 * ((x - s_energy) / 1.1) ** 2)
    )
    p_idx = int(np.argmin(np.abs(x - p_energy)))
    wrong = SignalCandidate(
        element="Co", line="3s", kind="PE", expected_energy=101.0,
        delta_e=1.0, score=-0.5, confident=False,
    )
    si = SignalCandidate(
        element="Si", line="2p", kind="PE", expected_energy=102.6,
        delta_e=-0.6, score=0.2, confident=False,
    )
    assignments = [PeakAssignment(
        peak=DetectedPeak(p_idx, float(x[p_idx]), float(y[p_idx]), 1100.0),
        candidates=[wrong, si],
        rejection_reason="Ambiguous",
    )]
    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")

    recovered = _recover_same_shell_sp_pairs(
        assignments, payload, selected_elements={"Co", "Si"}, energy_scale="Binding",
        photon_energy=1215.0, sample_mode="Automatic (prefer solids)",
    )

    labels = {a.best.label for a in recovered if a.best is not None}
    assert {"Si 2p", "Si 2s"} <= labels
