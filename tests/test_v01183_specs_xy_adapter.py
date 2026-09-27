from __future__ import annotations

from pathlib import Path

import numpy as np

from maxiv_panda.specs_xy_adapter import adapt_specs_xy, parse_and_adapt_specs_xy
from maxiv_panda.specs_xy_parser import (
    ParsedSpecsXY,
    XYAcquisition,
    XYExternalChannel,
    XYGroup,
    XYRegion,
)
from maxiv_panda.txt_parser import region_to_traces


def _acq(cycle, energy, intensity, *, kind="Scan", sub=0, date=None):
    return XYAcquisition(
        cycle_index=cycle,
        curve_index=0,
        sub_index=sub,
        sub_index_kind=kind,
        metadata={"Acquisition Date": date} if date else {},
        energy=np.asarray(energy, dtype=float),
        intensity=np.asarray(intensity, dtype=float),
    )


def test_single_spectrum_maps_to_regiondata_contract(tmp_path: Path):
    parsed = ParsedSpecsXY(
        path=tmp_path / "one.xy",
        file_metadata={"Energy Axis": "Binding Energy"},
        regions=[XYRegion("C1s", None, None, {"Spectrum ID": 7}, [_acq(0, [3, 2, 1], [10, 11, 12])])],
    )
    adapted = adapt_specs_xy(parsed)
    region = adapted.regions[0]
    assert region.region_name == "C1s"
    assert region.dim1_name() == "Binding Energy [eV]"
    assert region.data.shape == (3, 2)
    np.testing.assert_allclose(region.data[:, 0], [3, 2, 1])
    traces = region_to_traces(region)
    assert len(traces) == 1 and traces[0]["kind"] == "trace"


def test_repeated_acquisitions_become_ordinary_iteration_dimension(tmp_path: Path):
    parsed = ParsedSpecsXY(
        path=tmp_path / "series.xy",
        file_metadata={"Energy Axis": "Kinetic Energy"},
        regions=[XYRegion("VB", None, None, {}, [
            _acq(0, [1, 2, 3], [10, 11, 12], kind="Channel"),
            _acq(1, [1, 2, 3], [20, 21, 22], kind="Channel"),
        ])],
    )
    region = adapt_specs_xy(parsed).regions[0]
    assert region.dim1_name() == "Kinetic Energy [eV]"
    assert region.dim2_name() == "Iteration"
    assert region.dim2_scale() == [1.0, 2.0]
    assert region.data.shape == (3, 3)
    traces = region_to_traces(region)
    assert [t["kind"] for t in traces] == ["average", "iteration", "iteration"]
    assert region.acquisition_metadata[1]["Source index kind"] == "Channel"


def test_nonuniform_reference_axis_and_missing_point_are_aligned(tmp_path: Path):
    energy = np.array([536.35, 536.31, 536.245, 536.17, 536.08])
    parsed = ParsedSpecsXY(
        path=tmp_path / "snapshot.xy",
        file_metadata={"Energy Axis": "Binding Energy"},
        regions=[XYRegion("O1s", None, None, {}, [
            _acq(0, energy, [1, 2, 3, 4, 5], kind="Channel"),
            _acq(1, energy, [6, 7, 8, 9, 10], kind="Channel"),
            _acq(2, energy[[0, 1, 3, 4]], [11, 12, 14, 15], kind="Channel"),
        ])],
    )
    region = adapt_specs_xy(parsed).regions[0]
    np.testing.assert_allclose(region.data[:, 0], energy)
    assert np.isnan(region.data[2, 3])  # missing third energy point in acquisition 3
    assert region.data[3, 3] == 14


def test_badly_incomplete_acquisition_is_discarded(tmp_path: Path):
    e = np.arange(10.0)
    parsed = ParsedSpecsXY(
        path=tmp_path / "bad.xy",
        regions=[XYRegion("R", None, None, {}, [
            _acq(0, e, e),
            _acq(1, e, e + 1),
            _acq(2, e[:3], e[:3] + 2),
        ])],
    )
    region = adapt_specs_xy(parsed).regions[0]
    assert region.data.shape == (10, 3)  # energy + two kept acquisitions
    assert len(region.acquisition_metadata) == 2
    assert any("Discarded incomplete acquisition" in w for w in region.warnings)


def test_duplicate_region_names_use_spectrum_id_only_when_needed(tmp_path: Path):
    parsed = ParsedSpecsXY(
        path=tmp_path / "dup.xy",
        regions=[
            XYRegion("O1s", None, None, {"Spectrum ID": 62}, [_acq(0, [1, 2], [3, 4])]),
            XYRegion("O1s", None, None, {"Spectrum ID": 84}, [_acq(0, [1, 2], [5, 6])]),
            XYRegion("C1s", None, None, {"Spectrum ID": 85}, [_acq(0, [1, 2], [7, 8])]),
        ],
    )
    names = [r.region_name for r in adapt_specs_xy(parsed).regions]
    assert names == ["O1s [ID 62]", "O1s [ID 84]", "C1s"]


def test_group_and_external_channels_are_retained_not_used_as_spectral_axis(tmp_path: Path):
    group = XYGroup("Temperature sweep", {"Scan Mode": "FixedAnalyzerTransmission"})
    ext = XYExternalChannel(
        cycle_index=0,
        name="Sample temperature [K]",
        column_labels=("energy", "temperature"),
        data=np.array([[1.0, 723.0], [2.0, 723.0]]),
    )
    region = XYRegion("Pd3d", 0, group.name, {}, [_acq(0, [1, 2], [3, 4])], [ext])
    adapted = adapt_specs_xy(ParsedSpecsXY(tmp_path / "temp.xy", groups=[group], regions=[region]))
    out = adapted.regions[0]
    assert out.group_name == "Temperature sweep"
    assert out.external_channels[0]["Name"] == "Sample temperature [K]"
    assert out.dim2_size() is None  # one spectrum; temperature is not forced into Y
    assert out.section_meta["External channels"]["Number of blocks"] == "1"


def test_empty_file_remains_valid_and_empty(tmp_path: Path):
    path = tmp_path / "empty.xy"
    path.write_text("# Energy Axis: Binding Energy\n", encoding="latin-1")
    adapted = parse_and_adapt_specs_xy(path)
    assert adapted.regions == []
    assert adapted.file_info["Format"] == "SPECS Prodigy XY"


def test_txt_ibw_modules_are_not_imported_by_adapter_as_loaders():
    # Contract guard: adapter may reuse the neutral RegionData shape, but it
    # must not call or modify TXT/IBW parsing functions.
    import inspect
    import maxiv_panda.specs_xy_adapter as module

    source = inspect.getsource(module)
    assert "parse_structured_txt" not in source
    assert "parse_ibw" not in source
