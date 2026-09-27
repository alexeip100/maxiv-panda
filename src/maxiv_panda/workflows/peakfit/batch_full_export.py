from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def sanitize_name(text: Any, fallback: str = "fit") -> str:
    raw = str(text or "").strip() or fallback
    raw = re.sub(r"[\\/:*?\"<>|]+", "_", raw)
    raw = re.sub(r"\s+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("._ ")
    return raw or fallback


def _unique_component_headers(peaks: Iterable[dict[str, Any]], n_components: int) -> list[str]:
    used: set[str] = set()
    headers: list[str] = []
    peak_list = list(peaks or [])
    for i in range(1, int(n_components) + 1):
        label = ""
        if i - 1 < len(peak_list):
            label = str(peak_list[i - 1].get("label") or "").strip()
        base = sanitize_name(f"P{i}_{label}" if label else f"P{i}", f"P{i}")
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate)
        headers.append(candidate)
    return headers



def result_has_curves(result: dict[str, Any] | None) -> bool:
    """Return True when a batch result contains a complete retained curve set."""
    data = dict((result or {}).get("plot_data") or {})
    try:
        n = len(data.get("x") or [])
        return bool(
            n > 0
            and len(data.get("y") or []) == n
            and len(data.get("model") or []) == n
            and len(data.get("residual") or []) == n
            and all(len(c or []) == n for c in (data.get("components") or []))
        )
    except Exception:
        return False


def result_curve_table(result: dict[str, Any]) -> tuple[list[str], list[list[float]]]:
    """Build the plain CSV table for one stored batch-fit result.

    Returns an empty table when full plot curves were not retained for the result.
    The background is reconstructed exactly as total_fit - sum(peak_components).
    """
    data = dict((result or {}).get("plot_data") or {})
    try:
        x = np.asarray(data.get("x") or [], dtype=float)
        y = np.asarray(data.get("y") or [], dtype=float)
        model = np.asarray(data.get("model") or [], dtype=float)
        residual = np.asarray(data.get("residual") or [], dtype=float)
        components = [np.asarray(c, dtype=float) for c in (data.get("components") or [])]
    except Exception:
        return [], []
    n = int(x.size)
    if n <= 0 or y.size != n or model.size != n or residual.size != n:
        return [], []
    if any(c.size != n for c in components):
        return [], []
    if components:
        peaks_sum = np.sum(np.vstack(components), axis=0)
    else:
        peaks_sum = np.zeros(n, dtype=float)
    background = model - peaks_sum
    xlabel = str(data.get("xlabel") or "Energy").strip() or "Energy"
    component_headers = _unique_component_headers(result.get("peaks") or [], len(components))
    headers = [xlabel, "Data", "Total Fit", "Background", "Peaks Sum", "Residual", *component_headers]
    arrays = [x, y, model, background, peaks_sum, residual, *components]
    rows = [[float(arr[i]) for arr in arrays] for i in range(n)]
    return headers, rows


def _csv_bytes(headers: list[str], rows: list[list[Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def build_manifest_rows(pass_obj: dict[str, Any], results: list[dict[str, Any]], sequence_meta: list[dict[str, Any]] | None = None) -> tuple[list[str], list[list[Any]]]:
    meta_by_index: dict[int, dict[str, Any]] = {}
    for entry in sequence_meta or []:
        try:
            meta_by_index[int(entry.get("index"))] = entry
        except Exception:
            continue
    headers = [
        "fit_number", "spectrum_index", "fit_file", "sequence_key", "display",
        "source_file", "region", "status", "message", "pass_id", "pass_label",
        "source_pass_id", "stored_curves",
    ]
    rows: list[list[Any]] = []
    for fit_number, result in enumerate(results or [], start=1):
        try:
            spectrum_index = int(result.get("spectrum_index") or fit_number)
        except Exception:
            spectrum_index = fit_number
        meta = meta_by_index.get(spectrum_index, {})
        source_file = str(meta.get("file_name") or (meta.get("meta") or {}).get("source_file") or "")
        region = str(meta.get("region_name") or (meta.get("meta") or {}).get("region") or "")
        has_curves = result_has_curves(result)
        fit_file = ""
        if has_curves:
            display = str(result.get("display") or result.get("sequence_key") or f"spectrum_{spectrum_index}")
            fit_file = f"fits/fit_{spectrum_index:04d}_{sanitize_name(Path(display).stem, 'spectrum')}.csv"
        rows.append([
            fit_number,
            spectrum_index,
            fit_file,
            str(result.get("sequence_key") or ""),
            str(result.get("display") or ""),
            source_file,
            region,
            str(result.get("status") or ""),
            str(result.get("message") or ""),
            str(pass_obj.get("id") or ""),
            str(pass_obj.get("label") or ""),
            str(pass_obj.get("source_pass_id") or ""),
            "yes" if has_curves else "no",
        ])
    return headers, rows


def write_batch_fits_zip(path: str | Path, pass_obj: dict[str, Any], *, sequence_meta: list[dict[str, Any]] | None = None) -> dict[str, int]:
    """Write one ZIP containing one plain CSV per stored fit plus a manifest CSV."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    results = list((pass_obj or {}).get("results") or [])
    manifest_headers, manifest_rows = build_manifest_rows(pass_obj or {}, results, sequence_meta=sequence_meta)
    n_fit_files = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for row, result in zip(manifest_rows, results):
            fit_file = str(row[2] or "")
            if not fit_file:
                continue
            headers, rows = result_curve_table(result)
            if not headers or not rows:
                continue
            zf.writestr(fit_file, _csv_bytes(headers, rows))
            n_fit_files += 1
        zf.writestr("batch_manifest.csv", _csv_bytes(manifest_headers, manifest_rows))
    return {"fit_files": n_fit_files, "results": len(results)}
