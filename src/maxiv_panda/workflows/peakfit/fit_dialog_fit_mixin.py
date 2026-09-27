from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from PyQt6.QtWidgets import QApplication
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from . import fit_engine, fit_plotting
from .fit_exceptions import FitCancelled
from ...log_utils import log_noncritical_error


class FitDialogFitMixin:
    def _show_warning(self, title: str, message: str) -> None:
        try:
            QMessageBox.warning(self, title, message)
        except Exception as exc:
            log_noncritical_error(f"showing warning dialog: {title}", exc, logger=self._logger)
    def _set_fit_progress(self, text: str) -> None:
        try:
            self.lbl_fit_progress.setText(text)
        except Exception:
            pass
        try:
            QApplication.processEvents()
        except Exception:
            pass
    def _advance_fit_indicator(self) -> None:
        try:
            if not getattr(self, "_fit_is_running", False):
                return
            frames = getattr(self, "_fit_spinner_frames", ["◴", "◷", "◶", "◵"])
            self._fit_spinner_index = (int(getattr(self, "_fit_spinner_index", 0)) + 1) % max(len(frames), 1)
            self.lbl_fit_state.setText(frames[self._fit_spinner_index])
        except Exception:
            pass
    def _set_fit_running_state(self, running: bool) -> None:
        self._fit_is_running = bool(running)
        if running:
            self._fit_cancel_requested = False
            try:
                self.btn_start_fit.setChecked(True)
                self.btn_start_fit.setText("Stop fit")
            except Exception:
                pass
            try:
                self._fit_spinner_index = 0
                self.lbl_fit_state.setText(self._fit_spinner_frames[0])
                self.lbl_fit_state.setStyleSheet("QLabel { color: #b36b00; font-size: 14pt; font-weight: bold; }")
                self.lbl_fit_state.setToolTip("Fitting in progress")
                self._fit_spinner_timer.start()
            except Exception:
                pass
        else:
            try:
                self._fit_spinner_timer.stop()
            except Exception:
                pass
            try:
                self.btn_start_fit.setChecked(False)
                self.btn_start_fit.setText("Start fit")
            except Exception:
                pass
            try:
                self.lbl_fit_state.setText("○")
                self.lbl_fit_state.setStyleSheet("QLabel { color: #7a7a7a; font-size: 14pt; }")
                self.lbl_fit_state.setToolTip("Fitting stopped")
            except Exception:
                pass
    def _draw_intermediate_fit(self, xu, fit_values: dict, bg_type: str, fit_data: dict, iteration: int) -> None:
        try:
            self._remember_fit_legend_position()
        except Exception:
            pass
        state = fit_plotting.draw_intermediate_fit(
            self.ax,
            self.ax_res,
            self.canvas,
            self._clear_bg_artist,
            self._clear_peak_markers,
            self._clear_calc_artists,
            self._build_model_from_values,
            getattr(self, "_peak_widgets", []),
            xu,
            fit_values,
            bg_type,
            fit_data,
            view_state=getattr(self, "_fit_view_state", None),
            doublets=(self._capture_so_doublet_states() if hasattr(self, "_capture_so_doublet_states") else []),
            doublet_view=(self._doublet_view_enabled() if hasattr(self, "_doublet_view_enabled") else False),
        )
        if isinstance(state, dict):
            bg_artist = state.get("bg_artist")
            self._bg_artist = bg_artist
            self._bg_artists = [bg_artist] if bg_artist is not None else []
            self._calc_artists = state.get("calc_artists", [])
            try:
                self._refresh_fit_legend()
            except Exception:
                pass
        try:
            self._refresh_peak_markers()
        except Exception:
            pass
        # ax.clear() inside the intermediate redraw removes the fit-range
        # boundaries together with all other axes artists. Recreate them after
        # every live fit update so the selected fitting interval remains visible.
        try:
            self._refresh_fit_range_artists()
            # Force this repaint while the optimizer owns the event loop; an
            # idle draw can otherwise be postponed until the next live redraw.
            self.canvas.draw()
        except Exception:
            pass
    def _collect_bound_hit_params(self, result) -> set[str]:
        return fit_engine.collect_bound_hit_params(result)
    def _human_readable_param_name(self, param_name: str) -> str:
        return fit_engine.human_readable_param_name(param_name)
    def _collect_fit_curve_data(self):
        return fit_engine.collect_fit_curve_data(
            self._payload_by_key,
            self._get_checked_key(),
            fit_range=self._current_fit_range() if hasattr(self, "_current_fit_range") else None,
        )
    def _build_model_from_values(self, xu, bg_type: Optional[str] = None, values: Optional[dict] = None, measured_y=None, energy_scale: str = ""):
        return fit_engine.build_model_from_dialog_state(
            xu,
            getattr(self, "_peak_widgets", []),
            {
                "b0": self.sb_bg_b0,
                "b1": self.sb_bg_b1,
                "b2": self.sb_bg_b2,
                "bg_alpha": self.sb_bg_alpha,
            },
            bg_type=bg_type,
            values=values,
            measured_y=measured_y,
            energy_scale=energy_scale,
        )
    def _collect_peak_specs(self) -> List[Dict[str, Any]]:
        return fit_engine.collect_peak_specs(getattr(self, "_peak_widgets", []), self._param_mode)
    def _validate_fit_ready(self):
        fit_data, err = self._collect_fit_curve_data()
        if fit_data is None:
            return None, err
        try:
            bg_type = str(self.cb_bg_type.currentText())
        except Exception:
            bg_type = "constant"
        doublets = self._capture_so_doublet_states() if hasattr(self, "_capture_so_doublet_states") else []
        for ordinal, d in enumerate(doublets, start=1):
            if float(d.get("split_min", 0.0)) > float(d.get("split_max", 0.0)):
                return None, f"SO doublet {ordinal}: splitting min is larger than max."
            if str(d.get("split_mode", "Fixed")) == "Free" and not (float(d.get("split_min", 0.0)) <= float(d.get("split", 0.0)) <= float(d.get("split_max", 0.0))):
                return None, f"SO doublet {ordinal}: initial splitting is outside its bounds."
            if float(d.get("ratio", 0.0)) <= 0 or float(d.get("ratio_min", 0.0)) <= 0:
                return None, f"SO doublet {ordinal}: intensity ratio must be > 0."
            if float(d.get("ratio_min", 0.0)) > float(d.get("ratio_max", 0.0)):
                return None, f"SO doublet {ordinal}: ratio min is larger than max."
            if str(d.get("ratio_mode", "Fixed")) == "Free" and not (float(d.get("ratio_min", 0.0)) <= float(d.get("ratio", 0.0)) <= float(d.get("ratio_max", 0.0))):
                return None, f"SO doublet {ordinal}: initial ratio is outside its bounds."
        err = fit_engine.validate_fit_ready(
            fit_data,
            self._collect_peak_specs(),
            bg_type,
            bool(self.chk_bg_alpha_fixed.isChecked()),
            doublets=doublets,
        )
        if err:
            return None, err
        return fit_data, None
    def _build_lmfit_parameters(self, bg_type: str):
        self._refresh_all_tied_parameter_values()
        fit_data, _ = self._collect_fit_curve_data()
        bg_values = {
            "b0": float(self.sb_bg_b0.value()),
            "b1": float(self.sb_bg_b1.value()),
            "b2": float(self.sb_bg_b2.value()),
            "bg_alpha": float(self.sb_bg_alpha.value()),
            "bg_alpha_fixed": bool(self.chk_bg_alpha_fixed.isChecked()),
        }
        return fit_engine.build_lmfit_parameters(
            self._collect_peak_specs(), bg_type, bg_values, fit_data,
            doublets=(self._capture_so_doublet_states() if hasattr(self, "_capture_so_doublet_states") else []),
            energy_scale=self._current_energy_scale_for_doublet() if hasattr(self, "_current_energy_scale_for_doublet") else "",
        )
    def _classify_fit_outcome(self, result, fit_data: Optional[dict] = None) -> tuple[str, str]:
        outcome, detail, bound_hits = fit_engine.classify_fit_outcome(
            result,
            len(getattr(self, "_peak_widgets", [])),
            fit_data=fit_data,
            human_name_fn=self._human_readable_param_name,
        )
        self._last_fit_bound_hits = set(bound_hits)
        return outcome, detail
    def _run_single_curve_fit(self) -> None:
        fit_data, err = self._validate_fit_ready()
        if fit_data is None:
            self._set_fit_running_state(False)
            self._set_fit_progress("Fit not ready")
            self._update_fit_quality_summary("Fit not ready")
            self._show_warning("Fit not ready", err or "The fit setup is incomplete.")
            self._clear_fit_results_tables()
            return
        try:
            bg_type = str(self.cb_bg_type.currentText())
        except Exception:
            bg_type = "constant"

        self._pre_fit_snapshot = self._capture_pre_fit_snapshot()
        self._fit_view_state = fit_plotting.capture_axes_view(self.ax)
        try:
            self.btn_undo_fit.setEnabled(False)
        except Exception:
            pass
        self._set_fit_running_state(True)
        try:
            params = self._build_lmfit_parameters(bg_type)
            xu = fit_data["xu"]
            yu = fit_data["yu"]
            try:
                energy_scale = str(getattr(fit_data.get("payload"), "energy_scale", "") or "")
            except Exception:
                energy_scale = ""
            progress_state = {"best_rss": None, "iter": 0}

            def residual(params_obj):
                if getattr(self, "_fit_cancel_requested", False):
                    raise FitCancelled()
                vals = params_obj.valuesdict()
                model_u, _ = self._build_model_from_values(
                    xu,
                    bg_type=bg_type,
                    values=vals,
                    measured_y=yu if bg_type == "Shirley" else None,
                    energy_scale=energy_scale,
                )
                return model_u - yu

            def iter_cb(params_obj, iteration, resid, *args, **kwargs):
                if getattr(self, "_fit_cancel_requested", False):
                    raise FitCancelled()
                try:
                    import numpy as np
                    rss = float(np.nansum(np.asarray(resid, dtype=float) ** 2))
                    if progress_state["best_rss"] is None or (np.isfinite(rss) and rss < progress_state["best_rss"]):
                        progress_state["best_rss"] = rss
                    progress_state["iter"] = int(iteration)
                    if int(iteration) == 0:
                        self._set_fit_progress("Preparing fit...")
                    elif int(iteration) % 10 == 0:
                        best = progress_state["best_rss"]
                        if best is None or not np.isfinite(best):
                            self._set_fit_progress(f"Iteration: {int(iteration)}")
                        else:
                            self._set_fit_progress(f"Iteration: {int(iteration)} | Best RSS: {best:.4g}")
                        self._draw_intermediate_fit(
                            xu,
                            params_obj.valuesdict(),
                            bg_type,
                            fit_data,
                            int(iteration),
                        )
                except Exception:
                    pass
                return False

            result = fit_engine.run_lmfit_fit(params, residual, iter_cb=iter_cb, max_nfev=3000)
            outcome, detail = self._classify_fit_outcome(result, fit_data=fit_data)
            if outcome == "failed":
                self._clear_fit_results_tables()
                self._update_fit_quality_summary("Failed")
                self._set_fit_progress("Fit failed")
                self._show_warning("Fit failed", detail or "Fit failed.")
                return
            self._apply_fit_result_to_widgets(result, bg_type)
            self._populate_fit_results_tables(result, bg_type, fit_data)
            self._last_fit_result = result
            self._last_fit_data = fit_data
            self._last_fit_bg_type = bg_type
            self._last_fit_status = "Converged with warnings" if outcome == "warning" else "Converged"
            try:
                self.act_save_config_curves.setEnabled(True)
            except Exception:
                pass
            if outcome == "warning":
                self._update_fit_quality_summary("Converged with warnings", result, fit_data, bg_type)
            else:
                self._update_fit_quality_summary("Converged", result, fit_data, bg_type)
            self._on_calculate_spectrum()
            fit_plotting.restore_axes_view(
                self.ax, self.ax_res, getattr(self, "_fit_view_state", None)
            )
            try:
                self._refresh_fit_range_artists()
            except Exception:
                pass
            try:
                title = str(getattr(fit_data.get("payload"), "title", "") or fit_data.get("name", "") or "")
                if title:
                    self.ax.set_title(f"{title} - fitted", pad=2)
                    self.canvas.draw_idle()
            except Exception:
                pass
            try:
                nfev = int(getattr(result, "nfev", 0) or 0)
            except Exception:
                nfev = 0
            try:
                rss = float(getattr(result, "chisqr", 0.0) or 0.0)
            except Exception:
                rss = 0.0
            if outcome == "warning":
                self._set_fit_progress(f"Finished with warnings after {nfev} evals | RSS: {rss:.4g}")
                self._show_warning("Fit finished with warnings", detail)
            else:
                self._set_fit_progress(f"Fit converged after {nfev} evals | RSS: {rss:.4g}")
        except Exception as exc:
            if isinstance(exc, FitCancelled):
                self._set_fit_progress("Fit interrupted")
                # Leave the last live model visible, but make its status explicit
                # and restore persistent overlays/view after the interrupted run.
                try:
                    fit_plotting.restore_axes_view(
                        self.ax, self.ax_res, getattr(self, "_fit_view_state", None)
                    )
                except Exception:
                    pass
                try:
                    self._refresh_fit_range_artists()
                except Exception:
                    pass
                try:
                    title = str(getattr(fit_data.get("payload"), "title", "") or fit_data.get("name", "") or "")
                    if title:
                        self.ax.set_title(f"{title} - fit interrupted", pad=2)
                    self.canvas.draw_idle()
                except Exception:
                    pass
            else:
                import traceback
                traceback.print_exc()
                self._clear_fit_results_tables()
                self._show_warning("Fit failed", f"The fit could not be completed.\n\n{exc}")
        finally:
            self.btn_start_fit.setEnabled(True)
            self._set_fit_running_state(False)
            try:
                self.btn_undo_fit.setEnabled(getattr(self, "_pre_fit_snapshot", None) is not None)
            except Exception:
                pass
    def _on_start_fit(self) -> None:
        if getattr(self, "_fit_is_running", False):
            self._fit_cancel_requested = True
            self._set_fit_progress("Stopping fit...")
            try:
                QApplication.processEvents()
            except Exception:
                pass
            return
        self._run_single_curve_fit()
