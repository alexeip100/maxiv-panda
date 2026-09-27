from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout,
)

from . import fit_plotting, fit_widgets, so_doublets


class FitDialogDoubletMixin:
    """Spin-orbit doublet state, UI, and relationship management.

    This mixin is intentionally behavior-neutral: methods were extracted from
    ``FitDialogStateMixin`` without changing their public/private names or call
    contracts.
    """
    def _capture_so_doublet_states(self) -> list[dict[str, Any]]:
        out = []
        widget_map = getattr(self, "_so_doublet_widgets", {}) or {}
        for ordinal, raw in enumerate(getattr(self, "_so_doublets", []) or [], start=1):
            st = so_doublets.normalize_state(raw, ordinal=ordinal)
            wb = widget_map.get(int(st["id"]))
            if wb:
                try:
                    split_data = wb["split_mode"].currentData()
                    ratio_data = wb["ratio_mode"].currentData()
                    split_mode, split_target = split_data if isinstance(split_data, tuple) else (str(wb["split_mode"].currentText()), None)
                    ratio_mode, ratio_target = ratio_data if isinstance(ratio_data, tuple) else (str(wb["ratio_mode"].currentText()), None)
                    st.update({
                        "label": str(wb["label_edit"].text()).strip() or f"Doublet {ordinal}",
                        "orbital": str(wb["orbital"].currentText()),
                        "split": float(wb["split"].value()), "split_min": float(wb["split_min"].value()),
                        "split_max": float(wb["split_max"].value()), "split_mode": str(split_mode), "split_tie_target": split_target,
                        "ratio": float(wb["ratio"].value()), "ratio_min": float(wb["ratio_min"].value()),
                        "ratio_max": float(wb["ratio_max"].value()), "ratio_mode": str(ratio_mode), "ratio_tie_target": ratio_target,
                        "L_relation": str(wb["L_relation"].currentText()),
                        "G_relation": str(wb["G_relation"].currentText()),
                        "A_relation": str(wb["A_relation"].currentText()),
                    })
                except Exception:
                    pass
            st["id"] = len(out) + 1
            out.append(so_doublets.normalize_state(st, ordinal=len(out) + 1))
        return out

    def _doublet_view_enabled(self) -> bool:
        try:
            return bool(self.chk_doublet_view.isChecked())
        except Exception:
            return False

    def _on_doublet_view_toggled(self, checked: bool) -> None:
        """Switch component rendering without changing the underlying fit model."""
        try:
            self._refresh_peak_markers()
        except Exception:
            pass
        try:
            self._refresh_live_calculated_spectrum()
        except Exception:
            pass

    def _current_energy_scale_for_doublet(self) -> str:
        try:
            key = self._get_checked_key()
            payload = self._payload_by_key.get(key) if key else None
            return str(getattr(payload, "energy_scale", "") or "")
        except Exception:
            return ""

    def _apply_so_doublet_relations(self, *, refresh: bool = True) -> None:
        states = so_doublets.resolve_tied_values(self._capture_so_doublet_states())
        self._so_doublets = states
        # Keep tied values visible in the relationship editors during live preview.
        for st in states:
            wb = (getattr(self, "_so_doublet_widgets", {}) or {}).get(int(st.get("id", -1)))
            if not wb:
                continue
            for key in ("split", "ratio"):
                if str(st.get(f"{key}_mode")) == "Tied":
                    widget = wb.get(key)
                    if widget is not None:
                        widget.blockSignals(True)
                        widget.setValue(float(st[key]))
                        widget.blockSignals(False)
        used = so_doublets.member_indices(states)
        scale = self._current_energy_scale_for_doublet()
        # First return all peak editors to ordinary enabled/title state.
        for idx, w in enumerate(getattr(self, "_peak_widgets", []), start=1):
            title = w.get("title_label")
            if title is not None:
                title.setText(f"Peak {idx}")
            for prefix in ("E", "H", "L", "G", "A"):
                self._apply_constraint_ui_state(w, prefix)
        for ordinal, st in enumerate(states, start=1):
            major_i, minor_i = int(st["major"]), int(st["minor"])
            if major_i < 1 or minor_i < 1 or major_i > len(self._peak_widgets) or minor_i > len(self._peak_widgets):
                continue
            major = self._peak_widgets[major_i - 1]
            minor = self._peak_widgets[minor_i - 1]
            if major.get("title_label") is not None:
                major["title_label"].setText(f"Peak {major_i} — major (SO doublet {ordinal})")
            if minor.get("title_label") is not None:
                minor["title_label"].setText(f"Peak {minor_i} — minor (SO doublet {ordinal})")
            mvals = {p: float(major[p].value()) for p in ("E", "H", "L", "G", "A")}
            derived = so_doublets.derived_minor_values(st, mvals, energy_scale=scale)
            for p, value in derived.items():
                sb = minor[p]
                sb.blockSignals(True)
                # A derived E may legitimately fall outside old provisional bounds.
                if value < sb.minimum(): sb.setMinimum(value)
                if value > sb.maximum(): sb.setMaximum(value)
                sb.setValue(float(value))
                sb.blockSignals(False)
            # Minor E/H are always defined by the doublet relation.
            for p in ("E", "H"):
                for key in (p, f"{p}_min", f"{p}_max", f"{p}_mode"):
                    try: minor[key].setEnabled(False)
                    except Exception: pass
            # L/G/A are shared by default, but can explicitly be independent.
            for p in ("L", "G", "A"):
                same = str(st.get(f"{p}_relation", "Same")) == "Same"
                if same:
                    for key in (p, f"{p}_min", f"{p}_max", f"{p}_mode"):
                        try: minor[key].setEnabled(False)
                        except Exception: pass
        try:
            self.btn_create_so_doublet.setEnabled((len(self._peak_widgets) - len(used)) >= 2)
        except Exception:
            pass
        if refresh:
            self._refresh_peak_markers()
            self._refresh_live_calculated_spectrum()

    def _refresh_so_doublet_widgets(self) -> None:
        # Remove old relationship editors only; constituent peak cards stay put.
        for wb in list((getattr(self, "_so_doublet_widgets", {}) or {}).values()):
            gb = wb.get("group")
            if gb is not None:
                try: self._peak_scroll_lay.removeWidget(gb)
                except Exception: pass
                gb.setParent(None); gb.deleteLater()
        self._so_doublet_widgets = {}
        states = []
        n = len(getattr(self, "_peak_widgets", []))
        for ordinal, raw in enumerate(getattr(self, "_so_doublets", []) or [], start=1):
            st = so_doublets.normalize_state(raw, ordinal=ordinal)
            if st["major"] == st["minor"] or min(st["major"], st["minor"]) < 1 or max(st["major"], st["minor"]) > n:
                continue
            st["id"] = len(states) + 1
            states.append(st)
        self._so_doublets = states
        for st in states:
            wb = fit_widgets.create_so_doublet_group(
                st, self,
                on_changed=lambda: self._apply_so_doublet_relations(refresh=True),
                on_ungroup=lambda did: self._ungroup_so_doublet(did),
                on_clone=lambda did: self._clone_so_doublet(did),
                tie_options=states,
            )
            self._so_doublet_widgets[int(st["id"])] = wb
            # Put doublet relation panels at the top of the scroll area, before peaks.
            self._peak_scroll_lay.insertWidget(int(st["id"]) - 1, wb["group"])
        self._apply_so_doublet_relations(refresh=False)

    def _restore_so_doublet_states(self, states) -> None:
        self._so_doublets = [so_doublets.normalize_state(s, ordinal=i) for i, s in enumerate(states or [], start=1)]
        self._refresh_so_doublet_widgets()

    def _on_create_so_doublet(self) -> None:
        peak_states = self._capture_peak_states(include_color=True)
        used = so_doublets.member_indices(self._capture_so_doublet_states())
        available = [i for i in range(1, len(peak_states) + 1) if i not in used]
        if len(available) < 2:
            self._show_warning("Create SO doublet", "At least two standalone peaks are required.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Create spin-orbit doublet")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        cb_major = QComboBox(dlg); cb_minor = QComboBox(dlg)
        for i in available:
            label = str(peak_states[i-1].get("label") or f"P{i}")
            text = f"Peak {i} — {label}"
            cb_major.addItem(text, i); cb_minor.addItem(text, i)
        if cb_minor.count() > 1: cb_minor.setCurrentIndex(1)
        cb_type = QComboBox(dlg); cb_type.addItems(["p", "d", "f", "Custom"])
        le_label = QLineEdit(dlg); le_label.setPlaceholderText("e.g. S 2p, Sn 3d")
        form.addRow("Major peak:", cb_major)
        form.addRow("Minor peak:", cb_minor)
        form.addRow("Doublet type:", cb_type)
        form.addRow("Label:", le_label)
        lay.addLayout(form)
        note = QLabel("Major is the component expected to have the higher intensity. Splitting and intensity ratio can be fixed or fitted after creation.", dlg)
        note.setWordWrap(True); lay.addWidget(note)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=dlg)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject); lay.addWidget(bb)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        major_i = int(cb_major.currentData()); minor_i = int(cb_minor.currentData())
        if major_i == minor_i:
            self._show_warning("Create SO doublet", "Major and minor must be two different peaks.")
            return
        orbital = str(cb_type.currentText())
        st = so_doublets.derive_state_from_peaks(major_i, minor_i, peak_states, ordinal=len(self._so_doublets)+1, orbital=orbital)
        requested_base = str(le_label.text()).strip() or "Doublet"
        existing_labels = [str(s.get("label") or "") for s in self._capture_so_doublet_states()]
        normalized_labels, new_label = so_doublets.renumber_doublet_family(requested_base, existing_labels)
        for existing_state, normalized_label in zip(self._so_doublets, normalized_labels):
            existing_state["label"] = normalized_label
        st["label"] = new_label
        self._so_doublets.append(st)
        self._refresh_so_doublet_widgets()
        self._apply_so_doublet_relations(refresh=True)

    def _clone_so_doublet(self, doublet_id: int) -> None:
        peak_states = self._capture_peak_states(include_color=True)
        doublets = self._capture_so_doublet_states()
        source = next((s for s in doublets if int(s.get("id", -1)) == int(doublet_id)), None)
        if source is None:
            return
        if len(peak_states) + 2 > 10:
            self._show_warning("Clone SO doublet", "A clone needs two additional peaks; the 10-peak limit would be exceeded.")
            return
        major_i, minor_i = int(source["major"]), int(source["minor"])
        if min(major_i, minor_i) < 1 or max(major_i, minor_i) > len(peak_states):
            return
        new_major_i = len(peak_states) + 1
        new_minor_i = len(peak_states) + 2
        labels = [str(s.get("label") or "") for s in doublets]
        normalized_doublet_labels, clone_label = so_doublets.renumber_doublet_family(str(source.get("label") or "Doublet"), labels)
        for st, label in zip(doublets, normalized_doublet_labels):
            st["label"] = label
        source = next((s for s in doublets if int(s.get("id", -1)) == int(doublet_id)), source)
        clone, major_state, minor_state, _shift = so_doublets.clone_doublet_definition(
            source,
            peak_states[major_i - 1],
            peak_states[minor_i - 1],
            new_major_index=new_major_i,
            new_minor_index=new_minor_i,
            ordinal=len(doublets) + 1,
            energy_scale=self._current_energy_scale_for_doublet(),
            label=clone_label,
        )
        # New members should be visually distinguishable from the source while
        # retaining all physical shape/constraint settings.
        # Constituent mathematical peaks keep the simple, stable P1/P2/...
        # convention; physical-family naming belongs only to SO doublets.
        major_state["label"] = f"P{new_major_i}"
        minor_state["label"] = f"P{new_minor_i}"
        major_state["color"] = fit_plotting.default_peak_color(new_major_i)
        major_state["color_custom"] = False
        minor_state["color"] = fit_plotting.default_peak_color(new_minor_i)
        minor_state["color_custom"] = False
        all_peak_states = peak_states + [major_state, minor_state]

        self.sb_num_peaks.blockSignals(True)
        self.sb_num_peaks.setValue(len(all_peak_states))
        self.sb_num_peaks.blockSignals(False)
        self._rebuild_peak_widgets()
        self._restore_peak_states(all_peak_states)
        self._so_doublets = doublets + [clone]
        self._refresh_so_doublet_widgets()
        self._apply_so_doublet_relations(refresh=True)

    def _ungroup_so_doublet(self, doublet_id: int) -> None:
        self._so_doublets = so_doublets.remap_after_doublet_delete(self._capture_so_doublet_states(), int(doublet_id))
        self._refresh_so_doublet_widgets()
        self._apply_so_doublet_relations(refresh=True)
