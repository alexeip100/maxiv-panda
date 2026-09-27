"""Streaming parser for SPECS/SpecsLab Prodigy ``.xy`` exports.

This module is deliberately independent of PANDA's TXT/IBW loaders and UI.
It only translates the textual Prodigy hierarchy into neutral Python objects:

    file -> group session -> region -> acquisition block

Prodigy uses several closely related acquisition headers depending on export
settings, e.g. ``Scan`` for separately exported scans and ``Channel`` for
snapshot/channel data.  Those source terms are preserved rather than folded
into PANDA-specific concepts here; a later adapter can decide how to expose a
region as a 1D spectrum or a 2D sequence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


_GROUP_RE = re.compile(r"^#\s*Group:\s*(.*)$")
_REGION_RE = re.compile(r"^#\s*Region:\s*(.*)$")
_CYCLE_ONLY_RE = re.compile(r"^#\s*Cycle:\s*(\d+)\s*$")
_ACQUISITION_RE = re.compile(
    r"^#\s*Cycle:\s*(\d+)"
    r"(?:\s*,\s*Curve:\s*(\d+))?"
    r"(?:\s*,\s*(Scan|Channel):\s*(\d+))?\s*$"
)
_PARAMETER_RE = re.compile(r'^#\s*Parameter:\s*"([^"]+)"\s*=\s*(.*)$')
_EXTERNAL_RE = re.compile(r"^#\s*External Channel Data Cycle:\s*(\d+)\s*,\s*(.*)$")
_COLUMN_LABELS_RE = re.compile(r"^#\s*ColumnLabels:\s*(.*)$")
_KV_RE = re.compile(r"^#\s*([^:]+?):\s*(.*)$")


def _smart_cast(value: str) -> Any:
    """Convert a simple scalar string while preserving non-numeric metadata."""
    text = value.strip()
    if not text:
        return ""
    low = text.lower()
    if low == "yes":
        return True
    if low == "no":
        return False
    try:
        if re.fullmatch(r"[+-]?\d+", text):
            return int(text)
        return float(text)
    except ValueError:
        return text


def _try_numeric_row(line: str) -> tuple[float, ...] | None:
    parts = line.split()
    if len(parts) < 2:
        return None
    try:
        return tuple(float(part) for part in parts)
    except ValueError:
        return None


@dataclass
class XYExternalChannel:
    """One external/non-energy channel block associated with a cycle."""

    cycle_index: int
    name: str
    column_labels: tuple[str, ...] = ()
    data: np.ndarray = field(default_factory=lambda: np.empty((0, 0), dtype=float))


@dataclass
class XYAcquisition:
    """One exported spectral acquisition block within a Prodigy region."""

    cycle_index: int
    curve_index: int = 0
    sub_index: int = 0
    sub_index_kind: str | None = None  # ``Scan``, ``Channel``, or None
    metadata: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    column_labels: tuple[str, ...] = ()
    energy: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=float))
    intensity: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=float))
    extra_columns: np.ndarray | None = None

    def __len__(self) -> int:
        return len(self.energy)


@dataclass
class XYRegion:
    """One ``# Region:`` instance from the file."""

    name: str
    group_index: int | None
    group_name: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    acquisitions: list[XYAcquisition] = field(default_factory=list)
    external_channels: list[XYExternalChannel] = field(default_factory=list)

    @property
    def spectrum_id(self) -> int | str | None:
        return self.metadata.get("Spectrum ID")


@dataclass
class XYGroup:
    """One Prodigy Group session in source-file order."""

    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedSpecsXY:
    """Neutral parsed representation of a SPECS/Prodigy ``.xy`` file."""

    path: Path
    file_metadata: dict[str, Any] = field(default_factory=dict)
    groups: list[XYGroup] = field(default_factory=list)
    regions: list[XYRegion] = field(default_factory=list)

    @property
    def acquisition_count(self) -> int:
        return sum(len(region.acquisitions) for region in self.regions)


def parse_specs_xy(path: str | Path, *, encoding: str = "latin-1") -> ParsedSpecsXY:
    """Parse a SPECS/SpecsLab Prodigy ``.xy`` export in one streaming pass.

    The parser intentionally does *not* convert the result into PANDA's raw
    data model.  In particular it preserves Prodigy's Cycle/Curve/Scan/Channel
    identifiers, repeated region names, group sessions, timestamps, and actual
    sampled energy arrays.  Region-level counters such as ``Number of Scans``
    are kept as metadata but are not used to infer how many acquisition blocks
    really exist; the blocks present in the file are authoritative.
    """

    source = Path(path)
    parsed = ParsedSpecsXY(path=source)

    current_group_index: int | None = None
    current_region: XYRegion | None = None
    current_cycle_parameters: dict[str, Any] = {}

    acq_header: tuple[int, int, str | None, int] | None = None
    acq_metadata: dict[str, Any] = {}
    acq_column_labels: tuple[str, ...] = ()
    acq_rows: list[tuple[float, ...]] = []

    ext_cycle: int | None = None
    ext_name: str | None = None
    ext_column_labels: tuple[str, ...] = ()
    ext_rows: list[tuple[float, ...]] = []

    def flush_acquisition() -> None:
        nonlocal acq_header, acq_metadata, acq_column_labels, acq_rows
        if acq_header is not None and current_region is not None and acq_rows:
            rows = np.asarray(acq_rows, dtype=float)
            cycle, curve, kind, sub_index = acq_header
            current_region.acquisitions.append(
                XYAcquisition(
                    cycle_index=cycle,
                    curve_index=curve,
                    sub_index=sub_index,
                    sub_index_kind=kind,
                    metadata=dict(acq_metadata),
                    parameters=dict(current_cycle_parameters),
                    column_labels=acq_column_labels,
                    energy=rows[:, 0].copy(),
                    intensity=rows[:, 1].copy(),
                    extra_columns=rows[:, 2:].copy() if rows.shape[1] > 2 else None,
                )
            )
        acq_header = None
        acq_metadata = {}
        acq_column_labels = ()
        acq_rows = []

    def flush_external() -> None:
        nonlocal ext_cycle, ext_name, ext_column_labels, ext_rows
        if ext_cycle is not None and ext_name is not None and current_region is not None and ext_rows:
            rows = np.asarray(ext_rows, dtype=float)
            current_region.external_channels.append(
                XYExternalChannel(
                    cycle_index=ext_cycle,
                    name=ext_name,
                    column_labels=ext_column_labels,
                    data=rows,
                )
            )
        ext_cycle = None
        ext_name = None
        ext_column_labels = ()
        ext_rows = []

    def flush_data_blocks() -> None:
        flush_external()
        flush_acquisition()

    with source.open("r", encoding=encoding, errors="replace") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped:
                continue

            if stripped.startswith("#"):
                match = _GROUP_RE.match(stripped)
                if match:
                    flush_data_blocks()
                    group = XYGroup(name=match.group(1).strip())
                    parsed.groups.append(group)
                    current_group_index = len(parsed.groups) - 1
                    current_region = None
                    current_cycle_parameters = {}
                    continue

                match = _REGION_RE.match(stripped)
                if match:
                    flush_data_blocks()
                    group_name = (
                        parsed.groups[current_group_index].name
                        if current_group_index is not None
                        else None
                    )
                    current_region = XYRegion(
                        name=match.group(1).strip(),
                        group_index=current_group_index,
                        group_name=group_name,
                    )
                    parsed.regions.append(current_region)
                    current_cycle_parameters = {}
                    continue

                match = _EXTERNAL_RE.match(stripped)
                if match and current_region is not None:
                    flush_data_blocks()
                    ext_cycle = int(match.group(1))
                    ext_name = match.group(2).strip()
                    continue

                match = _CYCLE_ONLY_RE.match(stripped)
                if match and current_region is not None:
                    flush_data_blocks()
                    current_cycle_parameters = {}
                    continue

                match = _ACQUISITION_RE.match(stripped)
                if match and current_region is not None:
                    flush_data_blocks()
                    cycle = int(match.group(1))
                    curve = int(match.group(2)) if match.group(2) is not None else 0
                    kind = match.group(3)
                    sub_index = int(match.group(4)) if match.group(4) is not None else 0
                    acq_header = (cycle, curve, kind, sub_index)
                    continue

                match = _PARAMETER_RE.match(stripped)
                if match and current_region is not None:
                    current_cycle_parameters[match.group(1)] = _smart_cast(match.group(2))
                    continue

                match = _COLUMN_LABELS_RE.match(stripped)
                if match:
                    labels = tuple(match.group(1).split())
                    if ext_cycle is not None:
                        ext_column_labels = labels
                    elif acq_header is not None:
                        acq_column_labels = labels
                    continue

                match = _KV_RE.match(stripped)
                if match:
                    key = match.group(1).strip()
                    value = _smart_cast(match.group(2))
                    if ext_cycle is not None:
                        # External-channel descriptive comments beyond the
                        # header are uncommon; retain them as file/region
                        # metadata rather than interpreting them as spectra.
                        if current_region is not None:
                            current_region.metadata.setdefault(key, value)
                    elif acq_header is not None:
                        acq_metadata[key] = value
                    elif current_region is not None:
                        current_region.metadata[key] = value
                    elif current_group_index is not None:
                        parsed.groups[current_group_index].metadata[key] = value
                    else:
                        parsed.file_metadata[key] = value
                continue

            row = _try_numeric_row(stripped)
            if row is None:
                continue
            if ext_cycle is not None:
                ext_rows.append(row)
            elif acq_header is not None:
                acq_rows.append(row)

    flush_data_blocks()
    return parsed


__all__ = [
    "ParsedSpecsXY",
    "XYAcquisition",
    "XYExternalChannel",
    "XYGroup",
    "XYRegion",
    "parse_specs_xy",
]
