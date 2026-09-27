from maxiv_panda.energy_utils import (
    default_flip_for_energy_scale,
    extract_energy_unit,
    infer_energy_scale,
    normalize_energy_xlabel,
)


def test_infer_energy_scale_prefers_explicit_value():
    assert infer_energy_scale("Kinetic", ["Binding Energy [eV]"]) == "Kinetic"


def test_infer_energy_scale_from_common_hints():
    assert infer_energy_scale(None, ["sample_BE"]) == "Binding"
    assert infer_energy_scale(None, ["Kinetic Energy (eV)"]) == "Kinetic"
    assert infer_energy_scale(None, ["counts"]) == "Unknown"


def test_extract_energy_unit_from_brackets_and_parentheses():
    assert extract_energy_unit("Binding Energy [meV]") == "meV"
    assert extract_energy_unit("Energy (eV)") == "eV"
    assert extract_energy_unit("Energy", default="keV") == "keV"


def test_normalize_energy_xlabel_and_flip_defaults():
    assert normalize_energy_xlabel("Energy [eV]", "Binding") == "Binding Energy [eV]"
    assert normalize_energy_xlabel("x", "Kinetic") == "Kinetic Energy [eV]"
    assert default_flip_for_energy_scale("Binding") is True
    assert default_flip_for_energy_scale("Kinetic") is False
    assert default_flip_for_energy_scale("Unknown") is None
