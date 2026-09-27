from __future__ import annotations

import re
from typing import Any

import numpy as np
from PyQt6.QtWidgets import QComboBox, QTableWidget
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

def _cell_text(self, table: QTableWidget, row: int, col: int) -> str:
    """Return display text from a table cell or its combobox widget."""
    try:
        widget = table.cellWidget(row, col)
        if isinstance(widget, QComboBox):
            return str(widget.currentText()).strip()
    except Exception:
        pass
    try:
        item = table.item(row, col)
        if item is None:
            return ""
        return str(item.text()).strip()
    except Exception:
        return ""

def _parse_optional_float(self, text: Any, *, row: int, column_name: str, errors: list[str]) -> float | None:
    """Parse a numeric table value, accepting em-dash/blank as missing."""
    raw = str(text if text is not None else "").strip()
    if raw in {"", "—", "-", "None", "none", "nan", "NaN"}:
        return None
    raw = raw.replace(",", ".")
    try:
        value = float(raw)
    except Exception:
        errors.append(f"Row {row + 1}: {column_name} must be numeric or blank, got '{text}'.")
        return None
    if not np.isfinite(value):
        errors.append(f"Row {row + 1}: {column_name} must be finite, got '{text}'.")
        return None
    return float(value)

def _json_clean_value(self, value: Any) -> Any:
    """Convert common GUI/NumPy values to JSON-compatible primitives."""
    if isinstance(value, dict):
        return {str(k): self._json_clean_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [self._json_clean_value(v) for v in value]
    if isinstance(value, set):
        return sorted(self._json_clean_value(v) for v in value)
    try:
        if isinstance(value, np.generic):
            return value.item()
    except Exception:
        pass
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, float):
        return value if np.isfinite(value) else None
    return str(value)

def _sequence_descriptor_for_batch_config(self) -> list[dict[str, Any]]:
    """Return lightweight provenance for the spectra to be fitted later."""
    out: list[dict[str, Any]] = []
    for idx, entry in enumerate(self._effective_checked_entries_from_tree(), start=1):
        meta = entry.get("meta")
        meta_summary = {}
        if isinstance(meta, dict):
            for key in ("energy_scale", "xlabel", "ylabel", "region", "source_file"):
                if key in meta:
                    meta_summary[key] = self._json_clean_value(meta.get(key))
        out.append({
            "index": idx,
            "key": str(entry.get("key") or ""),
            "display": str(entry.get("display") or ""),
            "file_name": str(entry.get("file_name") or ""),
            "region_name": str(entry.get("region_name") or ""),
            "meta": meta_summary,
        })
    return out

def _anchor_center_index(self, anchor: dict[str, Any]) -> float | None:
    """Return the sequence-index centre of an anchor range, if available."""
    try:
        a = float(anchor.get("start_index"))
        b = float(anchor.get("end_index"))
        if np.isfinite(a) and np.isfinite(b):
            return 0.5 * (a + b)
    except Exception:
        pass
    return None

def _clip_guess_to_bounds(self, value: Any, lower: Any, upper: Any) -> tuple[Any, bool]:
    """Clip a generated numeric guess to table bounds and report whether clipping happened."""
    if value is None:
        return None, False
    try:
        v = float(value)
        changed = False
        if lower is not None and np.isfinite(float(lower)) and v < float(lower):
            v = float(lower)
            changed = True
        if upper is not None and np.isfinite(float(upper)) and v > float(upper):
            v = float(upper)
            changed = True
        return v, changed
    except Exception:
        return value, False

def _fallback_guess_value(self, row: dict[str, Any]) -> float | None:
    """Choose a robust scalar fallback from Initial, then Start/Middle/End anchor values."""
    for value in (row.get("initial"), *((row.get("anchor_values") or {}).get(a) for a in self._anchor_labels)):
        try:
            v = float(value)
            if np.isfinite(v):
                return v
        except Exception:
            continue
    return None

def _natural_label_sort_key(self, label: str) -> tuple[str, int, str]:
    m = re.fullmatch(r"([A-Za-z_]+)(\d+)", str(label or ""))
    if m:
        return (m.group(1), int(m.group(2)), str(label))
    return (str(label), 0, str(label))

def _validate_and_build_batch_config(self, show_messages: bool = True) -> bool:
    """Validate the Run-tab table and store the internal batch configuration.

    Returns True when both the JSON-compatible batch config and the
    per-spectrum initial guesses are available. ``show_messages`` is
    False when called automatically by Run batch fit.
    """
    config, errors, warnings = self._build_batch_config_from_table()
    warn_label = getattr(self, "lab_batch_warnings", None)
    if errors:
        self._clear_batch_config_and_guesses()
        try:
            if warn_label is not None:
                text = "Validation errors:\n• " + "\n• ".join(errors)
                if warnings:
                    text += "\n\nWarnings:\n• " + "\n• ".join(warnings[:10])
                warn_label.setText(text)
                warn_label.setVisible(True)
            self.lab_batch_run_status.setText("Batch setup validation failed.")
        except Exception:
            pass
        if show_messages:
            QMessageBox.warning(self, "Validate setup", "Validation failed:\n\n• " + "\n• ".join(errors[:12]))
        return False

    guesses, guess_errors, guess_warnings = self._build_initial_guess_sequence(config or {})
    warnings.extend(guess_warnings)
    if guess_errors:
        self._clear_batch_config_and_guesses()
        try:
            if warn_label is not None:
                warn_label.setText("Initial guess generation errors:\n• " + "\n• ".join(guess_errors))
                warn_label.setVisible(True)
            self.lab_batch_run_status.setText("Batch setup validation failed during initial-guess generation.")
        except Exception:
            pass
        if show_messages:
            QMessageBox.warning(self, "Validate setup", "Initial guess generation failed:\n\n• " + "\n• ".join(guess_errors[:12]))
        return False

    try:
        config["initial_guess_generation"] = {
            "available": True,
            "n_spectra": len(guesses),
            "anchor_positions": self._json_clean_value(self._anchor_positions_for_initial_guesses(config or {})),
            "note": "Per-spectrum fit_state objects are stored in memory as _batch_initial_guesses.",
        }
    except Exception:
        pass
    self._batch_config = config
    self._batch_config_valid = True
    self._batch_initial_guesses = guesses
    self._batch_initial_guesses_valid = True
    try:
        if warn_label is not None:
            if warnings:
                warn_label.setText("Warnings / notes:\n• " + "\n• ".join(warnings[:20]))
                warn_label.setVisible(True)
            else:
                warn_label.setText("")
                warn_label.setVisible(False)
    except Exception:
        pass
    n_spectra = int((config or {}).get("summary", {}).get("n_spectra", 0))
    n_params = int((config or {}).get("summary", {}).get("n_parameters", 0))
    n_guesses = len(self._batch_initial_guesses)
    try:
        self.lab_batch_run_status.setText(f"Validated: {n_spectra} spectra, {n_params} parameters; {n_guesses} initial guesses built. Ready to run.")
    except Exception:
        pass
    self._refresh_batch_run_controls()
    msg = (
        f"Batch setup is valid.\n\n"
        f"Internal config built for {n_spectra} spectra and {n_params} parameter rows.\n"
        f"Per-spectrum initial guesses built: {n_guesses}."
    )
    if warnings:
        msg += f"\n\nWarnings: {len(warnings)} warning(s). See the yellow notes box."
    if show_messages:
        QMessageBox.information(self, "Validate setup", msg)
    return True
