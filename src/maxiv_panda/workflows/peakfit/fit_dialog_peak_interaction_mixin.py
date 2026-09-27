from __future__ import annotations


class FitDialogPeakInteractionMixin:
    """Peak-marker interaction and peak initialization/default-placement helpers."""

    def _peak_marker_drag_enabled(self) -> bool:
        """Return True when peak Energy/Height markers may be dragged."""
        try:
            # Do not steal mouse gestures from Matplotlib pan/zoom modes.
            if getattr(getattr(self, "nav", None), "mode", ""):
                return False
        except Exception:
            pass
        return bool(getattr(self, "_peak_widgets", []))
    @staticmethod
    def _peak_parameter_is_tied(w, prefix: str) -> bool:
        try:
            combo = w.get(f"{prefix}_mode")
            text = str(combo.currentText()) if combo is not None else "Free"
            return text.startswith("Tied to")
        except Exception:
            return False
    def _current_spectrum_intensity_max(self) -> float:
        """Return the non-negative maximum measured intensity of the active spectrum."""
        try:
            import numpy as np
            key = self._get_checked_key()
            pl = self._payload_by_key.get(key) if key is not None else None
            yy = np.asarray(getattr(pl, "y", []), dtype=float)
            yy = yy[np.isfinite(yy)]
            if yy.size:
                return max(0.0, float(np.max(yy)))
        except Exception:
            pass
        try:
            return max(0.0, float(max(self._y_range)))
        except Exception:
            return 0.0
    def _enforce_peak_height_physical_bounds(self) -> None:
        """Clamp all manual Height controls to [0, active spectrum maximum]."""
        physical_max = self._current_spectrum_intensity_max()
        for w in getattr(self, "_peak_widgets", []) or []:
            try:
                sb_min = w["H_min"]
                sb_val = w["H"]
                sb_max = w["H_max"]
                for sb in (sb_min, sb_val, sb_max):
                    sb.blockSignals(True)
                sb_min.setProperty("hard_min", 0.0)
                sb_max.setProperty("hard_max", physical_max)
                sb_min.setRange(0.0, physical_max)
                sb_max.setRange(0.0, physical_max)
                lo = min(max(0.0, float(sb_min.value())), physical_max)
                hi = min(max(lo, float(sb_max.value())), physical_max)
                sb_min.setValue(lo)
                sb_max.setValue(hi)
                sb_val.setRange(lo, hi)
                sb_val.setValue(min(max(float(sb_val.value()), lo), hi))
            except Exception:
                pass
            finally:
                try:
                    for sb in (sb_min, sb_val, sb_max):
                        sb.blockSignals(False)
                except Exception:
                    pass
    def _on_peak_marker_press(self, event) -> None:
        """Start 2-D dragging of a peak Energy/Height marker."""
        self._drag_peak_index = None
        self._drag_peak_axes = (False, False)
        self._drag_peak_press_data = None
        if not self._peak_marker_drag_enabled():
            return
        if bool(getattr(self, "_fit_range_select_mode", False)) or getattr(self, "_drag_fit_range_side", None) is not None:
            return
        try:
            if event.inaxes is not self.ax or event.button != 1 or event.x is None:
                return
        except Exception:
            return

        # Work in display pixels so the horizontal hit tolerance is stable
        # regardless of zoom level, BE/KE direction, or figure size.  Energy
        # and Height are independently draggable: a tied Energy can still have
        # a free Height, and vice versa.
        best = None
        best_dist = None
        best_axes = (False, False)
        widgets_all = list(getattr(self, "_peak_widgets", []) or [])
        for idx in self._visible_peak_marker_indices():
            if idx < 0 or idx >= len(widgets_all):
                continue
            w = widgets_all[idx]
            try:
                drag_e = not self._peak_parameter_is_tied(w, "E")
                drag_h = not self._peak_parameter_is_tied(w, "H")
                if not (drag_e or drag_h):
                    continue
                e_val = float(w["E"].value())
                px = float(self.ax.transData.transform((e_val, 0.0))[0])
                dist = abs(float(event.x) - px)
            except Exception:
                continue
            if best_dist is None or dist < best_dist:
                best = idx
                best_dist = dist
                best_axes = (drag_e, drag_h)
        if best is not None and best_dist is not None and best_dist <= 10.0:
            self._drag_peak_index = int(best)
            self._drag_peak_axes = best_axes
            try:
                w = getattr(self, "_peak_widgets", [])[int(best)]
                self._drag_peak_press_data = (
                    None if event.xdata is None else float(event.xdata),
                    None if event.ydata is None else float(event.ydata),
                    float(w["E"].value()),
                    float(w["H"].value()),
                )
            except Exception:
                self._drag_peak_press_data = None
    def _on_peak_marker_motion(self, event) -> None:
        """Move the active marker in Energy and/or Height and redraw the live model."""
        idx = getattr(self, "_drag_peak_index", None)
        if idx is None:
            return
        try:
            if event.inaxes is not self.ax:
                return
            widgets = getattr(self, "_peak_widgets", [])
            if idx < 0 or idx >= len(widgets):
                return
            w = widgets[idx]
            drag_e, drag_h = getattr(self, "_drag_peak_axes", (True, True))

            changed = False
            touched = []
            press_data = getattr(self, "_drag_peak_press_data", None)
            press_x = press_data[0] if press_data is not None else None
            press_y = press_data[1] if press_data is not None else None
            start_e = press_data[2] if press_data is not None else float(w["E"].value())
            start_h = press_data[3] if press_data is not None else float(w["H"].value())
            if drag_e and event.xdata is not None:
                sb_e = w["E"]
                if press_x is None:
                    e_raw = float(event.xdata)
                else:
                    e_raw = float(start_e) + (float(event.xdata) - float(press_x))
                e_val = min(max(e_raw, float(sb_e.minimum())), float(sb_e.maximum()))
                if abs(float(sb_e.value()) - e_val) > 1e-12:
                    sb_e.blockSignals(True)
                    sb_e.setValue(e_val)
                    touched.append(sb_e)
                    changed = True

            if drag_h and event.ydata is not None:
                sb_h = w["H"]
                spectrum_max = self._current_spectrum_intensity_max()
                h_upper = min(float(sb_h.maximum()), spectrum_max)
                h_lower = max(0.0, float(sb_h.minimum()))
                if h_upper < h_lower:
                    h_upper = h_lower
                if press_y is None:
                    h_raw = float(event.ydata)
                else:
                    h_raw = float(start_h) + (float(event.ydata) - float(press_y))
                h_val = min(max(h_raw, h_lower), h_upper)
                if abs(float(sb_h.value()) - h_val) > 1e-12:
                    sb_h.blockSignals(True)
                    sb_h.setValue(h_val)
                    touched.append(sb_h)
                    changed = True

            for sb in touched:
                sb.blockSignals(False)

            if not changed:
                return
            self._refresh_all_tied_parameter_values()
            self._refresh_peak_markers()
            self._refresh_live_calculated_spectrum()
        except Exception:
            try:
                for sb in locals().get("touched", []):
                    sb.blockSignals(False)
            except Exception:
                pass
    def _on_peak_marker_release(self, event) -> None:
        """Finish marker dragging and leave plot/spin-box/model state synchronized."""
        if getattr(self, "_drag_peak_index", None) is None:
            return
        self._drag_peak_index = None
        self._drag_peak_axes = (False, False)
        self._drag_peak_press_data = None
        try:
            self._refresh_peak_markers()
            self._refresh_live_calculated_spectrum()
        except Exception:
            pass
    def _apply_peak_defaults_from_ranges(self, only_new: bool = False, update_existing_defaults: bool = False) -> None:
        """Update peak spinbox bounds from current plotted x/y ranges.

        - Hard bounds always follow the currently selected curve.
        - When only_new=True: existing peaks keep values unless update_existing_defaults=True and they still
          look like "auto defaults" (not manually adjusted).
        - Newly added peaks are always initialized from the current curve.
        """
        if not getattr(self, "_peak_widgets", None):
            return
        if not hasattr(self, "_x_range") or not hasattr(self, "_y_range"):
            return

        x0, x1 = self._x_range
        y0, y1 = self._y_range
        xmin = float(min(x0, x1))
        xmax = float(max(x0, x1))
        xmid = 0.5 * (xmin + xmax)

        ymin = float(min(y0, y1))
        ymax = float(max(y0, y1))

        # Keep the parameter hard bounds tied to the complete curve.  The fit
        # range selects which measured points are fitted; it is not itself a
        # hard parameter constraint.  However, automatic guesses for newly
        # added peaks should be derived from the active fit range.
        guess_xmin, guess_xmax = xmin, xmax
        try:
            fit_rng = self._current_fit_range()
        except Exception:
            fit_rng = None
        if fit_rng is not None:
            guess_xmin = max(xmin, float(min(fit_rng)))
            guess_xmax = min(xmax, float(max(fit_rng)))
            if not guess_xmin < guess_xmax:
                guess_xmin, guess_xmax = xmin, xmax
        guess_xmid = 0.5 * (guess_xmin + guess_xmax)

        # Default initial peak guess: use the strongest measured point inside
        # the active fit range (or the whole spectrum when the range is Full).
        x_at_ymax = guess_xmid
        y_at_ymax = float(max(0.0, ymax))
        guess_ymin = ymin
        guess_ymax = ymax
        try:
            key = self._get_checked_key()
            pl = self._payload_by_key.get(key) if key is not None else None
            if pl is not None and getattr(pl, 'x', None) is not None and getattr(pl, 'y', None) is not None:
                import numpy as np
                x_arr = np.asarray(pl.x, dtype=float)
                y_arr = np.asarray(pl.y, dtype=float)
                if x_arr.size and y_arr.size == x_arr.size:
                    mask = (
                        np.isfinite(x_arr) & np.isfinite(y_arr)
                        & (x_arr >= guess_xmin) & (x_arr <= guess_xmax)
                    )
                    if np.any(mask):
                        x_local = x_arr[mask]
                        y_local = y_arr[mask]
                        i0 = int(np.nanargmax(y_local))
                        x_at_ymax = float(x_local[i0])
                        y_at_ymax = float(max(0.0, y_local[i0]))
                        guess_ymin = float(np.nanmin(y_local))
                        guess_ymax = float(np.nanmax(y_local))
        except Exception:
            pass
        yr = float(abs(guess_ymax - guess_ymin))
        yhalf = 0.5 * yr

        # Height hard bounds are physical/manual-edit bounds: [0 .. spectrum max].
        # This keeps both typed values and vertical marker dragging from creating
        # a component taller than the measured spectrum.
        y_max_nonneg = max(0.0, float(y_at_ymax), float(ymax))
        h_hard_max = y_max_nonneg

        # Previous defaults (for detecting "still default" values)
        prev = getattr(self, "_prev_curve_defaults", None)
        if prev is not None:
            if len(prev) >= 7:
                prev_xmin, prev_xmax, prev_xmid, prev_ymax, prev_yhalf, prev_x_at_ymax, prev_y_at_ymax = prev
            else:
                prev_xmin, prev_xmax, prev_xmid, prev_ymax, prev_yhalf = prev
                prev_x_at_ymax = prev_xmid
                prev_y_at_ymax = prev_ymax
        else:
            prev_xmin = prev_xmax = prev_xmid = prev_ymax = prev_yhalf = None
            prev_x_at_ymax = prev_y_at_ymax = None

        tolE = 1e-6
        tolH = 1e-6

        last_count = int(getattr(self, "_last_peak_count", 0)) if only_new else 0

        for idx, w in enumerate(self._peak_widgets, start=1):
            is_existing = only_new and (idx <= last_count)

            # --- Energy: hard bounds are curve range
            sb_Emin = w.get("E_min")
            sb_E = w.get("E")
            sb_Emax = w.get("E_max")
            if sb_Emin and sb_Emax and sb_E:
                # Update hard bounds (properties)
                sb_Emin.setProperty("hard_min", xmin)
                sb_Emax.setProperty("hard_max", xmax)

                # Determine whether user narrowed previously
                user_narrowed_E = (sb_Emin.value() > xmin + tolE) or (sb_Emax.value() < xmax - tolE)

                # If not narrowed (i.e., still default-like), snap limits to full range for current curve
                if (not is_existing) or (update_existing_defaults and (not user_narrowed_E)):
                    sb_Emin.blockSignals(True); sb_Emax.blockSignals(True)
                    sb_Emin.setRange(xmin, xmax); sb_Emax.setRange(xmin, xmax)
                    sb_Emin.setValue(xmin); sb_Emax.setValue(xmax)
                    sb_Emin.blockSignals(False); sb_Emax.blockSignals(False)
                else:
                    # Clamp current limit boxes to new hard bounds
                    sb_Emin.setRange(xmin, xmax)
                    sb_Emax.setRange(xmin, xmax)
                    if sb_Emin.value() < xmin:
                        sb_Emin.setValue(xmin)
                    if sb_Emax.value() > xmax:
                        sb_Emax.setValue(xmax)
                    if sb_Emin.value() > sb_Emax.value():
                        sb_Emin.setValue(xmin); sb_Emax.setValue(xmax)

                # Apply value range and clamp
                sb_E.setRange(sb_Emin.value(), sb_Emax.value())
                if sb_E.value() < sb_Emin.value():
                    sb_E.setValue(sb_Emin.value())
                if sb_E.value() > sb_Emax.value():
                    sb_E.setValue(sb_Emax.value())

                # Default value update only if still default-like and not fixed.
                # For newly added peaks, always initialize from the currently selected curve.
                if not is_existing:
                    if idx == 1:
                        sb_E.setValue(max(xmin, min(x_at_ymax, xmax)))
                    else:
                        sb_E.setValue(guess_xmid)
                elif update_existing_defaults and (not user_narrowed_E) and (self._param_mode(w, "E") == "Free"):
                    still_default_E = False
                    if idx == 1:
                        ref_E = prev_x_at_ymax if prev_x_at_ymax is not None else prev_xmid
                    else:
                        ref_E = prev_xmid
                    if ref_E is None:
                        still_default_E = True
                    else:
                        still_default_E = abs(sb_E.value() - ref_E) < 1e-4
                    if still_default_E:
                        # For the first peak, use global maximum as a smarter initial guess
                        if idx == 1:
                            sb_E.setValue(max(xmin, min(x_at_ymax, xmax)))
                        else:
                            sb_E.setValue(xmid)

            # --- Height: hard bounds [0, h_hard_max]
            sb_Hmin = w.get("H_min")
            sb_H = w.get("H")
            sb_Hmax = w.get("H_max")
            if sb_Hmin and sb_Hmax and sb_H:
                sb_Hmin.setProperty("hard_min", 0.0)
                sb_Hmax.setProperty("hard_max", h_hard_max)

                user_narrowed_H = (sb_Hmin.value() > 0.0 + tolH) or (sb_Hmax.value() < h_hard_max - tolH)

                if (not is_existing) or (update_existing_defaults and (not user_narrowed_H)):
                    sb_Hmin.blockSignals(True); sb_Hmax.blockSignals(True)
                    sb_Hmin.setRange(0.0, h_hard_max); sb_Hmax.setRange(0.0, h_hard_max)
                    sb_Hmin.setValue(0.0); sb_Hmax.setValue(h_hard_max)
                    sb_Hmin.blockSignals(False); sb_Hmax.blockSignals(False)
                else:
                    sb_Hmin.setRange(0.0, h_hard_max)
                    sb_Hmax.setRange(0.0, h_hard_max)
                    if sb_Hmin.value() < 0.0:
                        sb_Hmin.setValue(0.0)
                    if sb_Hmax.value() > h_hard_max:
                        sb_Hmax.setValue(h_hard_max)
                    if sb_Hmin.value() > sb_Hmax.value():
                        sb_Hmin.setValue(0.0); sb_Hmax.setValue(h_hard_max)

                sb_H.setRange(sb_Hmin.value(), sb_Hmax.value())
                if sb_H.value() < sb_Hmin.value():
                    sb_H.setValue(sb_Hmin.value())
                if sb_H.value() > sb_Hmax.value():
                    sb_H.setValue(sb_Hmax.value())

                if not is_existing:
                    sb_H.setValue(max(0.0, min(y_at_ymax if idx == 1 else yhalf, h_hard_max)))
                elif update_existing_defaults and (not user_narrowed_H) and (self._param_mode(w, "H") == "Free"):
                    still_default_H = False
                    if idx == 1:
                        ref_H = prev_y_at_ymax if prev_y_at_ymax is not None else prev_yhalf
                    else:
                        ref_H = prev_yhalf
                    if ref_H is None:
                        still_default_H = True
                    else:
                        still_default_H = abs(sb_H.value() - ref_H) < 1e-4
                    if still_default_H:
                        sb_H.setValue(max(0.0, min(y_at_ymax if idx == 1 else yhalf, h_hard_max)))

            if is_existing and not update_existing_defaults:
                continue

            # For new peaks, reset widths/alpha defaults (if present)
            if not is_existing:
                try:
                    w["L"].setValue(0.2)
                    w["G"].setValue(0.3)
                    w["A"].setValue(0.0)
                except Exception:
                    pass
    def _force_initialize_peaks_from_current_ranges(self) -> None:
        """Initialize current peak widgets exactly from the currently plotted curve ranges."""
        if not getattr(self, "_peak_widgets", None):
            return
        if not hasattr(self, "_x_range") or not hasattr(self, "_y_range"):
            return
        x0, x1 = self._x_range
        y0, y1 = self._y_range
        xmin = float(min(x0, x1)); xmax = float(max(x0, x1))
        ymin = float(min(y0, y1)); ymax = float(max(y0, y1))
        xmid = 0.5 * (xmin + xmax)
        y_max_nonneg = max(0.0, float(ymax))
        yhalf = 0.5 * float(abs(ymax - ymin))

        x_at_ymax = xmid
        y_at_ymax = y_max_nonneg
        try:
            key = self._get_checked_key()
            pl = self._payload_by_key.get(key) if key is not None else None
            if pl is not None and getattr(pl, 'x', None) is not None and getattr(pl, 'y', None) is not None:
                import numpy as np
                xx = np.asarray(pl.x, dtype=float)
                yy = np.asarray(pl.y, dtype=float)
                if xx.size and yy.size == xx.size:
                    i0 = int(np.nanargmax(yy))
                    x_at_ymax = float(xx[i0])
                    y_at_ymax = float(max(0.0, yy[i0]))
                    y_max_nonneg = y_at_ymax
        except Exception:
            pass

        for idx, w in enumerate(self._peak_widgets, start=1):
            sb_Emin = w.get("E_min"); sb_E = w.get("E"); sb_Emax = w.get("E_max")
            if sb_Emin and sb_E and sb_Emax:
                for sb in (sb_Emin, sb_E, sb_Emax):
                    try: sb.blockSignals(True)
                    except Exception: pass
                sb_Emin.setRange(xmin, xmax); sb_Emax.setRange(xmin, xmax)
                sb_Emin.setValue(xmin); sb_Emax.setValue(xmax)
                sb_E.setRange(xmin, xmax)
                sb_E.setValue(max(xmin, min(x_at_ymax if idx == 1 else xmid, xmax)))
                for sb in (sb_Emin, sb_E, sb_Emax):
                    try: sb.blockSignals(False)
                    except Exception: pass

            sb_Hmin = w.get("H_min"); sb_H = w.get("H"); sb_Hmax = w.get("H_max")
            if sb_Hmin and sb_H and sb_Hmax:
                for sb in (sb_Hmin, sb_H, sb_Hmax):
                    try: sb.blockSignals(True)
                    except Exception: pass
                sb_Hmin.setRange(0.0, y_max_nonneg); sb_Hmax.setRange(0.0, y_max_nonneg)
                sb_Hmin.setValue(0.0); sb_Hmax.setValue(y_max_nonneg)
                sb_H.setRange(0.0, y_max_nonneg)
                sb_H.setValue(max(0.0, min(y_at_ymax if idx == 1 else yhalf, y_max_nonneg)))
                for sb in (sb_Hmin, sb_H, sb_Hmax):
                    try: sb.blockSignals(False)
                    except Exception: pass

            if idx > 1:
                try: w["L"].setValue(0.2)
                except Exception: pass
                try: w["G"].setValue(0.3)
                except Exception: pass
                try: w["A"].setValue(0.0)
                except Exception: pass
