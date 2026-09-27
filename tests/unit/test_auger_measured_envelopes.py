from types import SimpleNamespace

import numpy as np

from maxiv_panda.signal_identification.auger_detection import _broad_auger_assignments
from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
from maxiv_panda.signal_identification.peak_detection import DetectedPeak


def _oxygen_pe_support(x: np.ndarray, y: np.ndarray) -> list[PeakAssignment]:
    energy = 532.0
    index = int(np.argmin(np.abs(x - energy)))
    candidate = SignalCandidate(
        element="O",
        line="1s",
        kind="PE",
        expected_energy=energy,
        delta_e=0.0,
        score=0.0,
        confident=True,
        reason="synthetic support",
    )
    peak = DetectedPeak(index=index, energy=float(x[index]), intensity=float(y[index]), prominence=1.0)
    return [PeakAssignment(peak=peak, candidates=[candidate])]


def _identify_oxygen(x: np.ndarray, y: np.ndarray):
    return _broad_auger_assignments(
        _oxygen_pe_support(x, y),
        SimpleNamespace(x=x, y=y),
        energy_scale="Binding",
        photon_energy=1000.0,
        selected_elements={"O"},
        small_charging_possible=False,
    )


def test_broad_feature_produces_measured_core_and_soft_asymmetric_tails():
    x = np.arange(450.0, 551.0, 0.5)
    baseline = 1000.0 + 2.0 * (x - 450.0)
    broad = 450.0 * np.exp(-0.5 * ((x - 488.0) / 9.0) ** 2)
    shoulder = 170.0 * np.exp(-0.5 * ((x - 507.0) / 6.0) ** 2)
    oxygen_1s = 1200.0 * np.exp(-0.5 * ((x - 532.0) / 0.9) ** 2)
    y = baseline + broad + shoulder + oxygen_1s

    assignments = _identify_oxygen(x, y)
    candidate = next(a.best for a in assignments if a.best is not None and a.best.label == "O KLL")
    assert len(candidate.auger_subregions) == 1
    region = candidate.auger_subregions[0]
    assert 483.0 <= region.peak_energy <= 493.0
    assert region.tail_lo < region.core_lo <= region.peak_energy <= region.core_hi < region.tail_hi
    assert region.tail_hi - region.tail_lo >= 25.0


def test_narrow_peak_alone_is_not_accepted_as_an_auger_envelope():
    x = np.arange(450.0, 551.0, 0.5)
    baseline = 1000.0 + 2.0 * (x - 450.0)
    narrow = 700.0 * np.exp(-0.5 * ((x - 491.0) / 0.8) ** 2)
    oxygen_1s = 1200.0 * np.exp(-0.5 * ((x - 532.0) / 0.9) ** 2)
    assignments = _identify_oxygen(x, baseline + narrow + oxygen_1s)
    assert not any(a.best is not None and a.best.label == "O KLL" for a in assignments)


def test_monotonic_background_does_not_activate_theoretical_regions():
    x = np.arange(450.0, 551.0, 0.5)
    y = 1000.0 + 3.0 * (x - 450.0)
    assignments = _identify_oxygen(x, y)
    assert not assignments


def _gold_pe_support(x: np.ndarray, y: np.ndarray, energies=(84.0, 335.0, 643.0, 762.0)) -> list[PeakAssignment]:
    assignments: list[PeakAssignment] = []
    for i, energy in enumerate(energies):
        index = int(np.argmin(np.abs(x - energy)))
        candidate = SignalCandidate(
            element="Au",
            line=("4f7/2", "4d5/2", "4p1/2", "4s")[min(i, 3)],
            kind="PE",
            expected_energy=energy,
            delta_e=0.0,
            score=0.0,
            confident=True,
            reason="synthetic Au support",
        )
        peak = DetectedPeak(index=index, energy=float(x[index]), intensity=float(y[index]), prominence=1.0)
        assignments.append(PeakAssignment(peak=peak, candidates=[candidate]))
    return assignments


def test_eadl_only_au_nno_is_allowed_with_multiple_pe_lines_and_measured_broad_excess():
    x = np.arange(650.0, 851.0, 0.5)
    baseline = 1800.0 + 0.8 * (x - 650.0)
    broad_auger = 520.0 * np.exp(-0.5 * ((x - 765.0) / 12.0) ** 2)
    au_4s = 240.0 * np.exp(-0.5 * ((x - 762.0) / 1.2) ** 2)
    y = baseline + broad_auger + au_4s

    assignments = _broad_auger_assignments(
        _gold_pe_support(x, y),
        SimpleNamespace(x=x, y=y),
        energy_scale="Binding",
        photon_energy=1000.0,
        selected_elements={"Au"},
        small_charging_possible=False,
    )

    au_nno = next(a.best for a in assignments if a.best is not None and a.best.label == "Au NNO")
    assert au_nno.reference_confidence == "low"
    assert au_nno.reliability <= 70
    assert any(region.tail_lo < 765.0 < region.tail_hi for region in au_nno.auger_subregions)
    assert "EADL-only family" in au_nno.reason


def test_eadl_only_family_is_not_enabled_by_one_pe_line():
    x = np.arange(650.0, 851.0, 0.5)
    y = 1800.0 + 520.0 * np.exp(-0.5 * ((x - 765.0) / 12.0) ** 2)
    assignments = _broad_auger_assignments(
        _gold_pe_support(x, y, energies=(84.0,)),
        SimpleNamespace(x=x, y=y),
        energy_scale="Binding",
        photon_energy=1000.0,
        selected_elements={"Au"},
        small_charging_possible=False,
    )
    assert not any(a.best is not None and a.best.label == "Au NNO" for a in assignments)


def _sulfur_pe_support(x: np.ndarray, y: np.ndarray) -> list[PeakAssignment]:
    assignments: list[PeakAssignment] = []
    for energy, line in ((164.0, "2p"), (229.0, "2s")):
        index = int(np.argmin(np.abs(x - energy)))
        candidate = SignalCandidate(
            element="S",
            line=line,
            kind="PE",
            expected_energy=energy,
            delta_e=0.0,
            score=0.0,
            confident=True,
            reason="synthetic S support",
        )
        peak = DetectedPeak(index=index, energy=float(x[index]), intensity=float(y[index]), prominence=1000.0)
        assignments.append(PeakAssignment(peak=peak, candidates=[candidate]))
    return assignments


def test_eadl_only_s_lmm_is_allowed_when_separated_from_supporting_pe_lines():
    """Regression: S LMM near BE 853 eV must not need to overlap S 2s/2p."""
    x = np.arange(0.0, 1000.1, 0.5)
    baseline = 15000.0 + 6.0 * (1000.0 - x)
    broad_s_lmm = 85000.0 * np.exp(-0.5 * ((x - 853.0) / 13.0) ** 2)
    sulfur_2p = 25000.0 * np.exp(-0.5 * ((x - 164.0) / 1.1) ** 2)
    sulfur_2s = 13000.0 * np.exp(-0.5 * ((x - 229.0) / 1.2) ** 2)
    y = baseline + broad_s_lmm + sulfur_2p + sulfur_2s

    assignments = _broad_auger_assignments(
        _sulfur_pe_support(x, y),
        SimpleNamespace(x=x, y=y),
        energy_scale="Binding",
        photon_energy=1000.0,
        selected_elements={"S"},
        small_charging_possible=False,
    )

    sulfur_lmm = next(a.best for a in assignments if a.best is not None and a.best.label == "S LMM")
    assert sulfur_lmm.reference_confidence == "low"
    assert sulfur_lmm.reliability <= 70
    assert any(region.tail_lo < 853.0 < region.tail_hi for region in sulfur_lmm.auger_subregions)
