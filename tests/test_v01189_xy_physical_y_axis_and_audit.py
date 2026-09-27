from __future__ import annotations

from pathlib import Path

import numpy as np

from maxiv_panda.specs_xy_adapter import adapt_specs_xy, parse_and_adapt_specs_xy
from maxiv_panda.specs_xy_parser import ParsedSpecsXY, XYAcquisition, XYExternalChannel, XYRegion
from maxiv_panda.txt_parser import region_to_traces


def _acq(cycle: int, *, date: str | None = None, y_mm=None, z_mm=None):
    params = {}
    if y_mm is not None:
        params["Y [mm]"] = y_mm
    if z_mm is not None:
        params["Z [mm]"] = z_mm
    return XYAcquisition(
        cycle_index=cycle,
        metadata={"Acquisition Date": date} if date else {},
        parameters=params,
        energy=np.asarray([3.0, 2.0, 1.0]),
        intensity=np.asarray([10.0 + cycle, 20.0 + cycle, 30.0 + cycle]),
    )


def _ext(cycle: int, value0: float, value1: float | None = None):
    if value1 is None:
        value1 = value0
    return XYExternalChannel(
        cycle_index=cycle,
        name="Sample temperature [K] (Laser heater)",
        column_labels=("energy", "temperature"),
        data=np.asarray([[3.0, value0], [2.0, value1], [1.0, value1]], dtype=float),
    )


def test_varying_external_temperature_becomes_physical_y_and_wins_over_time(tmp_path):
    acqs = [
        _acq(0, date="2026-09-26 10:00:00 UTC"),
        _acq(0, date="2026-09-26 10:00:10 UTC"),
        _acq(0, date="2026-09-26 10:00:20 UTC"),
    ]
    region = XYRegion(
        "Pd3d", None, None, {}, acqs,
        [_ext(0, 700, 702), _ext(0, 720, 722), _ext(0, 740, 742)],
    )
    out = adapt_specs_xy(ParsedSpecsXY(tmp_path / "temp.xy", regions=[region])).regions[0]
    assert out.dim2_name() == "Sample temperature [K]"
    np.testing.assert_allclose(out.dim2_scale(), [702.0, 722.0, 742.0])
    assert out.section_meta["SPECS Physical Y axis"]["Source"].startswith("External channel:")
    traces = region_to_traces(out)
    assert traces[1]["iteration_axis_name"] == "Sample temperature [K]"
    assert traces[2]["iteration_axis_value"] == 722.0


def test_elapsed_time_is_used_when_no_better_physical_axis_exists(tmp_path):
    acqs = [
        _acq(0, date="2026-09-26 10:00:00 UTC"),
        _acq(1, date="2026-09-26 10:00:03 UTC"),
        _acq(2, date="2026-09-26 10:00:08 UTC"),
    ]
    out = adapt_specs_xy(ParsedSpecsXY(tmp_path / "time.xy", regions=[XYRegion("O1s", None, None, {}, acqs)])).regions[0]
    assert out.dim2_name() == "Elapsed Time [s]"
    assert out.dim2_scale() == [0.0, 3.0, 8.0]


def test_coarse_timestamps_fall_back_to_iteration(tmp_path):
    acqs = [
        _acq(i, date=f"2026-09-26 10:00:{i // 4:02d} UTC")
        for i in range(12)
    ]
    out = adapt_specs_xy(ParsedSpecsXY(tmp_path / "coarse.xy", regions=[XYRegion("snap", None, None, {}, acqs)])).regions[0]
    assert out.dim2_name() == "Iteration"
    assert out.dim2_scale() == [float(i) for i in range(1, 13)]


def test_single_varying_position_axis_wins_over_time(tmp_path):
    acqs = [
        _acq(0, date="2026-09-26 10:00:00 UTC", y_mm=0.0, z_mm=2.0),
        _acq(1, date="2026-09-26 10:00:01 UTC", y_mm=0.5, z_mm=2.0),
        _acq(2, date="2026-09-26 10:00:02 UTC", y_mm=1.0, z_mm=2.0),
    ]
    out = adapt_specs_xy(ParsedSpecsXY(tmp_path / "map.xy", regions=[XYRegion("map", None, None, {}, acqs)])).regions[0]
    assert out.dim2_name() == "Y [mm]"
    assert out.dim2_scale() == [0.0, 0.5, 1.0]


def test_ambiguous_two_position_axes_do_not_guess(tmp_path):
    acqs = [
        _acq(0, date="2026-09-26 10:00:00 UTC", y_mm=0.0, z_mm=0.0),
        _acq(1, date="2026-09-26 10:00:01 UTC", y_mm=0.5, z_mm=0.5),
        _acq(2, date="2026-09-26 10:00:02 UTC", y_mm=1.0, z_mm=1.0),
    ]
    out = adapt_specs_xy(ParsedSpecsXY(tmp_path / "ambiguous.xy", regions=[XYRegion("map", None, None, {}, acqs)])).regions[0]
    assert out.dim2_name() == "Elapsed Time [s]"


def test_single_spectrum_does_not_get_artificial_second_axis(tmp_path):
    out = adapt_specs_xy(ParsedSpecsXY(tmp_path / "single.xy", regions=[XYRegion("C1s", None, None, {}, [_acq(0, date="2026-09-26 10:00:00 UTC")])])).regions[0]
    assert out.dim2_size() is None
    assert out.dim2_name() == ""


def test_header_only_and_junk_xy_fail_gracefully_as_empty(tmp_path):
    header = tmp_path / "empty.xy"
    header.write_text("# Energy Axis: Binding Energy\n", encoding="latin-1")
    junk = tmp_path / "junk.xy"
    junk.write_text("this is not spectral data\n", encoding="latin-1")
    assert parse_and_adapt_specs_xy(header).regions == []
    assert parse_and_adapt_specs_xy(junk).regions == []


def test_xy_audit_keeps_txt_ibw_parsers_free_of_xy_logic():
    root = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"
    for rel in ("txt_parser.py", "ibw_parser.py"):
        text = (root / rel).read_text(encoding="utf-8").lower()
        assert "specs_xy" not in text
        assert ".xy" not in text


def test_external_axis_stays_aligned_when_one_bad_acquisition_is_discarded(tmp_path):
    good0 = _acq(0, date="2026-09-26 10:00:00 UTC")
    bad = XYAcquisition(
        cycle_index=1,
        metadata={"Acquisition Date": "2026-09-26 10:00:01 UTC"},
        energy=np.asarray([3.0]),
        intensity=np.asarray([99.0]),
    )
    good2 = _acq(2, date="2026-09-26 10:00:02 UTC")
    region = XYRegion(
        "Pd3d", None, None, {}, [good0, bad, good2],
        [_ext(0, 700), _ext(1, 720), _ext(2, 740)],
    )
    out = adapt_specs_xy(ParsedSpecsXY(tmp_path / "partial.xy", regions=[region])).regions[0]
    assert out.dim2_name() == "Sample temperature [K]"
    assert out.dim2_scale() == [700.0, 740.0]
    assert any("Discarded incomplete acquisition" in warning for warning in out.warnings)
