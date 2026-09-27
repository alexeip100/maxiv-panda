from maxiv_panda.signal_identification.cross_sections import (
    available_elements, available_subshells, cross_section_at,
    family_cross_section_at, get_cross_section_curve,
)


def test_cross_section_api_exposes_curves_for_future_gui():
    assert "Ni" in available_elements()
    assert "2p3/2" in available_subshells("Ni")
    curve = get_cross_section_curve("Ni", "2p3/2")
    assert curve is not None
    assert curve.photon_energy_eV.size > 10
    assert curve.photon_energy_eV.size == curve.cross_section_mb.size
    assert curve.photon_energy_eV.flags.writeable is False


def test_log_interpolation_and_family_sum():
    value = cross_section_at("Co", "3p3/2", 1215.0)
    family = family_cross_section_at("Co", "3p", 1215.0)
    assert value is not None and value > 0
    assert family is not None and family > value
    assert cross_section_at("Co", "3p3/2", 100000.0) is None
