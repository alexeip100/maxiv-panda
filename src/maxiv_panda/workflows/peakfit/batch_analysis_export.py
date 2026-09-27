from __future__ import annotations

from typing import Any

import csv
import re
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from . import batch_trend_models
from . import batch_full_export
from .batch_analysis_plot import _series_key_from_payload

try:
    from ... import __version__ as PACKAGE_VERSION
except Exception:  # pragma: no cover - defensive fallback for unusual launch modes
    PACKAGE_VERSION = ""

def _sanitize_export_name(text: str, fallback: str = "batch") -> str:
    """Return a filesystem-friendly filename fragment."""
    raw = str(text or "").strip() or str(fallback or "batch")
    raw = re.sub(r"[\\/:*?\"<>|]+", "_", raw)
    raw = re.sub(r"\s+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("._ ")
    return raw or str(fallback or "batch")

def _result_display_base(results: list[dict[str, Any]]) -> str:
    """Derive a compact data/source fragment from the first plotted result."""
    for result in results or []:
        for key in ("sequence_key", "display"):
            text = str(result.get(key) or "").strip()
            if text:
                text = Path(text).name
                text = re.sub(r"\.[A-Za-z0-9]{1,6}$", "", text)
                return _sanitize_export_name(text, "batch")
    return "batch"

def _selected_parameter_label_for_filename(self, series: list[dict[str, Any]]) -> str:
    """Return a compact label for the currently plotted parameter family."""
    try:
        family = str(self.cb_analyze_parameter_type.currentText() or "trend").strip()
    except Exception:
        family = "trend"
    if len(series) == 1:
        label = str(series[0].get("label") or family)
    else:
        label = family
    return _sanitize_export_name(label, "trend")

def _pass_number_fragment(pass_obj: dict[str, Any] | None) -> str:
    """Return passN fragment if possible."""
    if not pass_obj:
        return "pass"
    pid = str(pass_obj.get("id") or pass_obj.get("label") or "")
    m = re.search(r"pass[_\s-]*(\d+)", pid, flags=re.IGNORECASE)
    if not m:
        m = re.search(r"Pass\s*(\d+)", str(pass_obj.get("label") or ""), flags=re.IGNORECASE)
    return f"pass{m.group(1)}" if m else _sanitize_export_name(str(pass_obj.get("label") or "pass"), "pass")

def _series_column_name(entry: dict[str, Any]) -> str:
    payload = entry.get("payload") or {}
    kind = str(payload.get("kind") or "")
    if kind == "peak":
        code = str(payload.get("param") or "")
        label_map = {"E": "Energy", "H": "Height", "Area": "Area", "L": "LFWHM", "G": "GFWHM", "A": "Alpha"}
        return _sanitize_export_name(f"P{payload.get('index')}_{label_map.get(code, code)}", "parameter")
    if kind == "background":
        return _sanitize_export_name(f"BG_{payload.get('param')}", "background")
    if kind == "quality":
        return _sanitize_export_name(str(entry.get("label") or payload.get("param") or "quality"), "quality")
    return _sanitize_export_name(str(entry.get("label") or "parameter"), "parameter")

def _pass_sort_number(pass_obj: dict[str, Any]) -> int:
    text = str((pass_obj or {}).get("id") or (pass_obj or {}).get("label") or "")
    m = re.search(r"pass[_\s-]*(\d+)", text, flags=re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass
    return 10**9

def _constraint_label_list(constraints: list[dict[str, Any]]) -> str:
    labels: list[str] = []
    for c in constraints or []:
        label = str(c.get("label") or "").strip()
        if not label:
            target = str(c.get("target_label") or c.get("target_key") or "parameter")
            order = ((c.get("model") or {}).get("order") if isinstance(c.get("model"), dict) else None)
            label = f"{target} poly{order}" if order is not None else target
        labels.append(label)
    return "; ".join(labels) if labels else "none"

def _binning_metadata_for_pass(self, selected_pass: dict[str, Any] | None, results: list[dict[str, Any]] | None = None) -> str:
    """Return a compact human-readable description of binning used for exported trends."""
    selected_pass = selected_pass or {}
    stored = selected_pass.get("binning")
    if isinstance(stored, dict) and stored:
        enabled = bool(stored.get("enabled"))
        size = stored.get("bin_size", 1)
        discarded = stored.get("discarded", None)
        original_count = stored.get("original_checked", None)
        effective_count = stored.get("effective_count", None)
        if enabled:
            parts = [f"enabled, bin_size={size}"]
            if original_count not in (None, ""):
                parts.append(f"original_checked={original_count}")
            if effective_count not in (None, ""):
                parts.append(f"exported/binned_spectra={effective_count}")
            if discarded not in (None, "", 0):
                parts.append(f"discarded_remainder={discarded}")
            return "; ".join(parts)
        return "not applied (bin_size=1)"

    # Fallback for older pass objects: infer from result keys if possible.
    results = list(results or selected_pass.get("results") or [])
    bin_sizes: set[str] = set()
    for result in results:
        key = str(result.get("sequence_key") or "")
        parts = key.split(":")
        if len(parts) >= 5 and parts[0] == "bin":
            bin_sizes.add(str(parts[-2]))
    if bin_sizes:
        return f"enabled, bin_size={','.join(sorted(bin_sizes))}; details inferred from binned sequence keys"

    try:
        if bool(self._binned_mode_active()):
            size = int(self.sb_bin_size.value())
            return f"enabled, bin_size={size}; details from current GUI state"
    except Exception:
        pass
    return "not applied (bin_size=1)"

def _analyze_pass_history_lines(self, selected_pass: dict[str, Any] | None) -> list[str]:
    """Describe the selected pass and its ancestors for CSV metadata."""
    if not selected_pass:
        return []
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    cur = selected_pass
    while cur:
        pid = str(cur.get("id") or "")
        if pid in seen:
            break
        seen.add(pid)
        chain.append(cur)
        source = str(cur.get("source_pass_id") or "")
        cur = self._pass_by_id(source) if source else None
    chain.reverse()
    lines: list[str] = []
    for p in chain:
        label = str(p.get("label") or p.get("id") or "Pass")
        kind = str(p.get("kind") or "")
        start_from = str(p.get("start_from") or "")
        created = str(p.get("created_at") or "")
        summary = p.get("summary") or {}
        nres = summary.get("n_results", len(p.get("results") or []))
        failed = summary.get("failed", "")
        warn = summary.get("warnings", "")
        constraints = _constraint_label_list(list(p.get("constraints") or []))
        source = str(p.get("source_pass_id") or "none")
        lines.append(
            f"{label} | kind={kind or 'unknown'} | source={source} | start_from={start_from or 'unknown'} | "
            f"constraints={constraints} | spectra={nres} | failed={failed} | warnings={warn} | created={created}"
        )
    return lines

def _collect_current_analyze_export_rows(self, series: list[dict[str, Any]]) -> tuple[list[str], list[list[Any]], list[dict[str, Any]]]:
    """Collect currently selected raw trends and accepted analytical fits for export."""
    results = self._selected_analyze_results()
    series = list(series or [])
    columns = ["spectrum_number"]
    for entry in series:
        columns.append(_series_column_name(entry))

    selected_keys = {_series_key_from_payload(e.get("payload") or {}) for e in series}
    fit_maps: list[tuple[str, dict[int, float]]] = []
    stored = getattr(self, "_trend_analysis_stored_fits", {}) or {}
    current_pass_id = str((self._selected_analyze_pass() or {}).get("id") or "")
    for key, fit in stored.items():
        if str(key) not in selected_keys:
            continue
        if current_pass_id and str(fit.get("source_pass_id") or "") not in {"", current_pass_id}:
            continue
        col = _sanitize_export_name(f"{_series_column_name({'label': fit.get('series_label'), 'payload': fit.get('payload') or {}})}_fit", "trend_fit")
        fmap: dict[int, float] = {}
        for x, y in zip(fit.get("x") or [], fit.get("y_fit") or []):
            try:
                fmap[int(round(float(x)))] = float(y)
            except Exception:
                continue
        if fmap:
            fit_maps.append((col, fmap))
            columns.append(col)

    rows: list[list[Any]] = []
    for result in results:
        try:
            spectrum_number = int(result.get("spectrum_index") or len(rows) + 1)
        except Exception:
            spectrum_number = len(rows) + 1
        row: list[Any] = [spectrum_number]
        for entry in series:
            value = self._value_for_analyze_series(result, entry.get("payload") or {})
            row.append("" if value is None else float(value))
        for _col, fmap in fit_maps:
            row.append("" if spectrum_number not in fmap else float(fmap[spectrum_number]))
        rows.append(row)
    return columns, rows, results

def _region_fragment_from_text(text: str) -> str:
    """Extract a compact region label such as S2p, C1s, Au4f from a data label."""
    raw = str(text or "")
    matches = re.findall(r"(?<![A-Za-z])([A-Z][a-z]?\d+[spdf](?:\d/?\d)?)", raw)
    if matches:
        return _sanitize_export_name(matches[-1], "")
    # Also handle labels embedded after run numbers, e.g. XPS0108S2p.
    matches = re.findall(r"([A-Z][a-z]?\d+[spdf](?:\d/?\d)?)", raw)
    if matches:
        return _sanitize_export_name(matches[-1], "")
    return ""

def _data_file_fragment_for_filename(results: list[dict[str, Any]]) -> str:
    """Return a short original-data fragment for Analyze CSV export filenames."""
    texts: list[str] = []
    for result in results or []:
        for key in ("sequence_key", "display"):
            text = str(result.get(key) or "").strip()
            if text:
                texts.append(text)
        if texts:
            break
    if not texts:
        return "batch"
    joined = "_".join(texts)

    file_frag = ""
    # Prefer the original file name from binned keys: bin:<file>:<region>:<bin_size>:<idx>
    for text in texts:
        parts = str(text).split(":")
        if len(parts) >= 3 and parts[0] == "bin":
            file_frag = Path(parts[1]).stem
            break
    if not file_frag:
        for text in texts:
            m = re.search(r"(XPS\d+)", text, flags=re.IGNORECASE)
            if m:
                file_frag = m.group(1)
                break
    if not file_frag:
        text = Path(texts[0]).name
        text = re.sub(r"\.[A-Za-z0-9]{1,6}(?=(_|$))", "", text)
        text = re.sub(r"^bin[_:\-]*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"(_fixed_\d+_\d+|_pass\d+.*)$", "", text, flags=re.IGNORECASE)
        file_frag = text.split("_")[0] if "_" in text else text

    region_frag = ""
    for text in texts:
        region_frag = _region_fragment_from_text(text)
        if region_frag:
            break
    bits = [_sanitize_export_name(file_frag, "batch")]
    if region_frag and region_frag not in bits[0]:
        bits.append(region_frag)
    return "_".join(bit for bit in bits if bit) or "batch"

def _suggest_analyze_export_filename(self, series: list[dict[str, Any]]) -> str:
    """Suggest a compact CSV filename for the current Analyze trend export."""
    results = self._selected_analyze_results()
    data_frag = _data_file_fragment_for_filename(results)
    param_frag = _selected_parameter_label_for_filename(self, series)
    return f"{param_frag}_trends_for_{data_frag}.csv"

def _export_analyze_trends_csv(self, *args, **kwargs) -> None:
    """Export the currently plotted Analyze-tab parameter trends to CSV."""
    results = self._selected_analyze_results()
    series = self._selected_analyze_series()
    if not results:
        QMessageBox.warning(self, "Export CSV", "No batch-fit results are available to export.")
        return
    if not series:
        QMessageBox.warning(self, "Export CSV", "Select at least one parameter trend to export.")
        return
    columns, rows, _results = _collect_current_analyze_export_rows(self, series)
    if not rows:
        QMessageBox.warning(self, "Export CSV", "No finite trend data are available for the selected parameter(s).")
        return
    suggested = _suggest_analyze_export_filename(self, series)
    try:
        start_dir = str(getattr(self, "_last_batch_export_dir", "") or "")
    except Exception:
        start_dir = ""
    initial_path = str(Path(start_dir) / suggested) if start_dir else suggested
    path, _filter = QFileDialog.getSaveFileName(self, "Export plotted trends as CSV", initial_path, "CSV files (*.csv);;All files (*)")
    if not path:
        return
    out_path = Path(path)
    if out_path.suffix.lower() != ".csv":
        out_path = out_path.with_suffix(".csv")
    selected_pass = self._selected_analyze_pass() or {}
    try:
        parameter_label = str(self.cb_analyze_parameter_type.currentText() or "")
    except Exception:
        parameter_label = ""
    try:
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            # Comment-style metadata keeps the file readable as CSV while preserving
            # the processing context for later inspection.
            writer.writerow([f"# PANDA batch trend export"])
            writer.writerow([f"# package_version: {PACKAGE_VERSION}"])
            writer.writerow([f"# result_pass: {selected_pass.get('label') or selected_pass.get('id') or ''}"])
            writer.writerow([f"# parameter_family: {parameter_label}"])
            writer.writerow([f"# binning: {_binning_metadata_for_pass(self, selected_pass, results)}"])
            writer.writerow([f"# exported_series: {', '.join(_series_column_name(e) for e in series)}"])
            try:
                selected_keys = {_series_key_from_payload(e.get("payload") or {}) for e in series}
                stored = getattr(self, "_trend_analysis_stored_fits", {}) or {}
                cur_pass = str((self._selected_analyze_pass() or {}).get("id") or "")
                exported_fits = [fit for key, fit in stored.items() if str(key) in selected_keys and (not cur_pass or str(fit.get("source_pass_id") or "") in {"", cur_pass})]
                if exported_fits:
                    writer.writerow(["# analytical_trend_fits:"])
                    for fit in exported_fits:
                        metrics = fit.get("metrics") or {}
                        params = batch_trend_models.compact_params(fit.get("params") or {})
                        writer.writerow([
                            f"#   {fit.get('series_label') or fit.get('series_key')}: "
                            f"model={fit.get('model_label') or fit.get('model')}; "
                            f"nRMSE={batch_trend_models.format_metric(metrics.get('nrmse'))}; "
                            f"{params}"
                        ])
            except Exception:
                pass
            history = _analyze_pass_history_lines(self, selected_pass)
            if history:
                writer.writerow(["# pass_history:"])
                for line in history:
                    writer.writerow([f"#   {line}"])
            writer.writerow([])
            writer.writerow(columns)
            for row in rows:
                writer.writerow(row)
        self._last_batch_export_dir = str(out_path.parent)
        try:
            self.lab_analyze_status.setText(f"Exported {len(rows)} trend rows to {out_path.name}.")
        except Exception:
            pass
    except Exception as exc:
        QMessageBox.warning(self, "Export CSV", f"Could not export trend CSV:\n\n{exc}")

def _suggest_all_fits_zip_filename(self, selected_pass: dict[str, Any]) -> str:
    results = list((selected_pass or {}).get("results") or [])
    data_frag = _data_file_fragment_for_filename(results)
    pass_frag = _pass_number_fragment(selected_pass)
    return f"{data_frag}_{pass_frag}_all_fits.zip"

def _export_all_batch_fits_zip(self, *args, **kwargs) -> None:
    """Export all retained curve decompositions from the selected pass as a ZIP archive."""
    selected_pass = self._selected_analyze_pass() or {}
    results = list(selected_pass.get("results") or [])
    has_curves = any(batch_full_export.result_has_curves(r) for r in results)
    if not results or not bool(selected_pass.get("store_all_fit_results", False)) or not has_curves:
        QMessageBox.warning(
            self,
            "Export all fits",
            "Full fit curves were not stored for this pass. Enable 'Store all fit results' before running the pass.",
        )
        return
    suggested = _suggest_all_fits_zip_filename(self, selected_pass)
    try:
        start_dir = str(getattr(self, "_last_batch_export_dir", "") or "")
    except Exception:
        start_dir = ""
    initial_path = str(Path(start_dir) / suggested) if start_dir else suggested
    path, _filter = QFileDialog.getSaveFileName(
        self,
        "Export all stored fits",
        initial_path,
        "ZIP archives (*.zip);;All files (*)",
    )
    if not path:
        return
    out_path = Path(path)
    if out_path.suffix.lower() != ".zip":
        out_path = out_path.with_suffix(".zip")
    sequence_meta = []
    try:
        sequence_meta = list((getattr(self, "_batch_config", None) or {}).get("sequence") or [])
    except Exception:
        sequence_meta = []
    try:
        counts = batch_full_export.write_batch_fits_zip(out_path, selected_pass, sequence_meta=sequence_meta)
        self._last_batch_export_dir = str(out_path.parent)
        self.lab_analyze_status.setText(
            f"Exported {counts.get('fit_files', 0)} fit CSV files plus manifest to {out_path.name}."
        )
    except Exception as exc:
        QMessageBox.warning(self, "Export all fits", f"Could not export batch fits:\n\n{exc}")

