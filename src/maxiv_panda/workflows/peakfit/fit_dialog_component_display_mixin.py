from __future__ import annotations

from typing import Any, Dict
import sys

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog

from . import fit_models, fit_plotting, so_doublets


class FitDialogComponentDisplayMixin:
    """Calculated fit-component display, residuals, colors, and marker rendering."""

    def _clear_residual_axis(self) -> None:
        fit_plotting.clear_residual_axis(self.ax_res)
    def _plot_residuals(self, x, y_data, y_fit, descending: bool = False, xlabel: str = "") -> None:
        fit_plotting.plot_residuals(self.ax_res, x, y_data, y_fit, descending=descending, xlabel=xlabel)
    def _visible_peak_marker_indices(self) -> list[int]:
        """Return zero-based peak indices whose interactive markers are visible.

        Doublet view presents each SO pair as one summed component, therefore
        only the major member remains as the handle; standalone peaks are
        unaffected.
        """
        widgets = list(getattr(self, "_peak_widgets", []) or [])
        indices = list(range(len(widgets)))
        try:
            if not self._doublet_view_enabled():
                return indices
            minor = {int(st.get("minor", -1)) - 1 for st in self._capture_so_doublet_states()}
            return [i for i in indices if i not in minor]
        except Exception:
            return indices
    def _sync_peak_display_colors(self) -> dict[int, str]:
        """Resolve current plot colors once and mirror them into the GUI swatches."""
        all_widgets = list(getattr(self, "_peak_widgets", []) or [])
        try:
            colors = [str(w.get("color") or fit_plotting.default_peak_color(i + 1)) for i, w in enumerate(all_widgets)]
            custom = [bool(w.get("color_custom", False)) for w in all_widgets]
            cmap = so_doublets.visible_color_map(
                colors, custom, self._capture_so_doublet_states(), grouped=self._doublet_view_enabled()
            )
            for i, w in enumerate(all_widgets, start=1):
                w["_display_color"] = cmap.get(i, colors[i - 1])
                self._update_peak_color_button(w)
            return cmap
        except Exception:
            for w in all_widgets:
                w.pop("_display_color", None)
                self._update_peak_color_button(w)
            return {}
    def _refresh_peak_markers(self) -> None:
        """Draw/update vertical markers for visible peak handles."""
        all_widgets = list(getattr(self, "_peak_widgets", []) or [])
        visible = self._visible_peak_marker_indices()
        marker_widgets = [all_widgets[i] for i in visible if 0 <= i < len(all_widgets)]
        self._sync_peak_display_colors()
        self._peak_marker_artists = fit_plotting.refresh_peak_markers(
            self.ax,
            self.canvas,
            marker_widgets,
            True,
            getattr(self, "_peak_marker_artists", []),
        )
    def _clear_calc_artists(self) -> None:
        if hasattr(self, "_calc_artists"):
            for a in list(self._calc_artists):
                try:
                    a.remove()
                except Exception:
                    pass
        self._calc_artists = []
        self._last_calc_bg_curve = None
        if hasattr(self, "_calc_warning_artist") and self._calc_warning_artist is not None:
            try:
                self._calc_warning_artist.remove()
            except Exception:
                pass
        self._calc_warning_artist = None
    def _show_calc_warning(self, msg: str) -> None:
        self._clear_calc_artists()
        try:
            self._clear_residual_axis()
        except Exception:
            pass
        try:
            self._calc_warning_artist = self.ax.text(
                0.5, 0.5, msg,
                transform=self.ax.transAxes,
                ha="center", va="center",
                wrap=True
            )
        except Exception:
            pass
        try:
            self.canvas.draw_idle()
        except Exception:
            pass
    def _refresh_live_calculated_spectrum(self) -> None:
        """Recalculate the always-live modeled spectrum after manual parameter edits."""
        try:
            self._refresh_all_tied_parameter_values()
        except Exception:
            pass
        try:
            self._on_calculate_spectrum()
        except Exception:
            pass
    @staticmethod
    def _gaussian_kernel(x, sigma: float):
        return fit_models.gaussian_kernel(x, sigma)
    @staticmethod
    def _voigt_profile(x, x0: float, sigma: float, gamma: float):
        return fit_models.voigt_profile(x, x0, sigma, gamma)
    @staticmethod
    def _doniach_sunjic(x, x0: float, gamma: float, alpha: float, energy_scale: str = ""):
        return fit_models.doniach_sunjic(x, x0, gamma, alpha, energy_scale=energy_scale)
    def _on_calculate_spectrum(self) -> None:
        """Calculate and draw peak components + sum spectrum from current parameters."""
        import numpy as np

        # In live calculated-spectrum mode, keep any standalone/background-only artist
        # cleared so only the current BG/components/total are visible.
        try:
            self._clear_bg_artist()
        except Exception:
            pass

        key = self._get_checked_key()
        if key is None:
            self._show_calc_warning("No curve selected for fitting.")
            return
        pl = self._payload_by_key.get(key)
        if pl is None or getattr(pl, "x", None) is None or getattr(pl, "y", None) is None:
            self._show_calc_warning("Selected curve has no data.")
            return

        x_raw = np.asarray(pl.x, dtype=float)
        y_raw_all = np.asarray(pl.y, dtype=float)
        finite = np.isfinite(x_raw) & np.isfinite(y_raw_all)
        x_raw = x_raw[finite]
        y_raw_all = y_raw_all[finite]
        fit_range = self._current_fit_range() if hasattr(self, "_current_fit_range") else None
        if fit_range is not None:
            lo, hi = fit_range
            m = (x_raw >= float(lo)) & (x_raw <= float(hi))
            x_raw = x_raw[m]
            y_raw_all = y_raw_all[m]
        if x_raw.size < 5:
            self._show_calc_warning("Selected fit range is too short to calculate a spectrum.")
            return

        ascending = np.all(np.diff(x_raw) > 0)
        descending = np.all(np.diff(x_raw) < 0)
        if not (ascending or descending):
            self._show_calc_warning("Energy axis is not monotonic; cannot calculate spectrum reliably.")
            return

        x = x_raw.copy()
        if descending:
            x = x[::-1]

        dx = np.diff(x)
        if np.any(dx <= 0):
            self._show_calc_warning("Energy axis is not strictly monotonic; cannot calculate spectrum reliably.")
            return

        dx_med = float(np.median(dx))
        if dx_med <= 0:
            self._show_calc_warning("Energy step is invalid.")
            return
        rel = float(np.max(np.abs(dx - dx_med)) / dx_med)
        if rel > 0.01:
            xu = np.linspace(x.min(), x.max(), x.size)
        else:
            xu = x

        # Measured spectrum on the uniform grid xu (needed e.g. for Shirley BG)
        y_raw = y_raw_all.copy()
        if descending:
            y_raw = y_raw[::-1]
        if xu is x:
            y_data_u = y_raw
        else:
            y_data_u = np.interp(xu, x, y_raw)

        peaks = []
        for i, w in enumerate(getattr(self, "_peak_widgets", []), start=1):
            E = float(w["E"].value())
            H = float(w["H"].value())
            Lf = float(w["L"].value())
            Gf = float(w["G"].value())
            A = float(w["A"].value())
            # During/after fitting a parameter may legitimately sit exactly on a
            # lower bound (for example Height == 0).  Do not abort the whole
            # calculated-spectrum redraw in that case; instead keep the peak as a
            # zero (or numerically clipped) component so the rest of the fit stays
            # visible.
            H = max(0.0, H)
            if Lf <= 0 or Gf <= 0:
                self._show_calc_warning(f"Peak {i}: LFWHM and GFWHM must be > 0.")
                return
            c = w.get("color", None)
            peaks.append((E, H, Lf, Gf, A, c))

        if len(peaks) == 0:
            self._show_calc_warning("No peaks defined.")
            return

        self._clear_calc_artists()
        # Background (polynomial only for now; Shirley will be added next)
        bg_type = None
        key0 = self._get_checked_key()
        pl0 = self._payload_by_key.get(key0) if key0 is not None else None
        try:
            bg_type = self.cb_bg_type.currentText()
        except Exception:
            bg_type = "Shirley"

        bg_u = np.zeros_like(xu)
        if bg_type in ("constant", "linear", "parabolic"):
            try:
                b0 = float(self.sb_bg_b0.value())
                b1 = float(self.sb_bg_b1.value()) if bg_type in ("linear", "parabolic") else 0.0
                b2 = float(self.sb_bg_b2.value()) if bg_type == "parabolic" else 0.0
            except Exception:
                b0 = b1 = b2 = 0.0
            if (not getattr(self, "_bg_coeffs_touched", False)) and abs(b0) < 1e-15 and abs(b1) < 1e-15 and abs(b2) < 1e-15:
                try:
                    self._maybe_autoguess_bg(force=True)
                    b0 = float(self.sb_bg_b0.value())
                    b1 = float(self.sb_bg_b1.value()) if bg_type in ("linear", "parabolic") else 0.0
                    b2 = float(self.sb_bg_b2.value()) if bg_type == "parabolic" else 0.0
                except Exception:
                    pass
            bg_u = self._poly_background(xu, b0, b1, b2)
        elif bg_type == "Shirley":
            try:
                scale = str(getattr(pl0, "energy_scale", "")).lower() if pl0 is not None else ""
            except Exception:
                scale = ""
            alpha = float(self.sb_bg_alpha.value())
            bg_u = self._compute_shirley_background(xu, y_data_u, scale, alpha=alpha)

        try:
            self._last_calc_bg_curve = (np.asarray(xu, dtype=float).copy(), np.asarray(bg_u, dtype=float).copy(), str(bg_type))
        except Exception:
            self._last_calc_bg_curve = None

        # Start sum with background
        y_sum_u = bg_u.copy()

        # Draw current background as part of the live calculated spectrum view
        try:
            x_bg_plot = xu if not descending else xu[::-1]
            y_bg_plot = bg_u if not descending else bg_u[::-1]
            a_bg, = self.ax.plot(x_bg_plot, y_bg_plot, linestyle="--", linewidth=1.5, alpha=0.95, color=fit_plotting.BG_CURVE_COLOR, label="Background")
            self._calc_artists.append(a_bg)
        except Exception:
            pass

        component_arrays = []
        peak_labels = []
        peak_colors = []
        peak_color_custom = []
        for i, (E, H, Lf, Gf, A, c) in enumerate(peaks, start=1):
            gamma = max(1e-12, Lf / 2.0)
            sigma = max(1e-12, Gf / (2.0 * np.sqrt(2.0 * np.log(2.0))))

            if A <= 0.0:
                y_u = self._voigt_profile(xu, E, sigma, gamma)
            else:
                try:
                    scale = str(getattr(pl0, "energy_scale", "") or "") if pl0 is not None else ""
                except Exception:
                    scale = ""
                y_u = fit_models.broadened_doniach_sunjic_profile(
                    xu, E, gamma, A, sigma, energy_scale=scale
                )
            mmax = float(np.max(y_u)) if y_u.size else 0.0
            if mmax <= 0:
                # Keep redraw robust even for pathological/near-bound temporary
                # states during fitting; represent the component as a zero curve
                # instead of aborting the whole plot update.
                y_u = np.zeros_like(xu, dtype=float)
            else:
                y_u = (y_u / mmax) * H

            y_sum_u += y_u
            component_arrays.append(y_u)
            try:
                peak_label = str(self._peak_widgets[i - 1].get("label_edit").text()).strip()
            except Exception:
                peak_label = ""
            peak_labels.append(peak_label or f"Peak {i}")
            peak_colors.append(c if c is not None else fit_plotting.default_peak_color(i))
            try:
                peak_color_custom.append(bool(self._peak_widgets[i - 1].get("color_custom", False)))
            except Exception:
                peak_color_custom.append(False)

        # Resolve automatic/custom colors once for this redraw and mirror the
        # same result into the parameter-table color swatches.  This prevents
        # plot/table drift when the automatic allocator moves a component to
        # avoid a visible color collision.
        try:
            self._sync_peak_display_colors()
            peak_colors = [
                str(w.get("_display_color") or peak_colors[i])
                for i, w in enumerate(self._peak_widgets[:len(peak_colors)])
            ]
        except Exception:
            pass

        # Component presentation is independent of the fit model.  In Doublet
        # view each SO pair is replaced by its summed curve; standalone peaks
        # remain individual.
        try:
            display_specs = so_doublets.grouped_component_specs(
                component_arrays, peak_labels, peak_colors,
                self._capture_so_doublet_states(),
                grouped=self._doublet_view_enabled(), color_custom=peak_color_custom,
            )
        except Exception:
            display_specs = so_doublets.grouped_component_specs(
                component_arrays, peak_labels, peak_colors, [], grouped=False, color_custom=peak_color_custom
            )
        x_plot = xu if not descending else xu[::-1]
        for spec in display_specs:
            y_comp = spec["component"] if not descending else spec["component"][::-1]
            try:
                a, = self.ax.plot(
                    x_plot, y_comp, linewidth=1.2, alpha=0.9,
                    color=spec.get("color"), label=spec.get("label") or "Component"
                )
                self._calc_artists.append(a)
            except Exception:
                pass

        try:
            x_plot = xu if not descending else xu[::-1]
            y_plot = y_sum_u if not descending else y_sum_u[::-1]
            x_sum_plot, y_sum_plot_s = fit_plotting.smooth_curve_for_display(x_plot, y_plot)
            a_sum, = self.ax.plot(x_sum_plot, y_sum_plot_s, linewidth=2.2, color="red", zorder=5, antialiased=True, solid_joinstyle="round", solid_capstyle="round", label="Total fit")
            self._calc_artists.append(a_sum)
        except Exception:
            pass

        try:
            xlabel = getattr(pl, "xlabel", "Energy")
            ylabel = getattr(pl, "ylabel", "Height")
            self.ax.set_ylabel(ylabel)
            self._plot_residuals(xu, y_data_u, y_sum_u, descending=descending, xlabel=xlabel)
            self.ax.tick_params(axis="x", labelbottom=False)
            try:
                self.ax_res.set_xlim(self.ax.get_xlim())
            except Exception:
                pass
            try:
                self.ax.relim()
                self.ax.autoscale_view(scalex=False, scaley=True)
                fit_plotting.style_fit_axes(self.ax, self.ax_res)
            except Exception:
                pass
        except Exception:
            pass

        try:
            self._refresh_fit_range_artists()
        except Exception:
            pass
        try:
            self._refresh_fit_legend()
        except Exception:
            pass
        try:
            self.canvas.draw_idle()
        except Exception:
            pass
    def _clear_peak_markers(self) -> None:
        """Remove the vertical Energy/Height guess markers from the plot."""
        if hasattr(self, "_peak_marker_artists"):
            for a in list(self._peak_marker_artists):
                try:
                    a.remove()
                except Exception:
                    pass
        self._peak_marker_artists = []
    def _update_peak_color_button(self, w: Dict[str, Any]) -> None:
        """Keep the parameter-card swatch synchronized with the plotted color.

        ``color`` is the stored/user-selected base color.  Since 0.11.14 the
        automatic allocator may resolve a different ``_display_color`` so
        simultaneously visible components remain distinguishable.  The swatch
        must represent what the user actually sees on the plot, while the base
        color remains untouched for persistence/custom-color semantics.
        """
        btn = w.get("color_btn")
        if btn is None:
            return
        color = str(
            w.get("_display_color")
            or w.get("color")
            or fit_plotting.default_peak_color(int(btn.property("peak_index") or 1))
        )
        try:
            btn.setStyleSheet(f"QPushButton {{ background-color: {color}; border: 1px solid #555; }}")
        except Exception:
            pass
    def _choose_peak_color(self, peak_index: int) -> None:
        widgets = getattr(self, "_peak_widgets", []) or []
        if peak_index < 1 or peak_index > len(widgets):
            return
        w = widgets[peak_index - 1]
        current = QColor(str(w.get("color") or fit_plotting.default_peak_color(peak_index)))

        # On macOS the native QColorDialog can return focus to another top-level
        # application window when it closes.  The peak-fit dialog is deliberately
        # an independent top-level window, so use Qt's dialog there and then
        # explicitly restore this fit window to the foreground.
        options = QColorDialog.ColorDialogOption(0)
        if sys.platform == "darwin":
            options |= QColorDialog.ColorDialogOption.DontUseNativeDialog
        col = QColorDialog.getColor(
            current, self, f"Choose color for Peak {peak_index}", options
        )

        if sys.platform == "darwin":
            def _restore_fit_window_focus() -> None:
                try:
                    self.show()
                    self.raise_()
                    self.activateWindow()
                    self.setFocus(Qt.FocusReason.OtherFocusReason)
                except Exception:
                    pass
            QTimer.singleShot(0, _restore_fit_window_focus)
            QTimer.singleShot(80, _restore_fit_window_focus)

        if not col.isValid():
            return
        w["color"] = str(col.name())
        w["color_custom"] = True
        w["_display_color"] = str(col.name())
        self._update_peak_color_button(w)
        self._on_calculate_spectrum()
        # The calculated component is redrawn by _on_calculate_spectrum(), but
        # the draggable Energy/Height marker is a separate LineCollection.  Its
        # existing artist is recolored in place and this infrequent color-change
        # action is flushed immediately so Qt cannot leave the stale color on
        # screen until the next mouse/resize event.
        self._refresh_peak_markers()
        try:
            self.canvas.draw()
        except Exception:
            pass
