from __future__ import annotations

from typing import Any, Dict, Optional

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import QAbstractSpinBox, QLineEdit, QTreeWidgetItem

from . import fit_plotting
from .peak_detection import suggest_initial_peaks
from ...log_utils import log_noncritical_error


class FitDialogCurveMixin:
    def _build_payload_by_key_from_mainwindow(self, mw) -> tuple[dict, dict]:
        """Build key->PlotPayload mapping and key->display name from MainWindow selected tree
        (visible + checked leaf items). Display names match what the user sees in the main window."""
        payload_by_key: dict = {}
        display_by_key: dict = {}
        try:
            from ...ui import PlotPayload  # local import to avoid hard dependency at module import time
        except Exception:
            PlotPayload = None
        tree = getattr(mw, 'selected_tree', None)
        if tree is None:
            return payload_by_key, display_by_key
        for i in range(tree.topLevelItemCount()):
            top = tree.topLevelItem(i)
            stack = [top]
            while stack:
                it = stack.pop()
                if it.isHidden():
                    continue
                # LIFO stack: push children in reverse so they are visited in
                # the same top-to-bottom order as the Selected-curves tree.
                for c in range(it.childCount() - 1, -1, -1):
                    stack.append(it.child(c))
                if it.childCount() != 0:
                    continue
                if it.checkState(0) != Qt.CheckState.Checked:
                    continue
                kd = it.data(0, mw.ROLE_KEY)
                key = kd[0] if isinstance(kd, (tuple, list)) and kd else kd
                pl = it.data(0, mw.ROLE_PAYLOAD)
                if key is None or pl is None:
                    continue
                if PlotPayload is not None and not isinstance(pl, PlotPayload):
                    continue
                # Peak fitting must consume the same numerical curve that is
                # currently displayed in Processed Data.  Normalization is a
                # reversible view transform, so construct an effective payload
                # on demand rather than storing duplicate tree items.
                try:
                    controller = getattr(mw, "_processed_controller", None)
                    if controller is not None:
                        pl = controller.normalize_payload_for_workflow(pl, it)
                except Exception:
                    pass
                skey = str(key)
                payload_by_key[skey] = pl
                # Use the text shown in the main window tree as display label,
                # with an explicit virtual normalization tag when applicable.
                try:
                    label = it.text(0)
                    if "(Norm)" in str(getattr(pl, "title", "")) and "(Norm)" not in label:
                        label = f"{label} (Norm)"
                    display_by_key[skey] = label
                except Exception:
                    display_by_key[skey] = getattr(pl, 'title', skey)
        return payload_by_key, display_by_key
    def _ensure_single_checked(self) -> None:
        """Keep exactly one checked item (if any exist)."""
        first_checked = None
        for i in range(self.tree_curves.topLevelItemCount()):
            it = self.tree_curves.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked:
                if first_checked is None:
                    first_checked = it
                else:
                    it.setCheckState(0, Qt.CheckState.Unchecked)
        if first_checked is None and self.tree_curves.topLevelItemCount() > 0:
            first_checked = self.tree_curves.topLevelItem(0)
            first_checked.setCheckState(0, Qt.CheckState.Checked)
        if first_checked is not None:
            self.tree_curves.setCurrentItem(first_checked)
    def _get_checked_key(self) -> Optional[str]:
        for i in range(self.tree_curves.topLevelItemCount()):
            it = self.tree_curves.topLevelItem(i)
            if it.checkState(0) == Qt.CheckState.Checked:
                k = it.data(0, Qt.ItemDataRole.UserRole)
                return k if isinstance(k, str) else None
        return None
    def _get_tree_item_by_key(self, key: Optional[str]):
        if not key:
            return None
        for i in range(self.tree_curves.topLevelItemCount()):
            it = self.tree_curves.topLevelItem(i)
            try:
                if it.data(0, Qt.ItemDataRole.UserRole) == key:
                    return it
            except Exception:
                pass
        return None
    def _set_checked_curve_key(self, key: Optional[str]) -> None:
        """Force exactly one checked curve item by key, without re-entrant side effects."""
        if key is None:
            return
        self.tree_curves.blockSignals(True)
        try:
            target = None
            for i in range(self.tree_curves.topLevelItemCount()):
                it = self.tree_curves.topLevelItem(i)
                k = it.data(0, Qt.ItemDataRole.UserRole)
                want = (k == key)
                if want:
                    target = it
                it.setCheckState(0, Qt.CheckState.Checked if want else Qt.CheckState.Unchecked)
            if target is not None:
                self.tree_curves.setCurrentItem(target)
        finally:
            self.tree_curves.blockSignals(False)
    def _plot_checked_curve(self) -> None:
        """Plot the currently checked curve in the dialog and update x/y ranges."""
        key = self._get_checked_key()
        if key is None:
            return
        pl = self._payload_by_key.get(key)
        if pl is None:
            return

        # Convert x/y to numpy arrays (robust to lists)
        try:
            import numpy as np
            x = np.asarray(getattr(pl, "x", []), dtype=float)
            y = np.asarray(getattr(pl, "y", []), dtype=float)
        except Exception:
            return
        if x.size == 0 or y.size == 0:
            return

        # Compute ranges ignoring NaNs
        try:
            import numpy as np
            xmin = float(np.nanmin(x))
            xmax = float(np.nanmax(x))
            ymin = float(np.nanmin(y))
            ymax = float(np.nanmax(y))
        except Exception:
            return

        # Store previous curve defaults for detecting 'still default' values when curve changes
        if hasattr(self, '_x_range') and hasattr(self, '_y_range'):
            try:
                px0, px1 = self._x_range
                py0, py1 = self._y_range
                pxmin = float(min(px0, px1)); pxmax = float(max(px0, px1)); pxmid = 0.5*(pxmin+pxmax)
                pymin = float(min(py0, py1)); pymax = float(max(py0, py1)); pyhalf = 0.5*abs(pymax-pymin)
                px_at_ymax = pxmid
                py_at_ymax = max(0.0, pymax)
                try:
                    key_prev = self._active_curve_key if getattr(self, '_active_curve_key', None) is not None else self._get_checked_key()
                    pl_prev = self._payload_by_key.get(key_prev) if key_prev is not None else None
                    if pl_prev is not None and getattr(pl_prev, 'x', None) is not None and getattr(pl_prev, 'y', None) is not None:
                        x_prev = np.asarray(pl_prev.x, dtype=float)
                        y_prev = np.asarray(pl_prev.y, dtype=float)
                        if x_prev.size and y_prev.size == x_prev.size:
                            i_prev = int(np.nanargmax(y_prev))
                            px_at_ymax = float(x_prev[i_prev])
                            py_at_ymax = float(max(0.0, y_prev[i_prev]))
                except Exception:
                    pass
                self._prev_curve_defaults = (pxmin, pxmax, pxmid, max(0.0, pymax), pyhalf, px_at_ymax, py_at_ymax)
            except Exception:
                self._prev_curve_defaults = None
        else:
            self._prev_curve_defaults = None

        self._x_range = (xmin, xmax)
        self._y_range = (ymin, ymax)

        # Clear and plot.  Save any manually dragged legend position before
        # setup_payload_plot() clears the Matplotlib axes.
        try:
            self._remember_fit_legend_position()
        except Exception:
            pass
        self._clear_bg_artist()
        title = getattr(pl, "title", None) or self._display_by_key.get(key, "")
        state = None
        try:
            state = fit_plotting.setup_payload_plot(self.ax, self.ax_res, pl, title=title)
        except Exception:
            state = None
        if not state:
            self.ax.clear()
            fit_plotting.plot_data_curve(self.ax, x, y)
            self._clear_residual_axis()

        # Auto-guess polynomial background coefficients (if enabled/not touched)
        try:
            self._maybe_autoguess_bg(force=False)
        except Exception as exc:
            log_noncritical_error("auto-guessing background for plotted curve", exc, logger=self._logger)
        try:
            self._refresh_bg_artist()
        except Exception:
            pass

        self._refresh_peak_markers()
        try:
            self._refresh_fit_range_artists()
        except Exception:
            pass

        # Update peak default bounds for newly-added peaks only
        try:
            # Existing peaks should not be overwritten; only enforce bounds and init new ones
            if not getattr(self, '_ranges_initialized', False):
                # First time we have real x/y ranges -> initialize ALL existing peaks from ranges
                self._last_peak_count = 0
                self._ranges_initialized = True
            else:
                # Later curve changes: do not overwrite existing values
                self._last_peak_count = len(getattr(self, '_peak_widgets', []))
            self._apply_peak_defaults_from_ranges(only_new=True, update_existing_defaults=False)
        except Exception:
            pass

        self._refresh_live_calculated_spectrum()
    def _build_default_curve_state_for_current_curve(self) -> Dict[str, Any]:
        """Build a conservative automatic initial fitting state for the current curve."""
        key = self._get_checked_key()
        pl = self._payload_by_key.get(key) if key is not None else None
        if pl is None:
            return {}
        import numpy as np
        x = np.asarray(getattr(pl, "x", []), dtype=float)
        y = np.asarray(getattr(pl, "y", []), dtype=float)
        if x.size == 0 or y.size == 0 or x.size != y.size:
            return {}
        xmin = float(np.nanmin(x)); xmax = float(np.nanmax(x))
        ymax = float(np.nanmax(y))
        y_max_nonneg = max(0.0, ymax)

        try:
            suggestions = suggest_initial_peaks(
                x, y, max_peaks=5, min_separation_ev=0.3, edge_guard_ev=0.5
            )
        except Exception:
            suggestions = []
        if not suggestions:
            try:
                i0 = int(np.nanargmax(y))
                suggestions = [type("_S", (), {"energy": float(x[i0]), "height": float(max(0.0, y[i0]))})()]
            except Exception:
                suggestions = [type("_S", (), {"energy": 0.5 * (xmin + xmax), "height": y_max_nonneg})()]

        peak_states = []
        for suggestion in suggestions[:5]:
            peak_states.append({
                "E": max(xmin, min(float(suggestion.energy), xmax)),
                "E_min": xmin,
                "E_max": xmax,
                "E_mode": "Free",
                "H": max(0.0, min(float(suggestion.height), y_max_nonneg)),
                "H_min": 0.0,
                "H_max": y_max_nonneg,
                "H_mode": "Free",
                "L": 0.2,
                "L_min": 0.05,
                "L_max": 1.0,
                "L_mode": "Free",
                "G": 0.3,
                "G_min": 0.05,
                "G_max": 2.0,
                "G_mode": "Free",
                "A": 0.0,
                "A_min": 0.0,
                "A_max": 0.2,
                "A_mode": "Free",
            })

        return {
            "peak_states": peak_states,
            "bg_state": {
                "bg_type": "Shirley",
                "b0": 0.0,
                "b1": 0.0,
                "b2": 0.0,
                "bg_alpha": 1.0,
                "bg_alpha_fixed": False,
                "bg_touched": False,
                "calc_on": True,
            },
            "fit_table": None,
            "bg_table": None,
            "fit_quality": {
                "status": "Status: —",
                "rss": "RSS: —",
                "rms": "RMS: —",
                "redchi": "Reduced χ²: —",
            },
            "bound_hits": set(),
        }
    def _initialize_current_curve_state(self) -> None:
        """Initialize a newly visited curve with the original single-curve defaults."""
        self._plot_checked_curve()
        state = self._build_default_curve_state_for_current_curve()
        if not state:
            return
        self._restore_curve_state(state)
    def _on_curve_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0 or getattr(self, "_restoring_curve_state", False):
            return
        prev_key = getattr(self, "_active_curve_key", None)
        item_key = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        target_key = None

        if item.checkState(0) == Qt.CheckState.Checked:
            # Treat the item the user just checked as authoritative, instead of
            # rescanning the tree and accidentally snapping back to the first item.
            target_key = item_key if isinstance(item_key, str) else None
            self._set_checked_curve_key(target_key)
        else:
            # Do not fall back to the first curve automatically. If the user
            # unchecked the active item and no other item is checked, restore the
            # previously active curve instead.
            other_checked = self._get_checked_key()
            if other_checked is None:
                target_key = prev_key if isinstance(prev_key, str) else (item_key if isinstance(item_key, str) else None)
                if target_key is not None:
                    self._set_checked_curve_key(target_key)
            else:
                target_key = other_checked

        if target_key is None:
            target_key = self._get_checked_key()
        if prev_key and prev_key != target_key:
            try:
                self._curve_states[prev_key] = self._capture_curve_state()
            except Exception:
                pass
            # Fit ranges are intentionally not carried between spectra.
            # Every newly selected curve starts from its complete energy range.
            try:
                self._reset_fit_range_to_full()
            except Exception:
                pass

        if target_key and target_key in self._curve_states:
            self._set_checked_curve_key(target_key)
            self._plot_checked_curve()
            self._restore_curve_state(self._curve_states[target_key])
        else:
            self._set_checked_curve_key(target_key)
            self._initialize_current_curve_state()
            if target_key:
                try:
                    self._curve_states[target_key] = self._capture_curve_state()
                except Exception:
                    pass
        self._active_curve_key = target_key
        self._install_no_enter_close_filters()
    def _install_no_enter_close_filters(self) -> None:
        """Prevent Return/Enter in spinboxes from triggering the dialog default button."""
        try:
            for sb in self.findChildren(QAbstractSpinBox):
                sb.installEventFilter(self)
                # also catch returnPressed from the internal line edit, if present
                try:
                    le = sb.lineEdit()
                    if le is not None:
                        le.returnPressed.connect(lambda sb=sb: sb.interpretText())
                except Exception:
                    pass
        except Exception:
            pass
    def eventFilter(self, obj, event):  # noqa: N802 (Qt API)
        try:
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if isinstance(obj, QAbstractSpinBox):
                        try:
                            obj.interpretText()
                        except Exception:
                            pass
                        # keep dialog open
                        return True
                    if isinstance(obj, QLineEdit) and bool(obj.property("peak_label_edit")):
                        # The label is already live-updated by textChanged.
                        # Consume Return/Enter so it cannot activate the dialog's
                        # default OK button and close the fitting window.
                        try:
                            self._refresh_fit_legend()
                        except Exception:
                            pass
                        return True
        except Exception:
            pass
        return super().eventFilter(obj, event)
