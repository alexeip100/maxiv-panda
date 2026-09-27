from __future__ import annotations

from typing import Optional, Dict

import numpy as np

from PyQt6.QtWidgets import QTableWidgetItem

from . import fit_engine, fit_models, fit_results, fit_widgets


class FitDialogResultsMixin:
    def _constraint_item(self, text: str) -> QTableWidgetItem:
        return fit_results.make_constraint_item(text)
    def _bg_constraint_display_map(self, bg_type: str) -> dict:
        return fit_results.bg_constraint_display_map(bg_type, bool(self.chk_bg_alpha_fixed.isChecked()))
    def _clear_fit_results_tables(self) -> None:
        self._last_fit_bound_hits = set()
        self._last_fit_result = None
        self._last_fit_data = None
        self._last_fit_bg_type = None
        self._last_fit_status = ""
        try:
            self.act_save_config_curves.setEnabled(False)
        except Exception:
            pass
        self._update_fit_results_tables()
        self._clear_fit_quality_summary()
    def _result_item_for_param(self, text: str, param_name: str) -> QTableWidgetItem:
        return fit_results.make_result_item(text, param_name, getattr(self, "_last_fit_bound_hits", set()) or set())
    def _apply_fit_result_to_widgets(self, result, bg_type: str) -> None:
        fit_engine.apply_fit_result_to_widgets(
            result.params.valuesdict(),
            self._peak_widgets,
            bg_type,
            {
                "b0": self.sb_bg_b0,
                "b1": self.sb_bg_b1,
                "b2": self.sb_bg_b2,
                "bg_alpha": self.sb_bg_alpha,
            },
        )
        values = result.params.valuesdict()
        for ordinal, d in enumerate(self._capture_so_doublet_states() if hasattr(self, "_capture_so_doublet_states") else [], start=1):
            wb = (getattr(self, "_so_doublet_widgets", {}) or {}).get(int(d.get("id", ordinal)))
            if not wb:
                continue
            if f"d{ordinal}_split" in values:
                wb["split"].setValue(float(values[f"d{ordinal}_split"]))
            if f"d{ordinal}_ratio" in values:
                wb["ratio"].setValue(float(values[f"d{ordinal}_ratio"]))
        if hasattr(self, "_apply_so_doublet_relations"):
            self._apply_so_doublet_relations(refresh=False)
    def _clear_fit_quality_summary(self) -> None:
        fit_results.clear_fit_quality_summary(
            self.lbl_fit_status, self.lbl_fit_rss, self.lbl_fit_rms, self.lbl_fit_redchi
        )
    def _compute_fit_quality_metrics(self, result, fit_data: Optional[dict], bg_type: str) -> Dict[str, float]:
        return fit_engine.compute_fit_quality_metrics(result, fit_data, bg_type, self._build_model_from_values)
    def _update_fit_quality_summary(self, status: str, result=None, fit_data: Optional[dict] = None, bg_type: str = "") -> None:
        if result is None or fit_data is None:
            fit_results.update_fit_quality_summary(
                self.lbl_fit_status, self.lbl_fit_rss, self.lbl_fit_rms, self.lbl_fit_redchi, status, None
            )
            return
        metrics = self._compute_fit_quality_metrics(result, fit_data, bg_type)
        fit_results.update_fit_quality_summary(
            self.lbl_fit_status, self.lbl_fit_rss, self.lbl_fit_rms, self.lbl_fit_redchi, status, metrics
        )
    def _populate_fit_results_tables(self, result, bg_type: str, fit_data: Optional[dict] = None) -> None:
        peak_areas = None
        try:
            data = fit_data or getattr(self, "_last_fit_data", None)
            if data is not None:
                xu = np.asarray(data.get("xu", []), dtype=float)
                yu = np.asarray(data.get("yu", []), dtype=float)
                vals = result.params.valuesdict()
                energy_scale = str(getattr(data.get("payload"), "energy_scale", "") or "")
                _total, components = self._build_model_from_values(
                    xu,
                    bg_type=bg_type,
                    values=vals,
                    measured_y=yu if str(bg_type) == "Shirley" else None,
                    energy_scale=energy_scale,
                )
                peak_areas = fit_models.integrated_component_areas(xu, components)
        except Exception:
            peak_areas = None
        fit_results.populate_fit_results_tables(
            self.tbl_fit_results,
            self.tbl_bg_results,
            self._peak_widgets,
            result.params.valuesdict(),
            bg_type,
            getattr(self, "_last_fit_bound_hits", set()) or set(),
            self._constraint_display_text,
            bool(self.chk_bg_alpha_fixed.isChecked()),
            peak_areas=peak_areas,
        )
    def _capture_pre_fit_snapshot(self) -> dict:
        """Capture the editable state immediately before a fit attempt."""
        try:
            curve_state = self._capture_curve_state()
        except Exception:
            curve_state = {}
        try:
            fit_range = self._current_fit_range()
        except Exception:
            fit_range = None
        try:
            title = str(self.ax.get_title())
        except Exception:
            title = ""
        return {
            "curve_state": curve_state,
            "fit_range": tuple(fit_range) if fit_range is not None else None,
            "last_fit_result": getattr(self, "_last_fit_result", None),
            "last_fit_data": getattr(self, "_last_fit_data", None),
            "last_fit_bg_type": getattr(self, "_last_fit_bg_type", None),
            "last_fit_status": getattr(self, "_last_fit_status", ""),
            "title": title,
        }
    def _on_undo_fit(self) -> None:
        """Restore the configuration that existed immediately before the last fit."""
        snap = getattr(self, "_pre_fit_snapshot", None)
        if not snap or getattr(self, "_fit_is_running", False):
            return
        rng = snap.get("fit_range")
        self._fit_range = tuple(rng) if rng is not None else None
        try:
            self._restore_curve_state(snap.get("curve_state") or {})
        except Exception:
            return
        self._last_fit_result = snap.get("last_fit_result")
        self._last_fit_data = snap.get("last_fit_data")
        self._last_fit_bg_type = snap.get("last_fit_bg_type")
        self._last_fit_status = str(snap.get("last_fit_status", "") or "")
        try:
            self.act_save_config_curves.setEnabled(self._last_fit_result is not None)
        except Exception:
            pass
        try:
            self.ax.set_title(str(snap.get("title", "") or ""), pad=2)
        except Exception:
            pass
        try:
            self._update_fit_range_button()
            self._refresh_fit_range_artists()
            self._on_calculate_spectrum()
        except Exception:
            pass
        self._pre_fit_snapshot = None
        try:
            self.btn_undo_fit.setEnabled(False)
        except Exception:
            pass
        self._set_fit_progress("Restored pre-fit configuration")
    def _update_fit_results_tables(self) -> None:
        """Keep the fit-results tables structurally in sync with the UI."""
        try:
            n_peaks = int(self.sb_num_peaks.value()) if hasattr(self, 'sb_num_peaks') else 0
        except Exception:
            n_peaks = 0
        try:
            bg_type = str(self.cb_bg_type.currentText()) if hasattr(self, 'cb_bg_type') else 'constant'
        except Exception:
            bg_type = 'constant'
        try:
            fit_widgets.sync_results_tables_structure(self.tbl_fit_results, self.tbl_bg_results, n_peaks, bg_type)
        except Exception:
            pass
