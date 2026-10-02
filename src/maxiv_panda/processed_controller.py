from __future__ import annotations

from typing import Any

import numpy as np
from PyQt6.QtCore import Qt
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from .log_utils import log_noncritical_error
from .workflows.normalization.logic import normalization_interval, normalization_interval_if_reachable, mean_intensity_over_interval
from .intensity_units import CPS, time_per_spectrum_channel, scale_payload


class ProcessedController:
    """Processed-tab specific helpers kept outside the main GUI shell."""

    def __init__(self, app: Any):
        self.app = app

    def has_any_processed_curves(self) -> bool:
        try:
            for _k, _it in list(self.app._selected_by_key.items()):
                _m = _it.data(0, self.app.ROLE_META)
                if isinstance(_m, dict) and bool(_m.get("processed", False)):
                    return True
        except Exception as exc:
            log_noncritical_error("checking for processed curves", exc)
        return False

    def update_selected_tree_visibility(self, show_processed: bool) -> None:
        """Switch between raw and persistent E-calibrated representations.

        Calibrated children identify their raw parent through ``source_key``.
        Use that relationship explicitly rather than treating *all* raw and
        processed items as two global buckets.  This keeps the switch robust
        after session restore and also leaves uncalibrated raw curves visible
        when only part of a selection has been calibrated.
        """
        try:
            processed_sources: set[str] = set()
            for key, it in list(self.app._selected_by_key.items()):
                meta = it.data(0, self.app.ROLE_META)
                if not isinstance(meta, dict) or not bool(meta.get("processed", False)):
                    continue
                source_key = meta.get("source_key")
                if isinstance(source_key, str) and source_key:
                    processed_sources.add(source_key)

            for key, it in list(self.app._selected_by_key.items()):
                meta = it.data(0, self.app.ROLE_META)
                is_processed = isinstance(meta, dict) and bool(meta.get("processed", False))
                if is_processed:
                    # Persistent E-cal children are visible only in E-cal view.
                    it.setHidden(not bool(show_processed))
                else:
                    # A raw source with an E-cal counterpart is replaced by that
                    # counterpart in E-cal view.  Raw curves without a processed
                    # counterpart remain visible in both views.
                    it.setHidden(bool(show_processed) and str(key) in processed_sources)

            for (_fk, _rn), parent in list(self.app._selected_region_items.items()):
                any_visible = False
                for i in range(parent.childCount()):
                    ch = parent.child(i)
                    if ch is not None and not ch.isHidden():
                        any_visible = True
                        break
                parent.setHidden(not any_visible)
        except Exception as exc:
            log_noncritical_error("updating processed/raw visibility", exc)

    def guess_norm_default_energy(self) -> float | None:
        try:
            payloads = []
            for i in range(self.app.selected_tree.topLevelItemCount()):
                region_item = self.app.selected_tree.topLevelItem(i)
                if region_item is None:
                    continue
                try:
                    if region_item.isHidden():
                        continue
                except Exception:
                    pass
                try:
                    region_visible = region_item.checkState(0) != Qt.CheckState.Unchecked
                except Exception:
                    region_visible = True
                if not region_visible:
                    continue
                for j in range(region_item.childCount()):
                    it = region_item.child(j)
                    if it is None:
                        continue
                    try:
                        if it.isHidden():
                            continue
                    except Exception:
                        pass
                    try:
                        if it.checkState(0) != Qt.CheckState.Checked:
                            continue
                    except Exception:
                        continue
                    p = it.data(0, self.app.ROLE_PAYLOAD)
                    if p is not None:
                        payloads.append(p)
            return self._common_overlap_edge(payloads)
        except Exception as exc:
            log_noncritical_error("guessing normalization default energy", exc)
            return None

    def on_norm_toggled(self, enabled: bool) -> None:
        self.app._norm_to1_enabled = bool(enabled)
        if enabled:
            if self.app._norm_to1_energy is None:
                e0 = self.guess_norm_default_energy()
                if e0 is not None:
                    self.app._norm_to1_energy = float(e0)
            self.app._update_plot_from_selected()
        else:
            self.app._norm_to1_sig_when_enabled = None
            self.app._update_plot_from_selected()

    def on_norm_energy_changed(self, val: float) -> None:
        self.app._norm_to1_energy = float(val)
        self.app._norm_to1_user_override = True
        if self.app._norm_to1_enabled:
            self.app._update_plot_from_selected()

    def on_norm_span_changed(self, val: float) -> None:
        self.app._norm_span_percent = float(val)
        if self.app._norm_to1_enabled:
            self.app._update_plot_from_selected()


    def workflow_normalization_active(self) -> bool:
        """Return whether 1D Processed-data normalization is the active view transform.

        Downstream workflows (energy calibration and peak fitting) should consume
        the same numerical curves the user is currently looking at.  Normalization
        remains a reversible view transform; this helper exposes that state without
        creating persistent duplicate tree items.
        """
        try:
            return bool(getattr(self.app, "_norm_to1_enabled", False)) and bool(self.app._is_processed_tab_active())
        except Exception:
            return False

    def normalize_payload_for_workflow(self, p: Any, item: Any | None = None) -> Any:
        """Return the effective Processed-data payload used by child workflows.

        CPS conversion follows the Processed Data display setting.  Reversible
        normalization is then applied on top.

        Return a normalized copy of *p* when Processed normalization is active.

        The returned title is tagged ``(Norm)`` so fitting/calibration dialogs make
        it explicit that they are operating on the displayed normalized variant.
        If normalization cannot be evaluated, the original payload is returned.
        """
        try:
            if str(getattr(self.app, "_processed_intensity_mode", "counts")).lower() == CPS and item is not None:
                meta = item.data(0, self.app.ROLE_META)
                seconds = time_per_spectrum_channel(meta)
                if seconds is not None:
                    p = scale_payload(p, seconds=seconds, mode=CPS)
        except Exception as exc:
            log_noncritical_error("preparing CPS workflow payload", exc)

        if not self.workflow_normalization_active():
            return p
        try:
            e0 = getattr(self.app, "_norm_to1_energy", None)
            if e0 is None:
                return p
            x = np.asarray(getattr(p, "x", []), dtype=float)
            y = np.asarray(getattr(p, "y", []), dtype=float)
            finite = np.isfinite(x) & np.isfinite(y)
            x_i = x[finite]
            y_i = y[finite]
            if x_i.size < 2 or y_i.size < 2:
                return p
            order = np.argsort(x_i)
            xs = x_i[order]
            ys = y_i[order]
            e0f = float(e0)
            span_percent = float(getattr(self.app, "_norm_span_percent", 1.0))
            interval = normalization_interval_if_reachable(
                float(xs[0]), float(xs[-1]), e0f, span_percent
            )
            if interval is None:
                return p
            y0 = mean_intensity_over_interval(xs, ys, *interval)
            if not np.isfinite(y0) or abs(float(y0)) < 1e-15:
                return p
            title = str(getattr(p, "title", ""))
            if "(Norm)" not in title:
                title = f"{title} (Norm)".strip()
            try:
                marker = getattr(self.app, "_mark_source_usage_from_items", None)
                if callable(marker) and item is not None:
                    marker([(item, "")], "normalization")
            except Exception as exc:
                log_noncritical_error("recording workflow normalization source usage", exc)
            payload_cls = type(p)
            return payload_cls(
                title=title,
                x=getattr(p, "x", []),
                y=np.asarray(getattr(p, "y", []), dtype=float) / float(y0),
                xlabel=getattr(p, "xlabel", "x"),
                ylabel=getattr(p, "ylabel", "Intensity"),
                energy_scale=getattr(p, "energy_scale", "Unknown"),
                metadata=dict(getattr(p, "metadata", {}) or {}),
            )
        except Exception as exc:
            log_noncritical_error("preparing normalized workflow payload", exc)
            return p

    def apply_normalization_if_enabled(self, payloads: list[Any], items_in_order: list[tuple[Any, str]]) -> tuple[list[Any] | None, bool]:
        norm_allowed = False
        try:
            norm_allowed = bool(getattr(self.app, "_norm_to1_enabled", False)) and (getattr(self.app, "tabs", None) is not None) and self.app.tabs.currentIndex() == 1
        except Exception:
            norm_allowed = False

        if not norm_allowed:
            return payloads, False

        cur_sig = self._norm_sig_from_items(items_in_order)
        prev_sig = getattr(self.app, "_norm_to1_sig_when_enabled", None)
        if prev_sig is None:
            self.app._norm_to1_sig_when_enabled = cur_sig
        elif cur_sig != prev_sig:
            self.app._norm_to1_enabled = False
            self.app._norm_to1_sig_when_enabled = None
            try:
                cb = getattr(self.app, "cb_norm_to1_proc", None)
                if cb is not None:
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)
            except Exception as exc:
                log_noncritical_error("resetting normalization checkbox", exc)

            try:
                e_new = self._common_overlap_edge(payloads)
                if e_new is not None:
                    self.app._norm_to1_energy = float(e_new)
                    self.app._norm_to1_auto_default = float(e_new)
                    self.app._norm_to1_user_override = False
                    sb = getattr(self.app, "sb_norm_e_proc", None)
                    if sb is not None:
                        sb.blockSignals(True)
                        sb.setValue(float(e_new))
                        sb.blockSignals(False)
            except Exception as exc:
                log_noncritical_error("resetting normalization energy", exc)
            return payloads, False

        e0 = getattr(self.app, "_norm_to1_energy", None)
        if e0 is None or not payloads:
            return payloads, False

        span_percent = float(getattr(self.app, "_norm_span_percent", 1.0))

        # The automatic normalization point is tied to the common edge of the
        # *currently displayed* representations.  Energy calibration can shift
        # otherwise identical spectra by slightly different amounts, so a value
        # that was the common raw edge may sit just outside one E-calibrated
        # curve.  Keep automatic defaults following the active raw/E-cal view.
        if not bool(getattr(self.app, "_norm_to1_user_override", False)):
            e_auto = self._common_overlap_edge(payloads)
            if e_auto is not None:
                e0 = float(e_auto)
                self.app._norm_to1_energy = float(e_auto)
                self.app._norm_to1_auto_default = float(e_auto)
                try:
                    sb = getattr(self.app, "sb_norm_e_proc", None)
                    if sb is not None and abs(float(sb.value()) - float(e_auto)) > 1e-12:
                        sb.blockSignals(True)
                        sb.setValue(float(e_auto))
                        sb.blockSignals(False)
                except Exception as exc:
                    log_noncritical_error("tracking automatic normalization energy", exc)

        e0f = float(e0)
        self._update_span_ev_label(payloads)
        scaled_payloads: list[Any] = []
        used_intervals: list[tuple[float, float]] = []
        for p in payloads:
            x = np.asarray(getattr(p, "x", []), dtype=float)
            y = np.asarray(getattr(p, "y", []), dtype=float)
            finite = np.isfinite(x) & np.isfinite(y)
            x = x[finite]
            y = y[finite]
            if x.size < 2 or y.size < 2:
                scaled_payloads = []
                break
            order = np.argsort(x)
            x_i = x[order]
            y_i = y[order]
            xmin = float(x_i[0])
            xmax = float(x_i[-1])
            interval = normalization_interval_if_reachable(
                xmin, xmax, e0f, span_percent
            )
            if interval is None:
                scaled_payloads = []
                break
            y0 = mean_intensity_over_interval(x_i, y_i, *interval)
            if not np.isfinite(y0) or abs(y0) < 1e-15:
                scaled_payloads = []
                break
            used_intervals.append(interval)
            payload_cls = type(p)
            _title = str(getattr(p, "title", ""))
            if "(Norm)" not in _title:
                _title = f"{_title} (Norm)".strip()
            scaled_payloads.append(payload_cls(
                title=_title,
                x=getattr(p, "x", []),
                y=np.asarray(getattr(p, "y", []), dtype=float) / y0,
                xlabel=getattr(p, "xlabel", "x"),
                ylabel=getattr(p, "ylabel", "Intensity"),
                energy_scale=getattr(p, "energy_scale", "Unknown"),
                metadata=dict(getattr(p, "metadata", {}) or {}),
            ))

        if not scaled_payloads:
            try:
                QMessageBox.warning(
                    self.app,
                    "Normalization not applied",
                    "The normalization interval is unavailable or has a zero mean for at least one curve. No action was taken.",
                    QMessageBox.StandardButton.Ok,
                )
            except Exception as exc:
                log_noncritical_error("showing normalization warning", exc)
            self.app._norm_to1_enabled = False
            try:
                cb = getattr(self.app, "cb_norm_to1_proc", None)
                if cb is not None:
                    cb.blockSignals(True)
                    cb.setChecked(False)
                    cb.blockSignals(False)
            except Exception as exc:
                log_noncritical_error("reverting normalization checkbox", exc)
            return None, True

        try:
            marker = getattr(self.app, "_mark_source_usage_from_items", None)
            if callable(marker):
                marker(items_in_order, "normalization")
        except Exception as exc:
            log_noncritical_error("recording normalization source usage", exc)

        return scaled_payloads, True

    def update_norm_default_from_payloads(self, payloads: list[Any]) -> None:
        try:
            if not hasattr(self.app, "cb_norm_to1_proc") or bool(getattr(self.app, "_norm_to1_enabled", False)):
                return
            e0 = self._common_overlap_edge(payloads)
            if e0 is None:
                return
            self._update_span_ev_label(payloads)
            sb = getattr(self.app, "sb_norm_e_proc", None)
            cur = None
            try:
                if sb is not None:
                    cur = float(sb.value())
            except Exception:
                cur = None
            auto_prev = getattr(self.app, "_norm_to1_auto_default", None)
            user_over = bool(getattr(self.app, "_norm_to1_user_override", False))
            allow = (not user_over) or (auto_prev is not None and cur is not None and abs(cur - float(auto_prev)) < 1e-9)
            if not allow:
                return
            try:
                if sb is not None:
                    sb.blockSignals(True)
                    sb.setValue(float(e0))
                    sb.blockSignals(False)
            except Exception as exc:
                log_noncritical_error("updating normalization spinbox", exc)
            self.app._norm_to1_energy = float(e0)
            self.app._norm_to1_auto_default = float(e0)
            self.app._norm_to1_user_override = False
        except Exception as exc:
            log_noncritical_error("updating normalization default", exc)

    def _update_span_ev_label(self, payloads: list[Any]) -> None:
        label = getattr(self.app, "lbl_norm_span_ev_proc", None)
        if label is None:
            return
        widths: list[float] = []
        percent = float(getattr(self.app, "_norm_span_percent", 1.0))
        for p in payloads:
            x = np.asarray(getattr(p, "x", []), dtype=float)
            x = x[np.isfinite(x)]
            if x.size >= 2:
                widths.append((float(np.max(x)) - float(np.min(x))) * percent / 100.0)
        if not widths:
            label.setText("")
        elif max(widths) - min(widths) <= max(1e-9, 0.01 * max(widths)):
            label.setText(f"({widths[0]:.2g} eV)")
        else:
            label.setText("(varies)")

    def _norm_sig_from_items(self, items_in_order: list[tuple[Any, str]]) -> tuple[str, ...]:
        """Return a stable signature for the logical selected spectra.

        Raw and E-calibrated children represent the same logical source spectra.
        Switching the E-cal view must therefore *not* look like a new selection
        and disable the reversible normalization state.  Processed children carry
        their raw source key in metadata; use that canonical key when available.
        """
        sig: list[str] = []
        for it, _k in items_in_order:
            key_str: str | None = None
            try:
                meta = it.data(0, self.app.ROLE_META)
            except Exception:
                meta = None
            if isinstance(meta, dict):
                source_key = meta.get("source_key")
                if isinstance(source_key, str) and source_key:
                    key_str = source_key

            if not key_str:
                try:
                    kd = it.data(0, self.app.ROLE_KEY)
                except Exception:
                    kd = None
                if isinstance(kd, tuple) and len(kd) >= 1 and isinstance(kd[0], str):
                    key_str = kd[0]
                elif isinstance(kd, str):
                    key_str = kd

            if not key_str:
                try:
                    key_str = str(it.text(0))
                except Exception:
                    key_str = ""
            sig.append(key_str)
        return tuple(sig)

    def _common_overlap_edge(self, payloads: list[Any]) -> float | None:
        try:
            if not payloads:
                return None
            es = str(getattr(payloads[0], "energy_scale", "Binding"))
            xmins = []
            xmaxs = []
            for p in payloads:
                x = np.asarray(getattr(p, "x", []), dtype=float)
                if x.size == 0:
                    return None
                xmins.append(float(np.nanmin(x)))
                xmaxs.append(float(np.nanmax(x)))
            e_min = max(xmins)
            e_max = min(xmaxs)
            if not np.isfinite(e_min) or not np.isfinite(e_max) or e_min > e_max:
                return None
            return float(e_max) if es == "Kinetic" else float(e_min)
        except Exception as exc:
            log_noncritical_error("computing common overlap energy", exc)
            return None
