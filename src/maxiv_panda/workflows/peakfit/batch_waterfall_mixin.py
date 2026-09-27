from __future__ import annotations

import numpy as np
from matplotlib.ticker import AutoMinorLocator, ScalarFormatter

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QSizePolicy

from ...ui import PlotArea, PlotPayload

class BatchWaterfallMixin:
    """Extracted behavior for the batch Prepare workflow."""

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
        except Exception:
            pass
        self._update_waterfall_controls_width()


    def _update_waterfall_controls_width(self) -> None:
        """Keep waterfall controls centered and narrower than Plot A."""
        box = getattr(self, "waterfall_controls_box", None)
        plot = getattr(self, "plot_sequence", None)
        if box is None or plot is None:
            return
        try:
            width = int(max(520, min(860, plot.width() * 0.90)))
            box.setMaximumWidth(width)
        except Exception:
            pass


    def _on_waterfall_toggled(self, checked: bool) -> None:
        enabled = bool(checked)
        try:
            self.slider_waterfall.setEnabled(enabled)
        except Exception:
            pass
        try:
            self.sb_waterfall_value.setEnabled(enabled)
        except Exception:
            pass
        try:
            self.chk_waterfall_mono.setEnabled(enabled)
            if not enabled:
                self.chk_waterfall_mono.setChecked(False)
        except Exception:
            pass
        self._update_waterfall_color_button()
        self._update_prepare_plot_from_selected()


    def _on_waterfall_mono_toggled(self, checked: bool) -> None:
        self._update_waterfall_color_button()
        self._update_prepare_plot_from_selected()


    def _update_waterfall_color_button(self) -> None:
        btn = getattr(self, "btn_waterfall_color", None)
        if btn is None:
            return
        try:
            mono_enabled = bool(self.chk_waterfall.isChecked()) and bool(self.chk_waterfall_mono.isChecked())
        except Exception:
            mono_enabled = False
        try:
            btn.setEnabled(mono_enabled)
            btn.setStyleSheet(
                "QPushButton {"
                f" background-color: {self._waterfall_mono_color};"
                " border: 1px solid #555;"
                " border-radius: 2px;"
                " padding: 0px;"
                "}"
            )
        except Exception:
            pass


    def _choose_waterfall_mono_color(self) -> None:
        try:
            current = QColor(self._waterfall_mono_color)
            color = QColorDialog.getColor(current, self, "Choose waterfall curve color")
            if not color.isValid():
                return
            self._waterfall_mono_color = color.name()
        except Exception:
            return
        self._update_waterfall_color_button()
        self._update_prepare_plot_from_selected()


    def _waterfall_monochrome_enabled(self) -> bool:
        try:
            return bool(self.chk_waterfall.isChecked()) and bool(self.chk_waterfall_mono.isChecked())
        except Exception:
            return False


    def _on_waterfall_slider_changed(self, value: int) -> None:
        try:
            self.sb_waterfall_value.blockSignals(True)
            self.sb_waterfall_value.setValue(int(value))
        except Exception:
            pass
        finally:
            try:
                self.sb_waterfall_value.blockSignals(False)
            except Exception:
                pass
        self._update_prepare_plot_from_selected()


    def _on_waterfall_spin_changed(self, value: int) -> None:
        try:
            self.slider_waterfall.blockSignals(True)
            self.slider_waterfall.setValue(int(value))
        except Exception:
            pass
        finally:
            try:
                self.slider_waterfall.blockSignals(False)
            except Exception:
                pass
        self._update_prepare_plot_from_selected()


    def _waterfall_enabled(self) -> bool:
        try:
            return bool(self.chk_waterfall.isChecked()) and int(self.slider_waterfall.value()) > 0
        except Exception:
            return False


    def _apply_waterfall_offsets(self, payloads: list[PlotPayload]) -> list[PlotPayload]:
        """Return display-only payloads with uniform vertical offsets.

        Slider value 0 leaves spectra unchanged. At 100, neighboring curves are
        separated by one full global Y range, so their raw Y intervals no longer
        overlap except possibly at the boundary. The underlying effective spectra
        used later for fitting are not modified.
        """
        if not payloads or not self._waterfall_enabled():
            return payloads
        try:
            fraction = float(self.slider_waterfall.value()) / 100.0
        except Exception:
            fraction = 0.0
        if fraction <= 0.0:
            return payloads
        ymins: list[float] = []
        ymaxs: list[float] = []
        for p in payloads:
            try:
                y = np.asarray(p.y, dtype=float)
                if y.size:
                    ymins.append(float(np.nanmin(y)))
                    ymaxs.append(float(np.nanmax(y)))
            except Exception:
                pass
        if not ymins or not ymaxs:
            return payloads
        y_range = float(max(ymaxs) - min(ymins))
        if not np.isfinite(y_range) or y_range <= 0:
            return payloads
        step = fraction * y_range
        out: list[PlotPayload] = []
        for idx, p in enumerate(payloads):
            try:
                y = np.asarray(p.y, dtype=float) + idx * step
                out.append(PlotPayload(
                    title=p.title,
                    x=np.asarray(p.x, dtype=float),
                    y=y,
                    xlabel=getattr(p, "xlabel", "x"),
                    ylabel=getattr(p, "ylabel", "Intensity"),
                    energy_scale=getattr(p, "energy_scale", "Unknown"),
                ))
            except Exception:
                out.append(p)
        return out


    def _waterfall_color_list(self, count: int) -> list[str] | None:
        """Return a single-color list for waterfall display when requested."""
        if count <= 0 or not self._waterfall_monochrome_enabled():
            return None
        return [self._waterfall_mono_color for _ in range(count)]


    def _style_prepare_plot_area(self, plot: PlotArea) -> None:
        """Apply scientific Y formatting and the single-fit style grid."""
        try:
            ax = plot.ax
        except Exception:
            return
        major_kwargs = {"linewidth": 1.0, "alpha": 0.66, "color": "0.68"}
        minor_kwargs = {"linestyle": "--", "linewidth": 0.72, "alpha": 0.46, "color": "0.78"}
        try:
            ax.tick_params(axis="x", labelsize=9)
            ax.tick_params(axis="y", labelsize=9)
            ax.yaxis.get_offset_text().set_size(9)
            ax.xaxis.label.set_size(10)
            ax.yaxis.label.set_size(10)
            ax.title.set_size(10)
        except Exception:
            pass
        try:
            formatter = ScalarFormatter(useMathText=True)
            formatter.set_scientific(True)
            # Force scientific notation regardless of value magnitude, matching
            # the Run-tab monitor residual axis.
            formatter.set_powerlimits((0, 0))
            formatter.set_useOffset(False)
            ax.yaxis.set_major_formatter(formatter)
            ax.yaxis.get_offset_text().set_size(9)
        except Exception:
            pass
        try:
            ax.xaxis.set_minor_locator(AutoMinorLocator(5))
        except Exception:
            pass
        try:
            ax.yaxis.set_minor_locator(AutoMinorLocator(5))
        except Exception:
            pass
        try:
            ax.grid(True, which="major", axis="both", **major_kwargs)
            ax.grid(True, which="minor", axis="both", **minor_kwargs)
        except Exception:
            pass


    def _make_plot_area_expand(self, plot: PlotArea) -> None:
        try:
            plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            plot.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            plot.canvas.updateGeometry()
        except Exception:
            pass
        try:
            # Batch plots use explicit compact subplot margins.  PlotArea is
            # created with Matplotlib's constrained-layout engine, and calling
            # subplots_adjust() while that engine is active emits a warning and
            # ignores the requested margins.  Disable the engine locally before
            # applying the batch-specific geometry.
            try:
                plot.fig.set_layout_engine(None)
            except Exception:
                try:
                    plot.fig.set_constrained_layout(False)
                except Exception:
                    pass
            right = 0.925 if plot is getattr(self, "plot_sequence", None) else 0.985
            plot.fig.subplots_adjust(left=0.075, right=right, bottom=0.085, top=0.93)
        except Exception:
            pass


    def _compact_plot_margins(self, plot: PlotArea) -> None:
        try:
            # plot_many() restores constrained layout for ordinary PlotArea
            # rendering, so turn it off again before applying the compact batch
            # margins.  This avoids the constrained-layout/subplots_adjust
            # incompatibility warning on every redraw.
            try:
                plot.fig.set_layout_engine(None)
            except Exception:
                try:
                    plot.fig.set_constrained_layout(False)
                except Exception:
                    pass
            right = 0.925 if plot is getattr(self, "plot_sequence", None) else 0.985
            plot.fig.subplots_adjust(left=0.075, right=right, bottom=0.085, top=0.93)
            plot.canvas.draw_idle()
        except Exception:
            pass


