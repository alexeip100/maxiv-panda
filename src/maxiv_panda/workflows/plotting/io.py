from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


_CURVE_NAME_PLACEHOLDER = "<select curve name>"


@dataclass
class ImportedCurve:
    title: str
    x: np.ndarray
    y: np.ndarray
    xlabel: str = "Energy"
    ylabel: str = "Intensity"
    energy_scale: str = "Unknown"


def is_generic_curve_name(name: str) -> bool:
    """Return True only for an empty name or the unresolved GUI placeholder."""
    text = str(name or "").strip()
    return not text or text.casefold() == _CURVE_NAME_PLACEHOLDER.casefold()


def _sniff_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        return csv.excel


def import_shared_x_csv(path: str | Path) -> list[ImportedCurve]:
    """Read a CSV containing one x column followed by one or more y columns.

    The first row is treated as a header when its first cell is non-numeric.
    Comma, semicolon and tab delimiters are accepted.
    """
    src = Path(path)
    text = src.read_text(encoding="utf-8-sig")
    if not text.strip():
        raise ValueError("The selected CSV file is empty.")

    dialect = _sniff_dialect(text[:4096])
    rows = list(csv.reader(text.splitlines(), dialect))
    rows = [[cell.strip() for cell in row] for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("The selected CSV file contains no data.")

    def _is_number(value: str) -> bool:
        try:
            float(value)
            return True
        except (TypeError, ValueError):
            return False

    has_header = not rows[0] or not _is_number(rows[0][0])
    header = rows.pop(0) if has_header else []
    if not rows:
        raise ValueError("The selected CSV file contains no numeric rows.")

    width = max(len(row) for row in rows)
    if width < 2:
        raise ValueError("CSV must contain an energy column and at least one curve column.")

    numeric_rows: list[list[float]] = []
    for line_no, row in enumerate(rows, start=2 if has_header else 1):
        if len(row) < width:
            row = row + [""] * (width - len(row))
        try:
            numeric_rows.append([float(cell) for cell in row[:width]])
        except ValueError as exc:
            raise ValueError(f"Non-numeric value on CSV line {line_no}.") from exc

    values = np.asarray(numeric_rows, dtype=float)
    x = values[:, 0]
    finite_x = np.isfinite(x)
    if np.count_nonzero(finite_x) < 2:
        raise ValueError("The energy column must contain at least two finite values.")

    xlabel = header[0].strip() if header else "Energy"
    xlabel_lower = xlabel.lower()
    if "binding" in xlabel_lower:
        energy_scale = "Binding"
    elif "kinetic" in xlabel_lower:
        energy_scale = "Kinetic"
    else:
        energy_scale = "Unknown"
    curves: list[ImportedCurve] = []
    for column in range(1, width):
        y = values[:, column]
        mask = finite_x & np.isfinite(y)
        if np.count_nonzero(mask) < 2:
            continue
        title = header[column].strip() if column < len(header) else ""
        if not title:
            title = f"Curve {column}"
        curves.append(
            ImportedCurve(
                title=title,
                x=x[mask].copy(),
                y=y[mask].copy(),
                xlabel=xlabel or "Energy",
                energy_scale=energy_scale,
            )
        )

    if not curves:
        raise ValueError("No usable curve columns were found in the CSV file.")
    return curves


def export_shared_x_csv(path: str | Path, curves: Sequence[object]) -> None:
    """Write curves as one shared x column followed by y columns.

    All curves must use the same x grid. This explicit constraint avoids silent
    interpolation during data export.
    """
    if not curves:
        raise ValueError("There are no curves to export.")

    first_x = np.asarray(getattr(curves[0], "x", []), dtype=float)
    if first_x.ndim != 1 or first_x.size == 0:
        raise ValueError("The first curve has no valid energy axis.")

    columns = [first_x]
    names: list[str] = []
    for curve in curves:
        x = np.asarray(getattr(curve, "x", []), dtype=float)
        y = np.asarray(getattr(curve, "y", []), dtype=float)
        if x.shape != first_x.shape or y.shape != first_x.shape:
            raise ValueError("All exported curves must have the same number of points.")
        if not np.allclose(x, first_x, rtol=1e-9, atol=1e-12, equal_nan=True):
            raise ValueError("All exported curves must use the same energy grid.")
        columns.append(y)
        names.append(str(getattr(curve, "title", "")).strip())

    xlabel = str(getattr(curves[0], "xlabel", "Energy") or "Energy")
    matrix = np.column_stack(columns)
    dst = Path(path)
    if dst.suffix.lower() != ".csv":
        dst = dst.with_suffix(".csv")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([xlabel, *names])
        writer.writerows(matrix.tolist())
