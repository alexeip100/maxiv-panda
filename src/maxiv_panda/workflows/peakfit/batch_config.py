from __future__ import annotations

from typing import Any
from datetime import datetime

import numpy as np

from . import so_doublets
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidget


def _anchor_descriptor_for_batch_config(self) -> dict[str, dict[str, Any]]:
    """Return JSON-safe anchor provenance without embedding raw spectra arrays."""
    states = self._fitted_anchor_fit_states()
    anchors: dict[str, dict[str, Any]] = {}
    for label in self._anchor_labels:
        anchor = self._anchors.get(label) or {}
        state = states.get(label) or {}
        peaks = []
        for peak in state.get("peaks") or []:
            peaks.append({
                "label": str(peak.get("label") or ""),
                "index": int(peak.get("index") or len(peaks) + 1),
                "E": self._json_clean_value(peak.get("E")),
                "H": self._json_clean_value(peak.get("H")),
                "L": self._json_clean_value(peak.get("L")),
                "G": self._json_clean_value(peak.get("G")),
                "A": self._json_clean_value(peak.get("A")),
            })
        anchors[label] = {
            "built": bool(anchor),
            "fitted": bool(state),
            "range_text": str(anchor.get("range_text") or ""),
            "n_spectra": self._json_clean_value(anchor.get("n_spectra")),
            "start_index": self._json_clean_value(anchor.get("start_index")),
            "end_index": self._json_clean_value(anchor.get("end_index")),
            "center_index": self._json_clean_value(self._anchor_center_index(anchor)),
            "fit_status": str(anchor.get("fit_status") or ""),
            "bg_type": str(state.get("bg_type") or ""),
            "peaks": peaks,
            "so_doublets": self._json_clean_value(((state.get("fit_state") or {}).get("so_doublets") or [])),
        }
    return anchors

def _batch_row_metadata(self, table: QTableWidget, row: int) -> dict[str, Any]:
    try:
        item = table.item(row, 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return dict(data) if isinstance(data, dict) else {}
    except Exception:
        return {}

def _validate_batch_parameter_row(self, table: QTableWidget, row: int) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Validate one Run-tab parameter row and return its config representation."""
    errors: list[str] = []
    warnings: list[str] = []
    component = self._cell_text(table, row, 0)
    parameter = self._cell_text(table, row, 1)
    presence = self._cell_text(table, row, 2)
    strategy = self._cell_text(table, row, 7)
    mode = self._cell_text(table, row, 10) or "Free"
    tie = self._cell_text(table, row, 11)
    notes = self._cell_text(table, row, 12)
    metadata = self._batch_row_metadata(table, row)
    kind = str(metadata.get("kind") or ("background" if component == "Background" else "peak"))

    if not component or component == "—":
        errors.append(f"Row {row + 1}: missing component name.")
    if not parameter or parameter == "—":
        errors.append(f"Row {row + 1}: missing parameter name.")
    if kind == "derived":
        mode = "Derived"
    elif mode not in {"Free", "Fixed", "Tied"}:
        errors.append(f"Row {row + 1}: Mode must be Free, Fixed or Tied, got '{mode}'.")

    start = self._parse_optional_float(self._cell_text(table, row, 3), row=row, column_name="Start", errors=errors)
    middle = self._parse_optional_float(self._cell_text(table, row, 4), row=row, column_name="Middle", errors=errors)
    end = self._parse_optional_float(self._cell_text(table, row, 5), row=row, column_name="End", errors=errors)
    initial = self._parse_optional_float(self._cell_text(table, row, 6), row=row, column_name="Initial", errors=errors)
    lower = self._parse_optional_float(self._cell_text(table, row, 8), row=row, column_name="Min", errors=errors)
    upper = self._parse_optional_float(self._cell_text(table, row, 9), row=row, column_name="Max", errors=errors)

    if initial is None:
        errors.append(f"Row {row + 1}: Initial is required.")
    if kind != "derived" and lower is not None and upper is not None and lower >= upper:
        errors.append(f"Row {row + 1}: Min must be smaller than Max.")
    if kind != "derived" and initial is not None and lower is not None and initial < lower:
        errors.append(f"Row {row + 1}: Initial is below Min.")
    if kind != "derived" and initial is not None and upper is not None and initial > upper:
        errors.append(f"Row {row + 1}: Initial is above Max.")

    pnorm = parameter.strip().lower()
    if pnorm in {"height", "h"}:
        if lower is not None and lower < 0:
            errors.append(f"Row {row + 1}: Height Min must not be negative.")
        if initial is not None and initial < 0:
            errors.append(f"Row {row + 1}: Height Initial must not be negative.")
    if pnorm in {"lfwhm", "gfwhm", "l", "g"}:
        if lower is not None and lower <= 0:
            errors.append(f"Row {row + 1}: width Min should be positive.")
        if initial is not None and initial <= 0:
            errors.append(f"Row {row + 1}: width Initial should be positive.")
    if pnorm in {"alpha", "shirley alpha"}:
        if lower is not None and lower < 0:
            errors.append(f"Row {row + 1}: Alpha Min must not be negative.")
        if initial is not None and initial < 0:
            errors.append(f"Row {row + 1}: Alpha Initial must not be negative.")
        if upper is not None and upper > 1.0:
            warnings.append(f"Row {row + 1}: Alpha Max is rather high (>1); check that this is intentional.")

    if kind == "doublet" and pnorm in {"splitting", "ratio"}:
        if initial is not None and initial <= 0:
            errors.append(f"Row {row + 1}: {parameter} Initial must be > 0.")
        if lower is not None and lower <= 0 and pnorm == "ratio":
            errors.append(f"Row {row + 1}: Ratio Min must be > 0.")
        if lower is not None and lower < 0 and pnorm == "splitting":
            errors.append(f"Row {row + 1}: Splitting Min must not be negative.")

    if mode == "Tied" and not tie:
        errors.append(f"Row {row + 1}: Tied mode requires a Tie / Link description.")
    if presence in {"", "—"}:
        warnings.append(f"Row {row + 1}: Presence is empty; the parameter will be treated as template-only.")

    config_row = {
        "row": row + 1,
        "component": component,
        "parameter": parameter,
        "presence": presence,
        "anchor_values": {"Start": start, "Middle": middle, "End": end},
        "initial": initial,
        "initial_strategy": strategy,
        "bounds": {"min": lower, "max": upper},
        "mode": mode,
        "tie": tie,
        "notes": notes,
        "kind": kind,
        "doublet_id": metadata.get("doublet_id"),
        "doublet_label": metadata.get("doublet_label"),
        "major_label": metadata.get("major_label"),
        "minor_label": metadata.get("minor_label"),
        "orbital": metadata.get("orbital"),
        "L_relation": metadata.get("L_relation"),
        "G_relation": metadata.get("G_relation"),
        "A_relation": metadata.get("A_relation"),
    }
    if errors:
        return None, errors, warnings
    return config_row, errors, warnings

def _build_batch_config_from_table(self) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Validate the editable table and build the internal JSON-compatible batch config."""
    table = getattr(self, "tbl_batch_parameters", None)
    if table is None or int(table.rowCount()) <= 0:
        return None, ["No batch setup table has been created yet."], []

    errors: list[str] = []
    warnings: list[str] = []
    parameters: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for row in range(int(table.rowCount())):
        config_row, row_errors, row_warnings = self._validate_batch_parameter_row(table, row)
        errors.extend(row_errors)
        warnings.extend(row_warnings)
        if config_row is None:
            continue
        key = (str(config_row.get("component")), str(config_row.get("parameter")))
        if key in seen_keys:
            errors.append(f"Row {row + 1}: duplicate component/parameter combination: {key[0]} / {key[1]}.")
        seen_keys.add(key)
        parameters.append(config_row)

    peak_components = sorted({p["component"] for p in parameters if p.get("kind") in {"peak", "derived"}})
    for comp in peak_components:
        have = {str(p.get("parameter")) for p in parameters if p.get("component") == comp and p.get("kind") in {"peak", "derived"}}
        missing = [name for name in ("Energy", "Height", "LFWHM", "GFWHM", "Alpha") if name not in have]
        if missing:
            errors.append(f"Component {comp}: missing required peak parameter row(s): {', '.join(missing)}.")

    if not self._has_fitted_start_anchor():
        errors.append("The Start anchor must be fitted before building a batch config.")
    if self._current_effective_count() <= 0:
        errors.append("No spectra are available in the effective sequence.")
    try:
        model_mode, topology_errors = self._batch_anchor_model_mode_and_errors()
        errors.extend(topology_errors)
    except Exception:
        model_mode = str(getattr(self, "_batch_model_mode", "peak-only"))

    # Resolve doublet-level Tied-to labels to stable union-model IDs.
    doublet_rows = [p for p in parameters if p.get("kind") == "doublet"]
    label_to_id: dict[str, int] = {}
    for row_obj in doublet_rows:
        try:
            label_to_id[str(row_obj.get("component"))] = int(row_obj.get("doublet_id"))
        except Exception:
            pass
    for row_obj in doublet_rows:
        if str(row_obj.get("mode")) != "Tied":
            continue
        target_label = str(row_obj.get("tie") or "").strip()
        target_id = label_to_id.get(target_label)
        if target_id is None:
            errors.append(f"Row {row_obj.get('row')}: doublet Tied mode must name another SO doublet in Tie / Link.")
        elif int(target_id) == int(row_obj.get("doublet_id") or -1):
            errors.append(f"Row {row_obj.get('row')}: an SO doublet cannot be tied to itself.")
        else:
            row_obj["tie_target_id"] = int(target_id)

    if errors:
        return None, errors, warnings

    # Canonical union topology for SO-doublet batches.  The table rows carry
    # stable batch IDs and user labels; local anchor IDs are never used as identity.
    doublet_models: list[dict[str, Any]] = []
    seen_doublet_ids: set[int] = set()
    for row_obj in doublet_rows:
        try:
            did = int(row_obj.get("doublet_id"))
        except Exception:
            continue
        if did in seen_doublet_ids:
            continue
        seen_doublet_ids.add(did)
        doublet_models.append({
            "id": did,
            "label": str(row_obj.get("doublet_label") or row_obj.get("component") or f"Doublet #{did}"),
            "major_label": str(row_obj.get("major_label") or ""),
            "minor_label": str(row_obj.get("minor_label") or ""),
            "orbital": str(row_obj.get("orbital") or "Custom"),
            "L_relation": str(row_obj.get("L_relation") or "Same"),
            "G_relation": str(row_obj.get("G_relation") or "Same"),
            "A_relation": str(row_obj.get("A_relation") or "Same"),
        })
    doublet_models.sort(key=lambda x: int(x.get("id", 0)))

    anchors = self._anchor_descriptor_for_batch_config()
    config = {
        "format": "flexpes_pes_batch_setup",
        "format_version": 1,
        "created": datetime.now().isoformat(timespec="seconds"),
        "strategy": str(self.cb_batch_strategy.currentText()) if hasattr(self, "cb_batch_strategy") else "Independent fits from anchor guesses",
        "live_preview": bool(self.chk_batch_live_preview.isChecked()) if hasattr(self, "chk_batch_live_preview") else True,
        "sequence": self._sequence_descriptor_for_batch_config(),
        "anchors": anchors,
        "parameters": parameters,
        "model_mode": model_mode,
        "doublet_models": doublet_models,
        "summary": {
            "n_spectra": self._current_effective_count(),
            "n_parameters": len(parameters),
            "n_peak_components": len(peak_components),
            "has_start_anchor": self._has_fitted_start_anchor(),
            "fitted_anchors": [label for label, data in anchors.items() if data.get("fitted")],
        },
    }
    return self._json_clean_value(config), [], warnings

def _anchor_positions_for_initial_guesses(self, config: dict[str, Any]) -> dict[str, float]:
    """Map Start/Middle/End anchors to 1-based sequence positions for interpolation."""
    n = max(1, int((config.get("summary") or {}).get("n_spectra") or len(config.get("sequence") or []) or 1))
    fallback = {"Start": 1.0, "Middle": (n + 1.0) / 2.0, "End": float(n)}
    positions: dict[str, float] = {}
    anchors = config.get("anchors") or {}
    for label in self._anchor_labels:
        anchor_info = anchors.get(label, {}) or {}
        if anchor_info and anchor_info.get("fitted") is False:
            continue
        pos = None
        try:
            pos = anchor_info.get("center_index")
            pos = float(pos)
            if not np.isfinite(pos):
                pos = None
        except Exception:
            pos = None
        if pos is None:
            pos = fallback.get(label, 1.0)
        positions[label] = min(max(float(pos), 1.0), float(n))
    return positions


def _interpolated_guess_value(self, row: dict[str, Any], spectrum_index: int, positions: dict[str, float]) -> tuple[float | None, str]:
    """Generate one scalar initial value from Start/Middle/End anchor values.

    The generator intentionally accepts both the descriptive strategy texts created
    by the table builder ("interpolate anchor energies", etc.) and literal user
    edits such as "Start", "Middle" or "End".
    """
    anchors = row.get("anchor_values") or {}
    text = str(row.get("initial_strategy") or "").strip()
    text_l = text.lower()
    mode = str(row.get("mode") or "Free")
    if mode == "Fixed":
        return self._fallback_guess_value(row), "Fixed"

    # Explicit anchor strategy: use that anchor value for every spectrum.
    for label in self._anchor_labels:
        if text_l == label.lower():
            try:
                v = anchors.get(label)
                if v is not None:
                    return float(v), label
            except Exception:
                pass
            return self._fallback_guess_value(row), f"{label} fallback"

    points: list[tuple[float, float, str]] = []
    for label in self._anchor_labels:
        try:
            v = anchors.get(label)
            if v is None:
                continue
            v = float(v)
            if np.isfinite(v):
                points.append((float(positions.get(label, spectrum_index)), v, label))
        except Exception:
            continue
    points.sort(key=lambda item: item[0])

    # In the doublet-aware path, a component missing from a fitted anchor is an
    # explicit absence and contributes a zero-height guide point. An anchor that
    # was not fitted at all is absent from ``positions`` and contributes nothing.
    if str(row.get("parameter") or "").strip().lower() in {"height", "h"}:
        for label in self._anchor_labels:
            if anchors.get(label) is None and label in positions:
                points.append((float(positions[label]), 0.0, f"{label}=0"))
        points.sort(key=lambda item: item[0])

    if not points:
        return self._fallback_guess_value(row), "Initial"
    if len(points) == 1:
        return points[0][1], points[0][2]

    x = float(spectrum_index)
    xs = np.asarray([p[0] for p in points], dtype=float)
    ys = np.asarray([p[1] for p in points], dtype=float)
    if np.any(~np.isfinite(xs)) or np.any(~np.isfinite(ys)):
        return self._fallback_guess_value(row), "Initial"

    try:
        # np.interp clamps outside the anchor interval, which is safer for short
        # sequences than extrapolating widths/energies aggressively.
        return float(np.interp(x, xs, ys)), "interpolated"
    except Exception:
        return self._fallback_guess_value(row), "Initial"


def _build_initial_guess_sequence(self, config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Build JSON-compatible per-spectrum initial peak/BG fit states from the batch config."""
    errors: list[str] = []
    warnings: list[str] = []
    sequence = list(config.get("sequence") or [])
    parameters = list(config.get("parameters") or [])
    if not sequence:
        errors.append("Cannot generate initial guesses: the effective sequence is empty.")
        return [], errors, warnings
    if not parameters:
        errors.append("Cannot generate initial guesses: the batch config contains no parameters.")
        return [], errors, warnings

    positions = self._anchor_positions_for_initial_guesses(config)
    param_map = {
        "energy": "E", "e": "E",
        "height": "H", "h": "H",
        "lfwhm": "L", "l": "L",
        "gfwhm": "G", "g": "G",
        "alpha": "A", "a": "A",
    }
    required_peak_params = ("E", "H", "L", "G", "A")
    bg_key_map = {"b0": "b0", "b1": "b1", "b2": "b2", "shirley alpha": "bg_alpha", "bg_alpha": "bg_alpha"}

    guesses: list[dict[str, Any]] = []
    clipped_count = 0
    for idx, spectrum in enumerate(sequence, start=1):
        peak_rows: dict[str, dict[str, Any]] = {}
        bg_state: dict[str, Any] = {}
        per_param_values: list[dict[str, Any]] = []
        for row in parameters:
            component = str(row.get("component") or "")
            parameter = str(row.get("parameter") or "")
            lower = (row.get("bounds") or {}).get("min")
            upper = (row.get("bounds") or {}).get("max")
            value, source = self._interpolated_guess_value(row, idx, positions)
            value, clipped = self._clip_guess_to_bounds(value, lower, upper)
            if clipped:
                clipped_count += 1
            pnorm = parameter.strip().lower()
            mode = str(row.get("mode") or "Free")
            kind = str(row.get("kind") or ("background" if component == "Background" else "peak"))
            if kind == "doublet":
                per_param_values.append({
                    "row": row.get("row"), "component": component, "parameter": parameter,
                    "value": self._json_clean_value(value), "source": source, "mode": mode,
                })
                continue
            if component == "Background":
                key = bg_key_map.get(pnorm)
                if key is not None and value is not None:
                    bg_state[key] = float(value)
                per_param_values.append({
                    "row": row.get("row"), "component": component, "parameter": parameter,
                    "value": self._json_clean_value(value), "source": source, "mode": mode,
                })
                continue

            prefix = param_map.get(pnorm)
            if prefix is None:
                continue
            pstate = peak_rows.setdefault(component, {"label": component})
            if value is not None:
                pstate[prefix] = float(value)
            if lower is not None:
                pstate[f"{prefix}_min"] = float(lower)
            if upper is not None:
                pstate[f"{prefix}_max"] = float(upper)
            pstate[f"{prefix}_mode"] = "Fixed" if kind == "derived" else mode
            pstate[f"{prefix}_tie_text"] = str(row.get("tie") or "")
            per_param_values.append({
                "row": row.get("row"), "component": component, "parameter": parameter,
                "value": self._json_clean_value(value), "source": source, "mode": mode,
            })

        peak_states: list[dict[str, Any]] = []
        for label in sorted(peak_rows.keys(), key=lambda x: self._natural_label_sort_key(x)):
            pstate = peak_rows[label]
            missing = [p for p in required_peak_params if p not in pstate]
            if missing:
                errors.append(
                    f"Spectrum {idx}, component {label}: missing generated value(s): {', '.join(missing)}."
                )
                continue
            peak_states.append(pstate)

        if "bg_type" not in bg_state:
            try:
                bg_state["bg_type"] = str((config.get("anchors") or {}).get("Start", {}).get("bg_type") or "Shirley")
            except Exception:
                bg_state["bg_type"] = "Shirley"
        bg_state.setdefault("b0", 0.0)
        bg_state.setdefault("b1", 0.0)
        bg_state.setdefault("b2", 0.0)
        bg_state.setdefault("bg_alpha", 1.0)
        bg_state.setdefault("bg_alpha_fixed", False)
        bg_state.setdefault("bg_touched", True)
        bg_state.setdefault("calc_on", False)

        generated_doublets: list[dict[str, Any]] = []
        if str(config.get("model_mode") or "") == "doublet-aware":
            label_to_peak_index = {str(p.get("label") or ""): i for i, p in enumerate(peak_states, start=1)}
            row_by_key = {}
            for row in parameters:
                if str(row.get("kind")) == "doublet":
                    try:
                        row_by_key[(int(row.get("doublet_id")), str(row.get("parameter") or "").strip().lower())] = row
                    except Exception:
                        pass
            for model in list(config.get("doublet_models") or []):
                try:
                    did = int(model.get("id")); major = int(label_to_peak_index[str(model.get("major_label") or "")]); minor = int(label_to_peak_index[str(model.get("minor_label") or "")])
                except Exception:
                    errors.append(
                        f"Spectrum {idx}: cannot map SO doublet '{model.get('label')}' to its major/minor peak labels."
                    )
                    continue
                st = {
                    "id": did, "major": major, "minor": minor,
                    "label": str(model.get("label") or f"Doublet #{did}"),
                    "orbital": str(model.get("orbital") or "Custom"),
                    "L_relation": str(model.get("L_relation") or "Same"),
                    "G_relation": str(model.get("G_relation") or "Same"),
                    "A_relation": str(model.get("A_relation") or "Same"),
                }
                for key, pname in (("split", "splitting"), ("ratio", "ratio")):
                    row = row_by_key.get((did, pname))
                    if row is None:
                        errors.append(f"Spectrum {idx}: SO doublet '{st['label']}' is missing its {pname} batch row.")
                        continue
                    lower = (row.get("bounds") or {}).get("min"); upper = (row.get("bounds") or {}).get("max")
                    value, _source = self._interpolated_guess_value(row, idx, positions)
                    value, clipped = self._clip_guess_to_bounds(value, lower, upper)
                    if clipped:
                        clipped_count += 1
                    if value is None:
                        errors.append(f"Spectrum {idx}: no generated {pname} value for SO doublet '{st['label']}'.")
                        continue
                    st[key] = float(value)
                    st[f"{key}_min"] = float(lower) if lower is not None else (0.0 if key == "split" else 0.1)
                    st[f"{key}_max"] = float(upper) if upper is not None else max(float(value) * 2.0, float(value) + 0.1)
                    st[f"{key}_mode"] = str(row.get("mode") or "Free")
                    st[f"{key}_tie_target"] = int(row.get("tie_target_id")) if row.get("tie_target_id") is not None else None
                generated_doublets.append(so_doublets.normalize_state(st, ordinal=did))
            generated_doublets = so_doublets.resolve_tied_values(generated_doublets)


        guesses.append({
            "spectrum_index": idx,
            "sequence_key": str(spectrum.get("key") or ""),
            "display": str(spectrum.get("display") or ""),
            "fit_state": {
                "peak_states": peak_states,
                "so_doublets": generated_doublets,
                "bg_state": bg_state,
                "fit_table": {},
                "bg_table": {},
                "fit_quality": {},
                "bound_hits": [],
            },
            "parameters": per_param_values,
        })

    if clipped_count:
        warnings.append(f"Initial guess generation clipped {clipped_count} value(s) to the validated Min/Max bounds.")
    if errors:
        return [], errors, warnings
    return self._json_clean_value(guesses), [], warnings


