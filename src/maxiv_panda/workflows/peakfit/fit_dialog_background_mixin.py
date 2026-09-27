from __future__ import annotations

from . import fit_models, fit_plotting
from ...log_utils import log_noncritical_error


class FitDialogBackgroundMixin:
    """Background controls, estimation, and background-model helpers for the fit dialog."""

    def _update_bg_controls_visibility(self, bg_type: str) -> None:
        bg_type = str(bg_type)
        show_poly = bg_type in ("constant", "linear", "parabolic")
        show_k = bg_type == "Shirley"

        for w in (self.lab_bg_b0, self.sb_bg_b0, self.lab_bg_b1, self.sb_bg_b1, self.lab_bg_b2, self.sb_bg_b2):
            try:
                w.setVisible(show_poly)
            except Exception:
                pass
        for w in (self.lab_bg_alpha, self.sb_bg_alpha, self.chk_bg_alpha_fixed):
            try:
                w.setVisible(show_k)
            except Exception:
                pass

        try:
            self.sb_bg_b0.setEnabled(show_poly)
            self.sb_bg_b1.setEnabled(bg_type in ("linear", "parabolic"))
            self.sb_bg_b2.setEnabled(bg_type == "parabolic")
        except Exception:
            pass
        try:
            self.sb_bg_alpha.setEnabled(show_k)
            self.chk_bg_alpha_fixed.setEnabled(show_k)
        except Exception:
            pass
    def _on_bg_coeff_changed(self, *_args) -> None:
        # Mark that the user has manually adjusted BG coefficients
        self._bg_coeffs_touched = True
        try:
            self._refresh_bg_artist()
        except Exception as exc:
            log_noncritical_error("refreshing background preview for plotted curve", exc, logger=self._logger)
        self._refresh_live_calculated_spectrum()
    def _guess_poly_coeffs_from_shirley(self, bg_type: str):
        """Approximate the current Shirley background with a centered polynomial.

        This is used when the user switches from Shirley to a polynomial BG so the
        polynomial controls start from a visually reasonable background rather than
        resetting to a flat zero line.
        """
        if bg_type not in ("constant", "linear", "parabolic"):
            return None
        key = self._get_checked_key()
        if key is None:
            return None
        pl = self._payload_by_key.get(key)
        if pl is None or getattr(pl, "x", None) is None or getattr(pl, "y", None) is None:
            return None
        import numpy as np
        x = np.asarray(pl.x, dtype=float)
        y = np.asarray(pl.y, dtype=float)
        if x.size < 5 or y.size != x.size:
            return None
        try:
            scale = str(getattr(pl, "energy_scale", "")).lower()
        except Exception:
            scale = ""
        try:
            alpha = float(self.sb_bg_alpha.value()) if hasattr(self, "sb_bg_alpha") else 1.0
        except Exception:
            alpha = 1.0
        y_bg = self._compute_shirley_background(x, y, scale, alpha=alpha)
        x0 = self._poly_bg_center(x)
        xc = x - x0
        deg = 0 if bg_type == "constant" else (1 if bg_type == "linear" else 2)
        try:
            coeff = np.polyfit(xc, y_bg, deg)
        except Exception:
            return None
        b0 = b1 = b2 = 0.0
        if deg == 0:
            b0 = float(coeff[0])
        elif deg == 1:
            b1 = float(coeff[0]); b0 = float(coeff[1])
        else:
            b2 = float(coeff[0]); b1 = float(coeff[1]); b0 = float(coeff[2])
        xr = float(np.nanmax(x) - np.nanmin(x))
        yr = float(np.nanmax(y) - np.nanmin(y))
        xr = max(xr, 1e-12)
        slope_lim = 5.0 * (yr / xr) if yr > 0 else 1.0
        curv_lim = 5.0 * (yr / (xr * xr)) if yr > 0 else 1.0
        b1 = float(np.clip(b1, -slope_lim, slope_lim))
        b2 = float(np.clip(b2, -curv_lim, curv_lim))
        return b0, (b1 if bg_type in ("linear", "parabolic") else 0.0), (b2 if bg_type == "parabolic" else 0.0)
    def _guess_poly_coeffs_from_displayed_bg(self, bg_type: str):
        """Approximate the currently displayed BG curve with a centered polynomial.

        This is primarily used when switching from Shirley to a polynomial BG while
        the live model is active. It fits directly to the background curve the
        user is actually seeing, which is more reliable than recomputing a fresh
        Shirley estimate during the transition.
        """
        if bg_type not in ("constant", "linear", "parabolic"):
            return None
        import numpy as np
        arts = []
        try:
            arts = list(getattr(self, "_calc_artists", []) or [])
        except Exception:
            arts = []
        line = arts[0] if arts else None
        if line is None:
            return None
        try:
            x = np.asarray(line.get_xdata(), dtype=float)
            y_bg = np.asarray(line.get_ydata(), dtype=float)
        except Exception:
            return None
        if x.size < 5 or y_bg.size != x.size:
            return None
        x0 = self._poly_bg_center(x)
        xc = x - x0
        deg = 0 if bg_type == "constant" else (1 if bg_type == "linear" else 2)
        try:
            coeff = np.polyfit(xc, y_bg, deg)
        except Exception:
            return None
        b0 = b1 = b2 = 0.0
        if deg == 0:
            b0 = float(coeff[0])
        elif deg == 1:
            b1 = float(coeff[0]); b0 = float(coeff[1])
        else:
            b2 = float(coeff[0]); b1 = float(coeff[1]); b0 = float(coeff[2])
        xr = float(np.nanmax(x) - np.nanmin(x))
        yr = float(np.nanmax(y_bg) - np.nanmin(y_bg))
        xr = max(xr, 1e-12)
        slope_lim = 5.0 * (yr / xr) if yr > 0 else max(abs(b1), 1.0)
        curv_lim = 5.0 * (yr / (xr * xr)) if yr > 0 else max(abs(b2), 1.0)
        b1 = float(np.clip(b1, -slope_lim, slope_lim))
        b2 = float(np.clip(b2, -curv_lim, curv_lim))
        return b0, (b1 if bg_type in ("linear", "parabolic") else 0.0), (b2 if bg_type == "parabolic" else 0.0)
    def _guess_poly_coeffs_from_last_calc_bg(self, bg_type: str):
        """Approximate the last calculated Shirley BG array with a centered polynomial.

        This is more reliable than reading back plotted artists because it uses the
        actual BG values from the most recent live-model calculation.
        """
        if bg_type not in ("constant", "linear", "parabolic"):
            return None
        try:
            payload = getattr(self, "_last_calc_bg_curve", None)
        except Exception:
            payload = None
        if not payload or len(payload) < 3:
            return None
        try:
            x, y_bg, prev_type = payload
        except Exception:
            return None
        try:
            if str(prev_type) != "Shirley":
                return None
        except Exception:
            return None
        import numpy as np
        try:
            x = np.asarray(x, dtype=float)
            y_bg = np.asarray(y_bg, dtype=float)
        except Exception:
            return None
        if x.size < 5 or y_bg.size != x.size:
            return None
        x0 = self._poly_bg_center(x)
        xc = x - x0
        deg = 0 if bg_type == "constant" else (1 if bg_type == "linear" else 2)
        try:
            coeff = np.polyfit(xc, y_bg, deg)
        except Exception:
            return None
        b0 = b1 = b2 = 0.0
        if deg == 0:
            b0 = float(coeff[0])
        elif deg == 1:
            b1 = float(coeff[0]); b0 = float(coeff[1])
        else:
            b2 = float(coeff[0]); b1 = float(coeff[1]); b0 = float(coeff[2])
        xr = float(np.nanmax(x) - np.nanmin(x))
        yr = float(np.nanmax(y_bg) - np.nanmin(y_bg))
        xr = max(xr, 1e-12)
        slope_lim = 5.0 * (yr / xr) if yr > 0 else max(abs(b1), 1.0)
        curv_lim = 5.0 * (yr / (xr * xr)) if yr > 0 else max(abs(b2), 1.0)
        b1 = float(np.clip(b1, -slope_lim, slope_lim))
        b2 = float(np.clip(b2, -curv_lim, curv_lim))
        return b0, (b1 if bg_type in ("linear", "parabolic") else 0.0), (b2 if bg_type == "parabolic" else 0.0)
    def _on_bg_type_changed(self, bg_type: str) -> None:
        """Handle BG type change: update visibility and re-guess polynomial coefficients."""
        self._last_bg_type = str(bg_type)
        self._update_bg_controls_visibility(bg_type)
        self._bg_coeffs_touched = False
        try:
            self._maybe_autoguess_bg(force=True)
            self._refresh_bg_artist()
        except Exception:
            pass
        self._update_fit_results_tables()
        self._refresh_live_calculated_spectrum()
    def _maybe_autoguess_bg(self, force: bool = False) -> None:
        """Auto-guess BG coefficients directly from the data.

        The polynomial backgrounds are guessed in the centered internal basis
        used for drawing/fitting. For linear/parabolic BG the guess is based on
        both edge regions of the spectrum, which is substantially more stable
        than fitting only one edge. If the parabolic curvature still comes out
        too strong, it is damped progressively while keeping the result
        parabolic rather than silently falling back to a different BG type.
        """
        try:
            bg_type = str(self.cb_bg_type.currentText())
        except Exception:
            return
        if bg_type not in ("constant", "linear", "parabolic", "Shirley"):
            return

        if (not force) and getattr(self, "_bg_coeffs_touched", False):
            return

        key = self._get_checked_key()
        if key is None:
            return
        pl = self._payload_by_key.get(key)
        if pl is None or getattr(pl, "x", None) is None or getattr(pl, "y", None) is None:
            return

        import numpy as np
        x = np.asarray(pl.x, dtype=float)
        y = np.asarray(pl.y, dtype=float)
        if x.size < 10 or y.size != x.size:
            return

        order = np.argsort(x)
        x_sorted = x[order]
        y_sorted = y[order]
        x0 = self._poly_bg_center(x_sorted)
        xc_all = x_sorted - x0

        n = x_sorted.size
        n_edge = max(5, int(round(0.08 * n)))
        n_edge = min(n_edge, max(5, n // 3))
        x_edge = np.concatenate([x_sorted[:n_edge], x_sorted[-n_edge:]])
        y_edge = np.concatenate([y_sorted[:n_edge], y_sorted[-n_edge:]])
        xc_edge = x_edge - x0

        yr = float(np.nanmax(y_sorted) - np.nanmin(y_sorted)) if y_sorted.size else 0.0
        xr = float(np.nanmax(x_sorted) - np.nanmin(x_sorted)) if x_sorted.size else 0.0
        xr = max(xr, 1e-12)
        yr = max(yr, 1e-12)

        if bg_type == "Shirley":
            try:
                self.sb_bg_alpha.setValue(float(np.clip(self.sb_bg_alpha.value(), 0.0, 1.0)))
            except Exception:
                pass
            return

        if bg_type == "constant":
            b0 = float(np.median(y_edge))
            b1 = 0.0
            b2 = 0.0
        else:
            deg = 1 if bg_type == "linear" else 2
            try:
                coeff = np.polyfit(xc_edge, y_edge, deg)
            except Exception:
                coeff = np.polyfit(xc_edge, y_edge, 1)
                if deg == 2:
                    coeff = np.array([0.0, float(coeff[0]), float(coeff[1])], dtype=float)
            if deg == 1:
                b1 = float(coeff[0]); b0 = float(coeff[1]); b2 = 0.0
            else:
                b2 = float(coeff[0]); b1 = float(coeff[1]); b0 = float(coeff[2])

            slope_lim = 5.0 * (yr / xr)
            curv_lim = 5.0 * (yr / (xr * xr))
            b1 = float(np.clip(b1, -slope_lim, slope_lim))
            b2 = float(np.clip(b2, -curv_lim, curv_lim))

            # Edge-anchored vertical recentering: keep the mean of the guessed BG
            # on the edge regions close to the edge data level.
            try:
                bg_edge = b0 + b1 * xc_edge + b2 * (xc_edge ** 2)
                b0 += float(np.mean(y_edge) - np.mean(bg_edge))
            except Exception:
                pass

            if bg_type == "parabolic":
                # Keep the guess parabolic, but damp excessive curvature if it
                # would produce a background wildly outside the data scale.
                allowed_range = 2.5 * yr
                allowed_low = float(np.nanmin(y_sorted) - 0.75 * yr)
                allowed_high = float(np.nanmax(y_sorted) + 0.75 * yr)
                for _ in range(12):
                    bg_all = b0 + b1 * xc_all + b2 * (xc_all ** 2)
                    bg_range = float(np.nanmax(bg_all) - np.nanmin(bg_all))
                    bg_min = float(np.nanmin(bg_all))
                    bg_max = float(np.nanmax(bg_all))
                    if bg_range <= allowed_range and bg_min >= allowed_low and bg_max <= allowed_high:
                        break
                    b2 *= 0.5
                    bg_edge = b0 + b1 * xc_edge + b2 * (xc_edge ** 2)
                    b0 += float(np.mean(y_edge) - np.mean(bg_edge))

        try:
            for sb in (self.sb_bg_b0, self.sb_bg_b1, self.sb_bg_b2):
                sb.blockSignals(True)
            self.sb_bg_b0.setValue(float(b0))
            self.sb_bg_b1.setValue(float(b1) if bg_type in ("linear", "parabolic") else 0.0)
            self.sb_bg_b2.setValue(float(b2) if bg_type == "parabolic" else 0.0)
        finally:
            for sb in (self.sb_bg_b0, self.sb_bg_b1, self.sb_bg_b2):
                try:
                    sb.blockSignals(False)
                except Exception:
                    pass

        try:
            self._refresh_bg_artist()
        except Exception:
            pass
    def _clear_bg_artist(self) -> None:
        """Remove any previously drawn background lines."""
        fit_plotting.clear_artist_attributes(self, "_bg_artists", "_bg_artist")
    def _refresh_bg_artist(self) -> None:
        """Plot the current background guess (constant/linear/parabolic/Shirley)."""
        self._clear_bg_artist()

        try:
            bg_type = str(self.cb_bg_type.currentText())
        except Exception:
            bg_type = "Shirley"

        if bg_type not in ("constant", "linear", "parabolic", "Shirley"):
            try:
                self.canvas.draw_idle()
            except Exception:
                pass
            return

        key = self._get_checked_key()
        if key is None:
            return
        pl = self._payload_by_key.get(key)
        if pl is None or getattr(pl, "x", None) is None or getattr(pl, "y", None) is None:
            return

        import numpy as np
        x = np.asarray(pl.x, dtype=float)
        y = np.asarray(pl.y, dtype=float)
        if x.size < 2 or y.size != x.size:
            return

        scale = str(getattr(pl, "energy_scale", "")).lower()

        if bg_type == "Shirley":
            alpha = float(self.sb_bg_alpha.value()) if hasattr(self, "sb_bg_alpha") else 1.0
            y_bg = self._compute_shirley_background(x, y, scale, alpha=alpha)
        else:
            b0 = float(self.sb_bg_b0.value())
            b1 = float(self.sb_bg_b1.value()) if bg_type in ("linear", "parabolic") else 0.0
            b2 = float(self.sb_bg_b2.value()) if bg_type == "parabolic" else 0.0
            y_bg = self._poly_background(x, b0, b1, b2)

        try:
            ln = fit_plotting.plot_background_curve(self.ax, x, y_bg)
            self._bg_artist = ln
            self._bg_artists = [ln] if ln is not None else []
            self.canvas.draw_idle()
        except Exception:
            pass
    def _poly_bg_center(self, x: "np.ndarray") -> float:
        return fit_models.poly_bg_center(x)
    def _poly_background(self, x: "np.ndarray", b0: float, b1: float, b2: float = 0.0) -> "np.ndarray":
        return fit_models.poly_background_centered(x, b0, b1, b2)
    def _compute_shirley_background(self, x: "np.ndarray", y: "np.ndarray", scale: str, alpha: float = 1.0) -> "np.ndarray":
        return fit_models.compute_shirley_background(x, y, scale, alpha=alpha)
