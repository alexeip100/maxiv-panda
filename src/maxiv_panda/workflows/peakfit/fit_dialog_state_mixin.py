from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt6.QtWidgets import QTableWidgetItem
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from . import fit_plotting, fit_results, fit_widgets, so_doublets
from .state_models import FitSetupState, PeakState


class FitDialogStateMixin:
    def _capture_peak_states(self, include_color: bool = True):
        states = []
        for w in getattr(self, "_peak_widgets", []):
            state = {}
            for prefix in ("E", "H", "L", "G", "A"):
                try:
                    state[prefix] = float(w[prefix].value())
                    state[f"{prefix}_min"] = float(w[f"{prefix}_min"].value())
                    state[f"{prefix}_max"] = float(w[f"{prefix}_max"].value())
                    combo = w.get(f"{prefix}_mode")
                    state[f"{prefix}_mode"] = str(combo.currentText()) if combo is not None else "Free"
                except Exception:
                    pass
            try:
                label_edit = w.get("label_edit")
                label = str(label_edit.text()).strip() if label_edit is not None else ""
                state["label"] = label or f"P{len(states) + 1}"
            except Exception:
                state["label"] = f"P{len(states) + 1}"
            if include_color:
                try:
                    state["color"] = str(w.get("color") or fit_plotting.default_peak_color(len(states)+1))
                    state["color_custom"] = bool(w.get("color_custom", False))
                except Exception:
                    pass
            states.append(PeakState.from_mapping(state, ordinal=len(states) + 1).to_mapping())
        return states
    def _restore_peak_states(self, states) -> None:
        if not states:
            return
        states = [PeakState.from_mapping(state, ordinal=i).to_mapping() for i, state in enumerate(states, start=1)]
        # First restore raw numeric widget state without letting constraint callbacks
        # fire. Then restore the constraint modes with callbacks enabled so tie
        # metadata and greyed-out UI state are rebuilt correctly for the restored
        # curve.
        self._constraint_change_in_progress = True
        try:
            for idx, (w, state) in enumerate(zip(getattr(self, "_peak_widgets", []), states), start=1):
                title = w.get("title_label")
                if title is not None:
                    title.setText(f"Peak {idx}")
                delete_btn = w.get("delete_btn")
                if delete_btn is not None:
                    delete_btn.setProperty("peak_index", idx)
                    delete_btn.setEnabled(len(states) > 1)
                label_edit = w.get("label_edit")
                if label_edit is not None:
                    label_edit.setText(str(state.get("label") or f"P{idx}"))
                color_btn = w.get("color_btn")
                if color_btn is not None:
                    color_btn.setProperty("peak_index", idx)
                try:
                    w["color"] = str(state.get("color") or fit_plotting.default_peak_color(idx))
                    w["color_custom"] = bool(state.get("color_custom", False))
                except Exception:
                    w["color"] = fit_plotting.default_peak_color(idx)
                    w["color_custom"] = False
                self._update_peak_color_button(w)
                for prefix, label_name in (("E", "Energy"), ("H", "Height"), ("L", "LFWHM"), ("G", "GFWHM"), ("A", "Alpha")):
                    lab = w.get(f"{prefix}_label")
                    if lab is not None:
                        lab.setText(f"{label_name}_{idx}")
                    if f"{prefix}_min" in state:
                        w[f"{prefix}_min"].setValue(float(state[f"{prefix}_min"]))
                    if f"{prefix}_max" in state:
                        w[f"{prefix}_max"].setValue(float(state[f"{prefix}_max"]))
                    try:
                        w[prefix].setRange(float(state.get(f"{prefix}_min", w[f"{prefix}_min"].value())),
                                           float(state.get(f"{prefix}_max", w[f"{prefix}_max"].value())))
                    except Exception:
                        pass
                    if prefix in state:
                        w[prefix].setValue(float(state[prefix]))
                    # Clear stale tie metadata from the previously active curve.
                    w[f"{prefix}_tie"] = None
        finally:
            self._constraint_change_in_progress = False

        for idx, (w, state) in enumerate(zip(getattr(self, "_peak_widgets", []), states), start=1):
            for prefix in ("E", "H", "L", "G", "A"):
                combo = w.get(f"{prefix}_mode")
                if combo is None:
                    continue
                desired = str(state.get(f"{prefix}_mode", "Free"))
                self._set_constraint_combo_items(combo, prefix, idx, preserve_text=desired)
                combo.setCurrentText(desired)
                self._on_constraint_mode_changed(prefix, idx)

        try:
            self._enforce_peak_height_physical_bounds()
        except Exception:
            pass
        self._refresh_all_tied_parameter_values()
        self._refresh_peak_markers()
        self._refresh_live_calculated_spectrum()
        self._update_fit_results_tables()
    def _capture_bg_state(self, include_calc: bool = True) -> Dict[str, Any]:
        return {
            "bg_type": str(self.cb_bg_type.currentText()),
            "b0": float(self.sb_bg_b0.value()),
            "b1": float(self.sb_bg_b1.value()),
            "b2": float(self.sb_bg_b2.value()),
            "bg_alpha": float(self.sb_bg_alpha.value()),
            "bg_alpha_fixed": bool(self.chk_bg_alpha_fixed.isChecked()),
            "bg_touched": bool(getattr(self, "_bg_coeffs_touched", False)),
            # Compatibility field retained for saved states/templates from older releases.
            # The model is now always calculated and displayed.
            "calc_on": True,
        }
    def _restore_bg_state(self, state: Dict[str, Any], include_calc: bool = True) -> None:
        if not state:
            return
        widgets = [self.cb_bg_type, self.sb_bg_b0, self.sb_bg_b1, self.sb_bg_b2, self.sb_bg_alpha, self.chk_bg_alpha_fixed]
        for w in widgets:
            try:
                w.blockSignals(True)
            except Exception:
                pass
        try:
            self.cb_bg_type.setCurrentText(str(state.get("bg_type", self.cb_bg_type.currentText())))
            self.sb_bg_b0.setValue(float(state.get("b0", self.sb_bg_b0.value())))
            self.sb_bg_b1.setValue(float(state.get("b1", self.sb_bg_b1.value())))
            self.sb_bg_b2.setValue(float(state.get("b2", self.sb_bg_b2.value())))
            self.sb_bg_alpha.setValue(float(state.get("bg_alpha", self.sb_bg_alpha.value())))
            self.chk_bg_alpha_fixed.setChecked(bool(state.get("bg_alpha_fixed", self.chk_bg_alpha_fixed.isChecked())))
        finally:
            for w in widgets:
                try:
                    w.blockSignals(False)
                except Exception:
                    pass
        self._last_bg_type = str(self.cb_bg_type.currentText())
        self._update_bg_controls_visibility(self.cb_bg_type.currentText())
        self._bg_coeffs_touched = bool(state.get("bg_touched", False))
    def _capture_table_state(self, table) -> Dict[str, Any]:
        return fit_results.capture_table_state(table)
    def _restore_table_state(self, table, state: Optional[Dict[str, Any]]) -> None:
        fit_results.restore_table_state(table, state)
    def _new_results_table_item(self, text: str = "") -> QTableWidgetItem:
        return fit_widgets.make_plain_table_item(text)
    def _capture_curve_state(self) -> Dict[str, Any]:
        return {
            "peak_states": self._capture_peak_states(include_color=True),
            "so_doublets": self._capture_so_doublet_states(),
            "bg_state": self._capture_bg_state(include_calc=True),
            "fit_table": self._capture_table_state(self.tbl_fit_results),
            "bg_table": self._capture_table_state(self.tbl_bg_results),
            "fit_quality": {
                "status": self.lbl_fit_status.text(),
                "rss": self.lbl_fit_rss.text(),
                "rms": self.lbl_fit_rms.text(),
                "redchi": self.lbl_fit_redchi.text(),
            },
            "bound_hits": set(getattr(self, "_last_fit_bound_hits", set()) or set()),
        }
    def _restore_curve_state(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        self._restoring_curve_state = True
        try:
            peak_states = state.get("peak_states") or []
            self.sb_num_peaks.blockSignals(True)
            self.sb_num_peaks.setValue(max(1, len(peak_states) or 1))
            self.sb_num_peaks.blockSignals(False)
            self._rebuild_peak_widgets()
            if peak_states:
                self._restore_peak_states(peak_states)
            self._restore_so_doublet_states(state.get("so_doublets") or [])
            self._restore_bg_state(state.get("bg_state") or {}, include_calc=True)
            self._update_fit_results_tables()
            self._last_fit_bound_hits = set(state.get("bound_hits", set()) or set())
            self._restore_table_state(self.tbl_fit_results, state.get("fit_table"))
            self._restore_table_state(self.tbl_bg_results, state.get("bg_table"))
            fq = state.get("fit_quality") or {}
            self.lbl_fit_status.setText(str(fq.get("status", "Status: —")))
            self.lbl_fit_rss.setText(str(fq.get("rss", "RSS: —")))
            self.lbl_fit_rms.setText(str(fq.get("rms", "RMS: —")))
            self.lbl_fit_redchi.setText(str(fq.get("redchi", "Reduced χ²: —")))
            self._on_calculate_spectrum()
        finally:
            self._restoring_curve_state = False
    def _capture_fit_setup_template(self) -> Dict[str, Any]:
        setup = {
            "peak_states": self._capture_peak_states(include_color=False),
            "so_doublets": self._capture_so_doublet_states(),
            "bg_state": self._capture_bg_state(include_calc=False),
        }
        return FitSetupState.from_mapping(setup).to_mapping()
    def _apply_fit_setup_template(self, state: Dict[str, Any]) -> None:
        if not state:
            return
        state = FitSetupState.from_mapping(state).to_mapping()
        self._restoring_curve_state = True
        try:
            peak_states = state.get("peak_states") or []
            self.sb_num_peaks.blockSignals(True)
            self.sb_num_peaks.setValue(max(1, len(peak_states) or 1))
            self.sb_num_peaks.blockSignals(False)
            self._rebuild_peak_widgets()
            if peak_states:
                self._restore_peak_states(peak_states)
            self._restore_so_doublet_states(state.get("so_doublets") or [])
            self._restore_bg_state(state.get("bg_state") or {}, include_calc=False)
            self._clear_fit_results_tables()
            self._on_calculate_spectrum()
        finally:
            self._restoring_curve_state = False
    def _delete_peak_by_index(self, peak_index: int) -> None:
        n = len(getattr(self, "_peak_widgets", []))
        if n <= 1 or peak_index < 1 or peak_index > n:
            return
        try:
            answer = QMessageBox.question(
                self,
                "Delete peak",
                f"Delete Peak {peak_index}?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
        except Exception:
            answer = QMessageBox.StandardButton.Cancel
        if answer != QMessageBox.StandardButton.Ok:
            return
        states = self._capture_peak_states()
        doublets = so_doublets.remap_after_peak_delete(self._capture_so_doublet_states(), peak_index)
        del states[peak_index - 1]
        def _remap_mode_text(text: str) -> str:
            text = str(text or "Free")
            if text in ("Free", "Fixed"):
                return text
            import re as _re
            m = _re.fullmatch(r"Tied to ([A-Za-z]+)_(\d+)", text)
            if not m:
                return "Free"
            label = m.group(1)
            target = int(m.group(2))
            if target == peak_index:
                return "Free"
            if target > peak_index:
                target -= 1
            return f"Tied to {label}_{target}"
        for state in states:
            for prefix in ("E", "H", "L", "G", "A"):
                key = f"{prefix}_mode"
                state[key] = _remap_mode_text(state.get(key, "Free"))
        for w in getattr(self, "_peak_widgets", []):
            gb = w.get("group")
            if gb is not None:
                try:
                    self._peak_scroll_lay.removeWidget(gb)
                except Exception:
                    pass
                try:
                    gb.setParent(None)
                    gb.deleteLater()
                except Exception:
                    pass
        self._peak_widgets = []
        self.sb_num_peaks.blockSignals(True)
        self.sb_num_peaks.setValue(len(states))
        self.sb_num_peaks.blockSignals(False)
        self._rebuild_peak_widgets()
        self._restore_peak_states(states)
        self._restore_so_doublet_states(doublets)
        # Be explicit here: peak deletion changes the actual component list, so
        # force a full redraw instead of relying only on generic live-refresh helpers.
        try:
            self._on_calculate_spectrum()
        except Exception:
            pass
    def _rebuild_peak_widgets(self) -> None:
        """Ensure the peak-parameter UI contains exactly N peaks.

        - When N increases: append new peak editors to the end (existing peak settings preserved).
        - When N decreases via the peak-number selector: remove peak editors from the end first (remaining peak settings preserved).
        """
        n_target = int(self.sb_num_peaks.value()) if hasattr(self, "sb_num_peaks") else 1
        n_target = max(1, min(10, n_target))

        old_count = len(getattr(self, "_peak_widgets", []))

        # Peak-editor construction emits several parameter/widget signals.  The
        # active fit range is curve state and must never be changed as a side
        # effect of adding/removing peak editors, so protect it explicitly
        # across the rebuild.
        try:
            _saved_fit_range = self._current_fit_range()
            _saved_fit_range = tuple(_saved_fit_range) if _saved_fit_range is not None else None
        except Exception:
            _saved_fit_range = None

        # Ensure storage exists
        if not hasattr(self, "_peak_widgets"):
            self._peak_widgets = []  # list of per-peak widget dicts (preserves order)
        elif isinstance(self._peak_widgets, dict):
            self._peak_widgets = []

        lay = self._peak_scroll_lay

        # Helper: remove a peak group widget from layout safely
        def _remove_peak_group(idx_last: int) -> None:
            wdict = self._peak_widgets.pop(idx_last)
            gb = wdict.get("group")
            if gb is None:
                return
            lay.removeWidget(gb)
            gb.setParent(None)
            gb.deleteLater()

        # Grow: append new groups
        while len(self._peak_widgets) < n_target:
            i = len(self._peak_widgets) + 1  # 1-based index for labels/names
            peak_bundle = fit_widgets.create_peak_group(
                i,
                n_target,
                self,
                on_delete=lambda idx: self._delete_peak_by_index(idx),
                on_pick_color=lambda idx: self._choose_peak_color(idx),
                set_constraint_items=self._set_constraint_combo_items,
                on_refresh_peak_markers=self._refresh_peak_markers,
                on_refresh_all_tied=self._refresh_all_tied_parameter_values,
                on_refresh_live=self._refresh_live_calculated_spectrum,
                on_constraint_mode_changed=self._on_constraint_mode_changed,
            )

            insert_idx = lay.count()
            if insert_idx > 0:
                last_item = lay.itemAt(insert_idx - 1)
                if last_item is not None and last_item.spacerItem() is not None:
                    insert_idx = insert_idx - 1
            lay.insertWidget(insert_idx, peak_bundle["group"])

            self._peak_widgets.append(peak_bundle)

        # Shrink: remove from end only
        while len(self._peak_widgets) > n_target:
            _remove_peak_group(len(self._peak_widgets) - 1)

        for idx, w in enumerate(self._peak_widgets, start=1):
            title = w.get("title_label")
            if title is not None:
                title.setText(f"Peak {idx}")
            delete_btn = w.get("delete_btn")
            if delete_btn is not None:
                delete_btn.setProperty("peak_index", idx)
                delete_btn.setEnabled(len(self._peak_widgets) > 1)
            label_edit = w.get("label_edit")
            if label_edit is not None and not str(label_edit.text()).strip():
                label_edit.setText(f"P{idx}")
                label_edit.setPlaceholderText(f"P{idx}")
            color_btn = w.get("color_btn")
            if color_btn is not None:
                color_btn.setProperty("peak_index", idx)
            if not w.get("color"):
                w["color"] = fit_plotting.default_peak_color(idx)
                w["color_custom"] = False
            self._update_peak_color_button(w)
            for prefix, label_name in (("E", "Energy"), ("H", "Height"), ("L", "LFWHM"), ("G", "GFWHM"), ("A", "Alpha")):
                lab = w.get(f"{prefix}_label")
                if lab is not None:
                    lab.setText(f"{label_name}_{idx}")
                combo = w.get(f"{prefix}_mode")
                if combo is not None:
                    self._set_constraint_combo_items(combo, prefix, idx, preserve_text=str(combo.currentText()) or "Free")
                self._apply_constraint_ui_state(w, prefix)
        self._refresh_all_tied_parameter_values()

        # Restore the range *before* deriving defaults for a newly added peak.
        # This guarantees that its automatic Energy/Height guess is evaluated
        # only inside the user's custom fitting interval, even if one of the
        # widget-construction signals above temporarily disturbed dialog state.
        self._fit_range = _saved_fit_range
        try:
            self._update_fit_range_button()
        except Exception:
            pass
        self._last_peak_count = old_count
        self._apply_peak_defaults_from_ranges(only_new=True, update_existing_defaults=False)
        self._refresh_peak_markers()
        self._refresh_live_calculated_spectrum()

        # The rebuild is not allowed to alter the selected fitting interval.
        # Reassert it after live redraw as a final guard and restore its artists.
        self._fit_range = _saved_fit_range
        try:
            self._update_fit_range_button()
            self._refresh_fit_range_artists()
        except Exception:
            pass
        if hasattr(self, "_so_doublets"):
            self._refresh_so_doublet_widgets()
        self._update_fit_results_tables()
