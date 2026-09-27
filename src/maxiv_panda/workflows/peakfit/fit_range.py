from __future__ import annotations

from typing import Callable, Optional, Tuple

from PyQt6.QtCore import QLocale, Qt
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


def _format_energy(value: float) -> str:
    """Compact but precise display for energy limits."""
    return f"{float(value):.6f}".rstrip("0").rstrip(".")


class FitRangeDialog(QDialog):
    """Compact, live editor for the fitting interval.

    Numeric edits are applied immediately when they form a valid interval.
    The dialog therefore needs no Apply/Accept step: ``Close`` simply dismisses
    the editor while keeping the current live range.
    """

    def __init__(
        self,
        spectrum_min: float,
        spectrum_max: float,
        current_min: float,
        current_max: float,
        *,
        preview_callback: Optional[Callable[[float, float], None]] = None,
        select_callback: Optional[Callable[["FitRangeDialog"], None]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fit range")
        self.setModal(False)

        self._spectrum_min = float(min(spectrum_min, spectrum_max))
        self._spectrum_max = float(max(spectrum_min, spectrum_max))
        self._preview_callback = preview_callback
        self._select_callback = select_callback

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self.edit_min = QLineEdit(_format_energy(current_min), self)
        self.edit_max = QLineEdit(_format_energy(current_max), self)
        validator_min = QDoubleValidator(self._spectrum_min, self._spectrum_max, 8, self)
        validator_max = QDoubleValidator(self._spectrum_min, self._spectrum_max, 8, self)
        for validator in (validator_min, validator_max):
            # Energies are displayed and parsed with a decimal point regardless
            # of the system locale.
            validator.setLocale(QLocale.c())
            validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.edit_min.setValidator(validator_min)
        self.edit_max.setValidator(validator_max)
        self.edit_min.setMinimumWidth(105)
        self.edit_max.setMinimumWidth(105)
        grid.addWidget(QLabel("Min:", self), 0, 0)
        grid.addWidget(self.edit_min, 0, 1)
        grid.addWidget(QLabel("eV", self), 0, 2)
        grid.addWidget(QLabel("Max:", self), 1, 0)
        grid.addWidget(self.edit_max, 1, 1)
        grid.addWidget(QLabel("eV", self), 1, 2)
        lay.addLayout(grid)

        action_row = QHBoxLayout()
        action_row.setSpacing(6)
        self.btn_select_mouse = QPushButton("Select on plot", self)
        self.btn_select_mouse.setToolTip("Drag across the spectrum plot, or click two positions, to set the fit range.")
        self.btn_select_mouse.clicked.connect(self._request_mouse_selection)
        action_row.addWidget(self.btn_select_mouse)
        self.btn_full = QPushButton("Full", self)
        self.btn_full.setToolTip("Use the full spectrum range.")
        self.btn_full.clicked.connect(self._set_full_range)
        action_row.addWidget(self.btn_full)
        action_row.addStretch(1)
        self.btn_close = QPushButton("Close", self)
        self.btn_close.clicked.connect(self.close)
        action_row.addWidget(self.btn_close)
        lay.addLayout(action_row)

        # Live editing: valid ranges are applied as soon as the text changes.
        self.edit_min.textEdited.connect(self._preview_if_valid)
        self.edit_max.textEdited.connect(self._preview_if_valid)

    def set_range_from_plot(self, lo: float, hi: float) -> None:
        """Synchronize fields from plot interaction without re-applying it."""
        lo, hi = sorted((float(lo), float(hi)))
        lo = max(self._spectrum_min, min(lo, self._spectrum_max))
        hi = max(self._spectrum_min, min(hi, self._spectrum_max))
        if not lo < hi:
            return
        self.edit_min.blockSignals(True)
        self.edit_max.blockSignals(True)
        try:
            self.edit_min.setText(_format_energy(lo))
            self.edit_max.setText(_format_energy(hi))
        finally:
            self.edit_min.blockSignals(False)
            self.edit_max.blockSignals(False)
        self._mark_validity(True)

    def _request_mouse_selection(self) -> None:
        if self._select_callback is not None:
            # Keep the spectrum unobstructed while the user drags the range.
            self.hide()
            self._select_callback(self)

    def _mark_validity(self, valid: bool) -> None:
        style = "" if valid else "QLineEdit { background: #ffd9d9; color: #6b2020; }"
        self.edit_min.setStyleSheet(style)
        self.edit_max.setStyleSheet(style)

    def _validated_values(self) -> Optional[Tuple[float, float]]:
        try:
            lo = float(self.edit_min.text().strip())
            hi = float(self.edit_max.text().strip())
        except Exception:
            self._mark_validity(False)
            return None
        eps = max(1e-12, 1e-10 * max(1.0, abs(self._spectrum_min), abs(self._spectrum_max)))
        valid = (
            self._spectrum_min - eps <= lo <= self._spectrum_max + eps
            and self._spectrum_min - eps <= hi <= self._spectrum_max + eps
            and lo < hi
        )
        self._mark_validity(valid)
        if not valid:
            return None
        return float(lo), float(hi)

    def _preview_if_valid(self) -> None:
        values = self._validated_values()
        if values is None:
            return
        if self._preview_callback is not None:
            self._preview_callback(*values)

    def _set_full_range(self) -> None:
        self.edit_min.blockSignals(True)
        self.edit_max.blockSignals(True)
        try:
            self.edit_min.setText(_format_energy(self._spectrum_min))
            self.edit_max.setText(_format_energy(self._spectrum_max))
        finally:
            self.edit_min.blockSignals(False)
            self.edit_max.blockSignals(False)
        self._mark_validity(True)
        if self._preview_callback is not None:
            self._preview_callback(self._spectrum_min, self._spectrum_max)


class FitDialogRangeMixin:
    """Fit-range state, GUI dialog, masking hook, and plot-range artists."""

    def _full_spectrum_range(self) -> Optional[Tuple[float, float]]:
        key = self._get_checked_key()
        if key is None:
            return None
        pl = self._payload_by_key.get(key)
        if pl is None or getattr(pl, "x", None) is None:
            return None
        try:
            import numpy as np

            x = np.asarray(pl.x, dtype=float)
            x = x[np.isfinite(x)]
            if x.size == 0:
                return None
            return float(np.min(x)), float(np.max(x))
        except Exception:
            return None

    def _current_fit_range(self) -> Optional[Tuple[float, float]]:
        """Return custom accepted range, or None for the full spectrum."""
        rng = getattr(self, "_fit_range", None)
        if not rng or len(rng) != 2:
            return None
        return float(min(rng)), float(max(rng))

    def _is_full_range(self, lo: float, hi: float) -> bool:
        full = self._full_spectrum_range()
        if full is None:
            return True
        f0, f1 = full
        tol = max(1e-9, 1e-8 * max(1.0, abs(f0), abs(f1)))
        return abs(float(lo) - f0) <= tol and abs(float(hi) - f1) <= tol

    def _fit_range_status_text(self) -> str:
        """Return the intentionally compact fit-range state shown in the top row."""
        return "Full" if self._current_fit_range() is None else "Custom"

    def _update_fit_range_button(self) -> None:
        """Refresh the compact range status (name kept for older call sites)."""
        try:
            self.lbl_fit_range_value.setText(self._fit_range_status_text())
            rng = self._current_fit_range()
            if rng is None:
                self.lbl_fit_range_value.setToolTip("Using the full spectrum range.")
            else:
                lo, hi = rng
                self.lbl_fit_range_value.setToolTip(
                    f"Custom range: {_format_energy(lo)}–{_format_energy(hi)} eV"
                )
            self.btn_fit_range.setToolTip(
                "Set the fit range numerically or on the plot. The dashed boundaries can also be dragged directly."
            )
        except Exception:
            pass

    def _clear_fit_range_artists(self) -> None:
        for artist in list(getattr(self, "_fit_range_artists", []) or []):
            try:
                artist.remove()
            except Exception:
                pass
        self._fit_range_artists = []

    def _draw_fit_range_preview(self, lo: float, hi: float) -> None:
        """Draw preview/accepted range lines without changing fit state."""
        self._clear_fit_range_artists()
        if self._is_full_range(lo, hi):
            try:
                self.canvas.draw_idle()
            except Exception:
                pass
            return
        try:
            a0 = self.ax.axvline(float(lo), linestyle="--", linewidth=1.2, color="0.35", alpha=0.9, zorder=20)
            a1 = self.ax.axvline(float(hi), linestyle="--", linewidth=1.2, color="0.35", alpha=0.9, zorder=20)
            self._fit_range_artists = [a0, a1]
        except Exception:
            self._fit_range_artists = []
        try:
            self.canvas.draw_idle()
        except Exception:
            pass

    def _refresh_fit_range_artists(self) -> None:
        rng = self._current_fit_range()
        if rng is None:
            self._clear_fit_range_artists()
            try:
                self.canvas.draw_idle()
            except Exception:
                pass
            return
        self._draw_fit_range_preview(*rng)

    def _reset_fit_range_to_full(self) -> None:
        self._fit_range = None
        self._clear_fit_range_artists()
        self._update_fit_range_button()
        try:
            self.canvas.draw_idle()
        except Exception:
            pass

    def _fit_range_dialog_instance(self):
        dlg = getattr(self, "_fit_range_dialog", None)
        try:
            if dlg is not None and dlg.isVisible():
                return dlg
        except Exception:
            pass
        return dlg

    def _update_open_fit_range_dialog(self, lo: float, hi: float) -> None:
        dlg = self._fit_range_dialog_instance()
        if dlg is None:
            return
        try:
            dlg.set_range_from_plot(lo, hi)
        except Exception:
            pass

    def _arm_fit_range_mouse_selection(self, dlg=None) -> None:
        self._fit_range_select_mode = True
        self._fit_range_select_start = None
        self._fit_range_select_press_x = None
        self._fit_range_select_press_px = None
        self._fit_range_select_dragged = False
        self._fit_range_select_awaiting_second_click = False
        self._fit_range_select_dialog = dlg
        try:
            self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        except Exception:
            pass

    def _finish_fit_range_mouse_mode(self) -> None:
        self._fit_range_select_mode = False
        self._fit_range_select_start = None
        self._fit_range_select_press_x = None
        self._fit_range_select_press_px = None
        self._fit_range_select_dragged = False
        self._fit_range_select_awaiting_second_click = False
        dlg = getattr(self, "_fit_range_select_dialog", None)
        self._fit_range_select_dialog = None
        try:
            self.canvas.unsetCursor()
        except Exception:
            pass
        # ``Select on plot`` is a complete action: once the drag finishes,
        # keep the editor closed.  The user can press Edit again for numeric
        # fine-tuning if needed.
        try:
            if dlg is not None:
                dlg.close()
        except Exception:
            pass

    def _fit_range_event_x(self, event) -> Optional[float]:
        """Return an x position for a mouse event, clamped to the spectrum range.

        Matplotlib may set ``xdata`` to ``None`` when the pointer is released
        on or just beyond an axes edge.  For fit-range selection that should
        still mean "use this edge", so fall back to converting the event's
        pixel coordinate through the axes transform and clamp the result.
        """
        full = self._full_spectrum_range()
        if full is None:
            return None
        value = None
        try:
            if event.xdata is not None:
                value = float(event.xdata)
        except Exception:
            value = None
        if value is None:
            try:
                px = float(event.x)
                py = float(getattr(event, "y", 0.0) or 0.0)
                value = float(self.ax.transData.inverted().transform((px, py))[0])
            except Exception:
                return None
        lo, hi = sorted((float(full[0]), float(full[1])))
        return max(lo, min(float(value), hi))

    def _on_fit_range_mouse_press(self, event) -> None:
        try:
            if event.inaxes is not self.ax or event.button != 1:
                return
        except Exception:
            return

        if bool(getattr(self, "_fit_range_select_mode", False)):
            xpos = self._fit_range_event_x(event)
            if xpos is None:
                return
            if getattr(self, "_fit_range_select_start", None) is None:
                self._fit_range_select_start = float(xpos)
                self._fit_range_select_press_x = float(xpos)
                try:
                    self._fit_range_select_press_px = float(event.x)
                except Exception:
                    self._fit_range_select_press_px = None
                self._fit_range_select_dragged = False
                self._fit_range_select_awaiting_second_click = False
                # A single dashed line gives immediate feedback for the first border.
                self._draw_fit_range_preview(float(xpos), float(xpos) + 1e-12)
            else:
                # The first click was released without a drag.  This press is
                # the second border of the two-click selection gesture.
                self._fit_range_select_press_x = float(xpos)
                try:
                    self._fit_range_select_press_px = float(event.x)
                except Exception:
                    self._fit_range_select_press_px = None
                self._fit_range_select_dragged = False
            return

        rng = self._current_fit_range()
        if rng is None:
            return
        try:
            event_px = float(event.x)
            dists = []
            for xval in rng:
                px = float(self.ax.transData.transform((float(xval), 0.0))[0])
                dists.append(abs(event_px - px))
            side = 0 if dists[0] <= dists[1] else 1
            if dists[side] <= 10.0:
                self._drag_fit_range_side = side
                self._drag_fit_range_press_x = float(event.xdata)
                self._drag_fit_range_start = tuple(rng)
        except Exception:
            return

    def _apply_dragged_fit_range(self, lo: float, hi: float) -> None:
        full = self._full_spectrum_range()
        if full is None:
            return
        lo, hi = sorted((float(lo), float(hi)))
        lo = max(full[0], min(lo, full[1]))
        hi = max(full[0], min(hi, full[1]))
        min_sep = max(1e-12, 1e-10 * max(1.0, abs(full[0]), abs(full[1])))
        if hi - lo <= min_sep:
            return
        self._fit_range = None if self._is_full_range(lo, hi) else (lo, hi)
        self._update_fit_range_button()
        self._draw_fit_range_preview(lo, hi)
        self._update_open_fit_range_dialog(lo, hi)
        try:
            self._refresh_live_calculated_spectrum()
        except Exception:
            pass

    def _on_fit_range_mouse_motion(self, event) -> None:
        if bool(getattr(self, "_fit_range_select_mode", False)) and getattr(self, "_fit_range_select_start", None) is not None:
            current = self._fit_range_event_x(event)
            if current is None:
                return
            start = float(self._fit_range_select_start)
            try:
                press_px = getattr(self, "_fit_range_select_press_px", None)
                if press_px is not None and abs(float(event.x) - float(press_px)) >= 3.0:
                    self._fit_range_select_dragged = True
            except Exception:
                pass
            if abs(float(current) - start) > 1e-12:
                lo, hi = sorted((start, float(current)))
                self._draw_fit_range_preview(lo, hi)
                self._update_open_fit_range_dialog(lo, hi)
            return

        if event.inaxes is not self.ax or event.xdata is None:
            return
        side = getattr(self, "_drag_fit_range_side", None)
        start_rng = getattr(self, "_drag_fit_range_start", None)
        press_x = getattr(self, "_drag_fit_range_press_x", None)
        if side is None or start_rng is None or press_x is None:
            return
        delta = float(event.xdata) - float(press_x)
        vals = [float(start_rng[0]), float(start_rng[1])]
        vals[int(side)] = vals[int(side)] + delta
        self._apply_dragged_fit_range(vals[0], vals[1])

    def _on_fit_range_mouse_release(self, event) -> None:
        if bool(getattr(self, "_fit_range_select_mode", False)):
            start = getattr(self, "_fit_range_select_start", None)
            if start is not None:
                end = self._fit_range_event_x(event)
                awaiting_second = bool(getattr(self, "_fit_range_select_awaiting_second_click", False))
                dragged = bool(getattr(self, "_fit_range_select_dragged", False))
                if end is not None and (dragged or awaiting_second):
                    lo, hi = sorted((float(start), float(end)))
                    full = self._full_spectrum_range()
                    min_sep = 0.0
                    if full is not None:
                        min_sep = max(1e-12, 1e-10 * max(1.0, abs(full[0]), abs(full[1])))
                    if hi - lo > min_sep:
                        self._apply_dragged_fit_range(lo, hi)
                        self._finish_fit_range_mouse_mode()
                        self._drag_fit_range_side = None
                        self._drag_fit_range_press_x = None
                        self._drag_fit_range_start = None
                        return
                # A plain click-release defines only the first border.  Keep
                # selection mode armed; the next click-release supplies the
                # second border.
                self._fit_range_select_awaiting_second_click = True
                self._fit_range_select_press_x = None
                self._fit_range_select_press_px = None
                self._fit_range_select_dragged = False
                self._draw_fit_range_preview(float(start), float(start) + 1e-12)
            return

        self._drag_fit_range_side = None
        self._drag_fit_range_press_x = None
        self._drag_fit_range_start = None


    def _apply_fit_range_from_dialog(self, lo: float, hi: float) -> None:
        """Apply a valid numeric/full-range edit from the live dialog."""
        full = self._full_spectrum_range()
        if full is None:
            return
        lo, hi = sorted((float(lo), float(hi)))
        lo = max(full[0], min(lo, full[1]))
        hi = max(full[0], min(hi, full[1]))
        if not lo < hi:
            return
        self._fit_range = None if self._is_full_range(lo, hi) else (lo, hi)
        self._update_fit_range_button()
        self._draw_fit_range_preview(lo, hi)
        try:
            self._clear_fit_results_tables()
        except Exception:
            pass
        try:
            self._refresh_live_calculated_spectrum()
        except Exception:
            pass

    def _position_fit_range_dialog(self, dlg) -> None:
        """Place the small range editor over the parameter side, away from the plot."""
        try:
            dlg.adjustSize()
            parent_geo = self.frameGeometry()
            screen = self.screen()
            avail = screen.availableGeometry() if screen is not None else parent_geo
            margin = 18
            x = parent_geo.right() - dlg.width() - margin
            y = parent_geo.top() + 70
            x = max(avail.left() + margin, min(x, avail.right() - dlg.width() - margin))
            y = max(avail.top() + margin, min(y, avail.bottom() - dlg.height() - margin))
            dlg.move(int(x), int(y))
        except Exception:
            pass

    def _on_edit_fit_range(self) -> None:
        full = self._full_spectrum_range()
        if full is None:
            return
        existing = self._fit_range_dialog_instance()
        if existing is not None:
            try:
                existing.show()
                self._position_fit_range_dialog(existing)
                existing.raise_()
                existing.activateWindow()
                return
            except Exception:
                pass

        current = self._current_fit_range() or full
        dlg = FitRangeDialog(
            full[0], full[1], current[0], current[1],
            preview_callback=self._apply_fit_range_from_dialog,
            select_callback=self._arm_fit_range_mouse_selection,
            parent=self,
        )
        self._fit_range_dialog = dlg

        def _finished(_result):
            self._finish_fit_range_mouse_mode()
            self._fit_range_dialog = None

        dlg.finished.connect(_finished)
        dlg.show()
        self._position_fit_range_dialog(dlg)
        dlg.raise_()
        dlg.activateWindow()

