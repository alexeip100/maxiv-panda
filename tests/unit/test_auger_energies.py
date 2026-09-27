from maxiv_panda.signal_identification.auger_energies import (
    all_auger_energy_entries,
    available_auger_families,
    auger_candidates_near_energy,
    auger_entries_for_selection,
)


def test_oxygen_kll_is_available_as_auger_family():
    assert "KLL" in available_auger_families(["O"])
    rows = auger_entries_for_selection(["O"], ["KLL"])
    assert rows
    assert all(row.element == "O" and row.family == "KLL" for row in rows)
    assert any(row.source.startswith("XPS International") for row in rows)


def test_handbook_auger_positions_are_grouped_into_family_region():
    rows = [row for row in all_auger_energy_entries()
            if row.element == "O" and row.family == "KLL" and row.source.startswith("XPS International")]
    assert len(rows) == 1
    row = rows[0]
    assert row.energy_min_eV == 473.7
    assert row.energy_max_eV == 507.0
    assert "–" in row.energy_text


def test_auger_energy_candidates_use_kinetic_energy_regions():
    rows = auger_candidates_near_energy(487.7, 1.0)
    assert rows
    assert any(entry.element == "O" and entry.family == "KLL" and distance == 0.0
               for entry, distance in rows)
