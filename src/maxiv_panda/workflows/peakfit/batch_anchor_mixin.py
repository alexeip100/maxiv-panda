from __future__ import annotations

from typing import Any

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QDialog, QPushButton, QTableWidgetItem
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from ...ui import PlotPayload

class BatchAnchorMixin:
    """Extracted behavior for the batch Prepare workflow."""

    def _anchor_color_icon(self, label: str) -> QIcon:
        """Return a small color-square icon for an anchor row."""
        color = QColor(self._anchor_colors.get(str(label), "#777777"))
        pix = QPixmap(14, 14)
        try:
            pix.fill(Qt.GlobalColor.transparent)
            from PyQt6.QtGui import QPainter, QPen
            painter = QPainter(pix)
            painter.fillRect(1, 1, 12, 12, color)
            painter.setPen(QPen(QColor("#555555"), 1))
            painter.drawRect(0, 0, 13, 13)
            painter.end()
        except Exception:
            pix.fill(color)
        return QIcon(pix)


    def _anchor_table_item(self, text: str, *, anchor_label: str | None = None) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        if anchor_label:
            try:
                item.setIcon(self._anchor_color_icon(anchor_label))
            except Exception:
                pass
        try:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        except Exception:
            pass
        return item


    def _make_anchor_delete_button(self, label: str, has_anchor: bool) -> QPushButton:
        btn = QPushButton("×", self.anchor_status_table)
        btn.setToolTip(f"Delete the {label} anchor")
        btn.setEnabled(bool(has_anchor))
        btn.setFixedSize(24, 22)
        try:
            btn.setAutoDefault(False)
            btn.setDefault(False)
            btn.setStyleSheet(
                "QPushButton { font-weight: bold; padding: 0px; }"
                "QPushButton:disabled { color: #999999; }"
            )
        except Exception:
            pass
        btn.clicked.connect(lambda _checked=False, anchor_label=label: self._delete_anchor_with_confirmation(anchor_label))
        return btn


    def _delete_anchor_with_confirmation(self, label: str) -> None:
        if label not in self._anchors:
            return
        reply = QMessageBox.question(
            self,
            "Delete anchor",
            f"Delete the {label} anchor and its stored fit information?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            del self._anchors[label]
        except KeyError:
            pass
        self._refresh_anchor_status_table()
        self._update_anchor_preview_plot()
        if label == "Start":
            self._batch_setup_created = False
            self._clear_batch_config_and_guesses()
            self._update_proceed_button_state()
        elif getattr(self, "_batch_setup_created", False):
            self._refresh_run_tab_anchor_summary()
            self._populate_batch_parameter_table()


    def _refresh_anchor_status_table(self) -> None:
        table = getattr(self, "anchor_status_table", None)
        if table is None:
            return
        try:
            table.setRowCount(len(self._anchor_labels))
            for row, label in enumerate(self._anchor_labels):
                anchor = self._anchors.get(label)
                if anchor:
                    range_text = str(anchor.get("range_text", ""))
                    n_text = str(anchor.get("n_spectra", ""))
                    status = str(anchor.get("fit_status", "built, not fitted"))
                else:
                    range_text = "—"
                    n_text = "—"
                    status = "not built"
                table.setItem(row, 0, self._anchor_table_item(label, anchor_label=label))
                table.setItem(row, 1, self._anchor_table_item(range_text))
                table.setItem(row, 2, self._anchor_table_item(n_text))
                table.setItem(row, 3, self._anchor_table_item(status))
                table.setCellWidget(row, 4, self._make_anchor_delete_button(label, bool(anchor)))
            try:
                table.resizeRowsToContents()
            except Exception:
                pass
        except Exception:
            pass
        self._update_anchor_buttons()
        self._update_proceed_button_state()


    def _effective_checked_entries_from_tree(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for item in self._checked_leaf_items():
            try:
                payload = item.data(0, self.ROLE_PAYLOAD)
                if payload is None:
                    continue
                key = item.data(0, self.ROLE_KEY)
                # The batch Prepare tree is flat: each top-level row is the
                # actual spectrum.  Read its source identity directly from the
                # row rather than from a hierarchical parent.
                file_data = item.data(0, self.ROLE_FILE)
                region_data = item.data(0, self.ROLE_REGION)
                file_name = str(file_data or "")
                region_name = str(region_data or "")
                entries.append({
                    "file_name": file_name,
                    "region_name": region_name,
                    "display": str(item.text(0)),
                    "key": str(key or item.text(0)),
                    "payload": payload,
                    "meta": item.data(0, self.ROLE_META),
                })
            except Exception:
                continue
        return entries


    def _current_effective_count(self) -> int:
        try:
            return len(self._effective_checked_entries_from_tree())
        except Exception:
            return 0


    def _default_anchor_range(self, anchor_label: str, count: int) -> tuple[int, int]:
        if count <= 0:
            return 1, 1
        window = min(5, count)
        label = str(anchor_label or "").lower()
        if label.startswith("end"):
            return max(1, count - window + 1), count
        if label.startswith("middle"):
            center = (count + 1) // 2
            start = max(1, center - window // 2)
            end = min(count, start + window - 1)
            start = max(1, end - window + 1)
            return start, end
        return 1, window


    def _refresh_anchor_controls(self, *, keep_values: bool = False) -> None:
        count = max(1, self._current_effective_count())
        try:
            current_from = int(self.sb_anchor_from.value())
            current_to = int(self.sb_anchor_to.value())
        except Exception:
            current_from, current_to = 1, 1
        try:
            self.sb_anchor_from.blockSignals(True)
            self.sb_anchor_to.blockSignals(True)
            self.sb_anchor_from.setRange(1, count)
            self.sb_anchor_to.setRange(1, count)
            if keep_values:
                self.sb_anchor_from.setValue(max(1, min(count, current_from)))
                self.sb_anchor_to.setValue(max(1, min(count, current_to)))
            else:
                start, end = self._default_anchor_range(self.cb_anchor_type.currentText(), count)
                self.sb_anchor_from.setValue(start)
                self.sb_anchor_to.setValue(end)
        except Exception:
            pass
        finally:
            try:
                self.sb_anchor_from.blockSignals(False)
                self.sb_anchor_to.blockSignals(False)
            except Exception:
                pass
        self._update_anchor_buttons()


    def _on_anchor_type_changed(self, *_args: Any) -> None:
        self._refresh_anchor_controls(keep_values=False)
        self._update_anchor_buttons()


    def _update_anchor_buttons(self) -> None:
        try:
            label = self.cb_anchor_type.currentText()
            has_anchor = label in self._anchors
            has_entries = self._current_effective_count() > 0
            self.btn_build_anchor.setEnabled(has_entries)
            self.btn_fit_anchor.setEnabled(bool(has_anchor))
        except Exception:
            pass


    def _invalidate_anchors(self, reason: str = "sequence changed") -> None:
        self._anchor_model_note_shown = False
        if not getattr(self, "_anchors", None):
            self._refresh_anchor_controls(keep_values=True)
            self._update_anchor_buttons()
            return
        self._anchors.clear()
        self._batch_setup_created = False
        self._refresh_anchor_controls(keep_values=False)
        self._refresh_anchor_status_table()
        self._update_anchor_preview_plot()


    def _anchor_range_text(self, entries: list[dict[str, Any]], start: int, end: int) -> str:
        if not entries:
            return "—"
        first = str(entries[0].get("display", ""))
        last = str(entries[-1].get("display", ""))
        if start == end:
            return f"{start}: {first}"
        return f"{start}–{end}: {first} … {last}"


    def _build_current_anchor(self) -> None:
        entries_all = self._effective_checked_entries_from_tree()
        if not entries_all:
            QMessageBox.warning(self, "No spectra selected", "No checked spectra are available for anchor averaging.")
            return
        try:
            start = int(self.sb_anchor_from.value())
            end = int(self.sb_anchor_to.value())
        except Exception:
            start, end = 1, 1
        if start > end:
            start, end = end, start
        start = max(1, min(len(entries_all), start))
        end = max(1, min(len(entries_all), end))
        selected = entries_all[start - 1:end]
        x_arrays: list[np.ndarray] = []
        y_arrays: list[np.ndarray] = []
        min_len: int | None = None
        first_payload = None
        for entry in selected:
            p = entry.get("payload")
            if first_payload is None:
                first_payload = p
            try:
                x = np.asarray(p.x, dtype=float)
                y = np.asarray(p.y, dtype=float)
            except Exception:
                continue
            n = min(x.size, y.size)
            if n <= 0:
                continue
            min_len = n if min_len is None else min(min_len, n)
            x_arrays.append(x)
            y_arrays.append(y)
        if not x_arrays or min_len is None or min_len <= 0 or first_payload is None:
            QMessageBox.warning(self, "Cannot build anchor", "The selected spectra could not be averaged into an anchor spectrum.")
            return
        try:
            x_stack = np.vstack([x[:min_len] for x in x_arrays])
            y_stack = np.vstack([y[:min_len] for y in y_arrays])
            x_avg = np.nanmean(x_stack, axis=0)
            y_avg = np.nanmean(y_stack, axis=0)
        except Exception as exc:
            QMessageBox.warning(self, "Cannot build anchor", f"Averaging failed: {exc}")
            return
        label = str(self.cb_anchor_type.currentText() or "Start")
        range_text = self._anchor_range_text(selected, start, end)
        payload = PlotPayload(
            title=f"{label} anchor ({len(selected)} spectra)",
            x=x_avg,
            y=y_avg,
            xlabel=getattr(first_payload, "xlabel", "x"),
            ylabel=getattr(first_payload, "ylabel", "Intensity"),
            energy_scale=getattr(first_payload, "energy_scale", "Unknown"),
        )
        try:
            payload.source_keys = [str(e.get("key", "")) for e in selected]
            payload.anchor_label = str(label)
            payload.anchor_range_text = str(range_text)
        except Exception:
            pass
        self._anchors[label] = {
            "label": label,
            "start_index": start,
            "end_index": end,
            "range_text": range_text,
            "n_spectra": len(selected),
            "payload": payload,
            "source_keys": [str(e.get("key", "")) for e in selected],
            "fit_state": None,
            "fit_status": "built, not fitted",
        }
        self._refresh_anchor_status_table()
        self._update_anchor_preview_plot()


    def _update_anchor_preview_plot(self) -> None:
        plot = getattr(self, "plot_anchor", None)
        if plot is None:
            return
        payloads: list[PlotPayload] = []
        for label in self._anchor_labels:
            anchor = self._anchors.get(label)
            if anchor and anchor.get("payload") is not None:
                payloads.append(anchor["payload"])
        if not payloads:
            plot.clear("Anchor preview: build a Start, Middle or End anchor above")
            self._style_prepare_plot_area(plot)
            self._compact_plot_margins(plot)
            return
        flip_be = bool(getattr(self._mw, "cb_flip_be", None).isChecked()) if getattr(self._mw, "cb_flip_be", None) is not None else False
        colors = [self._anchor_colors.get(label, "#777777") for label in self._anchor_labels if self._anchors.get(label) and self._anchors[label].get("payload") is not None]
        plot.plot_many(payloads, flip_binding_energy=flip_be, colors=colors)
        try:
            plot.ax.set_title("Anchor spectra")
        except Exception:
            pass
        self._style_prepare_plot_area(plot)
        self._compact_plot_margins(plot)


    def _show_anchor_model_note_once(self) -> None:
        """Explain the batch-anchor model contract before the first anchor fit."""
        if bool(getattr(self, "_anchor_model_note_shown", False)):
            return
        QMessageBox.information(
            self,
            "Batch anchor model structure",
            "Keep component labels consistent across batch anchors.\n\n"
            "• A peak or doublet label identifies the same component across the series. Keep the same label if it shifts in energy or changes intensity; use a new label only for a different component.\n"
            "• Components may be absent from some anchors. PANDA builds the batch model from the union of labelled components found in the anchors.\n"
            "• For SO doublets, also keep the same major/minor pairing and Same/Independent shape relations.\n\n"
            "Fitted values may vary between anchors; the component identity and model structure should remain consistent.",
            QMessageBox.StandardButton.Ok,
        )
        self._anchor_model_note_shown = True


    def _fit_current_anchor(self) -> None:
        """Open the selected anchor in the single-curve fit editor and store the returned state."""
        label = str(self.cb_anchor_type.currentText() or "Start")
        anchor = self._anchors.get(label)
        if not anchor or anchor.get("payload") is None:
            QMessageBox.warning(self, "No anchor built", "Build the selected anchor before fitting it.")
            return

        self._show_anchor_model_note_once()

        try:
            from .fit_dialog import FitCoreLevelDialog
        except Exception as exc:
            QMessageBox.warning(self, "Cannot open fit window", f"Could not open the single-curve fit editor: {exc}")
            return

        supplied_label = f"{label} anchor"
        if anchor.get("range_text"):
            supplied_label = f"{supplied_label} ({anchor.get('range_text')})"
        dlg = FitCoreLevelDialog(
            self._mw,
            parent=self,
            supplied_payload=anchor.get("payload"),
            supplied_label=supplied_label,
            initial_fit_state=anchor.get("fit_state"),
            shared_fit_setup_ref=self._shared_anchor_fit_setup,
        )
        result = dlg.exec()
        if result != QDialog.DialogCode.Accepted:
            return

        fit_state = dlg.anchor_fit_state()
        fit_setup = dlg.anchor_fit_setup()
        if not fit_state:
            QMessageBox.warning(self, "No fit state returned", "The single-curve fit editor did not return a fit state for this anchor.")
            return

        anchor["fit_state"] = fit_state
        anchor["fit_setup"] = fit_setup
        if fit_setup is not None:
            self._shared_anchor_fit_setup["setup"] = fit_setup
        try:
            n_peaks = len((fit_state.get("peak_states") or []))
        except Exception:
            n_peaks = 0
        try:
            bg_type = str(((fit_state.get("bg_state") or {}).get("bg_type")) or "BG")
        except Exception:
            bg_type = "BG"
        if n_peaks > 0:
            anchor["fit_status"] = f"fitted ({n_peaks} peak{'s' if n_peaks != 1 else ''}, {bg_type} BG)"
        else:
            anchor["fit_status"] = "fit state stored"
        self._refresh_anchor_status_table()
        self._update_anchor_preview_plot()
        self._update_proceed_button_state()
        try:
            _mode, topology_errors = self._batch_anchor_model_mode_and_errors()
            if topology_errors:
                QMessageBox.warning(
                    self,
                    "Anchor model structure differs",
                    topology_errors[0] + "\n\nRefit this anchor with the same SO-doublet structure before creating the batch setup.",
                )
        except Exception:
            pass
        if getattr(self, "_batch_setup_created", False):
            self._refresh_run_tab_anchor_summary()
            self._populate_batch_parameter_table()


