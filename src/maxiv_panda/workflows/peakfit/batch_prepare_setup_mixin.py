from __future__ import annotations

from typing import Any

from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from . import batch_peak_only_table, batch_table_builder, batch_table_core, so_doublets

class BatchPrepareSetupMixin:
    """Extracted behavior for the batch Prepare workflow."""

    def _has_fitted_start_anchor(self) -> bool:
        """Return True once the Start anchor has a stored fit state with peak states."""
        try:
            fit_state = (self._anchors.get("Start") or {}).get("fit_state") or {}
            peaks = fit_state.get("peak_states") or []
            return bool(peaks)
        except Exception:
            return False


    def _fitted_anchor_fit_states(self) -> dict[str, dict[str, Any]]:
        """Return fitted anchor states keyed by anchor label.

        Peak labels are already stored in each peak state by the single-fit editor.
        This helper centralizes the anchor-fit-state contract for later batch-template building.
        """
        states: dict[str, dict[str, Any]] = {}
        for label in self._anchor_labels:
            try:
                fit_state = (self._anchors.get(label) or {}).get("fit_state") or {}
                peaks = fit_state.get("peak_states") or []
                if not peaks:
                    continue
                bg_state = fit_state.get("bg_state") or {}
                normalized_peaks: list[dict[str, Any]] = []
                for idx, peak in enumerate(peaks, start=1):
                    p = dict(peak or {})
                    p["label"] = str(p.get("label") or f"P{idx}")
                    p["index"] = idx
                    normalized_peaks.append(p)
                states[label] = {
                    "anchor": label,
                    "fit_state": fit_state,
                    "bg_state": dict(bg_state),
                    "bg_type": str(bg_state.get("bg_type", "BG")),
                    "peaks": normalized_peaks,
                    "range_text": str((self._anchors.get(label) or {}).get("range_text", "")),
                    "n_spectra": (self._anchors.get(label) or {}).get("n_spectra", ""),
                }
            except Exception:
                continue
        return states


    def _batch_anchor_model_mode_and_errors(self) -> tuple[str, list[str]]:
        """Return peak-only/doublet-aware mode and structural anchor errors."""
        states = self._fitted_anchor_fit_states()
        fit_states = {label: dict((state.get("fit_state") or {})) for label, state in states.items()}
        return so_doublets.validate_anchor_topologies(fit_states, self._anchor_labels)



    def _use_doublet_batch_path(self) -> bool:
        """Return True only when fitted anchors explicitly use SO doublets."""
        try:
            mode, _errors = self._batch_anchor_model_mode_and_errors()
            return str(mode) == "doublet-aware"
        except Exception:
            return str(getattr(self, "_batch_model_mode", "peak-only")) == "doublet-aware"

    def _batch_table_module(self):
        """Select an isolated batch-table implementation for the current model."""
        return batch_table_builder if self._use_doublet_batch_path() else batch_peak_only_table

    def _update_proceed_button_state(self) -> None:
        btn = getattr(self, "btn_proceed_batch_setup", None)
        if btn is None:
            return
        ready = self._has_fitted_start_anchor()
        try:
            btn.setEnabled(ready)
            if ready:
                btn.setToolTip("Create the initial batch setup from the fitted anchor spectra.")
            else:
                btn.setToolTip("Fit at least the Start anchor before creating the batch setup.")
        except Exception:
            pass
        try:
            if hasattr(self, "tabs") and hasattr(self, "_run_tab_index"):
                self.tabs.setTabEnabled(self._run_tab_index, bool(getattr(self, "_batch_setup_created", False)))
        except Exception:
            pass
        self._refresh_batch_run_controls()


    def _refresh_batch_run_controls(self) -> None:
        created = bool(getattr(self, "_batch_setup_created", False))
        valid = bool(getattr(self, "_batch_config_valid", False) and getattr(self, "_batch_initial_guesses_valid", False))
        running = bool(getattr(self, "_batch_fit_running", False))
        try:
            self.btn_validate_batch_setup.setEnabled(created and not running)
        except Exception:
            pass
        try:
            self.btn_run_batch_fit.setEnabled(created and not running)
            if created and not valid:
                self.btn_run_batch_fit.setToolTip("Run the sequence fit; validation and initial-guess generation will be performed automatically first.")
            elif running:
                self.btn_run_batch_fit.setToolTip("Batch fit is running.")
            else:
                self.btn_run_batch_fit.setToolTip("Run independent fits for all spectra from the generated initial guesses.")
        except Exception:
            pass
        try:
            self.btn_stop_batch_fit.setEnabled(running)
        except Exception:
            pass
        try:
            self.chk_batch_store_all_results.setEnabled(not running)
        except Exception:
            pass
        try:
            self._refresh_batch_fit_navigation_controls()
        except Exception:
            pass
        try:
            if not running and not valid:
                self.progress_batch_fit.setValue(0)
        except Exception:
            pass
        try:
            if running:
                return
            if created and valid:
                n = len(getattr(self, "_batch_initial_guesses", []) or [])
                done = len(getattr(self, "_batch_fit_results", []) or [])
                if done:
                    self.lab_batch_run_status.setText(f"Batch setup valid; {done}/{n} spectra fitted in memory.")
                else:
                    self.lab_batch_run_status.setText(f"Batch setup valid; {n} initial guesses ready.")
            elif created:
                self.lab_batch_run_status.setText("Batch setup ready; press Run to validate and fit.")
            else:
                self.lab_batch_run_status.setText("Batch setup not created.")
        except Exception:
            pass


    def _refresh_run_tab_anchor_summary(self) -> None:
        """Refresh the compact Run-tab summary derived from fitted anchors."""
        states = self._fitted_anchor_fit_states()
        try:
            n_effective = self._current_effective_count()
            fitted = [label for label in self._anchor_labels if label in states]
            if not fitted:
                self.lab_batch_setup_summary.setText(
                    "Batch setup has not been created yet. Fit at least the Start anchor on the Prepare sequence fit tab, "
                    "then press Proceed to batch setup."
                )
                return

            pieces = []
            for label in fitted:
                state = states.get(label) or {}
                bg = str(state.get("bg_type", "BG"))
                peaks = state.get("peaks") or []
                peak_labels = [str(p.get("label") or f"P{i+1}") for i, p in enumerate(peaks)]
                labels_text = ", ".join(peak_labels) if peak_labels else "no labelled peaks"
                n_doublets = len(((state.get("fit_state") or {}).get("so_doublets") or []))
                doublet_text = f", {n_doublets} SO doublet(s)" if n_doublets else ""
                pieces.append(f"{label}: {len(peaks)} peak(s) [{labels_text}]{doublet_text}, {bg} BG")

            self.lab_batch_setup_summary.setText(
                f"Effective sequence: {n_effective} spectra. "
                "Fitted anchors used to build this setup: "
                + " | ".join(pieces)
                + "."
            )
        except Exception:
            pass


    def _fmt_batch_value(self, *args, **kwargs):
        return batch_table_core._fmt_batch_value(self, *args, **kwargs)


    def _make_batch_table_item(self, *args, **kwargs):
        module = self._batch_table_module()
        return module._make_batch_table_item(self, *args, **kwargs)


    def _mode_from_anchor_modes(self, *args, **kwargs):
        return batch_table_core._mode_from_anchor_modes(self, *args, **kwargs)


    def _presence_pattern(self, *args, **kwargs):
        return batch_table_core._presence_pattern(self, *args, **kwargs)


    def _presence_note(self, *args, **kwargs):
        return batch_table_core._presence_note(self, *args, **kwargs)


    def _finite_floats(self, *args, **kwargs):
        return batch_table_core._finite_floats(self, *args, **kwargs)


    def _suggest_peak_bounds(self, *args, **kwargs):
        return batch_table_core._suggest_peak_bounds(self, *args, **kwargs)


    def _suggest_peak_mode(self, *args, **kwargs):
        return batch_table_core._suggest_peak_mode(self, *args, **kwargs)


    def _anchor_presence_kind(self, *args, **kwargs):
        return batch_table_core._anchor_presence_kind(self, *args, **kwargs)


    def _initial_strategy_for_peak_param(self, *args, **kwargs):
        return batch_table_core._initial_strategy_for_peak_param(self, *args, **kwargs)


    def _initial_strategy_for_background(self, *args, **kwargs):
        return batch_table_core._initial_strategy_for_background(self, *args, **kwargs)


    def _mean_if_fixed(self, *args, **kwargs):
        return batch_table_core._mean_if_fixed(self, *args, **kwargs)


    def _component_sort_key(self, *args, **kwargs):
        return batch_table_core._component_sort_key(self, *args, **kwargs)


    def _doublet_union_model(self, *args, **kwargs):
        return batch_table_builder._doublet_union_model(self, *args, **kwargs)


    def _build_doublet_parameter_rows(self, *args, **kwargs):
        return batch_table_builder._build_doublet_parameter_rows(self, *args, **kwargs)


    def _build_batch_parameter_rows_from_anchors(self, *args, **kwargs):
        module = self._batch_table_module()
        return module._build_batch_parameter_rows_from_anchors(self, *args, **kwargs)


    def _populate_batch_parameter_table(self, *args, **kwargs):
        module = self._batch_table_module()
        return module._populate_batch_parameter_table(self, *args, **kwargs)


    def _proceed_to_batch_setup(self) -> None:
        """Enable and switch to the Run tab after the Start anchor has been fitted."""
        if not self._has_fitted_start_anchor():
            QMessageBox.warning(
                self,
                "Start anchor not fitted",
                "Fit the Start anchor first. The Start anchor is required before creating the batch setup.",
            )
            return
        model_mode, topology_errors = self._batch_anchor_model_mode_and_errors()
        if topology_errors:
            QMessageBox.warning(
                self,
                "Anchor model structure differs",
                "The batch setup cannot be created until the fitted anchors use a consistent model structure.\n\n• "
                + "\n• ".join(topology_errors),
            )
            return
        self._batch_model_mode = model_mode
        self._batch_setup_created = True
        self._clear_batch_config_and_guesses()
        self._refresh_run_tab_anchor_summary()
        self._populate_batch_parameter_table()
        try:
            self.tabs.setTabEnabled(self._run_tab_index, True)
            self.tabs.setCurrentIndex(self._run_tab_index)
        except Exception:
            pass
        self._update_proceed_button_state()


