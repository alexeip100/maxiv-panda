from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np

from maxiv_panda.ibw_parser import parse_ibw
from maxiv_panda.ui_map_plot_mixin import MapPlotMixin


def test_add_dimension_region_iteration_is_not_mislabeled_as_photon_energy(tmp_path, monkeypatch):
    note = "\r".join([
        "[SES]",
        "Version=1.2.5",
        "Region Name=O1s 650eV",
        "Excitation Energy=650",
        "Energy Scale=Binding",
        "[Run Mode Information]",
        "Name=Add Dimension",
        "Counts [a.u.]Binding Energy [eV]Region Iteration[a.u.]",
    ])
    wave = {
        "wData": np.arange(40.0).reshape(10, 4),
        "wave_header": {
            "sfA": np.array([0.1, 1.0, 1.0, 1.0]),
            "sfB": np.array([100.0, 1.0, 0.0, 0.0]),
            "nDim": np.array([10, 4, 0, 0]),
        },
        "dimension_units": b"eV",
        "note": note.encode(),
        "bname": b"O1s_650eV",
    }
    fake_binarywave = SimpleNamespace(load=lambda _path: {"wave": wave})
    fake_igor2 = ModuleType("igor2")
    fake_igor2.binarywave = fake_binarywave
    monkeypatch.setitem(sys.modules, "igor2", fake_igor2)

    path = tmp_path / "XPS_0055O1s 650eV.ibw"
    path.write_bytes(b"placeholder")
    parsed = parse_ibw(path)
    region = parsed.regions[0]

    assert region.region_meta["Dimension 2 name"] == "Region Iteration [a.u.]"
    assert "photon" not in region.region_meta["Dimension 2 name"].lower()
    assert region.dim2_scale() == [1.0, 2.0, 3.0, 4.0]


def test_iteration_secondary_axis_is_not_treated_as_physical_map_axis():
    image = (
        np.arange(3.0), [1, 2, 3, 4], np.zeros((4, 3)), "map", "BE", "viridis",
        [1, 2, 3, 4], "Region Iteration [a.u.]",
    )
    values, label = MapPlotMixin._map_secondary_axis(image, 4)
    assert values is None
    assert label == ""
