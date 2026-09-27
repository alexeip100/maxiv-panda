from __future__ import annotations

from pathlib import Path

import numpy as np

from maxiv_panda.specs_xy_adapter import parse_and_adapt_specs_xy
from maxiv_panda.txt_parser import region_to_traces
from maxiv_panda.workflows.normalization.logic import (
    mean_intensity_over_interval,
    normalize_map_rows_at_energy,
)
from maxiv_panda.workflows.peakfit.fit_models import guess_linear_bg_raw


def _write_xy(path: Path, *, kinetic: bool = False) -> Path:
    axis = "Kinetic Energy" if kinetic else "Binding Energy"
    path.write_text(
        f'''# Energy Axis: {axis}\n# Count Rate: Counts per Second\n# Group: XPS\n# Scan Mode: FixedAnalyzerTransmission\n# Region: O1s\n# Spectrum ID: 42\n# Dwell Time: 0.2\n# Cycle: 0, Curve: 0, Scan: 0\n# Acquisition Date: 2026-09-25 10:00:00 UTC\n# ColumnLabels: energy counts/s\n535 10\n534 20\n533 30\n532 40\n# Cycle: 1, Curve: 0, Scan: 1\n# Acquisition Date: 2026-09-25 10:00:02 UTC\n# ColumnLabels: energy counts/s\n535 20\n534 30\n533 40\n532 50\n''',
        encoding="latin-1",
    )
    return path


def test_xy_series_matches_existing_trace_and_map_contract(tmp_path):
    parsed = parse_and_adapt_specs_xy(_write_xy(tmp_path / "series.xy"))
    region = parsed.regions[0]
    traces = region_to_traces(region)

    assert [t["kind"] for t in traces] == ["average", "iteration", "iteration"]
    np.testing.assert_allclose(traces[1]["x"], [535, 534, 533, 532])
    np.testing.assert_allclose(traces[1]["y"], [10, 20, 30, 40])
    np.testing.assert_allclose(traces[2]["y"], [20, 30, 40, 50])
    assert region.dim2_name() == "Elapsed Time [s]"
    assert region.dim2_scale() == [0.0, 2.0]

    # Same x + row-stack contract cached by LoadedTreeController for map views.
    rows = np.vstack([t["y"] for t in traces if t["kind"] == "iteration"])
    assert rows.shape == (2, 4)


def test_xy_descending_energy_works_with_existing_normalization_math(tmp_path):
    region = parse_and_adapt_specs_xy(_write_xy(tmp_path / "series.xy")).regions[0]
    traces = region_to_traces(region)
    x = np.asarray(traces[1]["x"], dtype=float)
    y = np.asarray(traces[1]["y"], dtype=float)

    # Existing normalization helpers accept descending X; no XY branch is needed.
    value = mean_intensity_over_interval(x, y, 533.0, 534.0)
    assert np.isfinite(value)
    assert value > 0

    rows = np.vstack([traces[1]["y"], traces[2]["y"]])
    norm, interval = normalize_map_rows_at_energy(x, rows, 534.0, 1.0)
    assert norm.shape == rows.shape
    assert interval == (533.5, 534.5)
    assert np.all(np.isfinite(norm))


def test_xy_payload_is_ready_for_existing_peakfit_numerics(tmp_path):
    region = parse_and_adapt_specs_xy(_write_xy(tmp_path / "series.xy")).regions[0]
    trace = next(t for t in region_to_traces(region) if t["kind"] == "iteration")
    x = np.asarray(trace["x"], dtype=float)
    y = np.asarray(trace["y"], dtype=float)
    a0, a1 = guess_linear_bg_raw(x, y)
    assert np.isfinite(a0)
    assert np.isfinite(a1)
    assert trace["energy_scale"] == "Binding"
    assert trace["xlabel"] == "Binding Energy [eV]"


def test_xy_kinetic_energy_metadata_reaches_shared_trace_contract(tmp_path):
    region = parse_and_adapt_specs_xy(_write_xy(tmp_path / "kinetic.xy", kinetic=True)).regions[0]
    trace = region_to_traces(region)[0]
    assert trace["energy_scale"] == "Kinetic"
    assert trace["xlabel"] == "Kinetic Energy [eV]"


def test_xy_preserves_native_cps_and_compact_acquisition_provenance(tmp_path):
    region = parse_and_adapt_specs_xy(_write_xy(tmp_path / "series.xy")).regions[0]
    assert region.native_intensity_mode == "cps"
    assert region.info_meta["Intensity Unit"] == "counts/s"
    summary = region.section_meta["SPECS Acquisition"]
    assert summary["Number of exported acquisitions"] == "2"
    assert summary["First acquisition"] == "2026-09-25 10:00:00 UTC"
    assert summary["Last acquisition"] == "2026-09-25 10:00:02 UTC"
    assert summary["Cycle range"] == "0 ... 1"
    assert summary["Acquisition index kind"] == "Scan"


def test_xy_release_does_not_add_xy_logic_to_txt_ibw_or_shared_workflows():
    root = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"
    for rel in (
        "txt_parser.py",
        "ibw_parser.py",
        "workflows/normalization/logic.py",
        "workflows/calibration/calibrate_logic.py",
        "workflows/peakfit/fit_models.py",
        "workflows/peakfit/batch_selection_mixin.py",
    ):
        text = (root / rel).read_text(encoding="utf-8").lower()
        assert "specs_xy" not in text
        assert ".xy" not in text
