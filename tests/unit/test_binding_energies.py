from maxiv_panda.signal_identification.binding_energies import (
    available_binding_elements, available_binding_shells,
    candidates_near_energy, entries_for_selection,
)

def test_element_and_shell_lookup():
    assert "O" in available_binding_elements()
    assert "1s" in available_binding_shells(["O"])
    rows = entries_for_selection(["O"], ["1s"])
    assert rows and all(r.element == "O" and r.transition == "1s" for r in rows)

def test_energy_candidates_are_sorted_and_include_interval_matches():
    rows = candidates_near_energy(531.5, 2.0)
    assert rows
    distances = [distance for _, distance in rows]
    assert distances == sorted(distances)
    assert any(entry.element == "O" and entry.transition == "1s" for entry, _ in rows)

def test_empty_selection_returns_no_rows():
    assert entries_for_selection([]) == ()
