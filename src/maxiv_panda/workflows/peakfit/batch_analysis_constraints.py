from __future__ import annotations

from typing import Any

import re

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTableWidgetItem
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox


def _derived_so_minor_peak_indices(self, source_pass_id: str | None = None) -> set[int]:
    """Return peak indices that are derived minor members of SO doublets.

    Minor-member peak parameters remain useful diagnostics in Analyze plots, but
    they are not independent next-pass constraint targets.
    """
    results = None
    if source_pass_id:
        try:
            source_pass = self._pass_by_id(str(source_pass_id))
            if isinstance(source_pass, dict):
                results = list(source_pass.get("results") or [])
        except Exception:
            results = None
    if results is None:
        try:
            results = list(self._selected_analyze_results() or [])
        except Exception:
            results = []

    minor_indices: set[int] = set()
    for result in results:
        fit_state = (result or {}).get("fit_state") or {}
        for doublet in fit_state.get("so_doublets") or []:
            try:
                minor_indices.add(int(doublet.get("minor")))
            except Exception:
                continue
    return minor_indices

def _is_derived_so_minor_target(self, target: dict[str, Any] | None, source_pass_id: str | None = None) -> bool:
    """Return True when *target* belongs to a derived SO-doublet minor peak."""
    if not isinstance(target, dict):
        return False
    payload = target.get("payload") or {}
    if str(payload.get("kind") or "") != "peak":
        return False
    try:
        peak_index = int(payload.get("index"))
    except Exception:
        return False
    return peak_index in self._derived_so_minor_peak_indices(source_pass_id)

def _refresh_smoothing_target_combo(self) -> None:
    """Populate the smoothing-target combo from the current Analyze parameter tree."""
    combo = getattr(self, "cb_smooth_target", None)
    tree = getattr(self, "tree_analyze_parameters", None)
    if combo is None or tree is None:
        return
    old_key = None
    try:
        old_key = str(combo.currentData().get("key") if isinstance(combo.currentData(), dict) else "")
    except Exception:
        old_key = None
    try:
        combo.blockSignals(True)
        combo.clear()
        minor_peak_indices = self._derived_so_minor_peak_indices()
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            payload = item.data(0, self.ROLE_PAYLOAD) or {}
            # Fit-quality/optimizer diagnostics are plottable but are not valid
            # next-pass constraints, so do not offer them as smoothing targets.
            if str((payload or {}).get("kind") or "") == "quality":
                continue
            if str((payload or {}).get("kind") or "") == "peak" and str((payload or {}).get("param") or "") == "Area":
                continue
            # SO-doublet minor members are derived from the independent doublet
            # parameters. Keep their trends plottable, but do not present them as
            # independently constrainable targets for a later pass.
            if str((payload or {}).get("kind") or "") == "peak":
                try:
                    if int(payload.get("index")) in minor_peak_indices:
                        continue
                except Exception:
                    pass
            key = str(item.data(0, self.ROLE_KEY) or "")
            label = str(item.text(0) or key)
            combo.addItem(label, {"key": key, "label": label, "payload": payload})
        if old_key:
            for i in range(combo.count()):
                data = combo.itemData(i) or {}
                if isinstance(data, dict) and str(data.get("key") or "") == old_key:
                    combo.setCurrentIndex(i)
                    break
        combo.blockSignals(False)
    except Exception:
        try:
            combo.blockSignals(False)
        except Exception:
            pass

def _current_smoothing_target(self) -> dict[str, Any] | None:
    combo = getattr(self, "cb_smooth_target", None)
    if combo is None or combo.count() <= 0:
        return None
    try:
        data = combo.currentData()
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None

def _target_sort_key(self, target: dict[str, Any]) -> str:
    payload = target.get("payload") or {}
    kind = str(payload.get("kind") or "")
    if kind == "peak":
        return f"peak:{payload.get('index')}:{payload.get('param')}"
    return f"{kind}:{payload.get('param')}"

def _target_short_label(self, target: dict[str, Any] | None = None) -> str:
    if target is None:
        target = self._current_smoothing_target() or {}
    payload = target.get("payload") or {}
    kind = str(payload.get("kind") or "")
    if kind == "peak":
        code = str(payload.get("param") or "")
        label_map = {"E": "Energy", "H": "Height", "Area": "Area", "L": "LFWHM", "G": "GFWHM", "A": "Alpha"}
        return f"P{payload.get('index')} {label_map.get(code, code)}"
    if kind == "background":
        return f"BG {payload.get('param')}"
    if kind == "quality":
        return str(target.get("label") or payload.get("param") or "quality")
    return str(target.get("label") or "parameter")

def _collect_trend_points_for_target(self, target: dict[str, Any], *, success_only: bool = True) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    """Return finite x/y trend points for the selected target and Analyze pass."""
    payload = target.get("payload") or {}
    xs: list[float] = []
    ys: list[float] = []
    used_results: list[dict[str, Any]] = []
    for result in self._selected_analyze_results():
        status = str(result.get("status") or "")
        if success_only and status not in {"success", "warning"}:
            continue
        value = self._value_for_analyze_series(result, payload)
        if value is None:
            continue
        try:
            x = float(result.get("spectrum_index") or len(xs) + 1)
            y = float(value)
        except Exception:
            continue
        if not (np.isfinite(x) and np.isfinite(y)):
            continue
        xs.append(x)
        ys.append(y)
        used_results.append(result)
    return np.asarray(xs, dtype=float), np.asarray(ys, dtype=float), used_results

def _table_bounds_for_target(self, target: dict[str, Any]) -> tuple[float | None, float | None]:
    """Look up Min/Max bounds from the editable batch table for a target parameter."""
    payload = target.get("payload") or {}
    kind = str(payload.get("kind") or "")
    if kind == "quality":
        return None, None
    comp = "BG"
    param = str(payload.get("param") or "")
    if kind == "peak":
        comp = f"P{payload.get('index')}"
        code_map = {"E": "Energy", "H": "Height", "Area": "Area", "L": "LFWHM", "G": "GFWHM", "A": "Alpha"}
        param = code_map.get(param, param)
    table = getattr(self, "tbl_batch_parameters", None)
    if table is None:
        return None, None
    errors: list[str] = []
    for row in range(table.rowCount()):
        c0 = self._cell_text(table, row, 0)
        c1 = self._cell_text(table, row, 1)
        if c0 == comp and c1 == param:
            mn = self._parse_optional_float(self._cell_text(table, row, 8), row=row, column_name="Min", errors=errors)
            mx = self._parse_optional_float(self._cell_text(table, row, 9), row=row, column_name="Max", errors=errors)
            return mn, mx
    return None, None

def _fit_selected_smooth_trend(self, *args, **kwargs) -> None:
    """Fit a low-order polynomial to one selected trend and overlay it on the plot."""
    target = self._current_smoothing_target()
    if not target:
        QMessageBox.warning(self, "Fit smooth trend", "No fit parameter is available for smoothing. Fit-quality diagnostics can be plotted, but not used as next-pass constraints.")
        return
    if self._is_derived_so_minor_target(target):
        QMessageBox.warning(
            self,
            "Fit smooth trend",
            "SO-doublet minor members are derived parameters and cannot be used as independent next-pass constraints. "
            "Constrain the major member and/or SO-doublet parameters instead.",
        )
        return
    try:
        order = int(self.cb_smooth_poly_order.currentData())
    except Exception:
        order = 0
    success_only = bool(getattr(self, "chk_smooth_success_only", None) is None or self.chk_smooth_success_only.isChecked())
    xs, ys, used_results = self._collect_trend_points_for_target(target, success_only=success_only)
    if xs.size == 0:
        QMessageBox.warning(self, "Fit smooth trend", "No finite values are available for this parameter trend.")
        return
    if xs.size <= order:
        QMessageBox.warning(self, "Fit smooth trend", f"Polynomial order {order} needs at least {order + 1} points.")
        return
    try:
        coeff = np.polyfit(xs, ys, order)
        desired = np.polyval(coeff, xs)
    except Exception as exc:
        QMessageBox.warning(self, "Fit smooth trend", f"Could not fit polynomial trend:\n\n{exc}")
        return
    if bool(getattr(self, "chk_smooth_clip_bounds", None) is not None and self.chk_smooth_clip_bounds.isChecked()):
        mn, mx = self._table_bounds_for_target(target)
        if mn is not None or mx is not None:
            lo = -np.inf if mn is None else float(mn)
            hi = np.inf if mx is None else float(mx)
            desired = np.clip(desired, lo, hi)
    residual = ys - desired
    rms = float(np.sqrt(np.nanmean(residual ** 2))) if residual.size else 0.0
    selected_pass = self._selected_analyze_pass() or {}
    pass_id = str(selected_pass.get("id") or self._active_analyze_pass_id or "")
    target_label = self._target_short_label(target)
    trend_id = f"trend_{len(getattr(self, '_batch_trend_models', []) or []) + 1:03d}"
    model = self._json_clean_value({
        "id": trend_id,
        "source_pass_id": pass_id,
        "source_pass_label": str(selected_pass.get("label") or pass_id),
        "target": target,
        "target_key": self._target_sort_key(target),
        "target_label": target_label,
        "model": {"type": "polynomial", "order": int(order), "coefficients": [float(c) for c in coeff]},
        "x": [float(v) for v in xs.tolist()],
        "y_raw": [float(v) for v in ys.tolist()],
        "values_by_spectrum": [
            {"spectrum_index": int(round(float(x))), "value": float(v)}
            for x, v in zip(xs.tolist(), desired.tolist())
        ],
        "rms": rms,
        "n_points": int(xs.size),
    })
    self._active_trend_model = model
    self._batch_trend_models.append(model)
    try:
        self.lab_smooth_status.setText(
            f"Fitted {target_label} with poly{order} from {model.get('source_pass_label')}; "
            f"{xs.size} points, RMS = {rms:.4g}. Use Add/update constraint to include it in the next pass."
        )
    except Exception:
        pass
    self._update_analyze_trend_plot()

def _add_update_next_pass_constraint(self, *args, **kwargs) -> None:
    """Turn the currently fitted smooth trend into an enabled next-pass constraint."""
    model = getattr(self, "_active_trend_model", None)
    if not model:
        QMessageBox.warning(self, "Add/update constraint", "Fit a smooth trend first.")
        return
    source_pass_id = str(model.get("source_pass_id") or "")
    if self._is_derived_so_minor_target(model.get("target") or {}, source_pass_id):
        QMessageBox.warning(
            self,
            "Add/update constraint",
            "SO-doublet minor members are derived parameters and cannot be added as independent next-pass constraints.",
        )
        return
    target_key = str(model.get("target_key") or "")
    order = int(((model.get("model") or {}).get("order") or 0))
    constraint = self._json_clean_value({
        "id": f"constraint_{target_key}_{source_pass_id}".replace(":", "_"),
        "source_pass_id": source_pass_id,
        "source_pass_label": str(model.get("source_pass_label") or source_pass_id),
        "trend_model_id": str(model.get("id") or ""),
        "target": model.get("target") or {},
        "target_key": target_key,
        "target_label": str(model.get("target_label") or target_key),
        "mode": "fixed",
        "model": model.get("model") or {},
        "values_by_spectrum": list(model.get("values_by_spectrum") or []),
        "rms": model.get("rms"),
        "enabled": True,
        "label": f"{model.get('target_label') or target_key} poly{order} from {model.get('source_pass_label') or source_pass_id}",
    })
    constraints = [c for c in (getattr(self, "_batch_next_constraints", []) or []) if str(c.get("target_key") or "") != target_key]
    constraints.append(constraint)
    self._batch_next_constraints = constraints
    self._refresh_next_constraints_table()
    try:
        self.lab_smooth_status.setText(f"Added next-pass constraint: {constraint.get('label')}.")
    except Exception:
        pass

def _refresh_next_constraints_table(self) -> None:
    table = getattr(self, "tbl_next_constraints", None)
    if table is None:
        return
    try:
        table.setRowCount(0)
        for constraint in getattr(self, "_batch_next_constraints", []) or []:
            row = table.rowCount()
            table.insertRow(row)
            use_item = QTableWidgetItem("")
            use_item.setFlags(use_item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            use_item.setCheckState(Qt.CheckState.Checked if bool(constraint.get("enabled", True)) else Qt.CheckState.Unchecked)
            table.setItem(row, 0, use_item)
            table.setItem(row, 1, self._make_batch_table_item(constraint.get("target_label") or "", editable=False))
            table.setItem(row, 2, self._make_batch_table_item(constraint.get("source_pass_label") or constraint.get("source_pass_id") or "", editable=False))
            order = ((constraint.get("model") or {}).get("order") if isinstance(constraint.get("model"), dict) else None)
            table.setItem(row, 3, self._make_batch_table_item(f"poly{order}", editable=False))
            rms = constraint.get("rms")
            table.setItem(row, 4, self._make_batch_table_item("" if rms is None else f"{float(rms):.4g}", editable=False))
    except Exception:
        pass

def _enabled_next_constraints_from_table(self) -> list[dict[str, Any]]:
    table = getattr(self, "tbl_next_constraints", None)
    constraints = list(getattr(self, "_batch_next_constraints", []) or [])
    if table is None:
        return [c for c in constraints if bool(c.get("enabled", True))]
    enabled: list[dict[str, Any]] = []
    for row, constraint in enumerate(constraints):
        use = True
        try:
            item = table.item(row, 0)
            use = item is None or item.checkState() == Qt.CheckState.Checked
        except Exception:
            pass
        constraint["enabled"] = bool(use)
        if use:
            enabled.append(constraint)
    return enabled

def _constraint_compact_list(self, constraints: list[dict[str, Any]]) -> str:
    pieces = []
    for c in constraints:
        target = str(c.get("target_label") or c.get("target_key") or "parameter")
        order = ((c.get("model") or {}).get("order") if isinstance(c.get("model"), dict) else 0)
        pieces.append(f"{target} poly{order}")
    return ", ".join(pieces) if pieces else "none"

def _next_strategy_pass_number(self) -> int:
    nums: list[int] = []
    for strategy in getattr(self, "_batch_strategies", []) or []:
        m = re.search(r"pass_(\d+)", str(strategy.get("pass_id") or strategy.get("id") or ""))
        if m:
            try:
                nums.append(int(m.group(1)))
            except Exception:
                pass
    for p in getattr(self, "_batch_passes", []) or []:
        m = re.search(r"pass_(\d+)", str(p.get("id") or ""))
        if m:
            try:
                nums.append(int(m.group(1)))
            except Exception:
                pass
    return (max(nums) + 1) if nums else 2

def _prepare_next_constrained_pass(self, *args, **kwargs) -> None:
    """Create/update the next constrained strategy and switch back to the Run tab."""
    constraints = self._enabled_next_constraints_from_table()
    if not constraints:
        QMessageBox.warning(self, "Prepare next pass", "Add and enable at least one smooth-trend constraint first.")
        return
    invalid_minor_constraints = [
        c for c in constraints
        if self._is_derived_so_minor_target(c.get("target") or {}, str(c.get("source_pass_id") or ""))
    ]
    if invalid_minor_constraints:
        QMessageBox.warning(
            self,
            "Prepare next pass",
            "A stored constraint targets a derived SO-doublet minor member. Remove it and constrain the major member and/or SO-doublet parameters instead.",
        )
        return
    source_pass_id = str(constraints[0].get("source_pass_id") or "")
    if not source_pass_id or self._pass_by_id(source_pass_id) is None:
        QMessageBox.warning(self, "Prepare next pass", "The source pass for the selected constraints is not available in memory.")
        return
    source_labels = {str(c.get("source_pass_id") or "") for c in constraints}
    if len(source_labels) > 1:
        QMessageBox.warning(self, "Prepare next pass", "This version expects next-pass constraints to come from one source pass. Please keep constraints from the same result pass.")
        return
    preferred = self._strategy_by_id(getattr(self, "_preferred_next_strategy_id", None))
    if preferred and str(preferred.get("kind") or "") == "constrained" and not bool(preferred.get("has_results")):
        n = int(re.search(r"pass_(\d+)", str(preferred.get("pass_id") or "pass_2")).group(1)) if re.search(r"pass_(\d+)", str(preferred.get("pass_id") or "")) else self._next_strategy_pass_number()
        pass_id = str(preferred.get("pass_id") or f"pass_{n}")
        strategy_id = str(preferred.get("id") or f"strategy_{pass_id}")
    else:
        n = self._next_strategy_pass_number()
        pass_id = f"pass_{n}"
        strategy_id = f"strategy_{pass_id}"
    constraint_text = self._constraint_compact_list(constraints)
    label = f"Pass {n}: constrained — {constraint_text}"
    source_pass = self._pass_by_id(source_pass_id) or {}
    strategy = self._json_clean_value({
        "id": strategy_id,
        "pass_id": pass_id,
        "label": label,
        "kind": "constrained",
        "source_pass_id": source_pass_id,
        "source_pass_label": str(source_pass.get("label") or source_pass_id),
        "constraints": constraints,
        "start_from": "source_pass_results",
        "has_results": bool(self._pass_by_id(pass_id)),
        "description": f"Prepared from {source_pass.get('label') or source_pass_id}. Constraints: {constraint_text}. Press Run batch fit to start.",
    })
    strategies = [s for s in (getattr(self, "_batch_strategies", []) or []) if str(s.get("id") or "") != strategy_id]
    strategies.append(strategy)
    self._batch_strategies = strategies
    self._preferred_next_strategy_id = strategy_id
    self._refresh_strategy_combo()
    self._refresh_pass_status_label(
        f"Pass status: prepared {label}.\nSource: {source_pass.get('label') or source_pass_id}.\nConstraints: {constraint_text}.\nPress Run batch fit to start."
    )
    try:
        self.tabs.setCurrentIndex(self._run_tab_index)
    except Exception:
        pass
    try:
        self.lab_smooth_status.setText(f"Prepared {label} and selected it on the Run tab.")
    except Exception:
        pass

