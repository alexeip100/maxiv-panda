from __future__ import annotations

from typing import Any

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidgetItem
from matplotlib.ticker import AutoMinorLocator

def _on_analyze_parameter_type_changed(self, *_args) -> None:
    self._populate_analyze_parameter_tree()
    self._refresh_smoothing_target_combo()
    self._refresh_trend_fit_target_combo()
    self._update_analyze_trend_plot()

def _on_analyze_parameter_item_changed(self, *_args) -> None:
    if bool(getattr(self, "_populating_analyze_parameters", False)):
        return
    self._refresh_smoothing_target_combo()
    self._refresh_trend_fit_target_combo()
    self._update_analyze_trend_plot()

def _populate_analyze_parameter_tree(self) -> None:
    tree = getattr(self, "tree_analyze_parameters", None)
    combo = getattr(self, "cb_analyze_parameter_type", None)
    if tree is None or combo is None:
        return
    code = combo.currentData()
    results = self._selected_analyze_results()
    checked_old = set()
    try:
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if item.checkState(0) == Qt.CheckState.Checked:
                checked_old.add(str(item.data(0, self.ROLE_KEY)))
    except Exception:
        pass
    self._populating_analyze_parameters = True
    try:
        tree.clear()
        if not code or not results:
            return
        items: list[tuple[str, str, dict[str, Any]]] = []
        if code in {"E", "H", "Area", "L", "G", "A"}:
            seen: dict[int, str] = {}
            for result in results:
                for peak in (result.get("peaks") or []):
                    try:
                        idx = int(peak.get("index"))
                    except Exception:
                        continue
                    if code in peak and idx not in seen:
                        seen[idx] = str(peak.get("label") or f"P{idx}")
            for idx in sorted(seen):
                key = f"peak:{idx}:{code}"
                label = f"P{idx}: {seen[idx]}"
                items.append((key, label, {"kind": "peak", "index": idx, "param": code}))
        elif code in {"b0", "b1", "b2", "bg_alpha"}:
            key = f"background:{code}"
            items.append((key, code, {"kind": "background", "param": code}))
        else:
            key = f"quality:{code}"
            items.append((key, combo.currentText() or str(code), {"kind": "quality", "param": code}))

        item_keys = {key for key, _label, _payload in items}
        checked_existing = checked_old.intersection(item_keys)
        check_all_by_default = not checked_existing

        for _n, (key, label, payload) in enumerate(items):
            item = QTreeWidgetItem([label])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            # When the user selects a new Y-parameter type, the previously checked
            # keys usually belong to another parameter family. In that case, check
            # all available curves by default so a trend appears immediately. If the
            # same parameter family is merely refreshed, preserve the user's checks.
            default_checked = check_all_by_default or (key in checked_existing)
            item.setCheckState(0, Qt.CheckState.Checked if default_checked else Qt.CheckState.Unchecked)
            item.setData(0, self.ROLE_KEY, key)
            item.setData(0, self.ROLE_PAYLOAD, payload)
            tree.addTopLevelItem(item)
    finally:
        self._populating_analyze_parameters = False
    self._refresh_smoothing_target_combo()
    self._refresh_trend_fit_target_combo()

def _selected_analyze_series(self) -> list[dict[str, Any]]:
    tree = getattr(self, "tree_analyze_parameters", None)
    if tree is None:
        return []
    selected = []
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        try:
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            payload = item.data(0, self.ROLE_PAYLOAD) or {}
            selected.append({"label": str(item.text(0)), "payload": payload})
        except Exception:
            continue
    return selected

def _value_for_analyze_series(self, result: dict[str, Any], series_payload: dict[str, Any]) -> float | None:
    kind = str(series_payload.get("kind") or "")
    param = str(series_payload.get("param") or "")
    try:
        if kind == "peak":
            idx = int(series_payload.get("index"))
            for peak in (result.get("peaks") or []):
                if int(peak.get("index")) == idx and param in peak:
                    value = float(peak.get(param))
                    return value if np.isfinite(value) else None
        if kind == "background":
            bg = result.get("background") or {}
            if param in bg:
                value = float(bg.get(param))
                return value if np.isfinite(value) else None
        if kind == "quality":
            if param in result:
                value = float(result.get(param))
                return value if np.isfinite(value) else None
            fq = result.get("fit_quality") or {}
            if param in fq:
                value = float(fq.get(param))
                return value if np.isfinite(value) else None
    except Exception:
        return None
    return None

def _series_key_from_payload(payload: dict[str, Any]) -> str:
    kind = str((payload or {}).get("kind") or "")
    if kind == "peak":
        return f"peak:{payload.get('index')}:{payload.get('param')}"
    return f"{kind}:{payload.get('param')}"

def _update_analyze_trend_plot(self, *args, **kwargs) -> None:
    plot = getattr(self, "plot_analyze_trend", None)
    if plot is None:
        return
    results = self._selected_analyze_results()
    series = self._selected_analyze_series()
    if not results:
        plot.clear("Run a batch fit to create in-memory results")
        self._style_prepare_plot_area(plot)
        return
    if not series:
        plot.clear("Select one or several parameters to plot")
        self._style_prepare_plot_area(plot)
        return
    plot.fig.clear()
    ax = plot.fig.add_subplot(111)
    plot.ax = ax
    any_plotted = False
    for entry in series:
        xs = []
        ys = []
        for result in results:
            value = self._value_for_analyze_series(result, entry.get("payload") or {})
            if value is None:
                continue
            try:
                xs.append(int(result.get("spectrum_index") or len(xs) + 1))
                ys.append(float(value))
            except Exception:
                continue
        if xs and ys:
            ax.plot(xs, ys, marker="o", linewidth=1.2, label=str(entry.get("label") or "parameter"))
            any_plotted = True
    selected_keys = {_series_key_from_payload(entry.get("payload") or {}) for entry in series}
    current_pass_id = str((self._selected_analyze_pass() or {}).get("id") or "")
    trend = getattr(self, "_active_trend_model", None)
    if trend:
        try:
            target_key = str(trend.get("target_key") or "")
            if target_key in selected_keys:
                tx = np.asarray(trend.get("x") or [], dtype=float)
                vals = trend.get("values_by_spectrum") or []
                ty = np.asarray([float(v.get("value")) for v in vals], dtype=float)
                if tx.size and ty.size == tx.size:
                    order = int(((trend.get("model") or {}).get("order") or 0))
                    ax.plot(tx, ty, linewidth=2.0, linestyle="--", label=f"constraint poly{order}: {trend.get('target_label')}")
                    any_plotted = True
        except Exception:
            pass
    try:
        stored = getattr(self, "_trend_analysis_stored_fits", {}) or {}
        for key, fit in stored.items():
            if str(key) not in selected_keys:
                continue
            if current_pass_id and str(fit.get("source_pass_id") or "") not in {"", current_pass_id}:
                continue
            tx = np.asarray(fit.get("x") or [], dtype=float)
            ty = np.asarray(fit.get("y_fit") or [], dtype=float)
            if tx.size and ty.size == tx.size:
                ax.plot(tx, ty, linewidth=2.0, linestyle="-.", label=f"fit: {fit.get('series_label') or key}")
                any_plotted = True
    except Exception:
        pass
    try:
        trial = getattr(self, "_trend_analysis_trial_fit", None)
        if isinstance(trial, dict) and str(trial.get("series_key") or "") in selected_keys and (not current_pass_id or str(trial.get("source_pass_id") or "") in {"", current_pass_id}):
            tx = np.asarray(trial.get("x") or [], dtype=float)
            ty = np.asarray(trial.get("y_fit") or [], dtype=float)
            if tx.size and ty.size == tx.size:
                ax.plot(tx, ty, linewidth=2.2, linestyle=":", label=f"trial: {trial.get('series_label') or trial.get('series_key')}")
                any_plotted = True
    except Exception:
        pass
    if not any_plotted:
        ax.text(0.5, 0.5, "No finite values for the selected parameter(s)", transform=ax.transAxes, ha="center", va="center")
    try:
        ylabel = self.cb_analyze_parameter_type.currentText() or "Parameter value"
    except Exception:
        ylabel = "Parameter value"
    ax.set_xlabel("Spectrum number")
    ax.set_ylabel(ylabel)
    try:
        selected_pass = self._selected_analyze_pass()
        pass_label = str((selected_pass or {}).get("label") or "Batch-fit")
    except Exception:
        pass_label = "Batch-fit"
    ax.set_title(f"{pass_label} parameter trends")
    try:
        from matplotlib.ticker import MaxNLocator
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    except Exception:
        pass
    try:
        ax.grid(True, which="major", alpha=0.35)
        ax.xaxis.set_minor_locator(AutoMinorLocator())
        ax.yaxis.set_minor_locator(AutoMinorLocator())
        ax.grid(True, which="minor", alpha=0.15)
    except Exception:
        pass
    if any_plotted:
        try:
            ax.legend(loc="best", fontsize=8)
        except Exception:
            pass
    try:
        plot.fig.subplots_adjust(left=0.10, right=0.985, top=0.92, bottom=0.12)
    except Exception:
        pass
    self._style_prepare_plot_area(plot)
    try:
        plot.canvas.draw_idle()
    except Exception:
        pass

