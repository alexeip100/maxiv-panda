import numpy as np

from maxiv_panda.signal_identification.matcher import (
    _distance_to_reference,
    _expected_auger_position,
    _expected_core_position,
    _shift_plausibility,
    _weighted_median,
)
from maxiv_panda.signal_identification.peak_detection import detect_peaks, refine_peak_near_reference
from maxiv_panda.signal_identification.spectrum_context import extract_photon_energy


def test_photon_energy_is_extracted_from_nested_metadata():
    meta = {"source_metadata": {"Monochromator energy": "650.0 eV"}}
    assert extract_photon_energy(meta) == 650.0
    assert extract_photon_energy({"hv": "-5"}) is None


def test_photon_energy_is_extracted_from_ibw_section_metadata():
    # IBW Scienta notes keep acquisition fields in grouped metadata sections.
    meta = {
        "source_metadata": {"Spectrum Name": "S2p_700eV"},
        "section_meta": {
            "Info 1": {
                "Pass Energy": "50",
                "Excitation Energy": "699.9998786467",
                "Energy Scale": "Binding",
            }
        },
    }
    assert extract_photon_energy(meta) == 699.9998786467


def test_reference_energy_conversion_between_be_and_ke():
    assert _expected_core_position(531.0, "Binding", 650.0, 1) == 531.0
    assert _expected_core_position(531.0, "Kinetic", 650.0, 1) == 119.0
    assert _expected_core_position(531.0, "Kinetic", None, 1) is None
    assert _expected_auger_position(510.0, "Binding", 650.0) == 140.0
    assert _expected_auger_position(510.0, "Kinetic", 650.0) == 510.0


def test_distance_to_reference_handles_inside_outside_and_reversed_bounds():
    assert _distance_to_reference(5.0, 4.0, 6.0) == (0.0, 5.0)
    assert _distance_to_reference(2.0, 6.0, 4.0) == (2.0, 4.0)


def test_weighted_median_and_shift_plausibility():
    assert _weighted_median([(0.0, 1.0), (5.0, 10.0), (10.0, 1.0)]) == 5.0
    assert _shift_plausibility(0.0) == 1.0
    assert _shift_plausibility(5.0) == 0.7
    assert _shift_plausibility(15.0) == 0.0
    assert _shift_plausibility(20.0) == 0.0


def test_detect_peaks_finds_two_synthetic_features():
    x = np.linspace(0.0, 20.0, 4001)
    y = 0.01 * x
    y += 2.0 * np.exp(-0.5 * ((x - 5.0) / 0.12) ** 2)
    y += 1.2 * np.exp(-0.5 * ((x - 14.0) / 0.18) ** 2)
    peaks = detect_peaks(x, y, prominence_fraction=0.02, min_distance_fraction=0.05)
    energies = [p.energy for p in peaks]
    assert any(abs(e - 5.0) < 0.05 for e in energies)
    assert any(abs(e - 14.0) < 0.05 for e in energies)


def test_refine_peak_near_reference_returns_local_maximum(synthetic_peak):
    x, y = synthetic_peak
    peak = refine_peak_near_reference(x, y, target_energy=8.0, search_half_width=0.8)
    assert peak is not None
    assert abs(peak.energy - 8.2) < 0.03


def test_refine_peak_handles_descending_energy_axis():
    x = np.linspace(300.0, 270.0, 301)
    baseline = np.linspace(20.0, 35.0, x.size)
    y = baseline + 12.0 * np.exp(-0.5 * ((x - 284.5) / 0.8) ** 2)
    peak = refine_peak_near_reference(x, y, target_energy=284.5, search_half_width=3.0)
    assert peak is not None
    assert abs(peak.energy - 284.5) < 0.2


def test_selected_carbon_1s_can_be_high_reliability_without_companion_core_lines():
    from maxiv_panda.signal_identification.matcher import match_peaks
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    peaks = [
        DetectedPeak(0, 284.7, 10000.0, 1600.0),
        DetectedPeak(1, 84.0, 100000.0, 80000.0),
    ]
    assignments = match_peaks(
        peaks,
        energy_scale="Binding",
        photon_energy=1000.0,
        tolerance_eV=5.0,
        elements={"C", "Au"},
        include_auger=False,
        include_second_order=False,
        small_charging_possible=False,
        sample_mode="Automatic (prefer solids)",
    )
    carbon = next(a for a in assignments if abs(a.peak.energy - 284.7) < 0.1)
    assert carbon.best is not None
    assert carbon.best.label == "C 1s"
    assert carbon.best.reliability >= 75


def test_small_charging_does_not_replace_good_mn_3p_with_neighbouring_element():
    """Charging assistance remains a fallback in a crowded TM 3p region."""
    from maxiv_panda.signal_identification.matcher import match_peaks
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    # Mn 2p establishes a modest positive shift.  Cr 2p is also present and can
    # establish a different shift, so the 49.5 eV feature is a realistic
    # cross-element charging ambiguity.  The ordinary Mn 3p match is already
    # satisfactory and must not be displaced by shifted Cr 3p.
    peaks = [
        DetectedPeak(0, 49.5, 3000.0, 2200.0),
        DetectedPeak(1, 579.0, 9000.0, 7000.0),
        DetectedPeak(2, 588.5, 5000.0, 3500.0),
        DetectedPeak(3, 642.0, 30000.0, 23000.0),
        DetectedPeak(4, 653.5, 15000.0, 9000.0),
    ]
    assignments = match_peaks(
        peaks,
        energy_scale="Binding",
        photon_energy=1215.0,
        tolerance_eV=3.0,
        elements={"Cr", "Mn"},
        include_auger=False,
        include_second_order=False,
        small_charging_possible=True,
        sample_mode="Automatic (prefer solids)",
    )
    shallow = next(a for a in assignments if abs(a.peak.energy - 49.5) < 0.1)
    assert shallow.best is not None
    assert shallow.best.label == "Mn 3p"


def test_condensed_ca_2p_doublet_uses_solid_anchor_with_atomic_splitting():
    """A solid-state Ca 2p doublet must not depend on gas-phase absolute BEs."""
    from maxiv_panda.signal_identification.matcher import match_peaks
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    peaks = [
        DetectedPeak(0, 347.5, 65000.0, 10500.0),
        DetectedPeak(1, 351.0, 58000.0, 4000.0),
    ]
    assignments = match_peaks(
        peaks,
        energy_scale="Binding",
        photon_energy=700.0,
        tolerance_eV=5.0,
        elements={"Ca"},
        include_auger=False,
        include_second_order=False,
        small_charging_possible=False,
        sample_mode="Automatic (prefer solids)",
    )
    labels = {assignment.best.label for assignment in assignments if assignment.best is not None}
    assert labels == {"Ca 2p3/2", "Ca 2p1/2"}


def test_family_partner_recovery_is_generic_not_ca_specific(monkeypatch):
    """Any normalized, resolvable family can recover a distinct measured partner."""
    import numpy as np
    from types import SimpleNamespace
    import maxiv_panda.signal_identification.element_consistency as ec
    from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    records = [
        {"element": "Xx", "transition": "3d5/2", "representative_energy_eV": 100.0},
        {"element": "Xx", "transition": "3d3/2", "representative_energy_eV": 106.0},
    ]
    monkeypatch.setattr(ec, "normalized_core_records", lambda _mode: records)
    monkeypatch.setattr(
        ec,
        "_reference_position_for_line",
        lambda *, line, **_kwargs: {"3d5/2": 100.0, "3d3/2": 106.0}.get(line),
    )
    monkeypatch.setattr(ec, "family_component_offsets", lambda _element, _family: {"3d5/2": 0.0, "3d3/2": 6.0})

    x = np.arange(90.0, 116.5, 0.5)
    y = 100.0 + 800.0 * np.exp(-0.5 * ((x - 100.0) / 0.8) ** 2)
    y += 420.0 * np.exp(-0.5 * ((x - 106.0) / 0.9) ** 2)
    payload = SimpleNamespace(x=x, y=y)
    anchor_peak = DetectedPeak(int(np.argmin(abs(x - 100.0))), 100.0, float(y[np.argmin(abs(x - 100.0))]), 700.0)
    anchor = SignalCandidate(
        element="Xx", line="3d5/2", kind="PE", expected_energy=100.0,
        delta_e=0.0, score=-1.0, confident=True, reliability=85,
    )
    assignments = [PeakAssignment(anchor_peak, [anchor])]

    result = ec._recover_resolved_family_partners(
        assignments, payload, selected_elements={"Xx"}, energy_scale="Binding",
        photon_energy=500.0, sample_mode="Automatic (prefer solids)",
    )
    labels = {a.best.label for a in result if a.best is not None}
    assert labels == {"Xx 3d5/2", "Xx 3d3/2"}
    partner = next(a for a in result if a.best is not None and a.best.line == "3d3/2")
    assert abs(partner.peak.energy - 106.0) <= 0.5


def test_normalized_core_reference_families_are_cached():
    """Repeated family lookups during one Apply operation must be inexpensive."""
    from maxiv_panda.signal_identification.core_reference_families import normalized_core_records

    normalized_core_records.cache_clear()
    first = normalized_core_records("Automatic")
    second = normalized_core_records("Automatic")
    assert first is second
    info = normalized_core_records.cache_info()
    assert info.misses == 1
    assert info.hits >= 1


def test_family_recovery_replaces_wrong_nearby_partner_by_reference_splitting(monkeypatch):
    """A nearby local maximum must not substitute for a doublet partner with the wrong splitting."""
    import numpy as np
    from types import SimpleNamespace
    import maxiv_panda.signal_identification.element_consistency as ec
    from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    records = [
        {"element": "Xx", "transition": "2p3/2", "representative_energy_eV": 100.0},
        {"element": "Xx", "transition": "2p1/2", "representative_energy_eV": 111.0},
    ]
    monkeypatch.setattr(ec, "normalized_core_records", lambda _mode: records)
    monkeypatch.setattr(ec, "family_component_offsets", lambda _element, _family: {"2p3/2": 0.0, "2p1/2": 11.0})

    x = np.arange(90.0, 121.5, 0.5)
    y = 100.0 + 900.0 * np.exp(-0.5 * ((x - 102.0) / 0.8) ** 2)
    # Wrong nearby peak at 110 eV plus the true partner at 113 eV.
    y += 180.0 * np.exp(-0.5 * ((x - 110.0) / 0.7) ** 2)
    y += 520.0 * np.exp(-0.5 * ((x - 113.0) / 0.9) ** 2)
    payload = SimpleNamespace(x=x, y=y)

    def assignment_at(energy, line, expected, prominence):
        idx = int(np.argmin(abs(x - energy)))
        peak = DetectedPeak(idx, float(x[idx]), float(y[idx]), prominence)
        candidate = SignalCandidate(
            element="Xx", line=line, kind="PE", expected_energy=expected,
            delta_e=float(x[idx]) - expected, score=-1.0, confident=True, reliability=85,
        )
        return PeakAssignment(peak, [candidate])

    assignments = [
        assignment_at(102.0, "2p3/2", 100.0, 800.0),
        assignment_at(110.0, "2p1/2", 111.0, 140.0),
    ]
    result = ec._recover_resolved_family_partners(
        assignments, payload, selected_elements={"Xx"}, energy_scale="Binding",
        photon_energy=500.0, sample_mode="Automatic",
    )
    result = ec._enforce_resolved_family_separations(result)

    good = [a for a in result if a.best is not None and a.best.line == "2p1/2"]
    assert any(abs(a.peak.energy - 113.0) <= 0.5 for a in good)
    wrong = next(a for a in result if abs(a.peak.energy - 110.0) <= 0.5)
    assert wrong.best is None


def test_strongest_component_selection_is_generic_for_p_d_f(monkeypatch):
    """Resolved families must anchor from the statistically stronger j component."""
    import maxiv_panda.signal_identification.core_reference_families as crf

    # Force the statistical-weight fallback so the test is independent of the
    # bundled cross-section table contents.
    monkeypatch.setattr(
        "maxiv_panda.signal_identification.cross_sections.cross_section_at",
        lambda _element, _line, _photon: None,
    )
    assert crf.strongest_component_line("Xx", {"2p1/2", "2p3/2"}, 1000.0) == "2p3/2"
    assert crf.strongest_component_line("Xx", {"3d3/2", "3d5/2"}, 1000.0) == "3d5/2"
    assert crf.strongest_component_line("Xx", {"4f5/2", "4f7/2"}, 1000.0) == "4f7/2"


def test_weak_component_does_not_bootstrap_generic_spin_orbit_family(monkeypatch):
    """A lone weak j component must not be used to search backwards for the strong member."""
    import numpy as np
    from types import SimpleNamespace
    import maxiv_panda.signal_identification.element_consistency as ec
    from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    records = [
        {"element": "Xx", "transition": "3d5/2", "representative_energy_eV": 100.0},
        {"element": "Xx", "transition": "3d3/2", "representative_energy_eV": 106.0},
    ]
    monkeypatch.setattr(ec, "normalized_core_records", lambda _mode: records)
    monkeypatch.setattr(ec, "family_component_offsets", lambda _element, _family: {"3d5/2": 0.0, "3d3/2": 6.0})
    monkeypatch.setattr(ec, "strongest_component_line", lambda _element, _lines, _photon: "3d5/2")

    x = np.arange(90.0, 116.5, 0.5)
    y = 100.0 + 850.0 * np.exp(-0.5 * ((x - 100.0) / 0.8) ** 2)
    y += 400.0 * np.exp(-0.5 * ((x - 106.0) / 0.9) ** 2)
    payload = SimpleNamespace(x=x, y=y)

    idx = int(np.argmin(abs(x - 106.0)))
    weak_peak = DetectedPeak(idx, 106.0, float(y[idx]), 350.0)
    weak = SignalCandidate(
        element="Xx", line="3d3/2", kind="PE", expected_energy=106.0,
        delta_e=0.0, score=-1.0, confident=True, reliability=85,
    )
    result = ec._recover_resolved_family_partners(
        [PeakAssignment(weak_peak, [weak])], payload, selected_elements={"Xx"},
        energy_scale="Binding", photon_energy=500.0,
        sample_mode="Automatic (prefer solids)",
    )
    labels = [a.best.label for a in result if a.best is not None]
    assert labels == ["Xx 3d3/2"]


def test_strong_first_partner_recovery_respects_kinetic_energy_axis(monkeypatch):
    """Relative spin-orbit offsets reverse sign on a kinetic-energy spectrum."""
    import numpy as np
    from types import SimpleNamespace
    import maxiv_panda.signal_identification.element_consistency as ec
    from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    records = [
        {"element": "Xx", "transition": "3d5/2", "representative_energy_eV": 100.0},
        {"element": "Xx", "transition": "3d3/2", "representative_energy_eV": 106.0},
    ]
    monkeypatch.setattr(ec, "normalized_core_records", lambda _mode: records)
    monkeypatch.setattr(ec, "family_component_offsets", lambda _element, _family: {"3d5/2": 0.0, "3d3/2": 6.0})
    monkeypatch.setattr(ec, "strongest_component_line", lambda _element, _lines, _photon: "3d5/2")

    x = np.arange(388.0, 407.0, 0.5)
    y = 100.0 + 850.0 * np.exp(-0.5 * ((x - 400.0) / 0.8) ** 2)
    y += 420.0 * np.exp(-0.5 * ((x - 394.0) / 0.9) ** 2)
    payload = SimpleNamespace(x=x, y=y)

    idx = int(np.argmin(abs(x - 400.0)))
    strong_peak = DetectedPeak(idx, 400.0, float(y[idx]), 750.0)
    strong = SignalCandidate(
        element="Xx", line="3d5/2", kind="PE", expected_energy=400.0,
        delta_e=0.0, score=-1.0, confident=True, reliability=85,
    )
    result = ec._recover_resolved_family_partners(
        [PeakAssignment(strong_peak, [strong])], payload, selected_elements={"Xx"},
        energy_scale="Kinetic", photon_energy=500.0,
        sample_mode="Automatic (prefer solids)",
    )
    partner = next(a for a in result if a.best is not None and a.best.line == "3d3/2")
    assert abs(float(partner.peak.energy) - 394.0) <= 0.5

    checked = ec._enforce_resolved_family_separations(result, energy_scale="Kinetic")
    labels = {a.best.label for a in checked if a.best is not None}
    assert labels == {"Xx 3d5/2", "Xx 3d3/2"}


def test_missing_weak_partner_penalty_scales_with_expected_cross_section_ratio(monkeypatch):
    """Missing an almost-equally-strong partner must hurt more than a weak one."""
    import maxiv_panda.signal_identification.element_consistency as ec
    from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    offsets = {"3d5/2": 0.0, "3d3/2": 6.0}
    monkeypatch.setattr(ec, "strongest_component_line", lambda *_args, **_kwargs: "3d5/2")

    strong_peak = DetectedPeak(0, 100.0, 1000.0, 500.0)
    strong = SignalCandidate(
        element="Xx", line="3d5/2", kind="PE", expected_energy=100.0,
        delta_e=0.0, score=-1.0, confident=True, reliability=90,
        reliability_support=1.0,
    )
    support_peak = DetectedPeak(1, 200.0, 900.0, 400.0)
    support = SignalCandidate(
        element="Xx", line="2p3/2", kind="PE", expected_energy=200.0,
        delta_e=0.0, score=-1.0, confident=True, reliability=90,
    )
    rows = [PeakAssignment(strong_peak, [strong]), PeakAssignment(support_peak, [support])]

    def run_with_ratio(ratio):
        def sigma(_element, line, _photon):
            return 1.0 if line == "3d5/2" else float(ratio)
        monkeypatch.setattr(ec, "cross_section_at", sigma)
        retained = ec._retain_strong_anchor_without_partner(
            rows[0], rows, family="3d", offsets=offsets, photon_energy=500.0,
        )
        assert retained is not None and retained.best is not None
        return retained.best.reliability

    assert run_with_ratio(0.25) > run_with_ratio(0.90)


def test_strong_spin_orbit_anchor_without_independent_element_support_is_rejected(monkeypatch):
    import maxiv_panda.signal_identification.element_consistency as ec
    from maxiv_panda.signal_identification.matcher import PeakAssignment, SignalCandidate
    from maxiv_panda.signal_identification.peak_detection import DetectedPeak

    monkeypatch.setattr(ec, "family_component_offsets", lambda *_args: {"3d5/2": 0.0, "3d3/2": 6.0})
    monkeypatch.setattr(ec, "strongest_component_line", lambda *_args, **_kwargs: "3d5/2")
    peak = DetectedPeak(0, 100.0, 1000.0, 500.0)
    candidate = SignalCandidate(
        element="Xx", line="3d5/2", kind="PE", expected_energy=100.0,
        delta_e=0.0, score=-1.0, confident=True, reliability=90,
        reliability_support=1.0,
    )
    result = ec._enforce_resolved_family_separations(
        [PeakAssignment(peak, [candidate])], photon_energy=500.0,
    )
    assert result[0].best is None
