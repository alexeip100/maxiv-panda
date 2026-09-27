from __future__ import annotations

from typing import Any

import io

from PyQt6.QtGui import QPixmap
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from . import batch_trend_models
from .batch_analysis_plot import _series_key_from_payload

def _refresh_trend_fit_target_combo(self, *args, **kwargs) -> None:
    """Populate the analytical-trend target combo from currently plotted curves."""
    combo = getattr(self, "cb_trend_fit_target", None)
    if combo is None:
        return
    old_key = ""
    try:
        data = combo.currentData()
        if isinstance(data, dict):
            old_key = str(data.get("key") or "")
    except Exception:
        pass
    try:
        combo.blockSignals(True)
        combo.clear()
        for entry in self._selected_analyze_series():
            payload = entry.get("payload") or {}
            key = _series_key_from_payload(payload)
            label = str(entry.get("label") or key)
            combo.addItem(label, {"key": key, "label": label, "payload": payload, "entry": entry})
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
    self._update_trend_analysis_summary()


def _current_trend_fit_target(self) -> dict[str, Any] | None:
    combo = getattr(self, "cb_trend_fit_target", None)
    if combo is None or combo.count() <= 0:
        return None
    try:
        data = combo.currentData()
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return None


def _on_trend_fit_target_changed(self, *args, **kwargs) -> None:
    self._update_trend_analysis_summary()


def _on_trend_fit_model_changed(self, *args, **kwargs) -> None:
    model = "poly"
    try:
        model = str(self.cb_trend_fit_model.currentData() or "poly")
    except Exception:
        pass
    row = getattr(self, "_trend_fit_order_row", None)
    if row is not None:
        try:
            row.setVisible(model == "poly")
        except Exception:
            pass
    try:
        order = _selected_trend_poly_order(self)
        formula = batch_trend_models.model_formula(model, order=order)
        _set_trend_fit_formula_label(self, formula)
    except Exception:
        pass
    self._update_trend_analysis_summary()



def _set_trend_fit_formula_label(self, formula: str) -> None:
    """Render the selected trend model formula as matplotlib mathtext in a QLabel."""
    label = getattr(self, "lab_trend_fit_formula", None)
    if label is None:
        return
    formula = str(formula or r"$y=f(x)$")
    # Make sure matplotlib receives mathtext, but keep the stored/fallback text clean.
    math_text = formula if formula.startswith("$") and formula.endswith("$") else f"${formula}$"
    try:
        fig = Figure(figsize=(2.8, 0.38), dpi=140)
        fig.patch.set_alpha(0.0)
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_axes([0.01, 0.02, 0.98, 0.96])
        ax.axis("off")
        ax.text(0.0, 0.5, math_text, va="center", ha="left", fontsize=11)
        buf = io.BytesIO()
        canvas.print_png(buf)
        pix = QPixmap()
        if pix.loadFromData(buf.getvalue(), "PNG"):
            label.setPixmap(pix)
            label.setText("")
            label.setMinimumHeight(max(34, int(pix.height() * 0.9)))
            label.setToolTip(
                "Analytical model used for the selected trend fit. "
                "Rendered with matplotlib mathtext; x₀ is fixed to the first finite spectrum number used in the trend."
            )
            return
    except Exception:
        pass
    # Fallback: show mathtext source without a prefix.
    try:
        label.setPixmap(QPixmap())
    except Exception:
        pass
    label.setText(formula.strip("$"))


def _selected_trend_model_code(self) -> str:
    try:
        return str(self.cb_trend_fit_model.currentData() or "poly")
    except Exception:
        return "poly"


def _selected_trend_poly_order(self) -> int:
    try:
        return int(self.cb_trend_fit_poly_order.currentData())
    except Exception:
        return 1


def _fit_selected_analysis_trend(self, *args, **kwargs) -> None:
    """Fit the selected raw trend curve with the selected analytical model."""
    target = _current_trend_fit_target(self)
    if not target:
        QMessageBox.warning(self, "Fit trend", "Select a trend curve to fit.")
        return
    success_only = True
    try:
        success_only = bool(self.chk_trend_fit_success_only.isChecked())
    except Exception:
        pass
    x, y, _used = self._collect_trend_points_for_target(target, success_only=success_only)
    if x.size < 2:
        QMessageBox.warning(self, "Fit trend", "The selected trend does not have enough finite data points.")
        return
    model = _selected_trend_model_code(self)
    order = _selected_trend_poly_order(self)
    try:
        fit = batch_trend_models.fit_trend_model(x, y, model=model, order=order)
    except Exception as exc:
        QMessageBox.warning(self, "Fit trend", f"Could not fit the selected trend:\n\n{exc}")
        return
    key = str(target.get("key") or "")
    label = str(target.get("label") or key)
    fit.update({
        "series_key": key,
        "series_label": label,
        "payload": target.get("payload") or {},
        "source_pass_id": str((self._selected_analyze_pass() or {}).get("id") or ""),
        "source_pass_label": str((self._selected_analyze_pass() or {}).get("label") or ""),
    })
    self._trend_analysis_trial_fit = fit
    self._update_analyze_trend_plot()
    self._update_trend_analysis_summary()


def _accept_trend_analysis_fit(self, *args, **kwargs) -> None:
    fit = getattr(self, "_trend_analysis_trial_fit", None)
    if not isinstance(fit, dict) or not fit.get("series_key"):
        QMessageBox.information(self, "Store trend fit", "Fit a selected trend first.")
        return
    stored = getattr(self, "_trend_analysis_stored_fits", None)
    if not isinstance(stored, dict):
        stored = {}
        self._trend_analysis_stored_fits = stored
    stored[str(fit.get("series_key"))] = dict(fit)
    self._update_analyze_trend_plot()
    self._update_trend_analysis_summary()


def _clear_selected_trend_analysis_fit(self, *args, **kwargs) -> None:
    target = _current_trend_fit_target(self)
    key = str((target or {}).get("key") or "")
    if key:
        try:
            self._trend_analysis_stored_fits.pop(key, None)
        except Exception:
            pass
        try:
            trial = getattr(self, "_trend_analysis_trial_fit", None)
            if isinstance(trial, dict) and str(trial.get("series_key") or "") == key:
                self._trend_analysis_trial_fit = None
        except Exception:
            pass
    self._update_analyze_trend_plot()
    self._update_trend_analysis_summary()


def _clear_all_trend_analysis_fits(self, *args, **kwargs) -> None:
    self._trend_analysis_trial_fit = None
    self._trend_analysis_stored_fits = {}
    self._update_analyze_trend_plot()
    self._update_trend_analysis_summary()


def _trend_fit_summary_line(fit: dict[str, Any]) -> str:
    label = str(fit.get("series_label") or fit.get("series_key") or "trend")
    model_label = str(fit.get("model_label") or fit.get("model") or "model")
    metrics = fit.get("metrics") or {}
    nrmse = batch_trend_models.format_metric(metrics.get("nrmse"))
    params = batch_trend_models.compact_params(fit.get("params") or {})
    return f"{label}: {model_label}; nRMSE={nrmse}" + (f"; {params}" if params else "")


def _update_trend_analysis_summary(self, *args, **kwargs) -> None:
    stored = getattr(self, "_trend_analysis_stored_fits", {}) or {}
    target = _current_trend_fit_target(self)
    target_key = str((target or {}).get("key") or "")
    current_pass_id = str((self._selected_analyze_pass() or {}).get("id") or "")
    trial = getattr(self, "_trend_analysis_trial_fit", None)
    lines: list[str] = []
    quality = "Fit quality: nRMSE = n/a"
    if isinstance(trial, dict) and str(trial.get("series_key") or "") == target_key and (not current_pass_id or str(trial.get("source_pass_id") or "") in {"", current_pass_id}):
        metrics = trial.get("metrics") or {}
        quality = f"Trial fit nRMSE = {batch_trend_models.format_metric(metrics.get('nrmse'))}"
        lines.append("Trial fit:")
        lines.append(_trend_fit_summary_line(trial))
        lines.append("")
    if target_key and target_key in stored and (not current_pass_id or str((stored.get(target_key) or {}).get("source_pass_id") or "") in {"", current_pass_id}):
        fit = stored[target_key]
        if quality.endswith("n/a"):
            metrics = fit.get("metrics") or {}
            quality = f"Stored fit nRMSE = {batch_trend_models.format_metric(metrics.get('nrmse'))}"
        lines.append("Stored fit for selected trend:")
        lines.append(_trend_fit_summary_line(fit))
        lines.append("")
    if stored:
        lines.append("Stored fits for export:")
        for _key, fit in sorted(stored.items(), key=lambda kv: str((kv[1] or {}).get("series_label") or kv[0])):
            if current_pass_id and str((fit or {}).get("source_pass_id") or "") not in {"", current_pass_id}:
                continue
            lines.append("• " + _trend_fit_summary_line(fit))
    else:
        lines.append("No stored analytical trend fits yet.")
    try:
        self.lab_trend_fit_quality.setText(quality)
    except Exception:
        pass
    try:
        self.txt_trend_fit_summary.setPlainText("\n".join(lines))
    except Exception:
        pass
