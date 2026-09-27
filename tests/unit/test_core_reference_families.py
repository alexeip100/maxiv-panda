from maxiv_panda.signal_identification.core_reference_families import normalized_core_records


def _lines(records, element, family):
    return {
        str(row.get("transition", row.get("line", ""))).strip()
        for row in records
        if str(row.get("element", "")) == element
        and str(row.get("transition", row.get("line", ""))).strip().startswith(family)
    }


def test_ca_2p_is_normalized_to_condensed_anchored_components():
    records = normalized_core_records("Automatic")
    lines = _lines(records, "Ca", "2p")
    assert "2p3/2" in lines
    assert "2p1/2" in lines
    assert "2p" not in lines
    rows = [r for r in records if r.get("element") == "Ca" and r.get("transition") in {"2p3/2", "2p1/2"}]
    assert rows
    assert all(r.get("reference_normalization") == "condensed anchor + atomic splitting" for r in rows)


def test_transition_metal_3p_remains_unresolved_when_atomic_split_is_small():
    records = normalized_core_records("Automatic")
    for element in ("Cr", "Mn", "Fe", "Co", "Ni"):
        lines = _lines(records, element, "3p")
        assert "3p" in lines
        assert "3p3/2" not in lines
        assert "3p1/2" not in lines


def test_well_separated_shallow_family_can_still_be_normalized():
    records = normalized_core_records("Automatic")
    lines = _lines(records, "Ag", "4p")
    assert "4p3/2" in lines
    assert "4p1/2" in lines
    assert "4p" not in lines


def test_gas_mode_preserves_original_reference_rows():
    records = normalized_core_records("Gas")
    lines = _lines(records, "Ca", "2p")
    assert {"2p", "2p3/2", "2p1/2"} <= lines


def test_resolved_mn_2p_has_no_parallel_generic_family_label():
    """Resolved condensed 2p families must not also expose a generic 2p line."""
    records = normalized_core_records("Automatic")
    lines = _lines(records, "Mn", "2p")
    assert "2p3/2" in lines
    assert "2p1/2" in lines
    assert "2p" not in lines
    compound_rows = [
        row for row in records
        if row.get("element") == "Mn"
        and row.get("category") == "handbook_compound"
        and str(row.get("transition", "")).startswith("2p")
    ]
    assert compound_rows
    assert all(row.get("transition") == "2p3/2" for row in compound_rows)


def test_sn_3d_rejects_inconsistent_generic_anchor_that_would_create_second_doublet():
    """A remote generic Sn 3d row must not become a second resolved family."""
    records = normalized_core_records("Automatic")
    rows = [
        row for row in records
        if row.get("element") == "Sn"
        and str(row.get("transition", "")).startswith("3d")
    ]
    assert rows
    energies_5_2 = [
        float(row.get("representative_energy_eV"))
        for row in rows
        if row.get("transition") == "3d5/2"
    ]
    energies_3_2 = [
        float(row.get("representative_energy_eV"))
        for row in rows
        if row.get("transition") == "3d3/2"
    ]
    # Correct elemental/compound 3d5/2 references near 485--487 eV remain.
    assert any(abs(e - 484.9) < 0.2 for e in energies_5_2)
    assert any(486.0 <= e <= 487.5 for e in energies_5_2)
    # The inconsistent generic 497.2 eV family row must not be relabelled as
    # another 3d5/2 anchor, which previously produced a false ~505/497 pair.
    assert not any(e > 492.0 for e in energies_5_2)
    assert any(abs(e - 493.3) < 0.2 for e in energies_3_2)
