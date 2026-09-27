from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import QComboBox

from . import fit_constraints


class FitDialogConstraintsMixin:
    def _constraint_display_text(self, prefix: str, w: dict) -> str:
        try:
            idx = list(getattr(self, "_peak_widgets", [])).index(w) + 1
            for ordinal, d in enumerate(self._capture_so_doublet_states() if hasattr(self, "_capture_so_doublet_states") else [], start=1):
                if int(d.get("minor", -1)) != idx:
                    continue
                if prefix in ("E", "H"):
                    return f"SO doublet {ordinal}"
                if prefix in ("L", "G", "A") and str(d.get(f"{prefix}_relation", "Same")) == "Same":
                    return f"Same as major"
        except Exception:
            pass
        mode = self._param_mode(w, prefix)
        combo = w.get(f"{prefix}_mode")
        combo_text = str(combo.currentText()) if combo is not None else ""
        return fit_constraints.render_constraint_display(prefix, mode, w.get(f"{prefix}_tie"), combo_text)
    def _constraint_label(self, prefix: str) -> str:
        return self._PARAM_LABELS.get(prefix, str(prefix))
    def _constraint_combo_text(self, prefix: str, peak_index: int) -> str:
        return f"Tied to {self._constraint_label(prefix)}_{peak_index}"
    def _set_constraint_combo_items(self, combo: QComboBox, prefix: str, peak_index: int, preserve_text: str = "Free") -> None:
        current = preserve_text if preserve_text is not None else str(combo.currentText())
        combo.blockSignals(True)
        combo.clear()
        n = len(getattr(self, "_peak_widgets", [])) + (0 if peak_index <= len(getattr(self, "_peak_widgets", [])) else 1)
        n = max(n, int(getattr(self, "sb_num_peaks", None).value()) if hasattr(self, "sb_num_peaks") else n)
        combo.addItems(fit_constraints.build_constraint_options(prefix, peak_index, n))
        idx = combo.findText(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)
    def _param_mode(self, w: dict, prefix: str) -> str:
        combo = w.get(f"{prefix}_mode")
        text = str(combo.currentText()) if combo is not None else "Free"
        if text == "Fixed":
            return "Fixed"
        if text.startswith("Tied to "):
            return "Tied"
        return "Free"
    def _parse_tie_target(self, prefix: str, text: str):
        return fit_constraints.parse_tie_target(prefix, text)
    def _tie_kind_for_prefix(self, prefix: str) -> str:
        return "offset" if prefix == "E" else "factor"
    def _constraint_tooltip(self, prefix: str, tie_meta: Optional[dict]) -> str:
        return fit_constraints.constraint_tooltip(prefix, tie_meta)
    def _apply_constraint_ui_state(self, w: dict, prefix: str) -> None:
        mode = self._param_mode(w, prefix)
        is_free = mode == "Free"
        is_fixed = mode == "Fixed"
        is_tied = mode == "Tied"
        try:
            w[prefix].setEnabled(not is_tied)
            w[f"{prefix}_min"].setEnabled(is_free)
            w[f"{prefix}_max"].setEnabled(is_free)
            combo = w.get(f"{prefix}_mode")
            if combo is not None:
                # A minor SO-doublet member disables its ordinary constraint
                # selector while grouped. Returning the peak to standalone
                # status (Ungroup) must restore that selector as well as the
                # value/min/max editors.
                combo.setEnabled(True)
                combo.setToolTip(self._constraint_tooltip(prefix, w.get(f"{prefix}_tie") if is_tied else None))
        except Exception:
            pass
    def _resolve_tie_root(self, prefix: str, peak_index: int):
        state_map = {}
        for idx, w in enumerate(getattr(self, "_peak_widgets", []), start=1):
            mode = self._param_mode(w, prefix)
            target = None
            if mode == "Tied":
                target = self._parse_tie_target(prefix, w[f"{prefix}_mode"].currentText())
            state_map[idx] = {"mode": mode, "target": target}
        return fit_constraints.resolve_tie_root(prefix, peak_index, state_map)
    def _compute_tie_relation(self, prefix: str, peak_index: int, target_index: int):
        src = self._peak_widgets[peak_index - 1][prefix]
        tgt = self._peak_widgets[target_index - 1][prefix]
        return fit_constraints.compute_tie_relation(prefix, float(src.value()), float(tgt.value()), target_index)
    def _refresh_all_tied_parameter_values(self) -> None:
        if getattr(self, "_constraint_refresh_in_progress", False):
            return
        self._constraint_refresh_in_progress = True
        try:
            for prefix in ("E", "H", "L", "G", "A"):
                for idx, w in enumerate(getattr(self, "_peak_widgets", []), start=1):
                    if self._param_mode(w, prefix) != "Tied":
                        continue
                    tie = w.get(f"{prefix}_tie") or {}
                    target = tie.get("target")
                    if not target or target < 1 or target > len(self._peak_widgets):
                        continue
                    src_widget = self._peak_widgets[target - 1][prefix]
                    src_val = float(src_widget.value())
                    if tie.get("kind") == "offset":
                        new_val = src_val + float(tie.get("value", 0.0))
                    else:
                        new_val = src_val * float(tie.get("value", 1.0))
                    sb = w[prefix]
                    sb.blockSignals(True)
                    sb.setValue(float(new_val))
                    sb.blockSignals(False)
            try:
                if hasattr(self, "_apply_so_doublet_relations") and not getattr(self, "_so_doublet_refresh_in_progress", False):
                    self._so_doublet_refresh_in_progress = True
                    try:
                        self._apply_so_doublet_relations(refresh=False)
                    finally:
                        self._so_doublet_refresh_in_progress = False
            except Exception:
                pass
        finally:
            self._constraint_refresh_in_progress = False
    def _on_constraint_mode_changed(self, prefix: str, peak_index: int) -> None:
        if getattr(self, "_constraint_change_in_progress", False):
            return
        if peak_index < 1 or peak_index > len(getattr(self, "_peak_widgets", [])):
            return
        w = self._peak_widgets[peak_index - 1]
        combo = w.get(f"{prefix}_mode")
        if combo is None:
            return
        text = str(combo.currentText())
        if text == "Free":
            w[f"{prefix}_tie"] = None
            self._apply_constraint_ui_state(w, prefix)
            self._refresh_all_tied_parameter_values()
            self._refresh_live_calculated_spectrum()
            return
        if text == "Fixed":
            w[f"{prefix}_tie"] = None
            self._apply_constraint_ui_state(w, prefix)
            self._refresh_all_tied_parameter_values()
            self._refresh_live_calculated_spectrum()
            return
        target = self._parse_tie_target(prefix, text)
        if target is None:
            return
        if target == peak_index:
            self._constraint_change_in_progress = True
            try:
                combo.setCurrentText("Free")
            finally:
                self._constraint_change_in_progress = False
            self._show_warning("Invalid tie", f"{self._constraint_label(prefix)}_{peak_index} cannot be tied to itself.")
            w[f"{prefix}_tie"] = None
            self._apply_constraint_ui_state(w, prefix)
            return
        try:
            root, chain = self._resolve_tie_root(prefix, target)
        except Exception as exc:
            self._constraint_change_in_progress = True
            try:
                combo.setCurrentText("Free")
            finally:
                self._constraint_change_in_progress = False
            self._show_warning("Invalid tie", str(exc))
            w[f"{prefix}_tie"] = None
            self._apply_constraint_ui_state(w, prefix)
            return
        try:
            tie_meta = self._compute_tie_relation(prefix, peak_index, root)
        except Exception as exc:
            self._constraint_change_in_progress = True
            try:
                combo.setCurrentText("Free")
            finally:
                self._constraint_change_in_progress = False
            self._show_warning("Invalid tie", str(exc))
            w[f"{prefix}_tie"] = None
            self._apply_constraint_ui_state(w, prefix)
            return
        w[f"{prefix}_tie"] = tie_meta
        desired_text = self._constraint_combo_text(prefix, root)
        if desired_text != text:
            self._constraint_change_in_progress = True
            try:
                combo.setCurrentText(desired_text)
            finally:
                self._constraint_change_in_progress = False
            self._show_warning("Chained tie simplified", f"A chained tie was detected for {self._constraint_label(prefix)}_{peak_index}. It was automatically changed to {desired_text}.")
        self._apply_constraint_ui_state(w, prefix)
        self._refresh_all_tied_parameter_values()
        self._refresh_live_calculated_spectrum()
