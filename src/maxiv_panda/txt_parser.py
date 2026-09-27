from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .energy_utils import infer_energy_scale, normalize_energy_xlabel


_SECTION_RE = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")


@dataclass
class RegionData:
    """One spectral region parsed from a structured TXT export."""

    index: int
    region_meta: dict[str, str] = field(default_factory=dict)
    info_meta: dict[str, str] = field(default_factory=dict)
    # Additional acquisition sections such as ``Manipulator`` and
    # ``Run Mode Information``.  Keeping them grouped preserves the source
    # structure for the metadata viewer without polluting the plotting keys.
    section_meta: dict[str, dict[str, str]] = field(default_factory=dict)
    data: np.ndarray | None = None  # shape (n_points, n_cols)
    warnings: list[str] = field(default_factory=list)

    @property
    def region_name(self) -> str:
        return (
            self.region_meta.get("Region Name")
            or self.info_meta.get("Spectrum Name")
            or f"Region {self.index}"
        )

    def dim1_name(self) -> str:
        return self.region_meta.get("Dimension 1 name", "x")

    def dim1_size(self) -> int | None:
        v = self.region_meta.get("Dimension 1 size")
        if not v:
            return None
        try:
            return int(v)
        except Exception:
            return None

    def dim2_size(self) -> int | None:
        v = self.region_meta.get("Dimension 2 size")
        if not v:
            return None
        try:
            return int(v)
        except Exception:
            return None

    def dim2_name(self) -> str:
        return self.region_meta.get("Dimension 2 name", "").strip()

    def dim2_scale(self) -> list[float] | None:
        raw = self.region_meta.get("Dimension 2 scale", "").strip()
        if not raw:
            return None
        try:
            vals = [float(v) for v in raw.split()]
        except Exception:
            return None
        n = self.dim2_size()
        if n is not None and len(vals) != n:
            return None
        return vals or None


@dataclass
class ParsedTXT:
    path: Path
    file_info: dict[str, str] = field(default_factory=dict)
    regions: list[RegionData] = field(default_factory=list)


def _parse_kv_lines(lines: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for ln in lines:
        if "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        out[k] = v
    return out


def _compact_section_metadata(values: dict[str, str]) -> dict[str, str]:
    """Return compact metadata for an auxiliary acquisition section.

    Scienta CIS/ResPES run-mode blocks may contain hundreds of ``Point N``
    entries.  They are useful for reconstructing the second-dimension axis but
    should not be duplicated into every tree leaf merely for display.
    """
    out: dict[str, str] = {}
    points: list[tuple[int, str]] = []
    point_re = re.compile(r"^Point\s+(\d+)$", re.IGNORECASE)
    for key, value in values.items():
        m = point_re.match(str(key).strip())
        if m:
            points.append((int(m.group(1)), str(value)))
        else:
            out[str(key)] = str(value)
    if points:
        points.sort(key=lambda pair: pair[0])
        out["Number of points"] = str(len(points))
        if len(points) == 1:
            out["Point range"] = points[0][1]
        else:
            out["Point range"] = f"{points[0][1]} ... {points[-1][1]}"
    return out


def _indexed_auxiliary_sections(sections: dict[str, list[str]], index: int) -> dict[str, dict[str, str]]:
    """Collect non-core ``[Section N]`` blocks belonging to one region."""
    suffix = f" {int(index)}"
    core = {f"Region {index}", f"Info {index}", f"Data {index}"}
    out: dict[str, dict[str, str]] = {}
    for name, lines in sections.items():
        if name in core or not name.endswith(suffix):
            continue
        base = name[: -len(suffix)].strip()
        if not base:
            continue
        values = _compact_section_metadata(_parse_kv_lines(lines))
        if values:
            out[base] = values
    return out


def parse_structured_txt(path: Path) -> ParsedTXT:
    """Parse a structured TXT export with [Info]/[Region i]/[Info i]/[Data i] blocks.

    This is designed to be tolerant: it will parse whatever indexed sections exist,
    and it records warnings rather than failing hard when something doesn't match.
    """

    text = path.read_text(encoding="utf-8", errors="replace").splitlines()

    # Collect sections in order, but store by name.
    sections: dict[str, list[str]] = {}
    current_name: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_name, current_lines
        if current_name is not None:
            sections.setdefault(current_name, []).extend(current_lines)
        current_name = None
        current_lines = []

    for ln in text:
        m = _SECTION_RE.match(ln)
        if m:
            flush()
            current_name = m.group("name").strip()
            current_lines = []
        else:
            if current_name is None:
                # Ignore preamble junk.
                continue
            current_lines.append(ln.rstrip("\n"))
    flush()

    parsed = ParsedTXT(path=path)
    parsed.file_info = _parse_kv_lines(sections.get("Info", []))

    # Determine region indices present by scanning section keys.
    idxs: set[int] = set()
    for key in sections.keys():
        for prefix in ("Region ", "Info ", "Data "):
            if key.startswith(prefix):
                tail = key[len(prefix) :].strip()
                if tail.isdigit():
                    idxs.add(int(tail))

    # If Number of Regions exists, also include 1..N (but still tolerate missing blocks).
    try:
        n = int(parsed.file_info.get("Number of Regions", "0"))
        if n > 0:
            idxs.update(range(1, n + 1))
    except Exception:
        pass

    for i in sorted(idxs):
        reg = RegionData(index=i)
        reg.region_meta = _parse_kv_lines(sections.get(f"Region {i}", []))
        reg.info_meta = _parse_kv_lines(sections.get(f"Info {i}", []))
        reg.section_meta = _indexed_auxiliary_sections(sections, i)

        # Data block (numeric)
        data_lines = sections.get(f"Data {i}")
        if not data_lines:
            reg.warnings.append("Missing [Data] block")
            parsed.regions.append(reg)
            continue

        rows: list[np.ndarray] = []
        for ln in data_lines:
            ln = ln.strip()
            if not ln:
                continue
            # Robust: fromstring returns empty if non-numeric.
            arr = np.fromstring(ln, sep=" ")
            if arr.size == 0:
                continue
            rows.append(arr)

        if not rows:
            reg.warnings.append("No numeric rows found in [Data]")
            parsed.regions.append(reg)
            continue

        # Make rectangular array: pad with NaN if needed.
        max_cols = max(r.size for r in rows)
        mat = np.full((len(rows), max_cols), np.nan, dtype=float)
        for r_idx, r in enumerate(rows):
            mat[r_idx, : r.size] = r
        reg.data = mat

        # Basic validations
        dim1 = reg.dim1_size()
        if dim1 is not None and abs(dim1 - mat.shape[0]) > 0:
            reg.warnings.append(
                f"Row count mismatch: Dimension 1 size={dim1} but data rows={mat.shape[0]}"
            )

        dim2 = reg.dim2_size()
        if dim2 is not None:
            expected_cols = 1 + dim2
            if mat.shape[1] != expected_cols:
                reg.warnings.append(
                    f"Column count mismatch: Dimension 2 size={dim2} expects {expected_cols} cols but got {mat.shape[1]}"
                )

        parsed.regions.append(reg)

    return parsed


def region_to_traces(region: RegionData) -> list[dict[str, Any]]:
    """Convert a RegionData into plottable trace dicts.

    Each dict has keys: kind, x, y, title, xlabel, ylabel, region_index.
    """

    if region.data is None:
        return []

    mat = region.data
    xlabel = region.dim1_name()
    ylabel = "Intensity"
    title = region.region_name

    # Energy scale metadata (Binding vs Kinetic). Some files may omit this.
    energy_scale = infer_energy_scale(
        region.info_meta.get("Energy Scale") or region.region_meta.get("Energy Scale") or "",
        hints=[
            region.dim1_name(),
            region.info_meta.get("Spectrum Name") or "",
            region.region_meta.get("Region Name") or "",
            region.info_meta.get("Wave note") or "",
            region.info_meta.get("Axis Label") or "",
            region.info_meta.get("X Label") or "",
            region.info_meta.get("Label") or "",
        ],
    )

    # Normalize the displayed x-axis label from the inferred energy scale when possible.
    # This keeps TXT and IBW behavior consistent even when the raw stored label is generic
    # like just "Energy" or "Energy [eV]".
    xlabel = normalize_energy_xlabel(xlabel, energy_scale)

    # Infer x/y columns.
    if mat.shape[1] == 1:
        x = np.arange(mat.shape[0])
        ys = mat[:, 0:1].T
        labels = ["Trace"]
    else:
        x = mat[:, 0]
        ys = mat[:, 1:].T
        labels = [f"Iteration {k+1}" for k in range(ys.shape[0])]

    n_traces = int(ys.shape[0])
    # Keep tree-item source metadata compact.  Large second-dimension scales
    # are represented explicitly on each iteration by ``iteration_axis_value``
    # and in the cached region stack, so duplicating the full scale string into
    # every leaf only adds QVariant conversion/copy overhead.
    source_metadata = {
        k: v for k, v in region.region_meta.items()
        if k not in {"Dimension 2 scale", "Wave note"}
    }
    source_metadata.update(
        {k: v for k, v in region.info_meta.items() if k != "Wave note"}
    )
    source_sections = {
        str(name): dict(values)
        for name, values in (getattr(region, "section_meta", {}) or {}).items()
        if values
    }
    # Promote the effective acquisition time to an explicit trace field.
    # It is still retained in source_metadata, but the explicit value is robust
    # across Qt tree copies and Processed-data derivatives.
    time_per_channel = source_metadata.get("Time per Spectrum Channel")

    # Parsing a long Dimension-2 scale string is not free.  Resolve it once,
    # not repeatedly for every iteration.
    dim2_name = region.dim2_name()
    dim2_scale = region.dim2_scale()

    out: list[dict[str, Any]] = []

    if ys.shape[0] == 1:
        out.append(
            {
                "kind": "trace",
                "x": x,
                "y": ys[0],
                "title": title,
                "xlabel": xlabel,
                "ylabel": ylabel,
                "energy_scale": energy_scale,
                "region_index": region.index,
                "n_traces": n_traces,
                "source_metadata": source_metadata,
                "section_meta": source_sections,
                "time_per_spectrum_channel": time_per_channel,
            }
        )
        return out

    # Multi-trace: add average + each iteration.
    y_avg = np.nanmean(ys, axis=0)
    out.append(
        {
            "kind": "average",
            "x": x,
            "y": y_avg,
            "title": f"{title} (Average)",
            "xlabel": xlabel,
            "ylabel": ylabel,
            "energy_scale": energy_scale,
            "region_index": region.index,
            "n_traces": n_traces,
            "source_metadata": source_metadata,
            "section_meta": source_sections,
            "time_per_spectrum_channel": time_per_channel,
        }
    )

    for idx, y in enumerate(ys):
        out.append(
            {
                "kind": "iteration",
                "iteration": idx + 1,
                "x": x,
                "y": y,
                "title": f"{title} ({labels[idx]})",
                "xlabel": xlabel,
                "ylabel": ylabel,
                "energy_scale": energy_scale,
                "region_index": region.index,
                "n_traces": n_traces,
                "source_metadata": source_metadata,
                "section_meta": source_sections,
                "time_per_spectrum_channel": time_per_channel,
                "iteration_axis_name": dim2_name,
                "iteration_axis_value": (
                    dim2_scale[idx]
                    if dim2_scale is not None and idx < len(dim2_scale)
                    else None
                ),
            }
        )

    return out
