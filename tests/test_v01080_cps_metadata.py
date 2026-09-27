from pathlib import Path

from maxiv_panda.intensity_units import time_per_spectrum_channel
from maxiv_panda.ibw_parser import _parse_note
from maxiv_panda.txt_parser import RegionData, parse_structured_txt, region_to_traces


def test_time_per_channel_accepts_explicit_curve_metadata():
    assert time_per_spectrum_channel({"time_per_spectrum_channel": "87.33"}) == 87.33


def test_time_per_channel_recovers_nested_scienta_metadata():
    meta = {"section_meta": {"Info": {"Time per Spectrum Channel": "29.11"}}}
    assert time_per_spectrum_channel(meta) == 29.11


def test_region_to_traces_promotes_time_per_channel_for_txt_and_ibw_style_region():
    region = RegionData(index=1)
    region.region_meta = {
        "Region Name": "S2p_700eV",
        "Dimension 1 name": "Binding Energy [eV]",
        "Dimension 1 size": "2",
    }
    region.info_meta = {
        "Energy Scale": "Binding",
        "Time per Spectrum Channel": "87.33",
    }
    import numpy as np
    region.data = np.array([[168.0, 1000.0], [167.975, 1100.0]])
    trace = region_to_traces(region)[0]
    assert trace["time_per_spectrum_channel"] == "87.33"
    assert time_per_spectrum_channel({
        "time_per_spectrum_channel": trace["time_per_spectrum_channel"],
        "source_metadata": trace["source_metadata"],
    }) == 87.33


def test_ibw_note_parser_preserves_time_per_spectrum_channel():
    note = (
        b"Spectrum Name=XPS_017\r"
        b"Time=02:18:21\r"
        b"Time per Spectrum Channel=10\r"
        b"DetectorMode=ADC\r"
    )
    kv, _raw = _parse_note(note)
    assert kv["Time per Spectrum Channel"] == "10"


def test_uploaded_xps_0022_all_regions_have_promoted_cps_time():
    path = Path("/mnt/data/XPS_0022(2).txt")
    if not path.exists():
        return
    parsed = parse_structured_txt(path)
    expected = [5.945, 29.11, 87.33, 87.33, 291.1]
    got = []
    for region in parsed.regions:
        trace = region_to_traces(region)[0]
        got.append(float(trace["time_per_spectrum_channel"]))
    assert got == expected
