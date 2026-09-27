from __future__ import annotations

from . import batch_full_export

def _available_analyze_parameter_types(self) -> list[tuple[str, str]]:
    """Return available trend parameter types as (code, label)."""
    results = self._selected_analyze_results()
    peak_codes: set[str] = set()
    bg_codes: set[str] = set()
    quality_codes: set[str] = set()
    for result in results:
        for peak in (result.get("peaks") or []):
            for code in ("E", "H", "Area", "L", "G", "A"):
                if code in peak:
                    peak_codes.add(code)
        bg = result.get("background") or {}
        for code in ("b0", "b1", "b2", "bg_alpha"):
            if code in bg:
                bg_codes.add(code)
        fq = result.get("fit_quality") or {}
        for code in (
            "norm_rms_residual",
            "rms_residual",
            "max_abs_residual",
            "n_bound_hits",
            "rms",
            "rss",
            "redchi_poisson",
            "mae",
            "r2",
        ):
            if code in fq:
                quality_codes.add(code)
        for code in ("chisqr", "redchi", "nfev"):
            if code in result:
                quality_codes.add(code)
    labels = {
        "E": "Peak energy", "H": "Peak height", "Area": "Peak area", "L": "Lorentzian FWHM",
        "G": "Gaussian FWHM", "A": "DS alpha", "b0": "Background b0",
        "b1": "Background b1", "b2": "Background b2", "bg_alpha": "Shirley alpha",
        "norm_rms_residual": "Normalized RMS residual",
        "rms_residual": "RMS residual",
        "max_abs_residual": "Max absolute residual",
        "n_bound_hits": "Parameters near bounds",
        "rms": "Fit RMS (legacy)", "rss": "Residual sum of squares",
        "redchi_poisson": "Reduced chi-square (Poisson estimate)",
        "mae": "Fit MAE", "r2": "Fit R²", "chisqr": "Chi-square",
        "redchi": "Reduced chi-square", "nfev": "Fit evaluations (optimizer effort)",
    }
    ordered: list[tuple[str, str]] = []
    for code in ("E", "H", "Area", "L", "G", "A"):
        if code in peak_codes:
            ordered.append((code, labels[code]))
    for code in ("b0", "b1", "b2", "bg_alpha"):
        if code in bg_codes:
            ordered.append((code, labels[code]))
    for code in (
        "norm_rms_residual",
        "rms_residual",
        "max_abs_residual",
        "n_bound_hits",
        "redchi",
        "chisqr",
        "rss",
        "redchi_poisson",
        "rms",
        "mae",
        "r2",
        "nfev",
    ):
        if code in quality_codes:
            ordered.append((code, labels[code]))
    return ordered

def _refresh_analyze_results_tab(self) -> None:
    """Refresh Analyze-tab controls from currently stored batch results."""
    results = self._selected_analyze_results()
    has_results = bool(results)
    try:
        if hasattr(self, "tabs") and hasattr(self, "_analyze_tab_index"):
            self.tabs.setTabEnabled(self._analyze_tab_index, has_results)
    except Exception:
        pass
    try:
        combo_pass = getattr(self, "cb_analyze_result_pass", None)
        if combo_pass is not None:
            current_id = self._active_analyze_pass_id
            try:
                current_id = str(combo_pass.currentData() or current_id or "")
            except Exception:
                pass
            self._populating_analyze_pass_combo = True
            combo_pass.blockSignals(True)
            combo_pass.clear()
            for entry in getattr(self, "_batch_passes", []) or []:
                combo_pass.addItem(str(entry.get("label") or entry.get("id") or "Pass"), str(entry.get("id") or ""))
            target = current_id or getattr(self, "_active_analyze_pass_id", None)
            if target:
                for i in range(combo_pass.count()):
                    if str(combo_pass.itemData(i)) == str(target):
                        combo_pass.setCurrentIndex(i)
                        break
            combo_pass.blockSignals(False)
            self._populating_analyze_pass_combo = False
    except Exception:
        try:
            self._populating_analyze_pass_combo = False
        except Exception:
            pass
    try:
        ok = sum(1 for r in results if str(r.get("status") or "") in {"success", "warning"})
        failed = sum(1 for r in results if str(r.get("status") or "") == "failed")
        selected_pass = self._selected_analyze_pass()
        pass_label = str((selected_pass or {}).get("label") or "Selected pass")
        self.lab_analyze_status.setText(
            f"{pass_label}: {len(results)} spectra ({ok} fitted with success/warning, {failed} failed)."
            if has_results else "No completed batch passes in memory yet."
        )
    except Exception:
        pass
    try:
        selected_pass = self._selected_analyze_pass() or {}
        stored_full = bool(selected_pass.get("store_all_fit_results", False))
        has_curve_data = any(batch_full_export.result_has_curves(r) for r in (selected_pass.get("results") or []))
        self.btn_export_all_batch_fits.setEnabled(bool(stored_full and has_curve_data))
        if stored_full and has_curve_data:
            self.btn_export_all_batch_fits.setToolTip(
                "Export the selected pass as one ZIP containing one plain CSV per stored fit plus batch_manifest.csv."
            )
        else:
            self.btn_export_all_batch_fits.setToolTip(
                "No full fit curves are stored for this pass. Enable 'Store all fit results' before running a pass to use this export."
            )
    except Exception:
        pass
    old_code = None
    try:
        old_code = self.cb_analyze_parameter_type.currentData()
    except Exception:
        old_code = None
    types = self._available_analyze_parameter_types()
    self._populating_analyze_parameters = True
    try:
        self.cb_analyze_parameter_type.blockSignals(True)
        self.cb_analyze_parameter_type.clear()
        for code, label in types:
            self.cb_analyze_parameter_type.addItem(label, code)
        if old_code is not None:
            for i in range(self.cb_analyze_parameter_type.count()):
                if self.cb_analyze_parameter_type.itemData(i) == old_code:
                    self.cb_analyze_parameter_type.setCurrentIndex(i)
                    break
        self.cb_analyze_parameter_type.blockSignals(False)
    finally:
        self._populating_analyze_parameters = False
    self._populate_analyze_parameter_tree()
    self._refresh_smoothing_target_combo()
    self._refresh_trend_fit_target_combo()
    self._update_analyze_trend_plot()










