"""Adapt parsed SPECS/SpecsLab Prodigy ``.xy`` data to PANDA's raw-data shape.

This module is intentionally separate from PANDA's TXT and IBW loaders.  It
accepts the neutral objects produced by :mod:`maxiv_panda.specs_xy_parser` and
returns RegionData-compatible objects: column 0 is the energy axis and columns
1..N are spectra/iterations.  Nothing here is registered in the GUI/loader
dispatch yet; 0.11.83 is an adapter-only milestone.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from datetime import datetime, timezone, timedelta
import re

import numpy as np

from .specs_xy_parser import ParsedSpecsXY, XYAcquisition, XYRegion, parse_specs_xy
from .txt_parser import ParsedTXT, RegionData


MAX_MISSING_FRACTION = 0.5
_AXIS_DECIMALS = 9


def _meta_text(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _metadata_as_text(values: dict[str, Any]) -> dict[str, str]:
    return {str(key): _meta_text(value) for key, value in values.items()}


def _native_energy_scale(parsed: ParsedSpecsXY, region: XYRegion) -> str:
    value = (
        parsed.file_metadata.get("Energy Axis")
        or region.metadata.get("Scan Variable")
        or region.metadata.get("Energy Axis")
        or ""
    )
    low = str(value).lower()
    if "binding" in low:
        return "Binding"
    if "kinetic" in low:
        return "Kinetic"
    return "Unknown"




def _native_intensity_mode(parsed: ParsedSpecsXY) -> str:
    """Return the ordinate convention declared by Prodigy's serializer."""
    raw = str(parsed.file_metadata.get("Count Rate") or "").strip().lower()
    compact = "".join(ch for ch in raw if ch.isalnum())
    if compact in {"countspersecond", "countspers", "cps"}:
        return "cps"
    if compact in {"counts", "count"}:
        return "counts"
    return "unknown"


def _acquisition_summary(acquisitions: list[XYAcquisition]) -> dict[str, str]:
    """Compact region-level summary without duplicating every acquisition block."""
    if not acquisitions:
        return {}
    out: dict[str, str] = {"Number of exported acquisitions": str(len(acquisitions))}
    dates = [str(a.metadata.get("Acquisition Date") or "").strip() for a in acquisitions]
    dates = [d for d in dates if d]
    if dates:
        out["First acquisition"] = dates[0]
        out["Last acquisition"] = dates[-1]
    kinds = [str(a.sub_index_kind or "").strip() for a in acquisitions if a.sub_index_kind]
    if kinds:
        out["Acquisition index kind"] = ", ".join(dict.fromkeys(kinds))
    cycles = [int(a.cycle_index) for a in acquisitions]
    if cycles:
        out["Cycle range"] = f"{min(cycles)} ... {max(cycles)}"
    return out



_ACQ_DATE_RE = re.compile(r"^(?P<dt>.+?)\s+UTC(?P<offset>[+-]\d+(?::?\d{2})?)?$")


def _parse_acquisition_datetime(value: Any) -> datetime | None:
    """Parse Prodigy Acquisition Date to an aware UTC datetime."""
    raw = str(value or "").strip()
    if not raw:
        return None
    m = _ACQ_DATE_RE.match(raw)
    if not m:
        return None
    try:
        dt = datetime.fromisoformat(m.group("dt").strip())
    except ValueError:
        return None
    offset = m.group("offset")
    if offset:
        sign = 1 if offset.startswith("+") else -1
        body = offset[1:]
        if ":" in body:
            hours_s, minutes_s = body.split(":", 1)
        elif len(body) > 2:
            hours_s, minutes_s = body[:-2], body[-2:]
        else:
            hours_s, minutes_s = body, "0"
        try:
            delta = timedelta(hours=int(hours_s), minutes=int(minutes_s)) * sign
        except ValueError:
            return None
        dt = dt.replace(tzinfo=timezone(delta)).astimezone(timezone.utc)
    else:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _varying_numeric(values: list[float]) -> bool:
    arr = np.asarray(values, dtype=float)
    if arr.size < 2 or not np.all(np.isfinite(arr)):
        return False
    span = float(np.nanmax(arr) - np.nanmin(arr))
    scale = max(1.0, float(np.nanmax(np.abs(arr))))
    return span > 1e-9 * scale


def _external_scalar_sequences(region: XYRegion) -> dict[str, list[float]]:
    """Return scalar external-channel sequences in Prodigy's source order.

    Many Prodigy exports keep ``Cycle: 0`` for every repeated Scan while the
    external-channel blocks are nevertheless emitted one-for-one in the same
    order as the spectral acquisitions.  Source order is therefore the most
    reliable association when the block count matches the acquisition count.
    """
    out: dict[str, list[float]] = {}
    for block in region.external_channels:
        data = np.asarray(block.data, dtype=float)
        if data.ndim != 2 or data.shape[0] == 0 or data.shape[1] < 2:
            continue
        vals = np.asarray(data[:, 1], dtype=float)
        vals = vals[np.isfinite(vals)]
        if vals.size == 0:
            continue
        # The external quantity can drift during one swept spectrum (e.g. a
        # temperature ramp).  Use the median over that acquisition as its
        # representative coordinate rather than requiring it to be constant.
        value = float(np.nanmedian(vals))
        out.setdefault(str(block.name).strip(), []).append(value)
    return out


def _clean_external_axis_label(name: str) -> str:
    label = str(name).strip()
    # Keep the physical quantity/unit concise on the plot while retaining the
    # full external-channel name in metadata.
    if "]" in label:
        end = label.find("]")
        if end >= 0:
            return label[: end + 1].strip()
    return label


def _discover_physical_second_axis(
    region: XYRegion, acquisitions: list[XYAcquisition], source_indices: list[int] | None = None
) -> tuple[str, list[float], str] | None:
    """Find one trustworthy physical per-acquisition coordinate for XY maps.

    Precedence is intentionally conservative: a complete varying external
    channel (temperature, pressure, etc.), then exactly one varying Y/Z
    manipulator coordinate, then elapsed acquisition time.  Iteration remains
    the independent sequence coordinate elsewhere in PANDA.
    """
    if len(acquisitions) < 2:
        return None

    # 1) Native Prodigy external channels.  Require a value for every kept
    # acquisition and prefer a unique temperature-like channel when several
    # complete varying channels exist.
    by_name = _external_scalar_sequences(region)
    candidates: list[tuple[str, list[float]]] = []
    for name, vals in by_name.items():
        if source_indices is not None and len(vals) == len(region.acquisitions):
            try:
                vals = [vals[i] for i in source_indices]
            except (IndexError, TypeError):
                continue
        elif len(vals) != len(acquisitions):
            continue
        vals = [float(v) for v in vals]
        if _varying_numeric(vals):
            candidates.append((name, vals))
    if candidates:
        temp = [item for item in candidates if "temp" in item[0].lower()]
        chosen = temp[0] if len(temp) == 1 else (candidates[0] if len(candidates) == 1 else None)
        if chosen is not None:
            name, vals = chosen
            return _clean_external_axis_label(name), vals, f"External channel: {name}"

    # 2) Position-resolved runs.  Promote only when exactly one physical Y/Z
    # coordinate varies across every acquisition.  Generic 'Step' is retained
    # as metadata but is not treated as a physical axis by itself.
    pos_candidates: list[tuple[str, list[float]]] = []
    for key in ("Y [mm]", "Z [mm]"):
        vals: list[float] = []
        ok = True
        for acq in acquisitions:
            try:
                vals.append(float(acq.parameters[key]))
            except (KeyError, TypeError, ValueError):
                ok = False
                break
        if ok and _varying_numeric(vals):
            pos_candidates.append((key, vals))
    if len(pos_candidates) == 1:
        name, vals = pos_candidates[0]
        return name, vals, f"Acquisition parameter: {name}"

    # 3) Time-resolved sequence.  Use actual timestamps and preserve irregular
    # spacing rather than assuming a constant cadence.
    times = [_parse_acquisition_datetime(acq.metadata.get("Acquisition Date")) for acq in acquisitions]
    if all(t is not None for t in times):
        t0 = times[0]
        assert t0 is not None
        vals = [(t - t0).total_seconds() for t in times if t is not None]
        unique_fraction = len({round(float(v), 9) for v in vals}) / max(1, len(vals))
        if len(vals) == len(acquisitions) and _varying_numeric(vals) and unique_fraction >= 0.5:
            return "Elapsed Time [s]", vals, "Acquisition Date"

    return None


def _energy_xlabel(scale: str) -> str:
    if scale == "Binding":
        return "Binding Energy [eV]"
    if scale == "Kinetic":
        return "Kinetic Energy [eV]"
    return "Energy [eV]"


def _axis_key(axis: np.ndarray) -> tuple[float, ...]:
    arr = np.asarray(axis, dtype=float)
    return tuple(np.round(arr, _AXIS_DECIMALS).tolist())


def _reference_energy_axis(acquisitions: list[XYAcquisition]) -> np.ndarray:
    """Return the complete energy grid used by the largest acquisition family.

    The full rounded axis participates in the majority key, rather than only
    first/last/length.  This matters for SnapshotFAT, whose detector energy
    grid can be non-uniform.
    """
    counts: Counter[tuple[float, ...]] = Counter()
    axes: dict[tuple[float, ...], np.ndarray] = {}
    for acq in acquisitions:
        axis = np.asarray(acq.energy, dtype=float)
        if axis.size == 0:
            continue
        key = _axis_key(axis)
        counts[key] += 1
        axes.setdefault(key, axis.copy())
    if not counts:
        raise ValueError("Region contains no acquisition with an energy axis")
    key, _ = counts.most_common(1)[0]
    return axes[key]


def _local_axis_tolerance(reference: np.ndarray) -> np.ndarray:
    """Per-point nearest-neighbour tolerance for possibly non-uniform axes."""
    ref = np.asarray(reference, dtype=float)
    n = ref.size
    if n <= 1:
        return np.full(n, np.inf, dtype=float)
    gaps = np.abs(np.diff(ref))
    tol = np.empty(n, dtype=float)
    tol[0] = gaps[0]
    tol[-1] = gaps[-1]
    if n > 2:
        tol[1:-1] = np.minimum(gaps[:-1], gaps[1:])
    # A little over half the local spacing accepts normal round-off but avoids
    # accidentally assigning a sample to the neighbouring detector bin.
    return np.maximum(tol * 0.55, 1e-9)


def _align_to_reference(reference: np.ndarray, acquisition: XYAcquisition) -> np.ndarray | None:
    """Align one acquisition to ``reference``, padding missing points with NaN.

    The fallback maps against the *actual* reference coordinates and therefore
    also works for non-uniform SnapshotFAT axes.  Acquisitions missing more
    than half the reference points are rejected rather than manufacturing a
    mostly-empty row.
    """
    ref = np.asarray(reference, dtype=float)
    x = np.asarray(acquisition.energy, dtype=float)
    y = np.asarray(acquisition.intensity, dtype=float)
    if x.size != y.size or x.size == 0:
        return None
    if x.size < ref.size * (1.0 - MAX_MISSING_FRACTION):
        return None
    if x.size == ref.size and np.allclose(x, ref, rtol=0.0, atol=1e-8, equal_nan=False):
        return y.copy()

    order = np.argsort(ref)
    sorted_ref = ref[order]
    sorted_tol = _local_axis_tolerance(ref)[order]
    pos = np.searchsorted(sorted_ref, x)
    right = np.clip(pos, 0, len(sorted_ref) - 1)
    left = np.clip(pos - 1, 0, len(sorted_ref) - 1)
    choose_left = np.abs(x - sorted_ref[left]) <= np.abs(x - sorted_ref[right])
    nearest_sorted = np.where(choose_left, left, right)
    distances = np.abs(x - sorted_ref[nearest_sorted])
    valid = distances <= sorted_tol[nearest_sorted]

    aligned = np.full(ref.size, np.nan, dtype=float)
    if np.any(valid):
        target = order[nearest_sorted[valid]]
        aligned[target] = y[valid]
    if np.count_nonzero(np.isfinite(aligned)) < ref.size * (1.0 - MAX_MISSING_FRACTION):
        return None
    return aligned


def _duplicate_safe_region_names(regions: list[XYRegion]) -> list[str]:
    """Keep ordinary names unchanged; disambiguate duplicates with Spectrum ID."""
    counts = Counter(str(region.name).strip() or "Region" for region in regions)
    used: set[str] = set()
    serials: Counter[str] = Counter()
    names: list[str] = []
    for region in regions:
        base = str(region.name).strip() or "Region"
        if counts[base] == 1:
            candidate = base
        else:
            spectrum_id = region.spectrum_id
            candidate = f"{base} [ID {spectrum_id}]" if spectrum_id not in (None, "") else base
        if candidate in used:
            serials[candidate] += 1
            candidate = f"{candidate} #{serials[candidate] + 1}"
        used.add(candidate)
        names.append(candidate)
    return names


@dataclass
class SpecsXYRegionData(RegionData):
    """RegionData-compatible PANDA representation with retained Prodigy provenance."""

    original_region_name: str = ""
    spectrum_id: int | str | None = None
    group_name: str | None = None
    acquisition_metadata: list[dict[str, Any]] = field(default_factory=list)
    external_channels: list[dict[str, Any]] = field(default_factory=list)
    # Prodigy .xy commonly exports count rate directly (``Counts per Second``).
    # Keep that fact on the XY-specific object rather than changing PANDA's
    # shared TXT/IBW intensity conversion rules.
    native_intensity_mode: str = "unknown"


@dataclass
class AdaptedSpecsXY(ParsedTXT):
    """ParsedTXT-compatible container produced by the isolated `.xy` adapter."""

    source_format: str = "SPECS Prodigy XY"


def _acquisition_metadata(acq: XYAcquisition) -> dict[str, Any]:
    out: dict[str, Any] = {
        "Cycle": acq.cycle_index,
        "Curve": acq.curve_index,
        "Source index": acq.sub_index,
        "Source index kind": acq.sub_index_kind,
        "Points": len(acq.energy),
    }
    if acq.sub_index_kind:
        out[acq.sub_index_kind] = acq.sub_index
    out.update(acq.metadata)
    if acq.parameters:
        out["Parameters"] = dict(acq.parameters)
    return out


def _external_channel_summary(region: XYRegion) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for channel in region.external_channels:
        result.append(
            {
                "Cycle": channel.cycle_index,
                "Name": channel.name,
                "Column labels": list(channel.column_labels),
                "Data": np.asarray(channel.data, dtype=float).copy(),
            }
        )
    return result


def adapt_specs_xy(parsed: ParsedSpecsXY) -> AdaptedSpecsXY:
    """Convert neutral Prodigy data into PANDA's existing region-array contract.

    This does not register `.xy` as a loadable GUI format.  It only constructs
    objects shaped like the TXT/IBW normalization boundary so later integration
    can reuse established PANDA workflows without changing TXT/IBW parsers.
    """
    out = AdaptedSpecsXY(path=Path(parsed.path))
    out.file_info = {
        "Format": "SPECS Prodigy XY",
        **_metadata_as_text(parsed.file_metadata),
    }

    display_names = _duplicate_safe_region_names(parsed.regions)
    for index, (region, display_name) in enumerate(zip(parsed.regions, display_names), start=1):
        adapted = SpecsXYRegionData(
            index=index,
            original_region_name=str(region.name),
            spectrum_id=region.spectrum_id,
            group_name=region.group_name,
            native_intensity_mode=_native_intensity_mode(parsed),
        )
        adapted.region_meta = {
            "Region Name": display_name,
            "Original Region Name": str(region.name),
        }
        if region.spectrum_id not in (None, ""):
            adapted.region_meta["Spectrum ID"] = _meta_text(region.spectrum_id)
        if region.group_name:
            adapted.region_meta["Group"] = str(region.group_name)
        adapted.region_meta.update(_metadata_as_text(region.metadata))

        energy_scale = _native_energy_scale(parsed, region)
        adapted.info_meta = {
            "Format": "SPECS Prodigy XY",
            "Energy Scale": energy_scale,
            "Spectrum Name": display_name,
        }
        if adapted.native_intensity_mode == "cps":
            adapted.info_meta["Intensity Unit"] = "counts/s"
        elif adapted.native_intensity_mode == "counts":
            adapted.info_meta["Intensity Unit"] = "counts"
        if region.group_index is not None and 0 <= region.group_index < len(parsed.groups):
            group = parsed.groups[region.group_index]
            if group.metadata:
                adapted.section_meta["SPECS Group"] = _metadata_as_text(group.metadata)

        acquisitions = [acq for acq in region.acquisitions if len(acq.energy) and len(acq.intensity)]
        adapted.acquisition_metadata = [_acquisition_metadata(acq) for acq in acquisitions]
        acquisition_summary = _acquisition_summary(acquisitions)
        if acquisition_summary:
            adapted.section_meta["SPECS Acquisition"] = acquisition_summary
        adapted.external_channels = _external_channel_summary(region)
        if region.external_channels:
            adapted.section_meta["External channels"] = {
                "Number of blocks": str(len(region.external_channels)),
                "Names": ", ".join(dict.fromkeys(ch.name for ch in region.external_channels)),
            }

        if not acquisitions:
            adapted.warnings.append("No spectral acquisition blocks found")
            out.regions.append(adapted)
            continue

        try:
            reference = _reference_energy_axis(acquisitions)
        except ValueError as exc:
            adapted.warnings.append(str(exc))
            out.regions.append(adapted)
            continue

        rows: list[np.ndarray] = []
        kept_meta: list[dict[str, Any]] = []
        kept_acquisitions: list[XYAcquisition] = []
        kept_source_indices: list[int] = []
        for source_index, (acq, meta) in enumerate(zip(acquisitions, adapted.acquisition_metadata)):
            aligned = _align_to_reference(reference, acq)
            if aligned is None:
                adapted.warnings.append(
                    "Discarded incomplete acquisition "
                    f"(Cycle {acq.cycle_index}, Curve {acq.curve_index}, "
                    f"{acq.sub_index_kind or 'Index'} {acq.sub_index})"
                )
                continue
            rows.append(aligned)
            kept_meta.append(meta)
            kept_acquisitions.append(acq)
            kept_source_indices.append(source_index)
        adapted.acquisition_metadata = kept_meta

        if not rows:
            adapted.warnings.append("No compatible spectral acquisitions remained after alignment")
            out.regions.append(adapted)
            continue

        matrix = np.column_stack([reference, np.asarray(rows, dtype=float).T])
        adapted.data = matrix
        adapted.region_meta["Dimension 1 name"] = _energy_xlabel(energy_scale)
        adapted.region_meta["Dimension 1 size"] = str(reference.size)
        adapted.region_meta["Exported acquisitions"] = str(len(rows))
        if len(rows) > 1:
            adapted.region_meta["Dimension 2 size"] = str(len(rows))
            physical_axis = _discover_physical_second_axis(
                region, kept_acquisitions, source_indices=kept_source_indices
            )
            if physical_axis is None:
                adapted.region_meta["Dimension 2 name"] = "Iteration"
                adapted.region_meta["Dimension 2 scale"] = " ".join(
                    str(i) for i in range(1, len(rows) + 1)
                )
            else:
                axis_name, axis_values, axis_source = physical_axis
                adapted.region_meta["Dimension 2 name"] = axis_name
                adapted.region_meta["Dimension 2 scale"] = " ".join(
                    f"{float(value):.12g}" for value in axis_values
                )
                adapted.section_meta["SPECS Physical Y axis"] = {
                    "Axis": axis_name,
                    "Source": axis_source,
                    "Number of values": str(len(axis_values)),
                    "Range": f"{float(min(axis_values)):.12g} ... {float(max(axis_values)):.12g}",
                }

        out.regions.append(adapted)

    return out


def parse_and_adapt_specs_xy(path: str | Path) -> AdaptedSpecsXY:
    """Convenience entry point for tests/future loader integration."""
    return adapt_specs_xy(parse_specs_xy(path))


__all__ = [
    "AdaptedSpecsXY",
    "MAX_MISSING_FRACTION",
    "SpecsXYRegionData",
    "adapt_specs_xy",
    "parse_and_adapt_specs_xy",
]
