from maxiv_panda.signal_identification.reference_search import (
    auger_ke_to_apparent_be_interval,
    candidates_in_be_region,
)


def test_auger_interval_is_reversed_onto_binding_energy_scale():
    lo, hi = auger_ke_to_apparent_be_interval(480.0, 500.0, 1000.0)
    assert lo == 500.0
    assert hi == 520.0


def test_default_region_search_returns_core_levels_only():
    candidates = candidates_in_be_region(493.0, 526.5)
    assert candidates
    assert all(candidate.kind == "core" for candidate in candidates)


def test_optional_auger_search_adds_auger_candidates():
    candidates = candidates_in_be_region(
        493.0, 526.5, 1000.0, include_auger=True
    )
    assert any(candidate.kind == "auger" and candidate.entry.element == "O" for candidate in candidates)
    assert any(candidate.kind == "core" for candidate in candidates)


def test_auger_search_requires_positive_photon_energy():
    try:
        candidates_in_be_region(493.0, 526.5, None, include_auger=True)
    except ValueError:
        pass
    else:
        raise AssertionError("Auger search should require photon energy")


def test_search_orders_by_binding_energy_position():
    candidates = candidates_in_be_region(0.0, 1000.0)
    positions = [candidate.representative_be_eV for candidate in candidates]
    assert positions == sorted(positions)
