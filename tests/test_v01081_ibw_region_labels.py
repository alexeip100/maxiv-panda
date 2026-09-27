from maxiv_panda.file_naming import format_curve_source_label
from maxiv_panda.ibw_parser import _choose_region_name_from_metadata


def test_ibw_prefers_region_name_over_generic_spectrum_name():
    meta = {
        "Region Name": "S2p_700eV",
        "Spectrum Name": "XPS_022_2",
    }
    name = _choose_region_name_from_metadata(meta, "XPS_022_2", "XPS_022_2")
    assert name == "S2p_700eV"
    assert format_curve_source_label("XPS_0022XPS_022_2.ibw", name) == "0022: S2p_700eV"


def test_ibw_region_name_matches_representative_flexpes_note():
    meta = {
        "Region Name": "VB_ResPES",
        "Spectrum Name": "XPS_017",
    }
    assert _choose_region_name_from_metadata(meta, "XPS_017", "XPS_017") == "VB_ResPES"


def test_ibw_falls_back_to_spectrum_name_when_region_name_missing():
    meta = {"Spectrum Name": "C1s_400eV"}
    assert _choose_region_name_from_metadata(meta, "C1s", "C1s_400eV") == "C1s_400eV"
