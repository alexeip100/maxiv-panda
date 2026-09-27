from __future__ import annotations

import numpy as np
from matplotlib.colors import to_rgba
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, ScalarFormatter


class LiveLinesView:
    """Lines-style cross-section view used by the Live Monitor.

    This intentionally mirrors the interaction model of Processed Data ->
    View: Lines, while keeping only the parts useful during acquisition:
    H/V cursors, side traces, symmetric thickness averaging and dragging.
    """

    def __init__(self, figure, canvas) -> None:
        self.figure = figure
        self.canvas = canvas
        self.x = np.array([], dtype=float)
        self.z = np.empty((0, 0), dtype=float)
        self.second_axis: np.ndarray | None = None
        self.second_axis_label = ""
        self.xlabel = "Energy [eV]"
        self.title = ""
        self.cmap = "terrain"
        self.flip_x = False
        self.h_thickness = 1
        self.v_thickness = 1
        self.row = 0
        self.col = 0
        self._drag_axis: str | None = None
        self.ax_map = None
        self.ax_right = None
        self.ax_bottom = None
        self.image = None
        self.colorbar = None
        self._cids = [
            canvas.mpl_connect("button_press_event", self._on_press),
            canvas.mpl_connect("motion_notify_event", self._on_motion),
            canvas.mpl_connect("button_release_event", self._on_release),
        ]

    @staticmethod
    def _odd(value: int) -> int:
        value = max(1, min(25, int(value)))
        return value if value % 2 else min(25, value + 1)

    def set_thickness(self, h: int, v: int) -> None:
        self.h_thickness = self._odd(h)
        self.v_thickness = self._odd(v)
        if self.image is not None:
            self._refresh_profiles()
            self.canvas.draw_idle()

    def set_cmap(self, cmap: str) -> None:
        self.cmap = str(cmap)
        if self.image is not None:
            self.image.set_cmap(self.cmap)
            self._style_labels()
            self.canvas.draw_idle()

    def set_flip_x(self, checked: bool) -> None:
        self.flip_x = bool(checked)
        self._apply_x_limits()
        self.canvas.draw_idle()

    def set_data(
        self,
        x,
        z,
        *,
        second_axis=None,
        second_axis_label: str = "",
        xlabel: str = "Energy [eV]",
        title: str = "",
        reset: bool = False,
    ) -> None:
        x = np.asarray(x, dtype=float).reshape(-1)
        z = np.asarray(z, dtype=float)
        if z.ndim == 1:
            z = z.reshape(1, -1)
        if z.ndim != 2 or x.size == 0 or z.shape[1] != x.size:
            return
        old_x = None
        old_y = None
        if self.x.size and self.z.size:
            try:
                old_x = float(self.x[min(self.col, self.x.size - 1)])
                old_y = self._row_coordinate(min(self.row, self.z.shape[0] - 1))
            except Exception:
                old_x = old_y = None
        self.x = x.copy()
        self.z = z.copy()
        self.second_axis = None if second_axis is None else np.asarray(second_axis, dtype=float).reshape(-1).copy()
        if self.second_axis is not None and self.second_axis.size != self.z.shape[0]:
            self.second_axis = None
        self.second_axis_label = str(second_axis_label or "").strip()
        self.xlabel = str(xlabel or "Energy [eV]")
        self.title = str(title or "")

        rows, cols = self.z.shape
        if reset or self.image is None:
            self.row = rows // 2
            self.col = cols // 2
        else:
            if old_x is not None:
                self.col = int(np.nanargmin(np.abs(self.x - old_x)))
            self.col = int(np.clip(self.col, 0, cols - 1))
            if old_y is not None:
                coords = self._row_coordinates()
                self.row = int(np.nanargmin(np.abs(coords - old_y)))
            self.row = int(np.clip(self.row, 0, rows - 1))
        self._build()

    def _has_physical_second_axis(self) -> bool:
        return bool(
            self.second_axis is not None
            and self.second_axis.size == self.z.shape[0]
            and self.second_axis_label
            and "iteration" not in self.second_axis_label.lower()
        )

    def _iteration_coordinates(self) -> np.ndarray:
        if (
            self.second_axis is not None
            and self.second_axis.size == self.z.shape[0]
            and "iteration" in self.second_axis_label.lower()
        ):
            return self.second_axis
        return np.arange(1, self.z.shape[0] + 1, dtype=float)

    def _row_coordinates(self) -> np.ndarray:
        # Cursor position memory follows the coordinate displayed on the map
        # itself.  Match Processed Data -> View: Lines: a genuine physical
        # second dimension (e.g. photon energy) belongs to the map's left
        # axis, while sequence iteration remains on the right trace.
        if self._has_physical_second_axis():
            return self.second_axis
        return self._iteration_coordinates()

    def _row_coordinate(self, row: int) -> float:
        return float(self._row_coordinates()[int(row)])

    @staticmethod
    def _tick_indices(rows: int) -> tuple[np.ndarray, np.ndarray]:
        if rows <= 12:
            step = 1
        elif rows <= 24:
            step = 2
        elif rows <= 60:
            step = 5
        elif rows <= 120:
            step = 10
        else:
            step = max(1, int(rows / 12))
        centers = np.arange(rows, dtype=float) + 0.5
        idx = np.arange(0, rows, step, dtype=int)
        return centers, idx

    def _build(self) -> None:
        if self.z.size == 0:
            return
        # Match Processed Data -> View: Lines: use a fixed GridSpec geometry
        # rather than constrained-layout, so the map and both traces do not
        # shift as tick labels change while acquisition grows.
        try:
            self.figure.set_layout_engine(None)
        except Exception:
            try:
                self.figure.set_constrained_layout(False)
            except Exception:
                pass
        self.figure.clear()
        map_left = 0.100
        gs = self.figure.add_gridspec(
            2, 2,
            width_ratios=(4.6, 1.35), height_ratios=(4.0, 1.25),
            left=map_left, right=0.925, bottom=0.09, top=0.94,
            wspace=0.045, hspace=0.065,
        )
        self.ax_map = self.figure.add_subplot(gs[0, 0])
        self.ax_right = self.figure.add_subplot(gs[0, 1])
        self.ax_bottom = self.figure.add_subplot(gs[1, 0], sharex=self.ax_map)
        ax_corner = self.figure.add_subplot(gs[1, 1])
        ax_corner.axis("off")

        rows, cols = self.z.shape
        xmin, xmax = float(self.x[0]), float(self.x[-1])
        self.image = self.ax_map.imshow(
            self.z, aspect="auto", origin="lower",
            extent=[xmin, xmax, 0.0, float(rows)], cmap=self.cmap,
        )
        self.ax_map.set_title(self.title)
        self.ax_map.tick_params(axis="x", labelbottom=False)
        self.ax_map.set_ylim(0.0, float(rows))

        self.ax_bottom.set_xlabel(self.xlabel)
        self.ax_bottom.set_ylabel("Intensity")
        self.ax_bottom.yaxis.set_label_coords(-0.075, 0.5, transform=self.ax_bottom.transAxes)
        self.ax_bottom.grid(True, linewidth=1.05, alpha=0.42)
        self.ax_right.set_xlabel("Intensity")
        self.ax_right.grid(True, linewidth=1.05, alpha=0.42)
        self.ax_right.set_ylim(0.0, float(rows))

        centers, tick_idx = self._tick_indices(rows)
        iterations = self._iteration_coordinates()
        if self._has_physical_second_axis():
            left_values = np.asarray(self.second_axis, dtype=float)
            left_label = self.second_axis_label
        else:
            left_values = iterations
            left_label = "Iteration"
        self.ax_map.set_yticks(centers[tick_idx])
        self.ax_map.set_yticklabels([self._format_value(left_values[i]) for i in tick_idx])
        self.ax_map.set_ylabel(left_label)
        self.ax_map.yaxis.set_label_coords(-0.075, 0.5, transform=self.ax_map.transAxes)
        self.ax_map.tick_params(axis="y", labelleft=True, labelright=False)

        self.ax_right.set_yticks(centers[tick_idx])
        self.ax_right.set_yticklabels([self._format_value(iterations[i]) for i in tick_idx])
        self.ax_right.yaxis.tick_right()
        self.ax_right.yaxis.set_label_position("right")
        self.ax_right.set_ylabel("Iteration")
        self.ax_right.tick_params(axis="y", labelleft=False, labelright=True)

        # Match Processed Data -> View: Lines exactly: the toolbar reports
        # physical BE/KE, physical Y (e.g. PhE) or Iteration, and intensity
        # from the nearest displayed map pixel.
        self._set_map_coordinate_formatter()
        try:
            self.image.get_cursor_data = lambda _event: None
        except Exception:
            pass

        x_pos = float(self.x[self.col])
        y_pos = float(self.row) + 0.5
        self.vline = self.ax_map.axvline(x_pos, linestyle="--", linewidth=1.05, zorder=3.6)
        self.hline = self.ax_map.axhline(y_pos, linestyle="--", linewidth=1.05, zorder=3.6)
        h_color, v_color = self.hline.get_color(), self.vline.get_color()

        self.vlabel = self.ax_map.text(
            x_pos, 0.985, self._x_caption(), transform=self.ax_map.get_xaxis_transform(),
            ha="center", va="top", fontsize=9, fontweight="bold", zorder=4.5, clip_on=True,
        )
        self.hlabel = self.ax_map.text(
            0.012, y_pos, self._y_caption(), transform=self.ax_map.get_yaxis_transform(),
            ha="left", va="center", fontsize=9, fontweight="bold", zorder=4.5, clip_on=True,
        )

        self.hband = Rectangle((min(xmin, xmax), 0), abs(xmax - xmin), 1,
                               facecolor=to_rgba(h_color, 0.32), edgecolor=h_color,
                               linewidth=1.8, zorder=3.0)
        self.vband = Rectangle((0, 0), 1, float(rows),
                               facecolor=to_rgba(v_color, 0.32), edgecolor=v_color,
                               linewidth=1.8, zorder=3.0)
        self.ax_map.add_patch(self.hband)
        self.ax_map.add_patch(self.vband)
        self.hband_right = self.ax_right.axhspan(0, 1, facecolor=to_rgba(h_color, 0.20),
                                                 edgecolor=h_color, linewidth=1.4, zorder=0.8)
        self.vband_bottom = self.ax_bottom.axvspan(0, 1, facecolor=to_rgba(v_color, 0.20),
                                                   edgecolor=v_color, linewidth=1.4, zorder=0.8)
        self.hline_right = self.ax_right.axhline(y_pos, linestyle="--", linewidth=1.0,
                                                 color=h_color, zorder=3.2)
        self.vline_bottom = self.ax_bottom.axvline(x_pos, linestyle="--", linewidth=1.0,
                                                   color=v_color, zorder=3.2)
        self.bottom_line = self.ax_bottom.plot(self.x, np.zeros(cols), linewidth=1.3, zorder=2.0)[0]
        self.right_line = self.ax_right.plot(np.zeros(rows), centers, linewidth=1.3, zorder=2.0)[0]

        try:
            fmt_right = ScalarFormatter(useMathText=True)
            fmt_right.set_scientific(True)
            fmt_right.set_powerlimits((0, 0))
            self.ax_right.xaxis.set_major_formatter(fmt_right)
            self.ax_right.ticklabel_format(axis="x", style="sci", scilimits=(0, 0), useMathText=True)
        except Exception:
            pass
        self.bottom_scale_text = self.ax_bottom.text(
            0.015, 0.94, "", transform=self.ax_bottom.transAxes,
            ha="left", va="top", clip_on=False,
        )
        self._refresh_profiles()
        self._apply_x_limits()
        self._style_labels()
        self.canvas.draw_idle()

    def _format_value(self, value: float) -> str:
        value = float(value)
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.4g}"

    def _x_caption(self) -> str:
        value = float(self.x[self.col])
        label = self.xlabel.lower()
        quantity = "KE" if "kinetic" in label else ("BE" if "binding" in label else "X")
        diffs = np.abs(np.diff(self.x))
        diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        if diffs.size:
            spacing = float(np.nanmedian(diffs))
            decimals = max(0, min(5, int(np.ceil(-np.log10(spacing))) + 1))
            number = f"{value:.{decimals}f}"
        else:
            number = self._format_value(value)
        unit = " eV" if "ev" in label else ""
        return f"{quantity} = {number}{unit}"

    @staticmethod
    def _cursor_number(value: float, spacing: float | None = None) -> str:
        try:
            value = float(value)
            if spacing is not None and np.isfinite(spacing) and spacing > 0:
                decimals = max(0, min(5, int(np.ceil(-np.log10(spacing))) + 1))
                return f"{value:.{decimals}f}"
            return str(int(round(value))) if abs(value - round(value)) < 1e-9 else f"{value:g}"
        except Exception:
            return str(value)

    def _y_caption(self) -> str:
        if self._has_physical_second_axis():
            values = np.asarray(self.second_axis, dtype=float)
            value = float(values[self.row])
            diffs = np.abs(np.diff(values))
            diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
            spacing = float(np.nanmedian(diffs)) if diffs.size else None
            number = self._cursor_number(value, spacing)
            low = self.second_axis_label.lower()
            if "photon" in low and "energy" in low:
                return f"PhE = {number} eV"
            return f"{self.second_axis_label} = {number}"
        value = float(self._iteration_coordinates()[self.row])
        return f"Iteration = {self._format_value(value)}"

    def _set_map_coordinate_formatter(self) -> None:
        rows = int(self.z.shape[0])
        x_arr = np.asarray(self.x, dtype=float).reshape(-1)
        z_arr = np.asarray(self.z, dtype=float)
        iterations = self._iteration_coordinates()
        sec = np.asarray(self.second_axis, dtype=float).reshape(-1) if self._has_physical_second_axis() else None
        sec_label = str(self.second_axis_label or "")
        sec_low = sec_label.lower()
        label_low = str(self.xlabel or "").lower()
        x_name = "KE" if "kinetic" in label_low else ("BE" if "binding" in label_low else "X")
        x_unit = " eV" if "ev" in label_low else ""

        def _fmt(x, y):
            try:
                xv = float(x)
                x_value = f"{xv:.1f}" if x_name in {"BE", "KE"} else self._format_value(xv)
                x_text = f"{x_name} = {x_value}{x_unit}"
            except Exception:
                x_text = f"{x_name} = {x}"
            try:
                row = int(np.clip(np.floor(float(y)), 0, rows - 1))
                if sec is not None and sec.size == rows:
                    if "photon" in sec_low and "energy" in sec_low:
                        y_text = f"PhE = {float(sec[row]):.1f} eV"
                    elif "iteration" in sec_low:
                        y_text = f"Iteration = {self._format_value(sec[row])}"
                    else:
                        y_text = f"{sec_label} = {self._format_value(sec[row])}"
                else:
                    y_text = f"Iteration = {self._format_value(iterations[row])}"
            except Exception:
                row = None
                y_text = f"Y = {y}"
            intensity_text = ""
            if row is not None and z_arr.size:
                try:
                    col = int(np.nanargmin(np.abs(x_arr - float(x))))
                    if 0 <= row < z_arr.shape[0] and 0 <= col < z_arr.shape[1]:
                        intensity = float(z_arr[row, col])
                        if np.isfinite(intensity):
                            intensity_text = f"Intensity = {intensity:.4e}"
                except Exception:
                    pass
            return f"{x_text:<14}  {y_text:<16}  {intensity_text}"

        self.ax_map.format_coord = _fmt

    def _style_labels(self) -> None:
        if self.image is None:
            return
        for artist, row, col in (
            (self.vlabel, max(0, self.z.shape[0] - 1), self.col),
            (self.hlabel, self.row, self.z.shape[1] - 1 if self.flip_x else 0),
        ):
            try:
                rgba = self.image.get_cmap()(self.image.norm(float(self.z[row, col])))
                lum = 0.2126 * rgba[0] + 0.7152 * rgba[1] + 0.0722 * rgba[2]
                fg, bg = ("black", "white") if lum >= 0.56 else ("white", "black")
                artist.set_color(fg)
                artist.set_bbox(dict(boxstyle="round,pad=0.24", facecolor=bg, edgecolor=fg,
                                     linewidth=0.65, alpha=0.78))
            except Exception:
                pass
        self._keep_labels_inside()

    def _keep_labels_inside(self) -> None:
        try:
            xp = self.ax_map.transData.transform((float(self.x[self.col]), 0))[0]
            frac = (xp - self.ax_map.bbox.x0) / max(self.ax_map.bbox.width, 1)
            self.vlabel.set_ha("left" if frac < 0.2 else ("right" if frac > 0.8 else "center"))
        except Exception:
            pass
        try:
            yp = self.ax_map.transData.transform((0, self.row + 0.5))[1]
            frac = (yp - self.ax_map.bbox.y0) / max(self.ax_map.bbox.height, 1)
            self.hlabel.set_va("bottom" if frac < 0.08 else ("top" if frac > 0.92 else "center"))
        except Exception:
            pass

    def _indices(self, center: int, requested: int, total: int) -> np.ndarray:
        half_req = (self._odd(requested) - 1) // 2
        half = min(half_req, int(center), int(total) - 1 - int(center))
        return np.arange(int(center) - half, int(center) + half + 1, dtype=int)

    def _column_span(self, indices: np.ndarray) -> tuple[float, float]:
        cols = self.z.shape[1]
        xmin, xmax = float(self.x[0]), float(self.x[-1])
        step = (xmax - xmin) / float(max(cols, 1))
        lo = xmin + int(indices.min()) * step
        hi = xmin + (int(indices.max()) + 1) * step
        return min(lo, hi), max(lo, hi)

    @staticmethod
    def _row_span(indices: np.ndarray) -> tuple[float, float]:
        return float(indices.min()), float(indices.max() + 1)

    def _set_bottom_scale(self, values) -> None:
        vals = np.asarray(values, dtype=float)
        finite = np.abs(vals[np.isfinite(vals)])
        vmax = float(np.nanmax(finite)) if finite.size else 0.0
        exponent = int(np.floor(np.log10(vmax))) if vmax > 0 else 0
        scale = 10.0 ** exponent if exponent else 1.0
        self.ax_bottom.yaxis.set_major_formatter(
            FuncFormatter(lambda value, _pos, _s=scale: f"{value / _s:g}")
        )
        self.bottom_scale_text.set_text(rf"$\times 10^{{{exponent}}}$")

    def _refresh_profiles(self) -> None:
        if self.z.size == 0:
            return
        rows, cols = self.z.shape
        self.row = int(np.clip(self.row, 0, rows - 1))
        self.col = int(np.clip(self.col, 0, cols - 1))
        hi = self._indices(self.row, self.h_thickness, rows)
        vi = self._indices(self.col, self.v_thickness, cols)
        bottom = np.nanmean(self.z[hi, :], axis=0)
        right = np.nanmean(self.z[:, vi], axis=1)
        self.bottom_line.set_data(self.x, bottom)
        self.right_line.set_data(right, np.arange(rows, dtype=float) + 0.5)
        self._set_bottom_scale(bottom)
        self.ax_bottom.relim(); self.ax_bottom.autoscale_view(scalex=False, scaley=True)
        self.ax_right.relim(); self.ax_right.autoscale_view(scalex=True, scaley=False)
        self.ax_right.set_ylim(0, float(rows))

        hy0, hy1 = self._row_span(hi)
        vx0, vx1 = self._column_span(vi)
        xmin, xmax = float(self.x[0]), float(self.x[-1])
        self.hband.set_x(min(xmin, xmax)); self.hband.set_width(abs(xmax - xmin))
        self.hband.set_y(hy0); self.hband.set_height(hy1 - hy0)
        try:
            self.hband_right.set_y(hy0); self.hband_right.set_height(hy1 - hy0)
        except Exception:
            pass
        self.vband.set_x(vx0); self.vband.set_width(vx1 - vx0); self.vband.set_height(float(rows))
        try:
            self.vband_bottom.set_x(vx0); self.vband_bottom.set_width(vx1 - vx0)
        except Exception:
            pass
        show_h = self.h_thickness > 1
        show_v = self.v_thickness > 1
        self.hband.set_visible(show_h); self.hband_right.set_visible(show_h)
        self.vband.set_visible(show_v); self.vband_bottom.set_visible(show_v)
        self._move_artists()

    def _move_artists(self) -> None:
        x = float(self.x[self.col]); y = float(self.row) + 0.5
        self.vline.set_xdata([x, x]); self.vline_bottom.set_xdata([x, x])
        self.hline.set_ydata([y, y]); self.hline_right.set_ydata([y, y])
        self.vlabel.set_x(x); self.vlabel.set_text(self._x_caption())
        self.hlabel.set_y(y); self.hlabel.set_text(self._y_caption())
        self._style_labels()

    def _apply_x_limits(self) -> None:
        if self.x.size == 0 or self.ax_map is None:
            return
        lo, hi = float(np.nanmin(self.x)), float(np.nanmax(self.x))
        if self.flip_x:
            self.ax_map.set_xlim(hi, lo); self.ax_bottom.set_xlim(hi, lo)
        else:
            self.ax_map.set_xlim(lo, hi); self.ax_bottom.set_xlim(lo, hi)
        self._keep_labels_inside()

    def _set_col(self, idx: int, *, redraw: bool = True) -> None:
        idx = int(np.clip(idx, 0, self.z.shape[1] - 1))
        if idx == self.col:
            return
        self.col = idx
        self._refresh_profiles()
        if redraw:
            self.canvas.draw_idle()

    def _set_row(self, idx: int, *, redraw: bool = True) -> None:
        idx = int(np.clip(idx, 0, self.z.shape[0] - 1))
        if idx == self.row:
            return
        self.row = idx
        self._refresh_profiles()
        if redraw:
            self.canvas.draw_idle()

    def _on_press(self, event) -> None:
        button = getattr(getattr(event, "button", None), "value", getattr(event, "button", None))
        if button not in (None, 1):
            return
        if self.ax_map is None or event.x is None or event.y is None:
            return
        try:
            if event.inaxes is self.ax_bottom and event.xdata is not None:
                px = self.ax_bottom.transData.transform((float(self.x[self.col]), 0))[0]
                if abs(float(event.x) - float(px)) <= 8:
                    self._drag_axis = "x_bottom"
                return
            if event.inaxes is self.ax_right and event.ydata is not None:
                py = self.ax_right.transData.transform((0, float(self.row) + 0.5))[1]
                if abs(float(event.y) - float(py)) <= 8:
                    self._drag_axis = "y_right"
                return
            if event.inaxes is not self.ax_map:
                return
            vx = self.ax_map.transData.transform((float(self.x[self.col]), 0))[0]
            hy = self.ax_map.transData.transform((0, float(self.row) + 0.5))[1]
            dv, dh = abs(float(event.x) - vx), abs(float(event.y) - hy)
            if dv <= 10 and dh <= 10:
                self._drag_axis = "both"
            elif dv <= 8 or dh <= 8:
                self._drag_axis = "x" if dv <= dh else "y"
        except Exception:
            self._drag_axis = None

    def _on_motion(self, event) -> None:
        drag = self._drag_axis
        if not drag:
            return
        if drag == "x_bottom":
            if event.inaxes is self.ax_bottom and event.xdata is not None:
                self._set_col(int(np.nanargmin(np.abs(self.x - float(event.xdata)))))
            return
        if drag == "y_right":
            if event.inaxes is self.ax_right and event.ydata is not None:
                self._set_row(int(np.clip(np.floor(float(event.ydata)), 0, self.z.shape[0] - 1)))
            return
        if event.inaxes is not self.ax_map:
            return
        if drag in ("x", "both") and event.xdata is not None:
            self._set_col(int(np.nanargmin(np.abs(self.x - float(event.xdata)))), redraw=(drag != "both"))
        if drag in ("y", "both") and event.ydata is not None:
            self._set_row(int(np.clip(np.floor(float(event.ydata)), 0, self.z.shape[0] - 1)), redraw=True)
        elif drag == "both":
            self.canvas.draw_idle()

    def _on_release(self, _event) -> None:
        self._drag_axis = None
