from __future__ import annotations

import csv
from itertools import zip_longest
from pathlib import Path
from typing import Iterable

import numpy as np

from .model import PlottedCurve


def _unique_names(curves: Iterable[PlottedCurve]) -> list[str]:
    used: dict[str, int] = {}
    names: list[str] = []
    for curve in curves:
        base = (curve.custom_name or curve.title or "Curve").strip() or "Curve"
        count = used.get(base, 0) + 1
        used[base] = count
        names.append(base if count == 1 else f"{base} ({count})")
    return names


def export_visible_curves_csv(
    path: str | Path,
    curves: Iterable[PlottedCurve],
    *,
    names: Iterable[str] | None = None,
) -> int:
    """Export visible curves as ordered X/Y column pairs without interpolation.

    ``names`` may be supplied by the panel so CSV headers exactly match the
    names currently displayed for the selected legend mode.
    """
    selected = [curve for curve in curves if curve.visible]
    if not selected:
        raise ValueError("No visible plotted curves to export.")

    if names is None:
        export_names = _unique_names(selected)
    else:
        provided = [str(name).strip() or "<select curve name>" for name in names]
        if len(provided) != len(selected):
            raise ValueError("The number of export names does not match the visible curves.")
        # Explicit panel-provided names must match the read-only curve list
        # exactly. Duplicate names are allowed; the placeholder warning is
        # handled by the panel before export.
        export_names = provided
    header: list[str] = []
    columns: list[list[float]] = []
    for name, curve in zip(export_names, selected):
        header.extend([f"{name} - Energy", f"{name} - Intensity"])
        columns.extend([curve.x.tolist(), curve.y.tolist()])

    output = Path(path)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for row in zip_longest(*columns, fillvalue=""):
            writer.writerow(row)
    return len(selected)


def _as_float(value: str) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if np.isfinite(number) else None


def _paired_curve_name(x_header: str, y_header: str, index: int) -> str:
    for header in (y_header, x_header):
        text = str(header).strip()
        for suffix in (" - Intensity", " - Energy"):
            if text.lower().endswith(suffix.lower()):
                text = text[: -len(suffix)].strip()
                break
        if text:
            return text
    return f"Curve {index}"


def import_curves_csv(path: str | Path) -> list[PlottedCurve]:
    """Read plotted curves from CSV.

    The preferred format is the pair-column format written by
    :func:`export_visible_curves_csv`.  A conventional shared-X format
    (Energy, Curve A, Curve B, ...) is accepted as well.
    """
    source = Path(path)
    with source.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        raise ValueError("The CSV file is empty.")

    header = [str(value).strip() for value in rows[0]]
    data_rows = rows[1:]
    if len(header) < 2:
        raise ValueError("The CSV must contain at least two columns.")

    curves: list[PlottedCurve] = []
    pair_format = (
        len(header) % 2 == 0
        and all(header[i].lower().endswith(" - energy") for i in range(0, len(header), 2))
        and all(header[i].lower().endswith(" - intensity") for i in range(1, len(header), 2))
    )

    if pair_format:
        for pair_index, col in enumerate(range(0, len(header), 2), start=1):
            x_values: list[float] = []
            y_values: list[float] = []
            for row in data_rows:
                x_value = _as_float(row[col]) if col < len(row) else None
                y_value = _as_float(row[col + 1]) if col + 1 < len(row) else None
                if x_value is None or y_value is None:
                    continue
                x_values.append(x_value)
                y_values.append(y_value)
            if not x_values:
                continue
            name = _paired_curve_name(header[col], header[col + 1], pair_index)
            curves.append(
                PlottedCurve(
                    title=name,
                    custom_name=name,
                    x=np.asarray(x_values, dtype=float),
                    y=np.asarray(y_values, dtype=float),
                    xlabel="Energy",
                    ylabel="Intensity",
                    energy_scale="Unknown",
                )
            )
    else:
        x_header = header[0] or "Energy"
        for col in range(1, len(header)):
            x_values: list[float] = []
            y_values: list[float] = []
            for row in data_rows:
                x_value = _as_float(row[0]) if row else None
                y_value = _as_float(row[col]) if col < len(row) else None
                if x_value is None or y_value is None:
                    continue
                x_values.append(x_value)
                y_values.append(y_value)
            if not x_values:
                continue
            name = header[col] or f"Curve {col}"
            curves.append(
                PlottedCurve(
                    title=name,
                    custom_name=name,
                    x=np.asarray(x_values, dtype=float),
                    y=np.asarray(y_values, dtype=float),
                    xlabel=x_header,
                    ylabel="Intensity",
                    energy_scale="Unknown",
                )
            )

    if not curves:
        raise ValueError("No numeric curve data were found in the CSV file.")
    return curves
