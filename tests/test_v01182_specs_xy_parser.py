from __future__ import annotations

import importlib
import sys
from pathlib import Path

import numpy as np

from maxiv_panda.specs_xy_parser import parse_specs_xy


def _write_xy(tmp_path: Path, body: str, name: str = "sample.xy") -> Path:
    path = tmp_path / name
    path.write_text(body.strip() + "\n", encoding="latin-1")
    return path


def test_parser_preserves_file_group_region_and_scan_hierarchy(tmp_path):
    path = _write_xy(
        tmp_path,
        r'''
# Created by: SpecsLab Prodigy, Version 4.137.2-r131684
# Energy Axis: Binding Energy
# Group: Test group
# Scan Mode: FixedAnalyzerTransmission
# Region: O1s
# Spectrum ID: 42
# Number of Scans: 99
# Cycle: 0
# Cycle: 0, Curve: 2, Scan: 7
# Acquisition Date: 2023-10-27 08:34:22 UTC
# ColumnLabels: energy counts/s
535.0  10.0
534.5  20.0
''',
    )
    parsed = parse_specs_xy(path)

    assert parsed.file_metadata["Created by"] == "SpecsLab Prodigy, Version 4.137.2-r131684"
    assert parsed.file_metadata["Energy Axis"] == "Binding Energy"
    assert [g.name for g in parsed.groups] == ["Test group"]
    assert parsed.groups[0].metadata["Scan Mode"] == "FixedAnalyzerTransmission"
    assert len(parsed.regions) == 1

    region = parsed.regions[0]
    assert region.name == "O1s"
    assert region.group_index == 0
    assert region.group_name == "Test group"
    assert region.spectrum_id == 42
    # Nominal metadata is retained, but the real number of exported blocks is
    # determined from what is physically present in the file.
    assert region.metadata["Number of Scans"] == 99
    assert len(region.acquisitions) == 1

    acq = region.acquisitions[0]
    assert (acq.cycle_index, acq.curve_index, acq.sub_index_kind, acq.sub_index) == (0, 2, "Scan", 7)
    assert acq.metadata["Acquisition Date"] == "2023-10-27 08:34:22 UTC"
    np.testing.assert_allclose(acq.energy, [535.0, 534.5])
    np.testing.assert_allclose(acq.intensity, [10.0, 20.0])


def test_snapshot_channel_blocks_keep_cycle_parameters_and_nonuniform_axis(tmp_path):
    path = _write_xy(
        tmp_path,
        r'''
# Energy Axis: Binding Energy
# Group: Snapshot
# Scan Mode: SnapshotFAT
# Region: C1s
# Spectrum ID: 25
# Cycle: 0
# Parameter: "Step" = 1
# Parameter: "Y [mm]" = 2
# Parameter: "Z [mm]" = -2.1
# Cycle: 0, Curve: 0, Channel: 0
# Acquisition Date: 2023-10-27 13:30:13 UTC
# ColumnLabels: energy counts/s
290.000  1
289.963  2
289.901  3
# Cycle: 1
# Parameter: "Step" = 2
# Parameter: "Y [mm]" = 2
# Parameter: "Z [mm]" = -2.0
# Cycle: 1, Curve: 0, Channel: 0
# Acquisition Date: 2023-10-27 13:30:16 UTC
# ColumnLabels: energy counts/s
290.000  4
289.963  5
289.901  6
''',
    )
    region = parse_specs_xy(path).regions[0]

    assert len(region.acquisitions) == 2
    assert [a.sub_index_kind for a in region.acquisitions] == ["Channel", "Channel"]
    assert [a.cycle_index for a in region.acquisitions] == [0, 1]
    assert region.acquisitions[0].parameters == {"Step": 1, "Y [mm]": 2, "Z [mm]": -2.1}
    assert region.acquisitions[1].parameters["Step"] == 2
    # The parser preserves the actual sampled points; it does not rebuild a
    # synthetic evenly-spaced SnapshotFAT axis from nominal metadata.
    np.testing.assert_allclose(region.acquisitions[0].energy, [290.000, 289.963, 289.901])


def test_bare_curve_header_is_valid_when_scans_are_not_separated(tmp_path):
    path = _write_xy(
        tmp_path,
        r'''
# Separate Scan Data: no
# Separate Channel Data: no
# Group: XPS
# Region: Co2p
# Spectrum ID: 5
# Number of Scans: 10
# Cycle: 0
# Cycle: 0, Curve: 0
# ColumnLabels: energy counts/s
805  100
804  110
''',
    )
    region = parse_specs_xy(path).regions[0]
    assert region.metadata["Number of Scans"] == 10
    assert len(region.acquisitions) == 1
    acq = region.acquisitions[0]
    assert acq.sub_index_kind is None
    assert acq.sub_index == 0


def test_external_channel_blocks_are_separate_from_spectral_data(tmp_path):
    path = _write_xy(
        tmp_path,
        r'''
# External Channel Data: yes
# Group: Heating
# Region: C 1s
# Spectrum ID: 31
# Cycle: 0
# Cycle: 0, Curve: 0, Scan: 0
# ColumnLabels: energy counts/s
290.0  100
289.9  110
# External Channel Data Cycle: 0, Sample temperature [K] (Laser heater)
# ColumnLabels: energy Sample temperature [K] (Laser heater)
290.0  723
289.9  723
# Cycle: 1
# Cycle: 1, Curve: 0, Scan: 1
# ColumnLabels: energy counts/s
290.0  120
289.9  130
# External Channel Data Cycle: 1, Sample temperature [K] (Laser heater)
# ColumnLabels: energy Sample temperature [K] (Laser heater)
290.0  724
289.9  724
''',
    )
    region = parse_specs_xy(path).regions[0]

    assert len(region.acquisitions) == 2
    assert len(region.external_channels) == 2
    np.testing.assert_allclose(region.acquisitions[0].intensity, [100, 110])
    assert region.external_channels[0].name == "Sample temperature [K] (Laser heater)"
    np.testing.assert_allclose(region.external_channels[0].data[:, 1], [723, 723])
    np.testing.assert_allclose(region.external_channels[1].data[:, 1], [724, 724])


def test_repeated_region_and_group_names_keep_source_order_and_identity(tmp_path):
    path = _write_xy(
        tmp_path,
        r'''
# Group: A
# Region: O1s
# Spectrum ID: 1
# Cycle: 0, Scan: 0
# ColumnLabels: energy counts/s
1 10
# Region: O1s
# Spectrum ID: 2
# Cycle: 0, Scan: 0
# ColumnLabels: energy counts/s
1 20
# Group: A
# Region: O1s
# Spectrum ID: 3
# Cycle: 0, Scan: 0
# ColumnLabels: energy counts/s
1 30
''',
    )
    parsed = parse_specs_xy(path)
    assert [g.name for g in parsed.groups] == ["A", "A"]
    assert [r.spectrum_id for r in parsed.regions] == [1, 2, 3]
    assert [r.group_index for r in parsed.regions] == [0, 0, 1]


def test_empty_prodigy_export_is_valid_and_has_no_regions(tmp_path):
    path = _write_xy(
        tmp_path,
        r'''
# Created by: SpecsLab Prodigy, Version 4.140.1-r133300
# Energy Axis: Binding Energy
# Group: Optimisation
# Scan Mode: FixedEnergies
''',
    )
    parsed = parse_specs_xy(path)
    assert len(parsed.groups) == 1
    assert parsed.regions == []
    assert parsed.acquisition_count == 0


def test_extra_numeric_columns_are_preserved_without_redefining_energy_intensity(tmp_path):
    path = _write_xy(
        tmp_path,
        r'''
# Group: Test
# Region: R
# Cycle: 0, Scan: 0
# ColumnLabels: energy counts/s auxiliary
3  30  300
2  20  200
''',
    )
    acq = parse_specs_xy(path).regions[0].acquisitions[0]
    np.testing.assert_allclose(acq.energy, [3, 2])
    np.testing.assert_allclose(acq.intensity, [30, 20])
    np.testing.assert_allclose(acq.extra_columns, [[300], [200]])


def test_specs_xy_parser_is_not_wired_into_txt_or_ibw_runtime_paths():
    """0.11.82 is parser-only: importing it must not pull in old loaders."""
    watched = {
        "maxiv_panda.txt_parser",
        "maxiv_panda.ibw_parser",
        "maxiv_panda.loaders",
    }
    before = {name: name in sys.modules for name in watched}
    module = importlib.import_module("maxiv_panda.specs_xy_parser")
    assert module is not None
    for name in watched:
        if not before[name]:
            assert name not in sys.modules
