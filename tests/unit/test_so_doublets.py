from maxiv_panda.workflows.peakfit import so_doublets


def _peaks():
    return [
        {"label":"A", "E":100.0, "H":200.0, "L":0.2, "G":0.3, "A":0.0},
        {"label":"B", "E":101.2, "H":100.0, "L":0.2, "G":0.3, "A":0.0},
        {"label":"C", "E":105.0, "H":50.0, "L":0.25, "G":0.35, "A":0.01},
    ]


def test_statistical_ratios_are_only_starting_values():
    assert so_doublets.statistical_ratio("p") == 2.0
    assert so_doublets.statistical_ratio("d") == 1.5
    assert abs(so_doublets.statistical_ratio("f") - 4/3) < 1e-12


def test_group_state_derives_split_and_ratio_from_existing_peaks():
    s = so_doublets.derive_state_from_peaks(1, 2, _peaks(), orbital="p")
    assert abs(s["split"] - 1.2) < 1e-12
    assert abs(s["ratio"] - 2.0) < 1e-12
    assert s["L_relation"] == "Same"
    assert s["G_relation"] == "Same"
    assert s["A_relation"] == "Same"


def test_minor_energy_direction_follows_energy_scale():
    s = so_doublets.derive_state_from_peaks(1, 2, _peaks(), orbital="p")
    m = {"E":100.0, "H":200.0, "L":0.2, "G":0.3, "A":0.0}
    be = so_doublets.derived_minor_values(s, m, energy_scale="Binding")
    ke = so_doublets.derived_minor_values(s, m, energy_scale="Kinetic")
    assert be["E"] == 101.2
    assert ke["E"] == 98.8
    assert be["H"] == 100.0


def test_delete_remaps_or_removes_doublets():
    d1 = so_doublets.derive_state_from_peaks(2, 3, _peaks(), ordinal=1)
    assert so_doublets.remap_after_peak_delete([d1], 2) == []
    d2 = {**d1, "major": 2, "minor": 3}
    remapped = so_doublets.remap_after_peak_delete([d2], 1)
    assert remapped[0]["major"] == 1 and remapped[0]["minor"] == 2


def test_p_d_f_grouping_uses_statistical_start_ratio_not_measured_ratio():
    peaks = _peaks()
    peaks[1]["H"] = 40.0  # measured ratio would be 5, deliberately far from textbook p value
    p = so_doublets.derive_state_from_peaks(1, 2, peaks, orbital="p")
    d = so_doublets.derive_state_from_peaks(1, 2, peaks, orbital="d")
    custom = so_doublets.derive_state_from_peaks(1, 2, peaks, orbital="Custom")
    assert p["ratio"] == 2.0
    assert d["ratio"] == 1.5
    assert custom["ratio"] == 5.0


def test_clone_doublet_is_shifted_weaker_and_preserves_definition():
    peaks = [
        {"label":"S major", "E":162.0, "E_min":160.0, "E_max":164.0, "E_mode":"Free",
         "H":1000.0, "H_min":100.0, "H_max":2000.0, "H_mode":"Free", "L":0.4, "L_min":0.2, "L_max":0.8, "L_mode":"Free", "G":0.5, "G_min":0.2, "G_max":1.0, "G_mode":"Free", "A":0.03, "A_min":0.0, "A_max":0.1, "A_mode":"Fixed"},
        {"label":"S minor", "E":163.2, "E_min":161.2, "E_max":165.2, "E_mode":"Free",
         "H":500.0, "H_min":50.0, "H_max":1000.0, "H_mode":"Free", "L":0.4, "L_min":0.2, "L_max":0.8, "L_mode":"Free", "G":0.5, "G_min":0.2, "G_max":1.0, "G_mode":"Free", "A":0.03, "A_min":0.0, "A_max":0.1, "A_mode":"Fixed"},
    ]
    src = so_doublets.derive_state_from_peaks(1, 2, peaks, ordinal=1, orbital="p")
    src.update({"split_mode":"Free", "ratio_mode":"Free", "L_relation":"Same", "G_relation":"Independent", "A_relation":"Same"})
    clone, major, minor, shift = so_doublets.clone_doublet_definition(
        src, peaks[0], peaks[1], new_major_index=3, new_minor_index=4, ordinal=2,
        energy_scale="Binding", label="S 2p #2"
    )
    assert shift == 1.0
    assert major["E"] == 163.0 and minor["E"] == 164.2
    assert major["H"] == 400.0 and minor["H"] == 200.0
    assert major["L"] == peaks[0]["L"] and minor["G"] == peaks[1]["G"]
    assert clone["split"] == src["split"] and clone["split_mode"] == "Free"
    assert clone["ratio"] == src["ratio"] and clone["ratio_mode"] == "Free"
    assert clone["G_relation"] == "Independent"
    assert clone["major"] == 3 and clone["minor"] == 4
    assert clone["label"] == "S 2p #2"


def test_clone_doublet_shift_reverses_on_kinetic_energy_scale():
    peaks = _peaks()[:2]
    src = so_doublets.derive_state_from_peaks(1, 2, peaks, orbital="p")
    _clone, major, minor, shift = so_doublets.clone_doublet_definition(
        src, peaks[0], peaks[1], new_major_index=3, new_minor_index=4,
        ordinal=2, energy_scale="Kinetic"
    )
    assert shift == -1.0
    assert major["E"] == 99.0 and minor["E"] == 100.2


def test_doublet_family_numbering_is_independent_of_peak_labels():
    labels, new_label = so_doublets.renumber_doublet_family("S 2p", [])
    assert labels == []
    assert new_label == "S 2p #1"
    labels, new_label = so_doublets.renumber_doublet_family("S 2p #1", ["S 2p #1"])
    assert labels == ["S 2p #1"]
    assert new_label == "S 2p #2"
    labels, new_label = so_doublets.renumber_doublet_family("S 2p (2)", ["S 2p", "S 2p (2)"])
    assert labels == ["S 2p #1", "S 2p #2"]
    assert new_label == "S 2p #3"
    labels, new_label = so_doublets.renumber_doublet_family("Doublet", ["Doublet #1", "Doublet #2"])
    assert new_label == "Doublet #3"


def test_exact_doublet_ties_resolve_for_live_preview():
    d1 = {**so_doublets.derive_state_from_peaks(1, 2, _peaks(), ordinal=1), "split": 1.4, "ratio": 1.8}
    d2 = {**so_doublets.derive_state_from_peaks(2, 3, _peaks(), ordinal=2),
          "split_mode": "Tied", "split_tie_target": 1,
          "ratio_mode": "Tied", "ratio_tie_target": 1}
    resolved = so_doublets.resolve_tied_values([d1, d2])
    assert resolved[1]["split"] == 1.4
    assert resolved[1]["ratio"] == 1.8


def test_removing_tie_source_falls_back_to_fixed_and_remaps_other_targets():
    d1 = {**so_doublets.derive_state_from_peaks(1, 2, _peaks(), ordinal=1), "label": "A"}
    d2 = {**so_doublets.derive_state_from_peaks(1, 2, _peaks(), ordinal=2), "label": "B",
          "split_mode": "Tied", "split_tie_target": 1}
    d3 = {**so_doublets.derive_state_from_peaks(1, 2, _peaks(), ordinal=3), "label": "C",
          "ratio_mode": "Tied", "ratio_tie_target": 2}
    remapped = so_doublets.remap_after_doublet_delete([d1, d2, d3], 1)
    assert remapped[0]["split_mode"] == "Fixed" and remapped[0]["split_tie_target"] is None
    assert remapped[1]["ratio_mode"] == "Tied" and remapped[1]["ratio_tie_target"] == 1


def test_doublet_family_numbering_numbers_first_sibling_immediately():
    labels, new_label = so_doublets.renumber_doublet_family("S 2p", ["S 2p", "Other"])
    assert labels == ["S 2p #1", "Other"]
    assert new_label == "S 2p #2"
    labels, new_label = so_doublets.renumber_doublet_family("S 2p #2", ["S 2p", "S 2p #2"])
    assert labels == ["S 2p #1", "S 2p #2"]
    assert new_label == "S 2p #3"
