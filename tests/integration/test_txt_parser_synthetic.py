from pathlib import Path

import numpy as np

from maxiv_panda.txt_parser import parse_structured_txt, region_to_traces


def test_parse_minimal_structured_txt(tmp_path: Path):
    path = tmp_path / "synthetic.txt"
    path.write_text(
        "[Info]\n"
        "Number of Regions = 1\n"
        "[Region 1]\n"
        "Region Name = O1s\n"
        "Dimension 1 name = Binding Energy [eV]\n"
        "Dimension 1 size = 3\n"
        "Dimension 2 size = 1\n"
        "[Info 1]\n"
        "Spectrum Name = O 1s synthetic\n"
        "Energy Scale = Binding\n"
        "Photon Energy = 650\n"
        "[Data 1]\n"
        "530.0 10\n"
        "531.0 20\n"
        "532.0 11\n",
        encoding="utf-8",
    )
    parsed = parse_structured_txt(path)
    assert len(parsed.regions) == 1
    traces = region_to_traces(parsed.regions[0])
    assert len(traces) == 1
    x = np.asarray(traces[0]["x"], dtype=float)
    y = np.asarray(traces[0]["y"], dtype=float)
    assert np.allclose(x, [530.0, 531.0, 532.0])
    assert np.allclose(y, [10.0, 20.0, 11.0])
    assert traces[0]["energy_scale"] == "Binding"
