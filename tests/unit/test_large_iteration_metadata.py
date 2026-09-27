from __future__ import annotations

import numpy as np

from maxiv_panda.ibw_parser import _parse_note
from maxiv_panda.txt_parser import RegionData, region_to_traces


def test_ibw_note_metadata_does_not_duplicate_cis_point_axis_entries():
    note = (
        "Spectrum Name: VB_ResPES\r"
        "Excitation Energy: 770 eV\r"
        "Point 1=770 eV\r"
        "Point 2=770.1 eV\r"
        "Point 3=770.2 eV\r"
    )
    metadata, raw = _parse_note(note)

    assert metadata["Spectrum Name"] == "VB_ResPES"
    assert metadata["Excitation Energy"] == "770 eV"
    assert not any(key.lower().startswith("point ") for key in metadata)
    # The raw note is still returned locally so parse_ibw can recover the
    # physical second-dimension axis before discarding the bulky text.
    assert "Point 3=770.2 eV" in raw


def test_region_to_traces_resolves_dim2_scale_once_and_keeps_leaf_metadata_compact():
    region = RegionData(index=1)
    region.region_meta.update(
        {
            "Region Name": "VB_ResPES",
            "Dimension 1 name": "Binding Energy [eV]",
            "Dimension 1 size": "4",
            "Dimension 2 name": "Photon Energy [eV]",
            "Dimension 2 size": "3",
            "Dimension 2 scale": "770 770.1 770.2",
        }
    )
    region.info_meta.update(
        {
            "Spectrum Name": "VB_ResPES",
            "Energy Scale": "Binding",
            "Wave note": "very large raw note that must not be copied to every leaf",
        }
    )
    region.data = np.array(
        [
            [3.0, 1.0, 2.0, 3.0],
            [2.0, 2.0, 3.0, 4.0],
            [1.0, 3.0, 4.0, 5.0],
            [0.0, 4.0, 5.0, 6.0],
        ],
        dtype=float,
    )

    original_dim2_scale = region.dim2_scale
    calls = 0

    def counted_dim2_scale():
        nonlocal calls
        calls += 1
        return original_dim2_scale()

    region.dim2_scale = counted_dim2_scale  # type: ignore[method-assign]
    traces = region_to_traces(region)

    assert calls == 1
    assert len(traces) == 4  # average + 3 iterations
    assert [trace["iteration_axis_value"] for trace in traces[1:]] == [770.0, 770.1, 770.2]
    for trace in traces:
        metadata = trace["source_metadata"]
        assert "Wave note" not in metadata
        assert "Dimension 2 scale" not in metadata


def test_ibw_note_parses_equals_before_colon_and_preserves_sections():
    from maxiv_panda.ibw_parser import _parse_note_sections

    note = (
        "Region Name=C1s 400eV\r"
        "File=Y:\\20250426\\raw\\XPS_0044.pxt,.ibw,.txt,.zip\r"
        "Time=15:31:52\r"
        "[Run Mode Information]\r"
        "Name=Add Dimension\r"
        "[Manipulator]\r"
        "X=-0.377\rY=5.486\rZ=570.998\rPolar=-107.020\r"
    )
    metadata, _raw = _parse_note(note)
    sections = _parse_note_sections(note)

    assert metadata["Time"] == "15:31:52"
    assert metadata["File"].startswith("Y:\\20250426")
    assert sections["Run Mode Information"]["Name"] == "Add Dimension"
    assert sections["Manipulator"] == {
        "X": "-0.377",
        "Y": "5.486",
        "Z": "570.998",
        "Polar": "-107.020",
    }


def test_txt_parser_preserves_manipulator_and_compacts_run_mode(tmp_path):
    from maxiv_panda.txt_parser import parse_structured_txt

    path = tmp_path / "sample.txt"
    path.write_text(
        "[Info]\nNumber of Regions=0001\nVersion=1.3.1\n"
        "[Region 1]\nRegion Name=VB_ResPES\nDimension 1 name=Binding Energy [eV]\nDimension 1 size=2\n"
        "[Info 1]\nSpectrum Name=VB_ResPES\nEnergy Scale=Binding\n"
        "[Run Mode Information 1]\nName=CIS\nPoint 1=570 eV\nPoint 2=570.1 eV\nPoint 3=570.2 eV\n"
        "[User Interface Information 1]\n"
        "[Manipulator 1]\nX=-0.975\nY=4.949\nZ=576.497\nPolar=-107.050\n"
        "[Data 1]\n1 10\n0 20\n",
        encoding="utf-8",
    )
    parsed = parse_structured_txt(path)
    region = parsed.regions[0]

    assert region.section_meta["Manipulator"] == {
        "X": "-0.975",
        "Y": "4.949",
        "Z": "576.497",
        "Polar": "-107.050",
    }
    assert region.section_meta["Run Mode Information"] == {
        "Name": "CIS",
        "Number of points": "3",
        "Point range": "570 eV ... 570.2 eV",
    }
