from pathlib import Path

from maxiv_panda.file_naming import make_loaded_curve_key
from maxiv_panda.txt_parser import parse_structured_txt


def test_region_name_prefers_region_block_over_generic_spectrum_name(tmp_path: Path):
    text = """[Info]\nNumber of Regions=0002\nVersion=1.3.1\n\n[Region 1]\nRegion Name=C1s_400eV\nDimension 1 name=Binding Energy [eV]\nDimension 1 size=2\n[Info 1]\nSpectrum Name=XPS_022\nEnergy Scale=Binding\n[Data 1]\n1 10\n0 11\n\n[Region 2]\nRegion Name=O1s_650eV\nDimension 1 name=Binding Energy [eV]\nDimension 1 size=2\n[Info 2]\nSpectrum Name=XPS_022\nEnergy Scale=Binding\n[Data 2]\n1 20\n0 21\n"""
    path = tmp_path / "XPS_0022.txt"
    path.write_text(text, encoding="utf-8")
    parsed = parse_structured_txt(path)
    assert [r.region_name for r in parsed.regions] == ["C1s_400eV", "O1s_650eV"]


def test_loaded_curve_keys_remain_unique_for_same_display_name():
    k1 = make_loaded_curve_key("XPS_0022.txt", "XPS_022", "Trace", 1)
    k2 = make_loaded_curve_key("XPS_0022.txt", "XPS_022", "Trace", 2)
    assert k1 != k2
    assert "#1" in k1 and "#2" in k2
