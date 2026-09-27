from __future__ import annotations

from typing import Any

import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QTableWidgetItem

from . import so_doublets


def _make_batch_table_item(self, text: Any, *, editable: bool = False, enabled: bool = True, metadata: dict[str, Any] | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(self._fmt_batch_value(text))
    try:
        flags = item.flags()
        if not editable:
            flags &= ~Qt.ItemFlag.ItemIsEditable
        if not enabled:
            flags &= ~Qt.ItemFlag.ItemIsEnabled
            flags &= ~Qt.ItemFlag.ItemIsSelectable
        item.setFlags(flags)
        if metadata is not None:
            item.setData(Qt.ItemDataRole.UserRole, dict(metadata))
    except Exception:
        pass
    return item












def _doublet_union_model(self, states: dict[str, dict[str, Any]], fitted_labels: list[str]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    """Build the union of labelled SO doublets across fitted anchors.

    Doublet labels are the primary identity across the series. A doublet may be
    absent from an anchor; where present repeatedly its structure has already been
    checked by ``validate_anchor_topologies``.
    """
    per_anchor: dict[str, dict[str, dict[str, Any]]] = {}
    warnings: list[str] = []
    ordered_labels: list[str] = []
    seen: set[str] = set()
    for anchor in fitted_labels:
        mapping, errs = so_doublets.anchor_doublets_by_label((states[anchor].get("fit_state") or {}))
        per_anchor[anchor] = mapping
        warnings.extend(f"{anchor}: {msg}" for msg in errs)
        for label in mapping:
            if label not in seen:
                seen.add(label); ordered_labels.append(label)

    models: list[dict[str, Any]] = []
    member_info: dict[str, dict[str, Any]] = {}
    for batch_id, label in enumerate(ordered_labels, start=1):
        present = [anchor for anchor in fitted_labels if label in per_anchor.get(anchor, {})]
        if not present:
            continue
        first = per_anchor[present[0]][label]
        d = dict(first["state"] or {})
        model = {
            "id": int(batch_id),
            "label": label,
            "major_label": str(first["major_label"]),
            "minor_label": str(first["minor_label"]),
            "orbital": str(d.get("orbital") or "Custom"),
            "L_relation": str(d.get("L_relation", "Same")),
            "G_relation": str(d.get("G_relation", "Same")),
            "A_relation": str(d.get("A_relation", "Same")),
            "present": set(present),
            "per_anchor": {a: per_anchor[a][label] for a in present},
        }
        models.append(model)
        for role, peak_label in (("major", model["major_label"]), ("minor", model["minor_label"])):
            existing = member_info.get(peak_label)
            if existing is not None and existing.get("doublet_label") != label:
                warnings.append(
                    f"Peak '{peak_label}' belongs to more than one explicit SO doublet in the anchor union; "
                    "check component labels before batch fitting."
                )
                continue
            member_info[peak_label] = {
                "role": role, "doublet_id": int(batch_id), "doublet_label": label,
                "L_relation": model["L_relation"], "G_relation": model["G_relation"], "A_relation": model["A_relation"],
            }
    return models, member_info, warnings


def _build_doublet_parameter_rows(self, states: dict[str, dict[str, Any]], fitted_labels: list[str]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    """Build Splitting/Ratio rows for the union of labelled SO doublets."""
    models, member_info, warnings = self._doublet_union_model(states, fitted_labels)
    rows: list[dict[str, Any]] = []
    for model in models:
        label = str(model["label"]); did = int(model["id"]); present = set(model["present"])
        for key, pname in (("split", "Splitting"), ("ratio", "Ratio")):
            vals: dict[str, Any] = {}; mins: list[float] = []; maxs: list[float] = []; modes: list[str] = []; tie_labels: list[str] = []
            for anchor in fitted_labels:
                info = (model.get("per_anchor") or {}).get(anchor)
                if info is None:
                    vals[anchor] = None
                    continue
                d = dict(info.get("state") or {})
                vals[anchor] = d.get(key)
                try: mins.append(float(d.get(f"{key}_min")))
                except Exception: pass
                try: maxs.append(float(d.get(f"{key}_max")))
                except Exception: pass
                mode = str(d.get(f"{key}_mode") or "Fixed")
                modes.append(mode)
                if mode == "Tied" and d.get(f"{key}_tie_target") is not None:
                    target_id = int(d.get(f"{key}_tie_target"))
                    anchor_map, _errs = so_doublets.anchor_doublets_by_label((states[anchor].get("fit_state") or {}))
                    target_label = next((dl for dl, di in anchor_map.items() if int((di.get("state") or {}).get("id", -1)) == target_id), "")
                    if target_label:
                        tie_labels.append(target_label)
            numeric = self._finite_floats(list(vals.values()))
            initial = next((vals.get(a) for a in fitted_labels if vals.get(a) is not None), numeric[0] if numeric else None)
            mode = self._mode_from_anchor_modes(modes)
            initial = self._mean_if_fixed(initial, numeric, mode)
            lower = max(mins) if mins else None; upper = min(maxs) if maxs else None
            tie = tie_labels[0] if mode == "Tied" and tie_labels and len(set(tie_labels)) == 1 else ""
            note = f"SO doublet: major {model['major_label']}, minor {model['minor_label']}"
            if len(present) < len(fitted_labels):
                note += "; optional component — absent anchor(s) contribute zero intensity, as in peak-only batch fitting"
            if len({self._mode_from_anchor_modes([m]) for m in modes}) > 1:
                note += "; anchor modes differ — using Free"
            if mode == "Tied" and not tie:
                mode = "Free"; note += "; anchor tie targets differ — using Free"
            metadata = {
                "kind": "doublet", "doublet_id": did, "doublet_label": label,
                "major_label": model["major_label"], "minor_label": model["minor_label"],
                "orbital": model["orbital"], "L_relation": model["L_relation"],
                "G_relation": model["G_relation"], "A_relation": model["A_relation"],
            }
            rows.append({
                **metadata, "component": label, "parameter": pname,
                "presence": self._presence_pattern(present, fitted_labels),
                "start": vals.get("Start"), "middle": vals.get("Middle"), "end": vals.get("End"),
                "initial": initial,
                "initial_strategy": f"interpolate anchor {pname.lower()}" if len(numeric) >= 2 and mode != "Fixed" else f"use available anchor {pname.lower()}",
                "min": lower, "max": upper, "mode": mode, "tie": tie, "notes": note,
            })
    return rows, member_info, warnings


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

    fit_states = {label: dict(states[label].get("fit_state") or {}) for label in fitted_labels}
    model_mode, topology_errors = so_doublets.validate_anchor_topologies(fit_states, fitted_labels)
    if topology_errors:
        return rows, topology_errors
    doublet_member_info: dict[str, dict[str, Any]] = {}
    if model_mode == "doublet-aware":
        doublet_rows, doublet_member_info, doublet_warnings = self._build_doublet_parameter_rows(states, fitted_labels)
        rows.extend(doublet_rows)
        warnings.extend(doublet_warnings)

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
            member = doublet_member_info.get(str(label)) if model_mode == "doublet-aware" else None
            derived = False
            if member and member.get("role") == "minor":
                derived = prefix in {"E", "H"} or (prefix in {"L", "G", "A"} and str(member.get(f"{prefix}_relation", "Same")) == "Same")
            if member:
                note += f"; {member.get('role')} member of {member.get('doublet_label')}"
            if derived:
                note += "; controlled by the SO-doublet relationship"
            row = {
                "kind": "derived" if derived else "peak",
                "component": str(label),
                "parameter": pname,
                "presence": presence,
                "start": vals.get("Start"),
                "middle": vals.get("Middle"),
                "end": vals.get("End"),
                "initial": initial,
                "initial_strategy": "Derived from SO doublet" if derived else strategy,
                "min": None if derived else suggested_min,
                "max": None if derived else suggested_max,
                "mode": "Derived" if derived else suggested_mode,
                "tie": "; ".join(dict.fromkeys(tie_texts)) if (not derived and suggested_mode == "Tied") else "",
                "notes": note,
                "doublet_id": int(member.get("doublet_id", 0)) if member else None,
                "doublet_label": str(member.get("doublet_label") or "") if member else "",
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
            "kind": "background",
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
    doublet_aware = any(str(row.get("kind")) == "doublet" for row in rows)
    self._batch_model_mode = "doublet-aware" if doublet_aware else "peak-only"
    try:
        header = table.horizontalHeaderItem(0)
        if header is not None:
            header.setText("Peak / Doublet / BG" if doublet_aware else "Peak / BG")
    except Exception:
        pass
    self._populating_batch_table = True
    try:
        table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            kind = str(row.get("kind") or "peak")
            derived = kind == "derived"
            metadata = {k: row.get(k) for k in (
                "kind", "doublet_id", "doublet_label", "component", "parameter",
                "major_label", "minor_label", "orbital", "L_relation", "G_relation", "A_relation"
            ) if k in row}
            table.setItem(row_idx, 0, self._make_batch_table_item(row.get("component"), metadata=metadata))
            table.setItem(row_idx, 1, self._make_batch_table_item(row.get("parameter")))
            table.setItem(row_idx, 2, self._make_batch_table_item(row.get("presence"), enabled=not derived))
            table.setItem(row_idx, 3, self._make_batch_table_item(row.get("start"), enabled=not derived))
            table.setItem(row_idx, 4, self._make_batch_table_item(row.get("middle"), enabled=not derived))
            table.setItem(row_idx, 5, self._make_batch_table_item(row.get("end"), enabled=not derived))
            table.setItem(row_idx, 6, self._make_batch_table_item(row.get("initial"), editable=not derived, enabled=not derived))
            table.setItem(row_idx, 7, self._make_batch_table_item(row.get("initial_strategy", ""), enabled=not derived))
            table.setItem(row_idx, 8, self._make_batch_table_item(row.get("min"), editable=not derived, enabled=not derived))
            table.setItem(row_idx, 9, self._make_batch_table_item(row.get("max"), editable=not derived, enabled=not derived))
            if derived:
                table.setItem(row_idx, 10, self._make_batch_table_item("Derived", enabled=False))
            else:
                mode_combo = QComboBox(table)
                mode_combo.addItems(["Free", "Fixed", "Tied"])
                mode = str(row.get("mode") or "Free")
                if mode not in {"Free", "Fixed", "Tied"}:
                    mode = "Free"
                mode_combo.setCurrentText(mode)
                mode_combo.currentTextChanged.connect(self._on_batch_table_edited)
                table.setCellWidget(row_idx, 10, mode_combo)
            table.setItem(row_idx, 11, self._make_batch_table_item(row.get("tie", ""), editable=not derived, enabled=not derived))
            table.setItem(row_idx, 12, self._make_batch_table_item(row.get("notes", ""), enabled=not derived))
        table.resizeRowsToContents()
    except Exception as exc:
        from ...log_utils import log_noncritical_error
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

