from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from maxiv_panda.workflows.plotting.io import (
    export_shared_x_csv,
    import_shared_x_csv,
    is_generic_curve_name,
)


@dataclass
class Curve:
    title: str
    x: object
    y: object
    xlabel: str = "Binding Energy [eV]"
    ylabel: str = "Intensity"
    energy_scale: str = "Binding"


def test_csv_roundtrip_with_shared_energy_axis(tmp_path):
    path = tmp_path / "curves.csv"
    curves = [
        Curve("sample A", [0, 1, 2], [2, 3, 4]),
        Curve("sample B", [0, 1, 2], [5, 6, 7]),
    ]
    export_shared_x_csv(path, curves)
    loaded = import_shared_x_csv(path)

    assert [curve.title for curve in loaded] == ["sample A", "sample B"]
    assert np.allclose(loaded[0].x, [0, 1, 2])
    assert np.allclose(loaded[1].y, [5, 6, 7])


def test_export_rejects_mismatched_energy_axes(tmp_path):
    with pytest.raises(ValueError, match="same energy grid"):
        export_shared_x_csv(
            tmp_path / "bad.csv",
            [Curve("A", [0, 1], [1, 2]), Curve("B", [0, 2], [3, 4])],
        )


@pytest.mark.parametrize("name", ["", "<select curve name>", "  <SELECT CURVE NAME>  "])
def test_unresolved_curve_names(name):
    assert is_generic_curve_name(name)


@pytest.mark.parametrize(
    "name",
    ["Curve", "Curve 1", "curve 2", "Spectrum_4", "Unnamed", "entry0001", "CaO 500 K"],
)
def test_user_curve_names_are_accepted(name):
    assert not is_generic_curve_name(name)
