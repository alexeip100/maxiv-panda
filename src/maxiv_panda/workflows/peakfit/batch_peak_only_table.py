from __future__ import annotations

from typing import Any

import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QTableWidgetItem



def _make_batch_table_item(self, text: Any, *, editable: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(self._fmt_batch_value(text))
    try:
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    except Exception:
        pass
    return item












def _build_batch_parameter_rows_from_anchors(self) -> tuple[list[dict[str, Any]], list[str]]:
    """Build the first editable batch-parameter table from fitted, labelled anchors.

    This is intentionally conservative: peak identity is based primarily on
    user labels. Peaks found only in some anchors are retained as optional
    components rather than silently removed. Actual batch execution is not
    performed here.
    """
    states = self._fitted_anchor_fit_states()
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    fitted_labels = [a for a in self._anchor_labels if a in states]
    if not fitted_labels:
        return rows, ["No fitted anchors are available."]

    warnings.append(
        "This is a proposed batch setup only. Initial strategies describe starting guesses; "
        "they are not hard constraints unless the Mode column is set to Fixed or Tied."
    )

    # Background consistency warnings.
    bg_types = {a: str((states[a].get("bg_type") or "BG")) for a in fitted_labels}
    unique_bg = sorted(set(bg_types.values()))
    if len(unique_bg) > 1:
        warnings.append(
            "Background type differs between fitted anchors ("
            + ", ".join(f"{a}: {bg_types[a]}" for a in fitted_labels)
            + "). The batch table lists Start-anchor background parameters as the primary template."
        )

    # Build union of peaks by label. Duplicate labels inside one anchor are kept separate with warnings.
    components: dict[str, dict[str, Any]] = {}
    for anchor in fitted_labels:
        seen_in_anchor: dict[str, int] = {}
        for idx, peak in enumerate(states[anchor].get("peaks") or [], start=1):
            raw_label = str(peak.get("label") or f"P{idx}").strip() or f"P{idx}"
            seen_in_anchor[raw_label] = seen_in_anchor.get(raw_label, 0) + 1
            label = raw_label
            if seen_in_anchor[raw_label] > 1:
                label = f"{raw_label}#{seen_in_anchor[raw_label]}"
                warnings.append(
                    f"Anchor {anchor} contains duplicate peak label '{raw_label}'. "
                    f"The duplicate was kept as '{label}'."
                )
            comp = components.setdefault(label, {"label": label, "anchors": {}, "source_labels": set()})
            comp["anchors"][anchor] = peak
            comp["source_labels"].add(anchor)

    # Warn if labels look generic. They are valid, but the user should know matching is label-based.
    for label in components:
        if re.fullmatch(r"P\d+", str(label)):
            continue
    if any(re.fullmatch(r"P\d+", str(label)) for label in components):
        warnings.append(
            "Some peaks still use default labels such as P1/P2. Matching across anchors is label-based, "
            "so rename peaks in the anchor fits if two components with similar energy have different chemical meaning."
        )

    param_defs = [
        ("E", "Energy"),
        ("H", "Height"),
        ("L", "LFWHM"),
        ("G", "GFWHM"),
        ("A", "Alpha"),
    ]
    for label, comp in sorted(components.items(), key=lambda kv: self._component_sort_key(kv[0], kv[1])):
        anchors_for_comp = comp.get("anchors") or {}
        present = set(anchors_for_comp.keys())
        base_note = self._presence_note(present, fitted_labels)
        for prefix, pname in param_defs:
            vals: dict[str, Any] = {}
            mins: list[float] = []
            maxs: list[float] = []
            modes: list[str] = []
            tie_texts: list[str] = []
            for anchor in fitted_labels:
                peak = anchors_for_comp.get(anchor)
                if peak is None:
                    vals[anchor] = None
                    continue
                vals[anchor] = peak.get(prefix)
                try:
                    mins.append(float(peak.get(f"{prefix}_min")))
                except Exception:
                    pass
                try:
                    maxs.append(float(peak.get(f"{prefix}_max")))
                except Exception:
                    pass
                mode = str(peak.get(f"{prefix}_mode", "Free") or "Free")
                modes.append(mode)
                if "tied" in mode.lower():
                    tie_texts.append(mode)
            numeric_vals = self._finite_floats(list(vals.values()))
            initial = None
            for anchor in ("Start", "Middle", "End"):
                if anchor in vals and vals.get(anchor) is not None:
                    initial = vals.get(anchor)
                    break
            if initial is None and numeric_vals:
                initial = numeric_vals[0]
            suggested_min, suggested_max = self._suggest_peak_bounds(prefix, numeric_vals, mins, maxs)
            suggested_mode = self._suggest_peak_mode(prefix, numeric_vals, modes)
            initial = self._mean_if_fixed(initial, numeric_vals, suggested_mode)
            strategy = self._initial_strategy_for_peak_param(prefix, present, fitted_labels, numeric_vals, suggested_mode)
            presence = self._presence_pattern(present, fitted_labels)
            note = base_note
            if len({self._mode_from_anchor_modes([m]) for m in modes}) > 1:
                note += "; anchor modes differ — using Free"
            elif suggested_mode in {"Fixed", "Tied"}:
                note += f"; inherited {suggested_mode} from anchor setup"
            if prefix == "H" and len(present) < len(fitted_labels):
                note += "; non-negative intensity lets this component vanish where absent"
            if prefix == "H" and self._anchor_presence_kind(present, fitted_labels) in {"appearing", "end_only", "middle_only"}:
                note += "; use small nonzero initial height before appearance"
            row = {
                "component": str(label),
                "parameter": pname,
                "presence": presence,
                "start": vals.get("Start"),
                "middle": vals.get("Middle"),
                "end": vals.get("End"),
                "initial": initial,
                "initial_strategy": strategy,
                "min": suggested_min,
                "max": suggested_max,
                "mode": suggested_mode,
                "tie": "; ".join(dict.fromkeys(tie_texts)) if suggested_mode == "Tied" else "",
                "notes": note,
            }
            rows.append(row)

    # Background rows. Use Start as primary template but show other anchors for context.
    bg_param_defs = [
        ("b0", "b0"),
        ("b1", "b1"),
        ("b2", "b2"),
        ("bg_alpha", "Shirley alpha"),
    ]
    for key, pname in bg_param_defs:
        vals = {}
        for anchor in fitted_labels:
            vals[anchor] = (states[anchor].get("bg_state") or {}).get(key)
        numeric_vals = self._finite_floats(list(vals.values()))
        initial = vals.get("Start") if vals.get("Start") is not None else (numeric_vals[0] if numeric_vals else None)
        if key == "bg_alpha":
            fixed_flags = [bool((states[a].get("bg_state") or {}).get("bg_alpha_fixed", False)) for a in fitted_labels]
            mode = "Fixed" if fixed_flags and all(fixed_flags) else "Free"
            mn = 0.0
            mx = max(1.0, max(numeric_vals) * 2.0) if numeric_vals else 1.0
        else:
            mode = "Free"
            if numeric_vals:
                span = max(numeric_vals) - min(numeric_vals)
                pad = max(abs(max(numeric_vals)) * 0.2, abs(min(numeric_vals)) * 0.2, span * 0.5, 1e-9)
                mn = min(numeric_vals) - pad
                mx = max(numeric_vals) + pad
            else:
                mn = None
                mx = None
        initial = self._mean_if_fixed(initial, numeric_vals, mode)
        rows.append({
            "component": "Background",
            "parameter": pname,
            "presence": self._presence_pattern({a for a in fitted_labels if vals.get(a) is not None}, fitted_labels),
            "start": vals.get("Start"),
            "middle": vals.get("Middle"),
            "end": vals.get("End"),
            "initial": initial,
            "initial_strategy": self._initial_strategy_for_background(key, numeric_vals, mode),
            "min": mn,
            "max": mx,
            "mode": mode,
            "tie": "",
            "notes": "background parameter",
        })

    return rows, warnings

def _populate_batch_parameter_table(self) -> None:
    table = getattr(self, "tbl_batch_parameters", None)
    if table is None:
        return
    rows, warnings = self._build_batch_parameter_rows_from_anchors()
    self._clear_batch_config_and_guesses()
    self._populating_batch_table = True
    try:
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            table.setItem(row_idx, 0, self._make_batch_table_item(row.get("component")))
            table.setItem(row_idx, 1, self._make_batch_table_item(row.get("parameter")))
            table.setItem(row_idx, 2, self._make_batch_table_item(row.get("presence")))
            table.setItem(row_idx, 3, self._make_batch_table_item(row.get("start")))
            table.setItem(row_idx, 4, self._make_batch_table_item(row.get("middle")))
            table.setItem(row_idx, 5, self._make_batch_table_item(row.get("end")))
            table.setItem(row_idx, 6, self._make_batch_table_item(row.get("initial"), editable=True))
            table.setItem(row_idx, 7, self._make_batch_table_item(row.get("initial_strategy", "")))
            table.setItem(row_idx, 8, self._make_batch_table_item(row.get("min"), editable=True))
            table.setItem(row_idx, 9, self._make_batch_table_item(row.get("max"), editable=True))
            mode_combo = QComboBox(table)
            mode_combo.addItems(["Free", "Fixed", "Tied"])
            mode = str(row.get("mode") or "Free")
            if mode not in {"Free", "Fixed", "Tied"}:
                mode = "Free"
            mode_combo.setCurrentText(mode)
            mode_combo.currentTextChanged.connect(self._on_batch_table_edited)
            table.setCellWidget(row_idx, 10, mode_combo)
            table.setItem(row_idx, 11, self._make_batch_table_item(row.get("tie", ""), editable=True))
            table.setItem(row_idx, 12, self._make_batch_table_item(row.get("notes", "")))
        table.resizeRowsToContents()
    except Exception as exc:
        log_noncritical_error("populating batch parameter table", exc, logger=self._logger)
    finally:
        self._populating_batch_table = False
    warn_label = getattr(self, "lab_batch_warnings", None)
    if warn_label is not None:
        try:
            if warnings:
                warn_label.setText("Warnings / notes:\n• " + "\n• ".join(warnings))
                warn_label.setVisible(True)
            else:
                warn_label.setText("")
                warn_label.setVisible(False)
        except Exception:
            pass
