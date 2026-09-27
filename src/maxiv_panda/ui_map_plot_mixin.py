from __future__ import annotations

"""Matplotlib rendering and mouse interaction for Processed Data 2D maps.

This mixin deliberately owns only map-specific plot behavior.  The generic
PlotArea remains in :mod:`ui`, while Simple/Lines/ROI rendering, ROI controls
and normalization-band interaction live here so the three map views share one
implementation surface.
"""

from typing import Any

import numpy as np
from matplotlib.ticker import ScalarFormatter, FuncFormatter
from matplotlib.colors import to_rgba


class MapPlotMixin:
    def _stabilize_map_toolbar_coordinate_font(self) -> None:
        """Use a fixed-width font for the Matplotlib MAP coordinate readout.

        ``format_coord`` already pads its fields to fixed character widths.
        On macOS the default Qt toolbar font is proportional, so different
        digits/symbols can still have different pixel widths and make later
        fields move slightly.  A fixed-width font makes that padding truly
        stable while a map is displayed.
        """
        try:
            label = getattr(getattr(self, "toolbar", None), "locLabel", None)
            if label is None:
                return
            if getattr(self, "_map_toolbar_default_font", None) is None:
                self._map_toolbar_default_font = label.font()
            if getattr(self, "_map_toolbar_default_alignment", None) is None:
                self._map_toolbar_default_alignment = label.alignment()
            from PyQt6.QtGui import QFontDatabase
            fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            default = self._map_toolbar_default_font
            try:
                if default.pointSizeF() > 0:
                    fixed.setPointSizeF(default.pointSizeF())
            except Exception:
                pass
            label.setFont(fixed)
            # Anchor the compact three-field MAP readout immediately after the
            # toolbar buttons instead of right-aligning it at the far edge.
            # This keeps the Intensity field inside the plot/toolbar area even
            # in narrower windows.
            try:
                from PyQt6.QtCore import Qt
                label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                label.setContentsMargins(14, 0, 0, 0)
            except Exception:
                pass
        except Exception:
            pass

    def _restore_toolbar_coordinate_font(self) -> None:
        """Restore the ordinary toolbar font after leaving MAP rendering."""
        try:
            label = getattr(getattr(self, "toolbar", None), "locLabel", None)
            font = getattr(self, "_map_toolbar_default_font", None)
            if label is not None and font is not None:
                label.setFont(font)
                alignment = getattr(self, "_map_toolbar_default_alignment", None)
                if alignment is not None:
                    label.setAlignment(alignment)
        except Exception:
            pass

    @staticmethod
    def _map_lines_memory_key(title: str, xlabel: str) -> tuple[str, str]:
        """Stable identity used to remember Lines cursor positions per map.

        Display-only binning appends `` — binned by N`` to a map title.  Strip
        that suffix so changing Bin size preserves the same physical H/V cursor
        positions instead of treating the binned rendering as a new map.
        """
        import re
        stable_title = re.sub(r"\s+—\s+binned by\s+\d+\s*$", "", str(title or ""))
        return (stable_title, str(xlabel or ""))

    def _remember_map_lines_state(self, state=None) -> None:
        """Persist current H/V Lines positions outside transient plot artists."""
        state = state if state is not None else getattr(self, "_map_cross_state", None)
        if not state:
            return
        try:
            x = np.asarray(state.get("x"), dtype=float).reshape(-1)
            y = np.asarray(state.get("y_labels"), dtype=float).reshape(-1)
            cols = int(state.get("cols", len(x)))
            rows = int(state.get("rows", len(y)))
            if cols <= 0 or rows <= 0 or x.size == 0 or y.size == 0:
                return
            vpos = float(state.get("animation_v_position", state.get("col", 0)))
            hpos = float(state.get("animation_h_position", state.get("row", 0)))
            vpos = float(np.clip(vpos, 0.0, cols - 1))
            hpos = float(np.clip(hpos, 0.0, rows - 1))

            def _interp(values, pos):
                lo = int(np.floor(pos))
                hi = int(np.ceil(pos))
                alpha = float(pos - lo) if hi != lo else 0.0
                lo = max(0, min(len(values) - 1, lo))
                hi = max(0, min(len(values) - 1, hi))
                return float(values[lo]) * (1.0 - alpha) + float(values[hi]) * alpha

            memory = getattr(self, "_map_lines_position_memory", None)
            if not isinstance(memory, dict):
                memory = {}
                self._map_lines_position_memory = memory
            key = self._map_lines_memory_key(state.get("title", ""), state.get("xlabel", ""))
            memory[key] = {
                "x": _interp(x, vpos),
                "y": _interp(y, hpos),
            }
        except Exception:
            return

    @staticmethod
    def _map_secondary_axis(image, rows: int):
        """Return a genuine physical second map dimension, not iteration."""
        try:
            sec = image[6] if len(image) >= 7 else None
            label = str(image[7] or "") if len(image) >= 8 else ""
            if (
                sec is not None
                and len(sec) == rows
                and label
                and "iteration" not in label.strip().lower()
            ):
                return np.asarray(sec, dtype=float), label
        except Exception:
            pass
        return None, ""

    @staticmethod
    def _map_tick_indices(rows: int):
        """Readable row-center ticks shared by Simple, Lines and ROI views."""
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

    @staticmethod
    def _format_map_axis_value(value) -> str:
        value = float(value)
        return str(int(round(value))) if abs(value - round(value)) < 1e-9 else f"{value:g}"

    def _set_map_coordinate_formatter(
        self, axes, x_values, rows: int, xlabel: str, iteration_labels,
        secondary_y=None, secondary_label: str = "", z_values=None,
    ) -> None:
        """Show physical MAP coordinates in the Matplotlib toolbar.

        Matplotlib's default formatter reports the internal image-row coordinate
        (0..N) and, with twinned axes, can even report coordinates from the wrong
        axes.  Maps use row coordinates only internally, so translate Y back to
        the physical second dimension (e.g. photon energy) or to iteration.
        """
        self._stabilize_map_toolbar_coordinate_font()
        try:
            import numpy as _np
            x_arr = _np.asarray(x_values, dtype=float).reshape(-1)
            z_arr = None if z_values is None else _np.asarray(z_values, dtype=float)
            if z_arr is not None:
                if z_arr.ndim == 1:
                    z_arr = z_arr.reshape(1, -1)
                elif z_arr.ndim > 2:
                    z_arr = z_arr.reshape(z_arr.shape[0], -1)
            sec = None if secondary_y is None else _np.asarray(secondary_y, dtype=float).reshape(-1)
            it = list(iteration_labels) if iteration_labels is not None else list(range(1, int(rows) + 1))
            label_low = str(xlabel or "").lower()
            x_name = "KE" if "kinetic" in label_low else ("BE" if "binding" in label_low else "X")
            x_unit = " eV" if "ev" in label_low else ""
            sec_label = str(secondary_label or "")
            sec_low = sec_label.lower()

            def _fmt(x, y):
                try:
                    xv = float(x)
                    # Binding-energy cursor readout is intentionally concise: the
                    # raw mouse coordinate has far more precision than is useful
                    # for an interactive PES map.
                    # Keep a fixed decimal place for physical energy axes so
                    # values such as 458.1 -> 458.0 retain exactly the same
                    # character geometry in the toolbar readout.
                    if x_name in {"BE", "KE"}:
                        x_value = f"{xv:.1f}"
                    else:
                        x_value = self._format_map_axis_value(xv)
                    x_text = f"{x_name} = {x_value}{x_unit}"
                except Exception:
                    x_text = f"{x_name} = {x}"
                try:
                    row = int(_np.clip(_np.floor(float(y)), 0, int(rows) - 1))
                    if sec is not None and sec.size == int(rows):
                        value = self._format_map_axis_value(sec[row])
                        if "photon" in sec_low and "energy" in sec_low:
                            # Fixed one-decimal formatting prevents the live
                            # coordinate string from changing width at integer
                            # photon-energy values.
                            y_text = f"PhE = {float(sec[row]):.1f} eV"
                        elif "iteration" in sec_low:
                            y_text = f"Iteration = {value}"
                        else:
                            y_text = f"{sec_label} = {value}"
                    else:
                        try:
                            value = self._format_map_axis_value(it[row])
                        except Exception:
                            value = str(row + 1)
                        y_text = f"Iteration = {value}"
                except Exception:
                    row = None
                    y_text = f"Y = {y}"
                intensity_text = ""
                if z_arr is not None and row is not None and z_arr.size:
                    try:
                        col = int(_np.nanargmin(_np.abs(x_arr - float(x))))
                        if 0 <= row < z_arr.shape[0] and 0 <= col < z_arr.shape[1]:
                            intensity = float(z_arr[row, col])
                            if _np.isfinite(intensity):
                                # Scientific notation with a fixed mantissa
                                # width keeps every significant digit in a
                                # stable screen position while the cursor moves.
                                intensity_text = f", Intensity = {intensity:.4e}"
                    except Exception:
                        pass
                # Keep the starting positions of the three coordinate fields
                # stable in the Matplotlib status bar.  Without padding, the
                # Y and intensity fields visibly jump as the preceding numeric
                # strings change length while the mouse moves.
                # Compact fixed-width fields keep the three readouts stable
                # without wasting toolbar width.  The largest normal BE/KE and
                # PhE/Iteration labels fit comfortably in these columns.
                x_field = f"{x_text:<14}"
                y_field = f"{y_text:<16}"
                intensity_field = intensity_text[2:] if intensity_text.startswith(", ") else intensity_text
                return f"{x_field}  {y_field}  {intensity_field}"

            if not isinstance(axes, (list, tuple, set)):
                axes = [axes]
            for ax in axes:
                if ax is not None:
                    ax.format_coord = _fmt
        except Exception:
            pass

    @staticmethod
    def _disable_map_artist_cursor_data(image_artist) -> None:
        """Suppress Matplotlib's separate ``[z]`` toolbar suffix for maps.

        MAP intensity is included explicitly by :meth:`_set_map_coordinate_formatter`
        so all map modes use one consistent readout.  The backend-generated
        image suffix was absent in Simple view and could be vertically clipped
        in the Qt toolbar in Lines/ROI/ResPES.
        """
        try:
            image_artist.get_cursor_data = lambda _event: None
        except Exception:
            pass

    @staticmethod
    def _has_meaningful_secondary_y(secondary_y, secondary_label: str, rows: int) -> bool:
        """Return True when a genuine alternative to iteration is available."""
        try:
            if secondary_y is None or len(secondary_y) != int(rows):
                return False
        except Exception:
            return False
        label = str(secondary_label or "").strip().lower()
        return bool(label) and "iteration" not in label

    @staticmethod
    def _right_y_display_label(label: str) -> str:
        """Compact display label for the optional physical right-trace axis."""
        text = str(label or "").strip()
        low = text.lower()
        if "photon" in low and "energy" in low:
            unit = " [eV]" if "ev" in low else ""
            return f"PhE{unit}"
        return text or "Y"

    def _apply_map_right_trace_y_axis(self, state, mode=None, *, redraw=False) -> None:
        """Apply Iteration/physical-Y tick labels to the Lines/ROI right trace."""
        if not state:
            return
        rows = int(state.get("rows", 0))
        ax = state.get("ax_right")
        if ax is None or rows <= 0:
            return
        secondary = state.get("secondary_y")
        secondary_label = str(state.get("secondary_ylabel") or "")
        has_secondary = self._has_meaningful_secondary_y(secondary, secondary_label, rows)
        requested = str(mode or getattr(self, "_map_right_y_mode", "iteration")).lower()
        use_secondary = bool(has_secondary and requested == "secondary")
        actual_mode = "secondary" if use_secondary else "iteration"
        state["right_y_mode"] = actual_mode
        self._map_right_y_mode = actual_mode

        centers, tick_idx = self._map_tick_indices(rows)
        ax.set_yticks(centers[tick_idx])
        if use_secondary:
            values = np.asarray(secondary, dtype=float).reshape(-1)
            labels = [self._format_map_axis_value(values[i]) for i in tick_idx]
            ylabel = self._right_y_display_label(secondary_label)
        else:
            values = list(state.get("y_labels", range(1, rows + 1)))
            labels = []
            for i in tick_idx:
                try:
                    labels.append(self._format_map_axis_value(values[i]))
                except Exception:
                    labels.append(str(i + 1))
            ylabel = "Iteration"
        ax.set_yticklabels(labels)
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")
        ax.set_ylabel(ylabel)
        ax.tick_params(axis="y", labelleft=False, labelright=True)

        # Keep toolbar coordinates consistent with the currently displayed
        # right-hand Y representation.
        def _fmt_right(x, y):
            try:
                row = int(np.clip(np.floor(float(y)), 0, rows - 1))
                if use_secondary:
                    val = self._format_map_axis_value(np.asarray(secondary, dtype=float)[row])
                    ytxt = f"{self._right_y_display_label(secondary_label).replace(' [eV]', '')} = {val}"
                    if "ev" in secondary_label.lower():
                        ytxt += " eV"
                else:
                    try:
                        val = self._format_map_axis_value(state.get("y_labels", [])[row])
                    except Exception:
                        val = str(row + 1)
                    ytxt = f"Iteration = {val}"
                return f"Intensity = {float(x):.5g}, {ytxt}"
            except Exception:
                return f"Intensity = {x}, Y = {y}"
        ax.format_coord = _fmt_right

        if redraw:
            self.canvas.draw_idle()

    def _event_hits_right_y_axis(self, event, ax) -> bool:
        if ax is None or event is None or event.x is None or event.y is None:
            return False
        try:
            if event.inaxes is ax and abs(float(event.x) - float(ax.bbox.x1)) <= 14.0:
                return True
            renderer = self.canvas.get_renderer()
            artists = [ax.yaxis.label] + list(ax.get_yticklabels())
            for artist in artists:
                if artist.get_visible():
                    bbox = artist.get_window_extent(renderer=renderer).expanded(1.25, 1.35)
                    if bbox.contains(float(event.x), float(event.y)):
                        return True
        except Exception:
            return False
        return False

    def _create_map_qt_overlay_button(self, text: str, rect, tooltip: str = ""):
        """Create a native Qt push button over the Matplotlib canvas.

        Matplotlib's ``widgets.Button`` can imitate a Qt button, but its text,
        border and platform rendering can never be pixel-identical to native
        controls.  MAP corner actions therefore use a real ``QPushButton``
        parented to the canvas.  The supplied rectangle is in figure-fraction
        coordinates and is re-applied after every draw so resizing remains
        correct.
        """
        try:
            from PyQt6.QtWidgets import QPushButton
        except Exception:
            return None, None

        button = QPushButton(str(text), self.canvas)
        if tooltip:
            button.setToolTip(str(tooltip))

        x0, y0, width, height = [float(v) for v in rect]

        def _position(_event=None):
            try:
                cw = max(1, int(self.canvas.width()))
                ch = max(1, int(self.canvas.height()))
                x = int(round(x0 * cw))
                y = int(round((1.0 - (y0 + height)) * ch))
                w = max(1, int(round(width * cw)))
                h = max(1, int(round(height * ch)))
                button.setGeometry(x, y, w, h)
                button.raise_()
            except Exception:
                pass

        _position()
        button.show()
        cid = self.canvas.mpl_connect("draw_event", _position)
        return button, cid



    def _create_map_qt_overlay_checkbox(self, text: str, rect, tooltip: str = "", checked: bool = False):
        """Create a native Qt checkbox over the Matplotlib canvas."""
        try:
            from PyQt6.QtWidgets import QCheckBox
        except Exception:
            return None, None

        checkbox = QCheckBox(str(text), self.canvas)
        checkbox.setChecked(bool(checked))
        # This overlay sits on the deliberately light Matplotlib canvas even
        # when the surrounding Qt application uses the Dark theme.  Keep its
        # label readable against that light background, including disabled
        # states such as the Lines-view Auto scale control.
        checkbox.setStyleSheet(
            "QCheckBox { color: #202020; spacing: 5px; } "
            "QCheckBox:disabled { color: #606060; }"
        )
        if tooltip:
            checkbox.setToolTip(str(tooltip))

        x0, y0, width, height = [float(v) for v in rect]

        def _position(_event=None):
            try:
                cw = max(1, int(self.canvas.width()))
                ch = max(1, int(self.canvas.height()))
                x = int(round(x0 * cw))
                y = int(round((1.0 - (y0 + height)) * ch))
                w = max(1, int(round(width * cw)))
                h = max(1, int(round(height * ch)))
                checkbox.setGeometry(x, y, w, h)
                checkbox.raise_()
            except Exception:
                pass

        _position()
        checkbox.show()
        cid = self.canvas.mpl_connect("draw_event", _position)
        return checkbox, cid

    def _create_map_qt_overlay_combo(self, items, rect, tooltip: str = ""):
        """Create a native Qt combo box over the Matplotlib canvas."""
        try:
            from PyQt6.QtWidgets import QComboBox
        except Exception:
            return None, None
        combo = QComboBox(self.canvas)
        combo.addItems([str(v) for v in items])
        if tooltip:
            combo.setToolTip(str(tooltip))
        x0, y0, width, height = [float(v) for v in rect]

        def _position(_event=None):
            try:
                cw = max(1, int(self.canvas.width()))
                ch = max(1, int(self.canvas.height()))
                x = int(round(x0 * cw))
                y = int(round((1.0 - (y0 + height)) * ch))
                w = max(1, int(round(width * cw)))
                h = max(1, int(round(height * ch)))
                combo.setGeometry(x, y, w, h)
                combo.raise_()
            except Exception:
                pass

        _position()
        combo.show()
        cid = self.canvas.mpl_connect("draw_event", _position)
        return combo, cid

    def _create_map_qt_overlay_label(self, text: str, rect, tooltip: str = ""):
        """Create a native Qt label over the Matplotlib canvas."""
        try:
            from PyQt6.QtWidgets import QLabel
            from PyQt6.QtCore import Qt
        except Exception:
            return None, None
        label = QLabel(str(text), self.canvas)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if tooltip:
            label.setToolTip(str(tooltip))
        x0, y0, width, height = [float(v) for v in rect]

        def _position(_event=None):
            try:
                cw = max(1, int(self.canvas.width()))
                ch = max(1, int(self.canvas.height()))
                x = int(round(x0 * cw))
                y = int(round((1.0 - (y0 + height)) * ch))
                w = max(1, int(round(width * cw)))
                h = max(1, int(round(height * ch)))
                label.setGeometry(x, y, w, h)
                label.raise_()
            except Exception:
                pass

        _position()
        label.show()
        cid = self.canvas.mpl_connect("draw_event", _position)
        return label, cid
    def _destroy_map_qt_overlay_button(self, button, draw_cid=None) -> None:
        if draw_cid is not None:
            try:
                self.canvas.mpl_disconnect(draw_cid)
            except Exception:
                pass
        if button is not None:
            try:
                button.hide()
                button.deleteLater()
            except Exception:
                pass

    @staticmethod
    def _style_map_overlay_button(button, axes, *, fontsize=None) -> None:
        """Make Matplotlib overlay buttons match ordinary Qt push-button text."""
        try:
            button.color = "#f0f0f0"
            button.hovercolor = "#e5f1fb"
            axes.set_facecolor(button.color)
            for spine in axes.spines.values():
                spine.set_edgecolor("#a9a9a9")
                spine.set_linewidth(0.8)

            # Match the application's native QPushButton font instead of using
            # a separate hard-coded Matplotlib size.  This keeps the overlay
            # controls visually consistent across Windows, macOS and Linux.
            if fontsize is None:
                try:
                    from PyQt6.QtWidgets import QApplication
                    qfont = QApplication.font("QPushButton")
                    pts = float(qfont.pointSizeF())
                    if pts > 0:
                        button.label.set_fontsize(pts)
                    family = str(qfont.family() or "").strip()
                    if family:
                        button.label.set_fontfamily(family)
                    button.label.set_fontweight("bold" if qfont.bold() else "normal")
                    button.label.set_fontstyle("italic" if qfont.italic() else "normal")
                except Exception:
                    button.label.set_fontsize(9.0)
            else:
                button.label.set_fontsize(float(fontsize))
            button.label.set_color("#202020")
        except Exception:
            pass

    def _update_map_hover_tooltip(self, event) -> None:
        """Expose MAP tooltips only over the small controls/axis regions they describe."""
        tip = ""
        state = self._map_cross_state or self._map_roi_state
        try:
            # Native Qt overlay buttons provide their own tooltips.  Keep the
            # canvas tooltip reserved for the right-hand Y-axis selector.
            if state:
                rows = int(state.get("rows", 0))
                secondary = state.get("secondary_y")
                secondary_label = str(state.get("secondary_ylabel") or "")
                if self._has_meaningful_secondary_y(secondary, secondary_label, rows):
                    ax = state.get("ax_right")
                    if self._event_hits_right_y_axis(event, ax):
                        tip = (
                            "Double-click the right-hand Y axis or its title to switch "
                            f"between Iteration and {self._right_y_display_label(secondary_label)}."
                        )
        except Exception:
            tip = ""
        try:
            if self.canvas.toolTip() != tip:
                self.canvas.setToolTip(tip)
        except Exception:
            pass

    def _maybe_select_map_right_y_axis(self, event, state) -> bool:
        """Open the compact right-Y selector on a double-click, if available."""
        if not state or not bool(getattr(event, "dblclick", False)):
            return False
        rows = int(state.get("rows", 0))
        secondary = state.get("secondary_y")
        secondary_label = str(state.get("secondary_ylabel") or "")
        if not self._has_meaningful_secondary_y(secondary, secondary_label, rows):
            return False
        ax = state.get("ax_right")
        if not self._event_hits_right_y_axis(event, ax):
            return False
        try:
            from PyQt6.QtWidgets import QInputDialog
            physical = self._right_y_display_label(secondary_label)
            items = ["Iteration", physical]
            current = 1 if state.get("right_y_mode") == "secondary" else 0
            choice, ok = QInputDialog.getItem(
                self, "Right Y axis", "Display right trace against:", items, current, False
            )
            if ok:
                self._apply_map_right_trace_y_axis(
                    state, "secondary" if str(choice) == physical else "iteration", redraw=True
                )
            return True
        except Exception:
            return False

    def _configure_map_y_axes(
        self, ax_map, ax_iteration, rows: int, iteration_labels,
        secondary_y=None, secondary_label: str = "",
    ):
        """Configure the two Y scales used by every Processed 2D map view.

        The map itself uses row coordinates internally.  A physical second
        dimension, when present (e.g. photon energy), is shown on the left;
        iteration remains on the right.  Keeping this in one helper avoids the
        formatter/axis drift that previously affected Simple and Lines.
        """
        centers, tick_idx = self._map_tick_indices(rows)
        ax_map.set_ylim(0.0, float(rows))
        ax_map.set_yticks(centers[tick_idx])
        if secondary_y is not None and len(secondary_y) == rows:
            left_values = secondary_y
            left_label = secondary_label
        else:
            # Iteration-only maps still carry a meaningful Y coordinate.  Show
            # it on the map as well as on the right-hand trace instead of
            # leaving the map's left side blank.
            left_values = iteration_labels
            left_label = "Iteration"
        ax_map.set_yticklabels([self._format_map_axis_value(left_values[i]) for i in tick_idx])
        ax_map.set_ylabel(left_label)
        # Lines/ROI use an identically sized bottom trace.  Pin the map label
        # to the same axes-coordinate X position as the bottom Intensity label
        # so the two left-side titles form one clean vertical column.
        ax_map.yaxis.set_label_coords(-0.075, 0.5, transform=ax_map.transAxes)
        ax_map.tick_params(axis="y", labelleft=True, labelright=False)

        if ax_iteration is not None:
            ax_iteration.set_ylim(0.0, float(rows))
            ax_iteration.set_yticks(centers[tick_idx])
            labels = []
            for i in tick_idx:
                try:
                    labels.append(self._format_map_axis_value(iteration_labels[i]))
                except Exception:
                    labels.append(str(i + 1))
            ax_iteration.set_yticklabels(labels)
            ax_iteration.yaxis.tick_right()
            ax_iteration.yaxis.set_label_position("right")
            ax_iteration.set_ylabel("Iteration")
            ax_iteration.tick_params(axis="y", labelleft=False, labelright=True)
        return centers, tick_idx

    def _cleanup_map_roi_widgets(self) -> None:
        """Disconnect ROI-only Matplotlib widgets before changing map mode.

        ``Figure.clear()`` removes their Axes visually, but Matplotlib widgets
        keep canvas event connections until explicitly disconnected.  Without
        this cleanup, an invisible Full width/Full height button from a prior
        ROI render can still react to clicks after switching to Lines/Simple.
        """
        state = self._map_roi_state
        if not state:
            return
        for button_key, cid_key in (
            ("btn_full_w", "btn_full_w_draw_cid"),
            ("btn_full_h", "btn_full_h_draw_cid"),
            ("btn_pass_plot", "btn_pass_plot_draw_cid"),
        ):
            self._destroy_map_qt_overlay_button(state.get(button_key), state.get(cid_key))
        self._map_roi_drag = None

    def _cleanup_map_lines_widgets(self) -> None:
        """Disconnect the Lines-only Animation Matplotlib button."""
        state = getattr(self, "_map_cross_state", None)
        if not state:
            return
        for widget_key, cid_key in (
            ("btn_animation", "btn_animation_draw_cid"),
            ("btn_trace_scale_h", "btn_trace_scale_h_draw_cid"),
            ("btn_trace_scale_v", "btn_trace_scale_v_draw_cid"),
        ):
            self._destroy_map_qt_overlay_button(state.get(widget_key), state.get(cid_key))

    def _draw_map_normalization_band(
        self, ax, interval, mode: str | None = None, callback=None
    ) -> None:
        """Draw the full-height map-normalization band.

        In both ``At BE`` and ``Area`` modes the band is interactive: drag its
        interior to move the normalization interval or either vertical edge to
        resize it.  The GUI callback receives the updated interval continuously
        and a final commit on mouse release.
        """
        self._map_norm_band_state = None
        self._map_norm_drag = None
        if ax is None or interval is None:
            return
        try:
            low, high = sorted((float(interval[0]), float(interval[1])))
            if not (low < high):
                return
            patch = ax.axvspan(
                low, high, facecolor="tab:orange", alpha=0.13,
                edgecolor="none", zorder=1.2,
            )
            left_line = ax.axvline(
                low, color="tab:orange", linestyle="--", linewidth=1.25,
                alpha=0.9, zorder=2.2,
            )
            right_line = ax.axvline(
                high, color="tab:orange", linestyle="--", linewidth=1.25,
                alpha=0.9, zorder=2.2,
            )
            label = ax.text(
                0.5 * (low + high), 0.985, "Norm",
                transform=ax.get_xaxis_transform(), ha="center", va="top",
                fontsize=8, color="tab:orange", zorder=2.3, clip_on=True,
            )
            if mode in {"at_be", "area"} and callable(callback):
                xlo, xhi = sorted((float(v) for v in ax.get_xlim()))
                self._map_norm_band_state = {
                    "ax": ax, "low": low, "high": high, "xmin": xlo, "xmax": xhi,
                    "patch": patch, "left_line": left_line, "right_line": right_line,
                    "label": label, "callback": callback,
                }
        except Exception:
            self._map_norm_band_state = None
            self._map_norm_drag = None

    def _update_map_norm_band_artists(self, low: float, high: float, notify: bool = True) -> None:
        state = self._map_norm_band_state
        if not state:
            return
        low, high = sorted((float(low), float(high)))
        state["low"], state["high"] = low, high
        patch = state.get("patch")
        try:
            patch.set_x(low)
            patch.set_width(high - low)
        except Exception:
            try:
                xy = patch.get_xy()
                xy[:, 0] = [low, low, high, high, low]
                patch.set_xy(xy)
            except Exception:
                pass
        state["left_line"].set_xdata([low, low])
        state["right_line"].set_xdata([high, high])
        state["label"].set_x(0.5 * (low + high))
        if notify:
            try:
                state["callback"]((low, high), False)
            except TypeError:
                state["callback"]((low, high))
            except Exception:
                pass

    def _map_primary_control_claims_press(self, event) -> bool:
        """Return True when a Lines/ROI handle should own a map press.

        The normalization interval can cover a large fraction of the map.  Its
        full-height band must therefore not claim a press that is actually on
        the active Lines cursors or inside/on the active ROI.  This helper is
        intentionally a hit test only; the established Lines/ROI handlers still
        perform the drag themselves later in the Matplotlib callback chain.
        """
        if event is None or event.x is None or event.y is None:
            return False

        roi = getattr(self, "_map_roi_state", None)
        if roi and event.inaxes is roi.get("ax_map"):
            try:
                patch = roi["patch"]
                ax = roi["ax_map"]
                xl = float(patch.get_x())
                xr = xl + float(patch.get_width())
                y0 = float(patch.get_y())
                y1 = y0 + float(patch.get_height())
                pxl = ax.transData.transform((xl, 0.0))[0]
                pxr = ax.transData.transform((xr, 0.0))[0]
                py0 = ax.transData.transform((0.0, y0))[1]
                py1 = ax.transData.transform((0.0, y1))[1]
                if min(
                    abs(float(event.x) - float(pxl)),
                    abs(float(event.x) - float(pxr)),
                    abs(float(event.y) - float(py0)),
                    abs(float(event.y) - float(py1)),
                ) <= 8.0:
                    return True
                if event.xdata is not None and event.ydata is not None:
                    return (
                        min(xl, xr) <= float(event.xdata) <= max(xl, xr)
                        and min(y0, y1) <= float(event.ydata) <= max(y0, y1)
                    )
            except Exception:
                pass

        cross = getattr(self, "_map_cross_state", None)
        if cross and event.inaxes is cross.get("ax_map"):
            try:
                ax = cross["ax_map"]
                vx = ax.transData.transform(
                    (float(cross["x"][int(cross["col"])]), 0.0)
                )[0]
                hy = ax.transData.transform(
                    (0.0, float(cross["row"]) + 0.5)
                )[1]
                return (
                    abs(float(event.x) - float(vx)) <= 8.0
                    or abs(float(event.y) - float(hy)) <= 8.0
                )
            except Exception:
                pass
        return False

    def _on_map_norm_band_press(self, event) -> None:
        button = getattr(getattr(event, "button", None), "value", getattr(event, "button", None))
        if button not in (None, 1):
            return
        state = self._map_norm_band_state
        # A ResPES cut may lie inside a broad normalization band.  Its press
        # handler runs first and claims only clicks near the cut; leave those
        # clicks to the specialised analysis instead of starting two drags.
        if getattr(self, "_respes_cut_drag", None) is not None:
            return
        if self._map_primary_control_claims_press(event):
            return
        if not state or event.inaxes is not state.get("ax") or event.x is None or event.xdata is None:
            return
        try:
            ax = state["ax"]
            low, high = float(state["low"]), float(state["high"])
            px_low = ax.transData.transform((low, 0.0))[0]
            px_high = ax.transData.transform((high, 0.0))[0]
            dl, dh = abs(float(event.x) - px_low), abs(float(event.x) - px_high)
            tol = 8.0
            if min(dl, dh) <= tol:
                mode = "left" if dl <= dh else "right"
            elif low <= float(event.xdata) <= high:
                mode = "move"
            else:
                return
            self._map_norm_drag = {
                "mode": mode, "x0": float(event.xdata),
                "low0": low, "high0": high,
            }
        except Exception:
            self._map_norm_drag = None

    def _on_map_norm_band_motion(self, event) -> None:
        state, drag = self._map_norm_band_state, self._map_norm_drag
        if not state or not drag or event.inaxes not in state.get("event_axes", {state.get("ax")}) or event.xdata is None:
            return
        xmin, xmax = float(state["xmin"]), float(state["xmax"])
        low0, high0 = float(drag["low0"]), float(drag["high0"])
        xnow = float(event.xdata)
        min_width = max((xmax - xmin) * 1.0e-9, 1.0e-9)
        if drag["mode"] == "move":
            width = high0 - low0
            center = 0.5 * (low0 + high0) + (xnow - float(drag["x0"]))
            half = 0.5 * width
            center = min(max(center, xmin + half), xmax - half)
            low, high = center - half, center + half
        elif drag["mode"] == "left":
            low = min(max(xnow, xmin), high0 - min_width)
            high = high0
        else:
            low = low0
            high = max(min(xnow, xmax), low0 + min_width)
        self._update_map_norm_band_artists(low, high, notify=True)
        self.canvas.draw_idle()

    def _on_map_norm_band_release(self, _event) -> None:
        state = self._map_norm_band_state
        drag = self._map_norm_drag
        self._map_norm_drag = None
        if not state or not drag:
            return
        try:
            state["callback"]((float(state["low"]), float(state["high"])), True)
        except TypeError:
            try:
                state["callback"]((float(state["low"]), float(state["high"])))
            except Exception:
                pass
        except Exception:
            pass

    def _plot_single_map_with_cross_sections(
        self, payloads, image, flip_binding_energy, colors,
        h_thickness=1, v_thickness=1, animation_callback=None,
        norm_interval=None, norm_mode=None, norm_callback=None,
    ):
        """Render one map with draggable horizontal/vertical cross-sections."""
        import numpy as _np
        from matplotlib.patches import Rectangle

        # plot_many() creates its ordinary single axes before dispatching here;
        # replace it with the dedicated cross-section layout.  Constrained layout
        # is intentionally disabled in this mode: it recomputes axes sizes from
        # changing profile tick-label widths on every drag, which makes the map
        # visibly jump.  Fixed subplot geometry keeps the 2D panel stationary.
        try:
            self.fig.set_layout_engine(None)
        except Exception:
            try:
                self.fig.set_constrained_layout(False)
            except Exception:
                pass
        # Preserve the Lines cursor coordinates across cosmetic redraws such as
        # palette changes.  The previous state survives until the figure is
        # rebuilt, so capture its physical coordinates before clearing axes.
        previous_cross = getattr(self, "_map_cross_state", None)
        previous_x = previous_y = None
        previous_title = previous_xlabel = None
        if previous_cross:
            try:
                previous_title = str(previous_cross.get("title") or "")
                previous_xlabel = str(previous_cross.get("xlabel") or "")
                previous_x = float(previous_cross["x"][int(previous_cross.get("col", 0))])
                _prev_labels = previous_cross.get("y_labels", [])
                _prev_row = int(previous_cross.get("row", 0))
                if _prev_row < len(_prev_labels):
                    previous_y = float(_prev_labels[_prev_row])
            except Exception:
                previous_x = previous_y = None
        self.fig.clear()
        x, y, Z, title, xlabel = image[:5]
        cmap = image[5] if len(image) >= 6 else None
        x_arr = _np.asarray(x, dtype=float).reshape(-1)
        Z_arr = _np.asarray(Z, dtype=float)
        if Z_arr.ndim == 1:
            Z_arr = Z_arr.reshape(1, -1)
        elif Z_arr.ndim > 2:
            Z_arr = Z_arr.reshape(Z_arr.shape[0], -1)
        rows, cols = Z_arr.shape
        if cols != x_arr.size:
            cols = min(cols, x_arr.size)
            Z_arr = Z_arr[:, :cols]
            x_arr = x_arr[:cols]
        try:
            # Keep fractional coordinates produced by even-sized bins (for
            # example iterations 1–2 are represented at 1.5) instead of
            # truncating them back to integers.
            y_labels = [float(v) for v in y]
            if len(y_labels) != rows:
                raise ValueError
        except Exception:
            y_labels = list(range(1, rows + 1))
        secondary_y, secondary_ylabel = self._map_secondary_axis(image, rows)

        # Reserve stable outer margins for all labels and a fixed internal
        # geometry.  A small fixed gap separates the cross-section traces
        # from the map: this improves visual separation and gives scientific
        # notation offset text enough room without allowing drag-time relayout.
        _map_left = 0.100
        gs = self.fig.add_gridspec(
            2, 2, width_ratios=(4.6, 1.35), height_ratios=(4.0, 1.25),
            left=_map_left, right=0.925, bottom=0.09, top=0.94,
            wspace=0.045, hspace=0.065
        )
        self.ax = self.fig.add_subplot(gs[0, 0])
        ax_map = self.ax
        ax_right = self.fig.add_subplot(gs[0, 1])
        ax_bottom = self.fig.add_subplot(gs[1, 0], sharex=ax_map)
        ax_corner = self.fig.add_subplot(gs[1, 1])
        ax_corner.axis("off")

        # The lower-right cell is otherwise unused in Lines view.  Use it for
        # controls that affect the *live* H/V traces, keeping them visually
        # separate from the Plot H/V trace buttons in the top control strip.
        btn_animation = None
        btn_animation_draw_cid = None
        btn_trace_scale_h = None
        btn_trace_scale_h_draw_cid = None
        btn_trace_scale_v = None
        btn_trace_scale_v_draw_cid = None
        corner = ax_corner.get_position()
        # Horizontal and vertical side traces have independent intensity axes.
        # Keep their autoscale choices independent as well.  For compatibility
        # with sessions created before 0.10.76, an old ``full`` mode initializes
        # both checkboxes unchecked; otherwise both default to Auto.
        old_mode = str(getattr(self, "_map_lines_trace_scale_mode", "auto") or "auto")
        default_auto = old_mode != "full"
        auto_h = bool(getattr(self, "_map_lines_auto_scale_h", default_auto))
        auto_v = bool(getattr(self, "_map_lines_auto_scale_v", default_auto))
        btn_trace_scale_h, btn_trace_scale_h_draw_cid = self._create_map_qt_overlay_checkbox(
            "Auto scale H",
            [corner.x0 + 0.18 * corner.width, corner.y0 + 0.49 * corner.height,
             0.78 * corner.width, 0.16 * corner.height],
            "Checked: autoscale the horizontal (bottom) trace intensity. "
            "Unchecked: use the full displayed MAP intensity range.",
            checked=auto_h,
        )
        btn_trace_scale_v, btn_trace_scale_v_draw_cid = self._create_map_qt_overlay_checkbox(
            "Auto scale V",
            [corner.x0 + 0.18 * corner.width, corner.y0 + 0.31 * corner.height,
             0.78 * corner.width, 0.16 * corner.height],
            "Checked: autoscale the vertical (right) trace intensity. "
            "Unchecked: use the full displayed MAP intensity range.",
            checked=auto_v,
        )

        if callable(animation_callback):
            btn_animation, btn_animation_draw_cid = self._create_map_qt_overlay_button(
                "Animation...",
                [corner.x0 + 0.18 * corner.width, corner.y0 + 0.04 * corner.height,
                 0.78 * corner.width, 0.20 * corner.height],
                "Animate the H or V line through the map using the selected "
                "line thickness as the frame step.",
            )
            if btn_animation is not None:
                btn_animation.clicked.connect(lambda _checked=False: animation_callback())

        xmin, xmax = float(x_arr[0]), float(x_arr[-1])
        map_image = ax_map.imshow(
            Z_arr, aspect="auto", origin="lower",
            extent=[xmin, xmax, 0.0, float(rows)], cmap=cmap
        )
        self._disable_map_artist_cursor_data(map_image)
        self._draw_map_normalization_band(ax_map, norm_interval, norm_mode, norm_callback)
        ax_map.set_title(title)
        ax_map.set_ylabel("")
        ax_map.tick_params(axis="x", labelbottom=False)
        ax_map.tick_params(axis="y", labelleft=False)

        centers, tick_idx = self._configure_map_y_axes(
            ax_map, ax_right, rows, y_labels, secondary_y, secondary_ylabel
        )
        self._set_map_coordinate_formatter(
            [ax_map, ax_right], x_arr, rows, xlabel, y_labels, secondary_y, secondary_ylabel, Z_arr
        )
        # Keep the profile and map aligned geometrically without sharing the
        # Matplotlib YAxis object.  sharey() also shares tick formatters/labels,
        # which caused the iteration labels on the right trace to overwrite the
        # physical photon-energy labels on the map's left axis.
        ax_map.set_ylim(0.0, float(rows))
        ax_right.set_ylim(0.0, float(rows))

        row_idx = max(0, min(rows - 1, rows // 2))
        col_idx = max(0, min(cols - 1, cols // 2))

        # Restore the last remembered physical cursor coordinates for this map.
        # The memory lives outside the transient Matplotlib state, so it survives
        # palette changes, leaving/re-entering Lines, and Raw/Processed tab
        # switches.  Physical coordinates are mapped to the nearest currently
        # available sample, which also makes restoration safe after binning or
        # other changes in map dimensions.
        saved_x = saved_y = None
        try:
            memory = getattr(self, "_map_lines_position_memory", {})
            saved = memory.get(self._map_lines_memory_key(title, xlabel), {}) if isinstance(memory, dict) else {}
            saved_x = saved.get("x")
            saved_y = saved.get("y")
        except Exception:
            saved_x = saved_y = None

        # Fall back to the immediately previous cross state when available.
        if saved_x is None and previous_title == str(title or "") and previous_xlabel == str(xlabel or ""):
            saved_x = previous_x
        if saved_y is None and previous_title == str(title or "") and previous_xlabel == str(xlabel or ""):
            saved_y = previous_y
        try:
            if saved_x is not None:
                col_idx = int(_np.nanargmin(_np.abs(x_arr - float(saved_x))))
            if saved_y is not None:
                _yl = _np.asarray(y_labels, dtype=float)
                row_idx = int(_np.nanargmin(_np.abs(_yl - float(saved_y))))
        except Exception:
            pass
        x_pos = float(x_arr[col_idx])
        y_pos = float(row_idx) + 0.5
        vline = ax_map.axvline(x_pos, linestyle="--", linewidth=1.05, zorder=3.6)
        hline = ax_map.axhline(y_pos, linestyle="--", linewidth=1.05, zorder=3.6)

        # Coordinate labels make the draggable Lines cursors self-describing.
        # They are drawn directly on the map and use a palette-aware contrast
        # box so that the text stays legible on both dark and bright colormaps.
        def _cursor_number(value, spacing=None):
            try:
                value = float(value)
                if spacing is not None and np.isfinite(spacing) and spacing > 0:
                    # Show enough precision to distinguish neighbouring samples.
                    decimals = max(0, min(5, int(np.ceil(-np.log10(spacing))) + 1))
                    return f"{value:.{decimals}f}"
                return self._format_map_axis_value(value)
            except Exception:
                return str(value)

        def _x_cursor_caption(col):
            xx = float(x_arr[int(col)])
            diffs = np.abs(np.diff(np.asarray(x_arr, dtype=float)))
            diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
            spacing = float(np.nanmedian(diffs)) if diffs.size else None
            label_l = str(xlabel or "").lower()
            quantity = "KE" if "kinetic" in label_l else ("BE" if "binding" in label_l else "X")
            unit = " eV" if "ev" in label_l else ""
            return f"{quantity} = {_cursor_number(xx, spacing)}{unit}"

        def _y_cursor_caption(row):
            rr = int(row)
            # Some files expose a redundant second axis such as
            # "Region Iteration [a.u]".  It is still iteration, not a more
            # meaningful physical coordinate, so present it simply and cleanly.
            if secondary_y is not None and len(secondary_y) == rows:
                vals = np.asarray(secondary_y, dtype=float)
                label_text = str(secondary_ylabel or "")
                label_low = label_text.lower()
                if "iteration" in label_low:
                    return f"Iteration = {self._format_map_axis_value(vals[rr])}"
                diffs = np.abs(np.diff(vals))
                diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
                spacing = float(np.nanmedian(diffs)) if diffs.size else None
                number = _cursor_number(vals[rr], spacing)
                if "photon" in label_low and "energy" in label_low:
                    return f"PhE = {number} eV"
                return f"{secondary_ylabel} = {number}"
            return f"Iteration = {self._format_map_axis_value(y_labels[rr])}"

        def _style_cursor_label(text_artist, row, col):
            try:
                z = float(Z_arr[int(row), int(col)])
                rgba = map_image.get_cmap()(map_image.norm(z))
                # Relative luminance is sufficiently robust for choosing a
                # high-contrast foreground/background pair.
                lum = 0.2126 * float(rgba[0]) + 0.7152 * float(rgba[1]) + 0.0722 * float(rgba[2])
                if lum >= 0.56:
                    fg, bg = "black", "white"
                else:
                    fg, bg = "white", "black"
                text_artist.set_color(fg)
                text_artist.set_bbox(dict(
                    boxstyle="round,pad=0.24", facecolor=bg, edgecolor=fg,
                    linewidth=0.65, alpha=0.78,
                ))
            except Exception:
                text_artist.set_color("white")
                text_artist.set_bbox(dict(
                    boxstyle="round,pad=0.24", facecolor="black", edgecolor="white",
                    linewidth=0.65, alpha=0.78,
                ))

        vlabel = ax_map.text(
            x_pos, 0.985, _x_cursor_caption(col_idx),
            transform=ax_map.get_xaxis_transform(), ha="center", va="top",
            fontsize=9, fontweight="bold", zorder=4.5, clip_on=True,
        )
        hlabel = ax_map.text(
            0.012, y_pos, _y_cursor_caption(row_idx),
            transform=ax_map.get_yaxis_transform(), ha="left", va="center",
            fontsize=9, fontweight="bold", zorder=4.5, clip_on=True,
        )

        def _keep_cursor_labels_inside(col, row):
            """Flip label anchoring near map edges so text is never clipped."""
            try:
                xp = ax_map.transData.transform((float(x_arr[int(col)]), 0.0))[0]
                xfrac = (xp - ax_map.bbox.x0) / max(ax_map.bbox.width, 1.0)
                if xfrac < 0.20:
                    vlabel.set_ha("left")
                elif xfrac > 0.80:
                    vlabel.set_ha("right")
                else:
                    vlabel.set_ha("center")
            except Exception:
                vlabel.set_ha("center")
            try:
                yp = ax_map.transData.transform((0.0, float(row) + 0.5))[1]
                yfrac = (yp - ax_map.bbox.y0) / max(ax_map.bbox.height, 1.0)
                if yfrac < 0.08:
                    hlabel.set_va("bottom")
                elif yfrac > 0.92:
                    hlabel.set_va("top")
                else:
                    hlabel.set_va("center")
            except Exception:
                hlabel.set_va("center")
        _style_cursor_label(vlabel, rows - 1, col_idx)
        # Pick the visual left edge of the map for the horizontal-label
        # contrast sample, respecting a reversed binding-energy display.
        _h_contrast_col = cols - 1 if flip_binding_energy else 0
        _style_cursor_label(hlabel, row_idx, _h_contrast_col)
        _keep_cursor_labels_inside(col_idx, row_idx)

        def _odd_thickness(value):
            value = max(1, min(25, int(value)))
            return value if value % 2 else min(25, value + 1)

        h_thickness = _odd_thickness(h_thickness)
        v_thickness = _odd_thickness(v_thickness)

        def _symmetric_indices(center, requested, total):
            # Keep the average genuinely symmetric around the selected sample.
            # Close to an edge, reduce the effective odd width rather than
            # shifting the averaging window away from the cursor.
            half_req = (_odd_thickness(requested) - 1) // 2
            half = min(half_req, int(center), int(total) - 1 - int(center))
            return _np.arange(int(center) - half, int(center) + half + 1, dtype=int)

        def _horizontal_profile(row):
            idx = _symmetric_indices(row, h_thickness, rows)
            return _np.nanmean(Z_arr[idx, :], axis=0), idx

        def _vertical_profile(col):
            idx = _symmetric_indices(col, v_thickness, cols)
            return _np.nanmean(Z_arr[:, idx], axis=1), idx

        bottom_values, h_indices = _horizontal_profile(row_idx)
        right_values, v_indices = _vertical_profile(col_idx)

        # Show the actual averaging footprint directly on the map.  The H/V
        # thickness values are counts of map rows/columns, so a translucent
        # band is more meaningful than merely changing the stroke width in
        # screen points.  The dashed line remains the exact cursor centre.
        def _column_span(indices):
            ii = _np.asarray(indices, dtype=int)
            lo_i, hi_i = int(ii.min()), int(ii.max())
            # imshow distributes the matrix uniformly across its extent.
            step = (xmax - xmin) / float(max(cols, 1))
            lo = xmin + lo_i * step
            hi = xmin + (hi_i + 1) * step
            return (min(lo, hi), max(lo, hi))

        def _row_span(indices):
            ii = _np.asarray(indices, dtype=int)
            return float(ii.min()), float(ii.max() + 1)

        hx0, hx1 = xmin, xmax
        hy0, hy1 = _row_span(h_indices)
        vx0, vx1 = _column_span(v_indices)
        # Make the averaging width unmistakable on top of any colormap.
        # Use a stronger translucent fill plus an opaque outline; the outline
        # moves with the band when H/V thickness changes, while the dashed
        # centre line continues to mark the exact cursor sample.  Supplying an
        # RGBA face colour (rather than patch-wide alpha) keeps the border fully
        # opaque and therefore visible even over bright map regions.
        h_color = hline.get_color()
        v_color = vline.get_color()
        hband = Rectangle(
            (min(hx0, hx1), hy0), abs(hx1 - hx0), hy1 - hy0,
            facecolor=to_rgba(h_color, 0.32), edgecolor=h_color,
            linewidth=1.8, linestyle="-", zorder=3.0,
        )
        vband = Rectangle(
            (vx0, 0.0), vx1 - vx0, float(rows),
            facecolor=to_rgba(v_color, 0.32), edgecolor=v_color,
            linewidth=1.8, linestyle="-", zorder=3.0,
        )
        ax_map.add_patch(hband)
        ax_map.add_patch(vband)
        # A one-sample selection is represented by the centre line only.
        # Showing a filled one-pixel band makes thickness=1 look much heavier
        # than the actual selection, especially for horizontal rows.
        hband.set_visible(h_thickness > 1)
        vband.set_visible(v_thickness > 1)

        # Continue the cross-hairs into their corresponding side traces.
        # This makes peak-centred positioning much easier because the selected
        # map row/column can be aligned directly with the 1D intensity maxima.
        # The translucent spans use the same effective averaging footprint as
        # the map bands, including the symmetric edge reduction.
        vband_bottom = ax_bottom.axvspan(
            vx0, vx1, facecolor=to_rgba(v_color, 0.20), edgecolor=v_color,
            linewidth=1.4, zorder=0.8,
        )
        vline_bottom = ax_bottom.axvline(
            x_pos, linestyle="--", linewidth=1.0, color=v_color, zorder=3.2
        )
        hband_right = ax_right.axhspan(
            hy0, hy1, facecolor=to_rgba(h_color, 0.20), edgecolor=h_color,
            linewidth=1.4, zorder=0.8,
        )
        hline_right = ax_right.axhline(
            y_pos, linestyle="--", linewidth=1.0, color=h_color, zorder=3.2
        )
        hband_right.set_visible(h_thickness > 1)
        vband_bottom.set_visible(v_thickness > 1)

        bottom_line = ax_bottom.plot(x_arr, bottom_values, linewidth=1.3, zorder=2.0)[0]
        ax_bottom.set_xlabel(xlabel)
        ax_bottom.set_ylabel("Intensity")
        # Keep the bottom-trace Y-axis title fixed in axes coordinates.
        # Matplotlib otherwise repositions it according to the current tick-label
        # bounding boxes, making "Intensity" visibly jump left/right as the
        # trace scale changes between integer- and decimal-looking tick labels.
        ax_bottom.yaxis.set_label_coords(-0.075, 0.5, transform=ax_bottom.transAxes)
        right_line = ax_right.plot(right_values, centers, linewidth=1.3, zorder=2.0)[0]
        ax_right.set_xlabel("Intensity")
        ax_right.tick_params(axis="y", labelleft=False, labelright=True)
        # Slightly stronger grids improve readability of the extracted traces
        # without competing with the data curves.
        ax_bottom.grid(True, linewidth=1.05, alpha=0.42)
        ax_right.grid(True, linewidth=1.05, alpha=0.42)

        # Keep profile intensity labels compact and stable.  The right profile
        # can use Matplotlib's standard scientific formatter.  For the bottom
        # profile we deliberately manage the multiplier ourselves: Matplotlib's
        # y-axis offset text is positioned above the axes by default and can
        # therefore disappear into (or overlap) the map panel.
        try:
            fmt_right = ScalarFormatter(useMathText=True)
            fmt_right.set_scientific(True)
            fmt_right.set_powerlimits((0, 0))
            ax_right.xaxis.set_major_formatter(fmt_right)
            ax_right.ticklabel_format(axis="x", style="sci", scilimits=(0, 0), useMathText=True)
        except Exception:
            pass

        bottom_scale_text = ax_bottom.text(
            0.015, 0.94, "", transform=ax_bottom.transAxes,
            ha="left", va="top", clip_on=False
        )

        def _set_bottom_scientific_scale(values) -> None:
            vals = _np.asarray(values, dtype=float)
            finite = _np.abs(vals[_np.isfinite(vals)])
            vmax = float(_np.nanmax(finite)) if finite.size else 0.0
            if vmax > 0.0:
                exponent = int(_np.floor(_np.log10(vmax)))
            else:
                exponent = 0
            # Always keep the profile in scientific notation, matching the
            # previous UI, but place the multiplier safely inside its panel.
            scale = 10.0 ** exponent if exponent != 0 else 1.0
            ax_bottom.yaxis.set_major_formatter(
                FuncFormatter(lambda value, _pos, _s=scale: f"{value / _s:g}")
            )
            bottom_scale_text.set_text(rf"$\times 10^{{{exponent}}}$")

        _set_bottom_scientific_scale(bottom_values)

        used_colors = []
        if payloads:
            ax_overlay = ax_map.twinx()
            ax_overlay.set_yticks([])
            ax_overlay.set_ylabel("")
            ax_overlay.patch.set_alpha(0)
            for idx, p in enumerate(payloads):
                col = colors[idx] if colors is not None and idx < len(colors) else None
                avg = "average" in str(getattr(p, "title", "")).lower()
                kwargs = {"linewidth": 2.0 if avg else 1.5}
                if avg:
                    kwargs["color"] = "white"
                elif col is not None:
                    kwargs["color"] = col
                line = ax_overlay.plot(p.x, p.y, **kwargs)[0]
                try:
                    used_colors.append(line.get_color())
                except Exception:
                    used_colors.append("#000000")

        xlo, xhi = float(_np.nanmin(x_arr)), float(_np.nanmax(x_arr))
        if flip_binding_energy:
            ax_map.set_xlim(xhi, xlo)
            ax_bottom.set_xlim(xhi, xlo)
        else:
            ax_map.set_xlim(xlo, xhi)
            ax_bottom.set_xlim(xlo, xhi)
        ax_map.set_ylim(0.0, float(rows))
        ax_right.set_ylim(0.0, float(rows))
        # Re-evaluate edge anchoring after the final X direction is known.
        _keep_cursor_labels_inside(col_idx, row_idx)

        self._map_cross_state = {
            "x": x_arr, "Z": Z_arr, "rows": rows, "cols": cols, "y_labels": y_labels,
            "secondary_y": secondary_y, "secondary_ylabel": secondary_ylabel,
            "xlabel": xlabel, "title": title,
            "row": row_idx, "col": col_idx, "ax_map": ax_map,
            "ax_right": ax_right, "ax_bottom": ax_bottom,
            "vline": vline, "hline": hline,
            "vlabel": vlabel, "hlabel": hlabel,
            "x_cursor_caption": _x_cursor_caption, "y_cursor_caption": _y_cursor_caption,
            "style_cursor_label": _style_cursor_label,
            "keep_cursor_labels_inside": _keep_cursor_labels_inside,
            "h_contrast_col": _h_contrast_col,
            "right_line": right_line, "bottom_line": bottom_line,
            "h_thickness": h_thickness, "v_thickness": v_thickness,
            "h_indices": h_indices, "v_indices": v_indices,
            "hband": hband, "vband": vband,
            "hband_right": hband_right, "vband_bottom": vband_bottom,
            "hline_right": hline_right, "vline_bottom": vline_bottom,
            "column_span": _column_span, "row_span": _row_span,
            "horizontal_profile": _horizontal_profile,
            "vertical_profile": _vertical_profile,
            "bottom_scale_text": bottom_scale_text,
            "set_bottom_scientific_scale": _set_bottom_scientific_scale,
            "btn_animation": btn_animation,
            "btn_animation_draw_cid": btn_animation_draw_cid,
            "btn_trace_scale_h": btn_trace_scale_h,
            "btn_trace_scale_h_draw_cid": btn_trace_scale_h_draw_cid,
            "btn_trace_scale_v": btn_trace_scale_v,
            "btn_trace_scale_v_draw_cid": btn_trace_scale_v_draw_cid,
            "trace_scale_min": float(_np.nanmin(Z_arr)) if _np.size(Z_arr) else 0.0,
            "trace_scale_max": float(_np.nanmax(Z_arr)) if _np.size(Z_arr) else 1.0,
        }
        if btn_trace_scale_h is not None:
            def _toggle_trace_scale_h(checked=False):
                self._map_lines_auto_scale_h = bool(checked)
                self._apply_map_lines_trace_scale(self._map_cross_state)
                self.canvas.draw_idle()
            btn_trace_scale_h.toggled.connect(_toggle_trace_scale_h)
        if btn_trace_scale_v is not None:
            def _toggle_trace_scale_v(checked=False):
                self._map_lines_auto_scale_v = bool(checked)
                self._apply_map_lines_trace_scale(self._map_cross_state)
                self.canvas.draw_idle()
            btn_trace_scale_v.toggled.connect(_toggle_trace_scale_v)
        self._apply_map_right_trace_y_axis(
            self._map_cross_state, getattr(self, "_map_right_y_mode", "iteration"), redraw=False
        )
        self._apply_map_lines_trace_scale(self._map_cross_state)
        self._remember_map_lines_state(self._map_cross_state)
        self.canvas.draw_idle()
        return used_colors

    def _plot_single_map_with_roi(
        self, payloads, image, flip_binding_energy, colors,
        roi_spec=None, roi_callback=None, roi_pass_callback=None,
        norm_interval=None, norm_mode=None, norm_callback=None,
    ):
        """Render one map with a draggable/resizable rectangular ROI.

        The bottom trace is the sum over the selected Y rows (spectrum vs X),
        while the right trace is the sum over the selected X columns (profile
        vs iteration/Y).  The rectangle therefore controls both projections.
        """
        import numpy as _np
        from matplotlib.patches import Rectangle
        
        try:
            self.fig.set_layout_engine(None)
        except Exception:
            try:
                self.fig.set_constrained_layout(False)
            except Exception:
                pass
        self.fig.clear()
        x, y, Z, title, xlabel = image[:5]
        cmap = image[5] if len(image) >= 6 else None
        x_arr = _np.asarray(x, dtype=float).reshape(-1)
        Z_arr = _np.asarray(Z, dtype=float)
        if Z_arr.ndim == 1:
            Z_arr = Z_arr.reshape(1, -1)
        elif Z_arr.ndim > 2:
            Z_arr = Z_arr.reshape(Z_arr.shape[0], -1)
        rows, cols = Z_arr.shape
        if cols != x_arr.size:
            cols = min(cols, x_arr.size)
            Z_arr = Z_arr[:, :cols]
            x_arr = x_arr[:cols]
        try:
            y_labels = _np.asarray([float(v) for v in y], dtype=float)
            if y_labels.size != rows:
                raise ValueError
        except Exception:
            y_labels = _np.arange(1, rows + 1, dtype=float)
        secondary_y, secondary_ylabel = self._map_secondary_axis(image, rows)

        _map_left = 0.100
        gs = self.fig.add_gridspec(
            2, 2, width_ratios=(4.6, 1.35), height_ratios=(4.0, 1.25),
            left=_map_left, right=0.925, bottom=0.09, top=0.94,
            wspace=0.045, hspace=0.065,
        )
        self.ax = self.fig.add_subplot(gs[0, 0])
        ax_map = self.ax
        # ROI projections deliberately have independent axes.  Their displayed
        # coordinate ranges follow the ROI itself, while the 2D map always
        # stays at the full map extent.
        ax_right = self.fig.add_subplot(gs[0, 1])
        ax_bottom = self.fig.add_subplot(gs[1, 0])

        # The lower-right GridSpec cell is intentionally left empty.  The ROI
        # extent toggles are figure-overlay controls placed inside that unused
        # corner, so they do not claim layout space or displace/crop either
        # trace axis, its ticks, or its axis title.  Keep the upper part of the
        # corner clear for the right-trace X label.
        bottom_pos = ax_bottom.get_position()
        right_pos = ax_right.get_position()
        corner_x0, corner_x1 = right_pos.x0, right_pos.x1
        corner_y0, corner_y1 = bottom_pos.y0, bottom_pos.y1
        corner_w = max(0.001, corner_x1 - corner_x0)
        corner_h = max(0.001, corner_y1 - corner_y0)
        btn_h = 0.18 * corner_h
        btn_gap = 0.055 * corner_h
        btn_y0 = corner_y0 + 0.035 * corner_h
        btn_x0 = corner_x0 + 0.06 * corner_w
        btn_w = 0.88 * corner_w
        btn_pass_plot, btn_pass_plot_draw_cid = self._create_map_qt_overlay_button(
            "Pass to plotting", [btn_x0, btn_y0, btn_w, btn_h]
        )
        btn_full_h, btn_full_h_draw_cid = self._create_map_qt_overlay_button(
            "Full height", [btn_x0, btn_y0 + btn_h + btn_gap, btn_w, btn_h]
        )
        btn_full_w, btn_full_w_draw_cid = self._create_map_qt_overlay_button(
            "Full width", [btn_x0, btn_y0 + 2 * (btn_h + btn_gap), btn_w, btn_h]
        )
        if btn_full_w is not None:
            btn_full_w.setCheckable(True)
        if btn_full_h is not None:
            btn_full_h.setCheckable(True)

        xmin, xmax = float(x_arr[0]), float(x_arr[-1])
        map_image = ax_map.imshow(
            Z_arr, aspect="auto", origin="lower",
            extent=[xmin, xmax, 0.0, float(rows)], cmap=cmap,
        )
        self._disable_map_artist_cursor_data(map_image)
        self._draw_map_normalization_band(ax_map, norm_interval, norm_mode, norm_callback)
        ax_map.set_title(title)
        ax_map.set_ylabel("")
        ax_map.tick_params(axis="x", labelbottom=False)
        ax_map.tick_params(axis="y", labelleft=False)

        centers, tick_idx = self._configure_map_y_axes(
            ax_map, ax_right, rows, y_labels, secondary_y, secondary_ylabel
        )
        self._set_map_coordinate_formatter(
            [ax_map, ax_right], x_arr, rows, xlabel, y_labels, secondary_y, secondary_ylabel, Z_arr
        )

        # Convert requested ROI into snapped data indices.  Widths are physical
        # X units and Y-label units respectively, with practical minimums of one
        # sampled column/row.
        spec = dict(roi_spec or {})
        xlo_data, xhi_data = float(_np.nanmin(x_arr)), float(_np.nanmax(x_arr))
        x_step = float(_np.nanmedian(_np.abs(_np.diff(x_arr)))) if cols > 1 else 1.0
        if not _np.isfinite(x_step) or x_step <= 0:
            x_step = max(abs(xhi_data - xlo_data), 1.0)
        ylo_data, yhi_data = float(_np.nanmin(y_labels)), float(_np.nanmax(y_labels))
        y_step = float(_np.nanmedian(_np.abs(_np.diff(y_labels)))) if rows > 1 else 1.0
        if not _np.isfinite(y_step) or y_step <= 0:
            y_step = 1.0

        x_center_req = float(spec.get("x_center", 0.5 * (xlo_data + xhi_data)))
        y_center_req = float(spec.get("y_center", y_labels[rows // 2]))
        x_width_req = float(spec.get("x_width", max(x_step, 0.20 * abs(xhi_data - xlo_data))))
        y_width_req = float(spec.get("y_width", max(y_step, 0.20 * max(abs(yhi_data - ylo_data), y_step))))
        x_width_req = min(max(abs(x_width_req), x_step), max(abs(xhi_data - xlo_data), x_step))
        y_width_req = min(max(abs(y_width_req), y_step), max(abs(yhi_data - ylo_data) + y_step, y_step))

        def _centered_indices(values, center, width, step_size):
            n_total = int(values.size)
            count = max(1, min(n_total, int(round(float(width) / float(step_size)))))
            center_idx = int(_np.nanargmin(_np.abs(values - float(center))))
            lo = center_idx - (count - 1) // 2
            hi = lo + count
            if lo < 0:
                hi -= lo
                lo = 0
            if hi > n_total:
                lo -= hi - n_total
                hi = n_total
            lo = max(0, lo)
            return _np.arange(lo, hi, dtype=int)

        def _indices_from_spec(xc, xw, yc, yw):
            xidx = _centered_indices(x_arr, xc, xw, x_step)
            yidx = _centered_indices(y_labels, yc, yw, y_step)
            return xidx, yidx

        xidx, yidx = _indices_from_spec(x_center_req, x_width_req, y_center_req, y_width_req)

        def _bounds_from_indices(xi, yi):
            # Pixel-like cell edges around sampled X points; works for either
            # ascending or descending energy axes.
            xv = _np.sort(x_arr[xi])
            xl = float(xv[0] - 0.5 * x_step)
            xr = float(xv[-1] + 0.5 * x_step)
            xl = max(xlo_data - 0.5 * x_step, xl)
            xr = min(xhi_data + 0.5 * x_step, xr)
            y0 = max(0.0, float(int(yi[0])))
            y1 = min(float(rows), float(int(yi[-1]) + 1))
            return xl, xr, y0, y1

        xl, xr, y0, y1 = _bounds_from_indices(xidx, yidx)
        roi_patch = Rectangle(
            (xl, y0), xr - xl, y1 - y0,
            facecolor="white", edgecolor="white", alpha=0.20,
            linewidth=1.8, linestyle="--", zorder=7,
        )
        ax_map.add_patch(roi_patch)

        # Both projections are projections of the rectangle itself, not of
        # full-map stripes.  Thus their coordinate axes directly represent
        # the current ROI bounds.
        roi_block = Z_arr[_np.ix_(yidx, xidx)]
        bottom_values = _np.nansum(roi_block, axis=0)
        right_values = _np.nansum(roi_block, axis=1)
        bottom_line = ax_bottom.plot(x_arr[xidx], bottom_values, linewidth=1.3)[0]
        right_line = ax_right.plot(right_values, centers[yidx], linewidth=1.3)[0]
        ax_bottom.set_xlabel(xlabel)
        ax_bottom.set_ylabel("Intensity")
        # Use the same fixed label position as Lines so ROI projection scaling
        # cannot shift the bottom-trace title horizontally either.
        ax_bottom.yaxis.set_label_coords(-0.075, 0.5, transform=ax_bottom.transAxes)
        ax_right.set_xlabel("Intensity")
        ax_bottom.grid(True, linewidth=1.25, alpha=0.45)
        ax_right.grid(True, linewidth=1.25, alpha=0.45)

        try:
            fmt_right = ScalarFormatter(useMathText=True)
            fmt_right.set_scientific(True)
            fmt_right.set_powerlimits((0, 0))
            ax_right.xaxis.set_major_formatter(fmt_right)
            ax_right.ticklabel_format(axis="x", style="sci", scilimits=(0, 0), useMathText=True)
        except Exception:
            pass

        bottom_scale_text = ax_bottom.text(
            0.015, 0.94, "", transform=ax_bottom.transAxes,
            ha="left", va="top", clip_on=True,
        )

        def _set_bottom_scientific_scale(values):
            vals = _np.asarray(values, dtype=float)
            finite = _np.abs(vals[_np.isfinite(vals)])
            vmax = float(_np.nanmax(finite)) if finite.size else 0.0
            exponent = int(_np.floor(_np.log10(vmax))) if vmax > 0 else 0
            scale = 10.0 ** exponent if exponent != 0 else 1.0
            ax_bottom.yaxis.set_major_formatter(
                FuncFormatter(lambda value, _pos, _s=scale: f"{value / _s:g}")
            )
            bottom_scale_text.set_text(rf"$\times 10^{{{exponent}}}$")

        _set_bottom_scientific_scale(bottom_values)

        used_colors = []
        if payloads:
            ax_overlay = ax_map.twinx()
            ax_overlay.set_yticks([])
            ax_overlay.set_ylabel("")
            ax_overlay.patch.set_alpha(0)
            for idx, p in enumerate(payloads):
                col = colors[idx] if colors is not None and idx < len(colors) else None
                avg = "average" in str(getattr(p, "title", "")).lower()
                kwargs = {"linewidth": 2.0 if avg else 1.5}
                if avg:
                    kwargs["color"] = "white"
                elif col is not None:
                    kwargs["color"] = col
                line = ax_overlay.plot(p.x, p.y, **kwargs)[0]
                try:
                    used_colors.append(line.get_color())
                except Exception:
                    used_colors.append("#000000")

        xlo, xhi = xlo_data, xhi_data
        if flip_binding_energy:
            ax_map.set_xlim(xhi, xlo)
            ax_bottom.set_xlim(xr, xl)
        else:
            ax_map.set_xlim(xlo, xhi)
            ax_bottom.set_xlim(xl, xr)
        ax_map.set_ylim(0.0, float(rows))
        ax_right.set_ylim(y0, y1)

        state = {
            "x": x_arr, "Z": Z_arr, "rows": rows, "cols": cols,
            "y_labels": y_labels, "secondary_y": secondary_y,
            "secondary_ylabel": secondary_ylabel, "xlabel": xlabel, "title": title,
            "x_step": x_step, "y_step": y_step,
            "xidx": xidx, "yidx": yidx, "ax_map": ax_map,
            "ax_right": ax_right, "ax_bottom": ax_bottom,
            "patch": roi_patch, "right_line": right_line,
            "bottom_line": bottom_line, "bottom_scale_text": bottom_scale_text,
            "set_bottom_scientific_scale": _set_bottom_scientific_scale,
            "callback": roi_callback,
            # Toggle state.  Saved indices are the exact pre-expansion ROI and
            # are restored when the corresponding button is unpressed.
            "full_w_active": bool(spec.get("_full_w_active", False)),
            "full_h_active": bool(spec.get("_full_h_active", False)),
            "saved_xidx": None, "saved_yidx": None,
            # Keep strong references to the Matplotlib buttons.
            "btn_full_w": btn_full_w, "btn_full_h": btn_full_h,
            "btn_pass_plot": btn_pass_plot,
            "btn_full_w_draw_cid": btn_full_w_draw_cid,
            "btn_full_h_draw_cid": btn_full_h_draw_cid,
            "btn_pass_plot_draw_cid": btn_pass_plot_draw_cid,
            "pass_callback": roi_pass_callback,
        }

        def _saved_indices_from_spec(axis_name):
            saved = spec.get(f"_full_{axis_name}_saved")
            if not isinstance(saved, dict):
                return None
            try:
                if axis_name == "w":
                    return _centered_indices(
                        x_arr, float(saved["center"]), float(saved["width"]), x_step
                    )
                return _centered_indices(
                    y_labels, float(saved["center"]), float(saved["width"]), y_step
                )
            except Exception:
                return None

        state["saved_xidx"] = _saved_indices_from_spec("w")
        state["saved_yidx"] = _saved_indices_from_spec("h")
        if state["full_w_active"]:
            if state["saved_xidx"] is None:
                state["saved_xidx"] = state["xidx"].copy()
            state["xidx"] = _np.arange(cols, dtype=int)
        if state["full_h_active"]:
            if state["saved_yidx"] is None:
                state["saved_yidx"] = state["yidx"].copy()
            state["yidx"] = _np.arange(rows, dtype=int)
        self._map_roi_state = state
        self._apply_map_right_trace_y_axis(
            self._map_roi_state, getattr(self, "_map_right_y_mode", "iteration"), redraw=False
        )

        def _style_extent_button(button, active):
            # Use the native Qt checked state, so the extent controls have the
            # exact same platform style/font as ordinary application buttons.
            try:
                button.setChecked(bool(active))
            except Exception:
                pass

        def _set_full_width(_event):
            current = self._map_roi_state
            if not current:
                return
            if not current.get("full_w_active", False):
                current["saved_xidx"] = _np.asarray(current["xidx"], dtype=int).copy()
                current["xidx"] = _np.arange(int(current["cols"]), dtype=int)
                current["full_w_active"] = True
            else:
                saved = current.get("saved_xidx")
                if saved is not None and len(saved):
                    current["xidx"] = _np.asarray(saved, dtype=int).copy()
                current["full_w_active"] = False
                current["saved_xidx"] = None
            _style_extent_button(btn_full_w, current["full_w_active"])
            self._update_map_roi_artists(notify=True)
            self.canvas.draw_idle()

        def _set_full_height(_event):
            current = self._map_roi_state
            if not current:
                return
            if not current.get("full_h_active", False):
                current["saved_yidx"] = _np.asarray(current["yidx"], dtype=int).copy()
                current["yidx"] = _np.arange(int(current["rows"]), dtype=int)
                current["full_h_active"] = True
            else:
                saved = current.get("saved_yidx")
                if saved is not None and len(saved):
                    current["yidx"] = _np.asarray(saved, dtype=int).copy()
                current["full_h_active"] = False
                current["saved_yidx"] = None
            _style_extent_button(btn_full_h, current["full_h_active"])
            self._update_map_roi_artists(notify=True)
            self.canvas.draw_idle()

        def _pass_roi_to_plotting(_event):
            current = self._map_roi_state
            if not current:
                return
            callback = current.get("pass_callback")
            if callable(callback):
                callback()

        state["style_extent_button"] = _style_extent_button
        if btn_full_w is not None:
            btn_full_w.clicked.connect(_set_full_width)
        if btn_full_h is not None:
            btn_full_h.clicked.connect(_set_full_height)
        if btn_pass_plot is not None:
            btn_pass_plot.clicked.connect(_pass_roi_to_plotting)
        _style_extent_button(btn_full_w, state["full_w_active"])
        _style_extent_button(btn_full_h, state["full_h_active"])

        self._update_map_roi_artists(notify=True)
        self.canvas.draw_idle()
        return used_colors

    def _update_map_roi_artists(self, notify=True):
        state = self._map_roi_state
        if not state:
            return
        import numpy as _np
        xi = _np.asarray(state["xidx"], dtype=int)
        yi = _np.asarray(state["yidx"], dtype=int)
        x = state["x"]
        Z = state["Z"]
        xs = _np.sort(x[xi])
        xstep = float(state["x_step"])
        xl = float(xs[0] - 0.5 * xstep)
        xr = float(xs[-1] + 0.5 * xstep)
        y0 = float(int(yi[0]))
        y1 = float(int(yi[-1]) + 1)
        patch = state["patch"]
        patch.set_x(xl)
        patch.set_y(y0)
        patch.set_width(xr - xl)
        patch.set_height(y1 - y0)

        roi_block = Z[_np.ix_(yi, xi)]
        bottom = _np.nansum(roi_block, axis=0)
        right = _np.nansum(roi_block, axis=1)
        bottom_line = state["bottom_line"]
        right_line = state["right_line"]
        bottom_line.set_data(x[xi], bottom)
        centers = _np.arange(int(state["rows"]), dtype=float) + 0.5
        right_line.set_data(right, centers[yi])
        state["set_bottom_scientific_scale"](bottom)

        # The projection coordinate axes follow the ROI continuously.  Keep
        # the 2D map itself at the full extent; only the two trace axes zoom
        # to the rectangle currently selected.
        ax_bottom = state["ax_bottom"]
        ax_right = state["ax_right"]
        map_x0, map_x1 = state["ax_map"].get_xlim()
        if map_x0 > map_x1:  # reversed binding-energy display
            ax_bottom.set_xlim(xr, xl)
        else:
            ax_bottom.set_xlim(xl, xr)
        ax_right.set_ylim(y0, y1)
        ax_bottom.relim()
        ax_bottom.autoscale_view(scalex=False, scaley=True)
        ax_right.relim()
        ax_right.autoscale_view(scalex=True, scaley=False)

        if notify and callable(state.get("callback")):
            ylabels = state["y_labels"]
            spec = {
                "x_center": float(_np.mean(x[xi])),
                "x_width": float(max(xstep, abs(float(xs[-1] - xs[0])) + xstep)),
                "y_center": float(_np.mean(ylabels[yi])),
                "y_width": float(max(state["y_step"], abs(float(ylabels[yi[-1]] - ylabels[yi[0]])) + state["y_step"])),
                "_full_w_active": bool(state.get("full_w_active", False)),
                "_full_h_active": bool(state.get("full_h_active", False)),
            }
            sx = state.get("saved_xidx")
            if sx is not None and len(sx):
                sx = _np.asarray(sx, dtype=int)
                sxv = _np.sort(x[sx])
                spec["_full_w_saved"] = {
                    "center": float(_np.mean(x[sx])),
                    "width": float(max(xstep, abs(float(sxv[-1] - sxv[0])) + xstep)),
                }
            sy = state.get("saved_yidx")
            if sy is not None and len(sy):
                sy = _np.asarray(sy, dtype=int)
                spec["_full_h_saved"] = {
                    "center": float(_np.mean(ylabels[sy])),
                    "width": float(max(state["y_step"], abs(float(ylabels[sy[-1]] - ylabels[sy[0]])) + state["y_step"])),
                }
            try:
                state["callback"](spec)
            except Exception:
                pass

    def _on_map_roi_press(self, event) -> None:
        button = getattr(getattr(event, "button", None), "value", getattr(event, "button", None))
        if button not in (None, 1):
            return
        if self._map_norm_drag is not None:
            return
        state = self._map_roi_state
        if self._maybe_select_map_right_y_axis(event, state):
            return
        if not state or event.inaxes is not state.get("ax_map") or event.x is None or event.y is None:
            return
        patch = state["patch"]
        ax = state["ax_map"]
        try:
            xl = patch.get_x(); xr = xl + patch.get_width()
            y0 = patch.get_y(); y1 = y0 + patch.get_height()
            pxl = ax.transData.transform((xl, 0))[0]
            pxr = ax.transData.transform((xr, 0))[0]
            py0 = ax.transData.transform((0, y0))[1]
            py1 = ax.transData.transform((0, y1))[1]
            dxl, dxr = abs(event.x-pxl), abs(event.x-pxr)
            dy0, dy1 = abs(event.y-py0), abs(event.y-py1)
            tol = 8.0
            if min(dxl, dxr, dy0, dy1) <= tol:
                dmin = min(dxl, dxr, dy0, dy1)
                if dmin == dxl: mode = "left"
                elif dmin == dxr: mode = "right"
                elif dmin == dy0: mode = "bottom"
                else: mode = "top"
            elif event.xdata is not None and event.ydata is not None and xl <= event.xdata <= xr and y0 <= event.ydata <= y1:
                mode = "move"
            else:
                return
            self._map_roi_drag = {
                "mode": mode, "x0": float(event.xdata), "y0": float(event.ydata),
                "xidx0": state["xidx"].copy(), "yidx0": state["yidx"].copy(),
            }
        except Exception:
            self._map_roi_drag = None

    def _on_map_roi_motion(self, event) -> None:
        self._update_map_hover_tooltip(event)
        state = self._map_roi_state
        drag = self._map_roi_drag
        if not state or not drag or event.inaxes is not state.get("ax_map") or event.xdata is None or event.ydata is None:
            return
        import numpy as _np
        x = state["x"]; rows = state["rows"]
        mode = drag["mode"]
        xi0 = _np.asarray(drag["xidx0"], dtype=int)
        yi0 = _np.asarray(drag["yidx0"], dtype=int)
        if mode in ("left", "right"):
            if state.get("full_w_active", False):
                state["full_w_active"] = False
                state["saved_xidx"] = None
                try:
                    btn = state.get("btn_full_w")
                    styler = state.get("style_extent_button")
                    if btn is not None and callable(styler):
                        styler(btn, False)
                except Exception:
                    pass
            idx = int(_np.nanargmin(_np.abs(x - float(event.xdata))))
            # "left/right" refer to visual X edges, not array-index order;
            # binding-energy axes are commonly stored descending.
            xv0 = x[xi0]
            if mode == "left":
                opposite_value = float(_np.nanmax(xv0))
            else:
                opposite_value = float(_np.nanmin(xv0))
            opposite = int(_np.nanargmin(_np.abs(x - opposite_value)))
            lo, hi = sorted((idx, opposite))
            state["xidx"] = _np.arange(lo, hi + 1, dtype=int)
        elif mode in ("bottom", "top"):
            if state.get("full_h_active", False):
                state["full_h_active"] = False
                state["saved_yidx"] = None
                try:
                    btn = state.get("btn_full_h")
                    styler = state.get("style_extent_button")
                    if btn is not None and callable(styler):
                        styler(btn, False)
                except Exception:
                    pass
            idx = int(_np.clip(_np.floor(float(event.ydata)), 0, rows - 1))
            lo, hi = int(yi0.min()), int(yi0.max())
            if mode == "bottom": lo = min(idx, hi)
            else: hi = max(idx, lo)
            state["yidx"] = _np.arange(lo, hi + 1, dtype=int)
        elif mode == "move":
            # Move by nearest sampled column/row while preserving ROI size.
            start_col = int(_np.nanargmin(_np.abs(x - drag["x0"])))
            now_col = int(_np.nanargmin(_np.abs(x - float(event.xdata))))
            dc = now_col - start_col
            if state.get("full_w_active", False):
                state["xidx"] = _np.arange(int(state["cols"]), dtype=int)
            else:
                n = xi0.size
                lo = int(_np.clip(int(xi0.min()) + dc, 0, state["cols"] - n))
                state["xidx"] = _np.arange(lo, lo + n, dtype=int)
            start_row = int(_np.clip(_np.floor(drag["y0"]), 0, rows - 1))
            now_row = int(_np.clip(_np.floor(float(event.ydata)), 0, rows - 1))
            dr = now_row - start_row
            if state.get("full_h_active", False):
                state["yidx"] = _np.arange(int(rows), dtype=int)
            else:
                nyr = yi0.size
                ylo = int(_np.clip(int(yi0.min()) + dr, 0, rows - nyr))
                state["yidx"] = _np.arange(ylo, ylo + nyr, dtype=int)
        self._update_map_roi_artists(notify=True)
        self.canvas.draw_idle()

    def _on_map_roi_release(self, _event) -> None:
        self._map_roi_drag = None

    def _on_map_cross_press(self, event) -> None:
        button = getattr(getattr(event, "button", None), "value", getattr(event, "button", None))
        if button not in (None, 1):
            return
        if self._map_norm_drag is not None:
            return
        state = self._map_cross_state
        if not state:
            return
        if self._maybe_select_map_right_y_axis(event, state):
            return
        if event.x is None or event.y is None:
            return

        ax_map = state.get("ax_map")
        ax_bottom = state.get("ax_bottom")
        ax_right = state.get("ax_right")

        # The continued guides in the side traces are drag handles too.
        # Bottom trace controls the vertical/X cursor; right trace controls the
        # horizontal/Y cursor.  Use a small screen-space hit tolerance so the
        # behavior is independent of axis units and zoom.
        try:
            if event.inaxes is ax_bottom and event.xdata is not None:
                xpos = float(state["x"][state["col"]])
                px = ax_bottom.transData.transform((xpos, 0.0))[0]
                if abs(float(event.x) - float(px)) <= 8.0:
                    self._map_drag_axis = "x_bottom"
                return
            if event.inaxes is ax_right and event.ydata is not None:
                ypos = float(state["row"]) + 0.5
                py = ax_right.transData.transform((0.0, ypos))[1]
                if abs(float(event.y) - float(py)) <= 8.0:
                    self._map_drag_axis = "y_right"
                return
        except Exception:
            return

        if event.inaxes is not ax_map:
            return
        try:
            vx = ax_map.transData.transform((float(state["x"][state["col"]]), 0.0))[0]
            hy = ax_map.transData.transform((0.0, float(state["row"]) + 0.5))[1]
            dv = abs(float(event.x) - float(vx))
            dh = abs(float(event.y) - float(hy))
        except Exception:
            return

        # Near the H/V intersection, drag both cursors together.  Away from
        # the crossing, retain the established nearest-line behavior.
        if dv <= 10.0 and dh <= 10.0:
            self._map_drag_axis = "both"
        elif dv <= 8.0 or dh <= 8.0:
            self._map_drag_axis = "x" if dv <= dh else "y"

    def _apply_map_lines_trace_scale(self, state=None) -> None:
        """Apply independent Auto/full-dataset limits to H and V live traces."""
        state = state or self._map_cross_state
        if not state:
            return
        ax_bottom = state.get("ax_bottom")
        ax_right = state.get("ax_right")
        if ax_bottom is None or ax_right is None:
            return

        # Compatibility with the pre-0.10.76 combined mode, while making new
        # sessions independently autoscaled by default.
        old_mode = str(getattr(self, "_map_lines_trace_scale_mode", "auto") or "auto")
        default_auto = old_mode != "full"
        auto_h = bool(getattr(self, "_map_lines_auto_scale_h", default_auto))
        auto_v = bool(getattr(self, "_map_lines_auto_scale_v", default_auto))

        lo = hi = None
        if not auto_h or not auto_v:
            try:
                lo = float(state.get("trace_scale_min"))
                hi = float(state.get("trace_scale_max"))
                if not np.isfinite(lo) or not np.isfinite(hi):
                    raise ValueError
                if hi <= lo:
                    pad = max(abs(lo) * 1.0e-6, 1.0e-12)
                    lo, hi = lo - pad, hi + pad
            except Exception:
                lo = hi = None

        if auto_h or lo is None:
            # Explicitly re-enable autoscale after a prior fixed set_ylim().
            ax_bottom.set_autoscaley_on(True)
            ax_bottom.relim()
            ax_bottom.autoscale_view(scalex=False, scaley=True)
        else:
            ax_bottom.set_ylim(lo, hi)
            try:
                state["set_bottom_scientific_scale"](state.get("Z"))
            except Exception:
                pass

        if auto_v or lo is None:
            # Explicitly re-enable autoscale after a prior fixed set_xlim().
            ax_right.set_autoscalex_on(True)
            ax_right.relim()
            ax_right.autoscale_view(scalex=True, scaley=False)
        else:
            ax_right.set_xlim(lo, hi)


    def set_map_lines_cursor_index(self, orientation: str, index: int, *, redraw: bool = True) -> bool:
        """Move a Lines cursor to a sampled index using the manual-drag path.

        ``orientation`` is ``"v"`` for the vertical line (X/column) and
        ``"h"`` for the horizontal line (Y/row).  Animation calls this method
        so profiles, labels, averaging bands and side-trace continuations stay
        exactly synchronized with interactive dragging.
        """
        state = self._map_cross_state
        if not state:
            return False
        try:
            if str(orientation).lower().startswith("v"):
                idx = int(np.clip(int(index), 0, int(state["cols"]) - 1))
                state["col"] = idx
                state["animation_v_position"] = float(idx)
                xpos = float(state["x"][idx])
                state["vline"].set_xdata([xpos, xpos])
                try:
                    state["vline_bottom"].set_xdata([xpos, xpos])
                except Exception:
                    pass
                try:
                    state["vlabel"].set_x(xpos)
                    state["vlabel"].set_text(state["x_cursor_caption"](idx))
                    state["style_cursor_label"](state["vlabel"], state["rows"] - 1, idx)
                    state["keep_cursor_labels_inside"](idx, state["row"])
                except Exception:
                    pass
                values, indices = state["vertical_profile"](idx)
                state["v_indices"] = indices
                try:
                    lo, hi = state["column_span"](indices)
                    state["vband"].set_x(lo)
                    state["vband"].set_width(hi - lo)
                    state["vband_bottom"].set_x(lo)
                    state["vband_bottom"].set_width(hi - lo)
                except Exception:
                    pass
                state["right_line"].set_xdata(values)
                self._apply_map_lines_trace_scale(state)
            else:
                idx = int(np.clip(int(index), 0, int(state["rows"]) - 1))
                state["row"] = idx
                state["animation_h_position"] = float(idx)
                ypos = float(idx) + 0.5
                state["hline"].set_ydata([ypos, ypos])
                try:
                    state["hline_right"].set_ydata([ypos, ypos])
                except Exception:
                    pass
                try:
                    state["hlabel"].set_y(ypos)
                    state["hlabel"].set_text(state["y_cursor_caption"](idx))
                    state["style_cursor_label"](state["hlabel"], idx, state.get("h_contrast_col", 0))
                    state["keep_cursor_labels_inside"](state["col"], idx)
                except Exception:
                    pass
                values, indices = state["horizontal_profile"](idx)
                state["h_indices"] = indices
                try:
                    lo, hi = state["row_span"](indices)
                    state["hband"].set_y(lo)
                    state["hband"].set_height(hi - lo)
                    state["hband_right"].set_y(lo)
                    state["hband_right"].set_height(hi - lo)
                except Exception:
                    pass
                state["bottom_line"].set_ydata(values)
                state["set_bottom_scientific_scale"](values)
                self._apply_map_lines_trace_scale(state)
            self._remember_map_lines_state(state)
            if redraw:
                self.canvas.draw_idle()
            return True
        except Exception:
            return False

    def set_map_lines_cursor_position(self, orientation: str, position: float, *, redraw: bool = True) -> bool:
        """Move a Lines cursor to a fractional sampled position for smooth animation.

        Physical/key animation positions are still separated by the selected
        H/V thickness.  Between them this method linearly interpolates both the
        cursor/band geometry and the neighbouring extracted profiles, producing
        presentation-smooth motion without modifying the stored map data.
        """
        state = self._map_cross_state
        if not state:
            return False
        try:
            is_v = str(orientation).lower().startswith("v")
            total = int(state["cols"] if is_v else state["rows"])
            if total <= 0:
                return False
            pos = float(np.clip(float(position), 0.0, float(total - 1)))
            lo = int(np.floor(pos))
            hi = int(np.ceil(pos))
            alpha = float(pos - lo) if hi != lo else 0.0
            nearest = int(np.clip(int(round(pos)), 0, total - 1))

            def _blend(a, b):
                aa = np.asarray(a, dtype=float)
                bb = np.asarray(b, dtype=float)
                return aa * (1.0 - alpha) + bb * alpha

            if is_v:
                xvals = np.asarray(state["x"], dtype=float)
                xpos = float(xvals[lo] * (1.0 - alpha) + xvals[hi] * alpha)
                state["col"] = nearest
                state["animation_v_position"] = pos
                state["vline"].set_xdata([xpos, xpos])
                try:
                    state["vline_bottom"].set_xdata([xpos, xpos])
                except Exception:
                    pass
                p0, i0 = state["vertical_profile"](lo)
                p1, i1 = state["vertical_profile"](hi)
                values = _blend(p0, p1)
                try:
                    s0 = state["column_span"](i0)
                    s1 = state["column_span"](i1)
                    band_lo = float(s0[0]) * (1.0 - alpha) + float(s1[0]) * alpha
                    band_hi = float(s0[1]) * (1.0 - alpha) + float(s1[1]) * alpha
                    state["vband"].set_x(band_lo)
                    state["vband"].set_width(band_hi - band_lo)
                    state["vband_bottom"].set_x(band_lo)
                    state["vband_bottom"].set_width(band_hi - band_lo)
                except Exception:
                    pass
                try:
                    state["vlabel"].set_x(xpos)
                    state["vlabel"].set_text(state["x_cursor_caption"](nearest))
                    state["style_cursor_label"](state["vlabel"], state["rows"] - 1, nearest)
                    state["keep_cursor_labels_inside"](nearest, state["row"])
                except Exception:
                    pass
                state["right_line"].set_xdata(values)
                self._apply_map_lines_trace_scale(state)
            else:
                ypos = pos + 0.5
                state["row"] = nearest
                state["animation_h_position"] = pos
                state["hline"].set_ydata([ypos, ypos])
                try:
                    state["hline_right"].set_ydata([ypos, ypos])
                except Exception:
                    pass
                p0, i0 = state["horizontal_profile"](lo)
                p1, i1 = state["horizontal_profile"](hi)
                values = _blend(p0, p1)
                try:
                    s0 = state["row_span"](i0)
                    s1 = state["row_span"](i1)
                    band_lo = float(s0[0]) * (1.0 - alpha) + float(s1[0]) * alpha
                    band_hi = float(s0[1]) * (1.0 - alpha) + float(s1[1]) * alpha
                    state["hband"].set_y(band_lo)
                    state["hband"].set_height(band_hi - band_lo)
                    state["hband_right"].set_y(band_lo)
                    state["hband_right"].set_height(band_hi - band_lo)
                except Exception:
                    pass
                try:
                    state["hlabel"].set_y(ypos)
                    state["hlabel"].set_text(state["y_cursor_caption"](nearest))
                    state["style_cursor_label"](
                        state["hlabel"], nearest, state.get("h_contrast_col", 0)
                    )
                    state["keep_cursor_labels_inside"](state["col"], nearest)
                except Exception:
                    pass
                state["bottom_line"].set_ydata(values)
                state["set_bottom_scientific_scale"](values)
                self._apply_map_lines_trace_scale(state)
            self._remember_map_lines_state(state)
            if redraw:
                self.canvas.draw_idle()
            return True
        except Exception:
            return False

    def map_lines_animation_context(self, orientation: str) -> dict[str, Any] | None:
        """Return sampled coordinates and valid full-width animation centres."""
        state = self._map_cross_state
        if not state:
            return None
        try:
            is_v = str(orientation).lower().startswith("v")
            if is_v:
                total = int(state["cols"])
                thickness = int(state.get("v_thickness", 1))
                coords = np.asarray(state["x"], dtype=float).reshape(-1)
                current = int(state.get("col", 0))
                label_low = str(state.get("xlabel") or "").lower()
                if "kinetic" in label_low:
                    coordinate_label, coordinate_unit = "KE", "eV"
                elif "binding" in label_low:
                    coordinate_label, coordinate_unit = "BE", "eV"
                else:
                    coordinate_label, coordinate_unit = str(state.get("xlabel") or "X"), ""
            else:
                total = int(state["rows"])
                thickness = int(state.get("h_thickness", 1))
                current = int(state.get("row", 0))
                use_secondary = (
                    state.get("right_y_mode") == "secondary"
                    and self._has_meaningful_secondary_y(
                        state.get("secondary_y"), str(state.get("secondary_ylabel") or ""), total
                    )
                )
                if use_secondary:
                    coords = np.asarray(state.get("secondary_y"), dtype=float).reshape(-1)
                    label = self._right_y_display_label(str(state.get("secondary_ylabel") or ""))
                    coordinate_label = label.replace(" [eV]", "")
                    coordinate_unit = "eV" if "[eV]" in label else ""
                else:
                    try:
                        coords = np.asarray(state.get("y_labels"), dtype=float).reshape(-1)
                    except Exception:
                        coords = np.arange(1, total + 1, dtype=float)
                    coordinate_label, coordinate_unit = "Iteration", ""
            thickness = max(1, min(25, thickness))
            half = (thickness - 1) // 2
            first = half
            last = total - 1 - half
            if last < first:
                return None
            return {
                "orientation": "v" if is_v else "h",
                "coordinates": coords.tolist(),
                "coordinate_label": coordinate_label,
                "coordinate_unit": coordinate_unit,
                "title": str(state.get("title") or "MAP"),
                "thickness": thickness,
                "current_index": current,
                "valid_indices": list(range(first, last + 1)),
            }
        except Exception:
            return None

    def _on_map_cross_motion(self, event) -> None:
        self._update_map_hover_tooltip(event)
        state = self._map_cross_state
        drag = self._map_drag_axis
        if not state or not drag:
            return
        import numpy as _np

        ax_map = state.get("ax_map")
        ax_bottom = state.get("ax_bottom")
        ax_right = state.get("ax_right")

        if drag == "x_bottom":
            if event.inaxes is not ax_bottom or event.xdata is None:
                return
            idx = int(_np.nanargmin(_np.abs(state["x"] - float(event.xdata))))
            if idx != state["col"]:
                self.set_map_lines_cursor_index("v", idx, redraw=True)
            return

        if drag == "y_right":
            if event.inaxes is not ax_right or event.ydata is None:
                return
            idx = int(_np.clip(_np.floor(float(event.ydata)), 0, state["rows"] - 1))
            if idx != state["row"]:
                self.set_map_lines_cursor_index("h", idx, redraw=True)
            return

        if event.inaxes is not ax_map:
            return

        if drag in ("x", "both") and event.xdata is not None:
            idx = int(_np.nanargmin(_np.abs(state["x"] - float(event.xdata))))
            if idx != state["col"]:
                # When moving both, postpone the draw until H has also updated.
                self.set_map_lines_cursor_index("v", idx, redraw=(drag != "both"))
        if drag in ("y", "both") and event.ydata is not None:
            idx = int(_np.clip(_np.floor(float(event.ydata)), 0, state["rows"] - 1))
            if idx != state["row"]:
                self.set_map_lines_cursor_index("h", idx, redraw=True)
            elif drag == "both":
                # V may have changed even when H stayed on the same sampled row.
                self.canvas.draw_idle()

    def update_map_lines_averaging(self, h_thickness=1, v_thickness=1) -> None:
        """Update displayed Lines profiles after H/V averaging-width changes."""
        state = self._map_cross_state
        if not state:
            return
        try:
            def _odd(value):
                value = max(1, min(25, int(value)))
                return value if value % 2 else min(25, value + 1)

            state["h_thickness"] = _odd(h_thickness)
            state["v_thickness"] = _odd(v_thickness)

            # Rebind the closures because their original local thickness values
            # are immutable integers.  Keep the same symmetric-edge behavior.
            Z = state["Z"]
            rows, cols = int(state["rows"]), int(state["cols"])
            def _indices(center, requested, total):
                half_req = (_odd(requested) - 1) // 2
                half = min(half_req, int(center), int(total) - 1 - int(center))
                return np.arange(int(center) - half, int(center) + half + 1, dtype=int)

            def _h(row):
                idx = _indices(row, state["h_thickness"], rows)
                return np.nanmean(Z[idx, :], axis=0), idx

            def _v(col):
                idx = _indices(col, state["v_thickness"], cols)
                return np.nanmean(Z[:, idx], axis=1), idx

            state["horizontal_profile"] = _h
            state["vertical_profile"] = _v
            bottom, hi = _h(int(state["row"]))
            right, vi = _v(int(state["col"]))
            state["h_indices"], state["v_indices"] = hi, vi
            try:
                hlo, hhi = state["row_span"](hi)
                state["hband"].set_y(hlo)
                state["hband"].set_height(hhi - hlo)
                state["hband_right"].set_y(hlo)
                state["hband_right"].set_height(hhi - hlo)
                show_h_band = state["h_thickness"] > 1
                state["hband"].set_visible(show_h_band)
                state["hband_right"].set_visible(show_h_band)
                vlo, vhi = state["column_span"](vi)
                state["vband"].set_x(vlo)
                state["vband"].set_width(vhi - vlo)
                state["vband_bottom"].set_x(vlo)
                state["vband_bottom"].set_width(vhi - vlo)
                show_v_band = state["v_thickness"] > 1
                state["vband"].set_visible(show_v_band)
                state["vband_bottom"].set_visible(show_v_band)
            except Exception:
                pass
            state["bottom_line"].set_ydata(bottom)
            state["right_line"].set_xdata(right)
            state["set_bottom_scientific_scale"](bottom)
            self._apply_map_lines_trace_scale(state)
            self.canvas.draw_idle()
        except Exception:
            return

    def _on_map_cross_release(self, _event) -> None:
        self._map_drag_axis = None


    # ------------------------------------------------------------------
    # ResPES cut analysis (Simple view only)
    # ------------------------------------------------------------------
    @staticmethod
    def _respes_trace_values(
        x_arr, hv_arr, Z_arr, cut_type, position, width, work_function=4.5,
        source_axis="be",
    ):
        """Return intensity(hν) for finite-width constant-BE or constant-KE cuts.

        ``x_arr`` may be either the measured BE or KE coordinate.  The requested
        physical cut is converted row by row to that source coordinate using
        ``KE = hν - BE - Φ``.
        """
        x_arr = np.asarray(x_arr, dtype=float).reshape(-1)
        hv_arr = np.asarray(hv_arr, dtype=float).reshape(-1)
        Z_arr = np.asarray(Z_arr, dtype=float)
        half = 0.5 * max(float(width or 0.0), 0.0)
        phi = float(work_function)
        source_axis = "ke" if str(source_axis).lower() == "ke" else "be"
        out = np.full(hv_arr.shape, np.nan, dtype=float)
        for i, hv in enumerate(hv_arr):
            same_axis = ((source_axis == "be" and cut_type == "constant_be") or
                         (source_axis == "ke" and cut_type == "constant_ke"))
            target = (float(position) if same_axis
                      else float(hv) - phi - float(position))
            if target < float(np.nanmin(x_arr)) or target > float(np.nanmax(x_arr)):
                continue
            if half > 0:
                mask = np.isfinite(x_arr) & (np.abs(x_arr - target) <= half)
            else:
                mask = np.zeros_like(x_arr, dtype=bool)
            if np.any(mask):
                vals = Z_arr[i, :x_arr.size][mask]
                if np.any(np.isfinite(vals)):
                    out[i] = float(np.nanmean(vals))
                    continue
            # For a cut narrower than the sampling grid, interpolate rather than
            # silently snapping to one detector channel.
            try:
                order = np.argsort(x_arr)
                xs = x_arr[order]
                ys = Z_arr[i, :x_arr.size][order]
                good = np.isfinite(xs) & np.isfinite(ys)
                if np.count_nonzero(good) >= 2:
                    out[i] = float(np.interp(target, xs[good], ys[good]))
            except Exception:
                pass
        return out

    @staticmethod
    def _respes_constant_hv_trace(x_arr, hv_arr, Z_arr, position, width):
        """Return spectrum intensity(E) for a finite-width constant-photon-energy cut."""
        x_arr = np.asarray(x_arr, dtype=float).reshape(-1)
        hv_arr = np.asarray(hv_arr, dtype=float).reshape(-1)
        Z_arr = np.asarray(Z_arr, dtype=float)
        if Z_arr.ndim == 1:
            Z_arr = Z_arr.reshape(1, -1)
        cols = min(x_arr.size, Z_arr.shape[1])
        x_arr = x_arr[:cols]
        Z_arr = Z_arr[:, :cols]
        if hv_arr.size != Z_arr.shape[0] or cols == 0:
            return np.full(x_arr.shape, np.nan, dtype=float)
        half = 0.5 * max(float(width or 0.0), 0.0)
        if half > 0:
            mask = np.isfinite(hv_arr) & (np.abs(hv_arr - float(position)) <= half)
        else:
            mask = np.zeros(hv_arr.shape, dtype=bool)
        if np.any(mask):
            return np.nanmean(Z_arr[mask, :], axis=0)

        # If the requested width is narrower than the photon-energy sampling,
        # interpolate each energy channel along hν rather than snapping to a row.
        out = np.full(cols, np.nan, dtype=float)
        order = np.argsort(hv_arr)
        hs = hv_arr[order]
        for j in range(cols):
            ys = Z_arr[:, j][order]
            good = np.isfinite(hs) & np.isfinite(ys)
            if np.count_nonzero(good) >= 2:
                lo, hi = float(hs[good][0]), float(hs[good][-1])
                if lo <= float(position) <= hi:
                    out[j] = float(np.interp(float(position), hs[good], ys[good]))
        return out

    @staticmethod
    def _respes_map_to_ke(x_be, hv_arr, Z_arr, work_function=4.5):
        """Return a rectangular KE-grid representation without modifying source data.

        Each photon-energy row has its own KE coordinates.  Rows are interpolated
        only along their measured energy coordinate onto a common *union* KE grid;
        regions not measured in a given row remain NaN.  This preserves the full
        measured map instead of cropping to the much smaller common-overlap range.
        """
        x_be = np.asarray(x_be, dtype=float).reshape(-1)
        hv_arr = np.asarray(hv_arr, dtype=float).reshape(-1)
        Z_arr = np.asarray(Z_arr, dtype=float)
        if Z_arr.ndim == 1:
            Z_arr = Z_arr.reshape(1, -1)
        cols = min(x_be.size, Z_arr.shape[1])
        x_be = x_be[:cols]
        Z_arr = Z_arr[:, :cols]
        if x_be.size < 2 or hv_arr.size != Z_arr.shape[0]:
            return np.asarray([], dtype=float), np.empty((0, 0), dtype=float)
        diffs = np.abs(np.diff(np.sort(x_be[np.isfinite(x_be)])))
        diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        step = float(np.nanmedian(diffs)) if diffs.size else 0.1
        phi = float(work_function)
        ke_min = float(np.nanmin(hv_arr) - phi - np.nanmax(x_be))
        ke_max = float(np.nanmax(hv_arr) - phi - np.nanmin(x_be))
        if not np.isfinite(ke_min) or not np.isfinite(ke_max) or ke_max <= ke_min:
            return np.asarray([], dtype=float), np.empty((0, 0), dtype=float)
        n = int(np.floor((ke_max - ke_min) / max(step, 1e-12))) + 1
        n = max(2, min(n, 10000))
        ke_grid = np.linspace(ke_min, ke_max, n)
        out = np.full((hv_arr.size, n), np.nan, dtype=float)
        for i, hv in enumerate(hv_arr):
            ke_row = float(hv) - phi - x_be
            vals = Z_arr[i, :]
            good = np.isfinite(ke_row) & np.isfinite(vals)
            if np.count_nonzero(good) < 2:
                continue
            order = np.argsort(ke_row[good])
            xs = ke_row[good][order]
            ys = vals[good][order]
            inside = (ke_grid >= xs[0]) & (ke_grid <= xs[-1])
            out[i, inside] = np.interp(ke_grid[inside], xs, ys)
        return ke_grid, out

    @staticmethod
    def _respes_map_to_be(x_ke, hv_arr, Z_arr, work_function=4.5):
        """Return a rectangular BE-grid representation of a measured KE map.

        This is the inverse counterpart of :meth:`_respes_map_to_ke`.  Because
        BE = hν - KE - Φ, each photon-energy row is interpolated only along its
        measured energy coordinate onto a common union BE grid.
        """
        x_ke = np.asarray(x_ke, dtype=float).reshape(-1)
        hv_arr = np.asarray(hv_arr, dtype=float).reshape(-1)
        Z_arr = np.asarray(Z_arr, dtype=float)
        if Z_arr.ndim == 1:
            Z_arr = Z_arr.reshape(1, -1)
        cols = min(x_ke.size, Z_arr.shape[1])
        x_ke = x_ke[:cols]
        Z_arr = Z_arr[:, :cols]
        if x_ke.size < 2 or hv_arr.size != Z_arr.shape[0]:
            return np.asarray([], dtype=float), np.empty((0, 0), dtype=float)
        diffs = np.abs(np.diff(np.sort(x_ke[np.isfinite(x_ke)])))
        diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        step = float(np.nanmedian(diffs)) if diffs.size else 0.1
        phi = float(work_function)
        be_min = float(np.nanmin(hv_arr) - phi - np.nanmax(x_ke))
        be_max = float(np.nanmax(hv_arr) - phi - np.nanmin(x_ke))
        if not np.isfinite(be_min) or not np.isfinite(be_max) or be_max <= be_min:
            return np.asarray([], dtype=float), np.empty((0, 0), dtype=float)
        n = int(np.floor((be_max - be_min) / max(step, 1e-12))) + 1
        n = max(2, min(n, 10000))
        be_grid = np.linspace(be_min, be_max, n)
        out = np.full((hv_arr.size, n), np.nan, dtype=float)
        for i, hv in enumerate(hv_arr):
            be_row = float(hv) - phi - x_ke
            vals = Z_arr[i, :]
            good = np.isfinite(be_row) & np.isfinite(vals)
            if np.count_nonzero(good) < 2:
                continue
            order = np.argsort(be_row[good])
            xs = be_row[good][order]
            ys = vals[good][order]
            inside = (be_grid >= xs[0]) & (be_grid <= xs[-1])
            out[i, inside] = np.interp(be_grid[inside], xs, ys)
        return be_grid, out

    @staticmethod
    def _respes_source_energy_axis(xlabel):
        """Return ``be``/``ke`` from the measured map X label."""
        low = str(xlabel or "").lower()
        if "kinetic" in low or " ke" in f" {low}":
            return "ke"
        return "be"

    def _draw_respes_cut(self, ax, x_arr, hv_arr, rows, cut_type, position, width,
                         trace_ax, trace_line, callback=None, energy_axis="be",
                         work_function=4.5, source_x=None, source_Z=None,
                         source_axis="be", display_Z=None, trace_x_label=""):
        half = 0.5 * max(float(width or 0.0), 0.0)
        centers = np.arange(rows, dtype=float) + 0.5
        hv = np.asarray(hv_arr, dtype=float)
        phi = float(work_function)

        def hv_to_y(value):
            order = np.argsort(hv)
            return float(np.interp(float(value), hv[order], centers[order]))

        if cut_type == "constant_hv":
            position = float(np.clip(float(position), np.nanmin(hv), np.nanmax(hv)))
            low_hv = max(float(np.nanmin(hv)), position - half)
            high_hv = min(float(np.nanmax(hv)), position + half)
            yc, yl, yh = hv_to_y(position), hv_to_y(low_hv), hv_to_y(high_hv)
            patch = ax.axhspan(min(yl, yh), max(yl, yh), alpha=0.12, zorder=5.1,
                               edgecolor="none", facecolor="tab:red")
            center_line = ax.axhline(yc, linestyle="-", linewidth=1.35,
                                     color="tab:red", alpha=0.95, zorder=5.4)
            low_line = ax.axhline(yl, linestyle="--", linewidth=1.0,
                                  color="tab:red", alpha=0.8, zorder=5.3)
            high_line = ax.axhline(yh, linestyle="--", linewidth=1.0,
                                   color="tab:red", alpha=0.8, zorder=5.3)
            x_for_label = float(np.nanmax(x_arr))
            label = ax.text(x_for_label, yc, "hν cut", color="tab:red", fontsize=8,
                            ha="right", va="bottom", zorder=5.5, clip_on=True)
        else:
            same_axis = ((energy_axis == "be" and cut_type == "constant_be") or
                         (energy_axis == "ke" and cut_type == "constant_ke"))
            if same_axis:
                center_x = np.full(rows, float(position), dtype=float)
            else:
                center_x = hv - phi - float(position)
            label_text = "KE cut" if cut_type == "constant_ke" else "BE cut"
            low_x = center_x - half
            high_x = center_x + half
            patch = ax.fill_betweenx(centers, low_x, high_x, alpha=0.12, zorder=5.1,
                                     edgecolor="none", facecolor="tab:red")
            center_line = ax.plot(center_x, centers, linestyle="-", linewidth=1.35,
                                  color="tab:red", alpha=0.95, zorder=5.4)[0]
            low_line = ax.plot(low_x, centers, linestyle="--", linewidth=1.0,
                               color="tab:red", alpha=0.8, zorder=5.3)[0]
            high_line = ax.plot(high_x, centers, linestyle="--", linewidth=1.0,
                                color="tab:red", alpha=0.8, zorder=5.3)[0]
            label = ax.text(center_x[-1], centers[-1], label_text, color="tab:red",
                            fontsize=8, ha="center", va="bottom", zorder=5.5, clip_on=True)

        self._respes_cut_state = {
            "ax": ax, "event_axes": {ax}, "x": np.asarray(x_arr, dtype=float),
            "hv": hv, "rows": int(rows), "type": str(cut_type),
            "position": float(position), "width": float(width or 0.0), "centers": centers,
            "patch": patch, "center_line": center_line, "low_line": low_line,
            "high_line": high_line, "label": label, "trace_ax": trace_ax,
            "trace_line": trace_line, "callback": callback, "energy_axis": str(energy_axis),
            "work_function": phi, "trace_x_label": str(trace_x_label or ""),
            "source_x": np.asarray(source_x if source_x is not None else x_arr, dtype=float),
            "source_axis": "ke" if str(source_axis).lower() == "ke" else "be",
            "source_Z": np.asarray(source_Z if source_Z is not None else np.empty((0, 0)), dtype=float),
            "display_Z": np.asarray(display_Z if display_Z is not None else np.empty((0, 0)), dtype=float),
        }

    def _update_respes_cut_artists(self, position, width, notify=True):
        state = self._respes_cut_state
        if not state:
            return
        position = float(position); width = max(0.0, float(width))
        half = 0.5 * width
        hv = state["hv"]; centers = state["centers"]
        state["position"], state["width"] = position, width
        if state["type"] == "constant_hv":
            order = np.argsort(hv)
            def hv_to_y(value):
                return float(np.interp(float(value), hv[order], centers[order]))
            position = float(np.clip(position, np.nanmin(hv), np.nanmax(hv)))
            state["position"] = position
            lo_hv = max(float(np.nanmin(hv)), position - half)
            hi_hv = min(float(np.nanmax(hv)), position + half)
            yc, yl, yh = hv_to_y(position), hv_to_y(lo_hv), hv_to_y(hi_hv)
            state["center_line"].set_ydata([yc, yc])
            state["low_line"].set_ydata([yl, yl])
            state["high_line"].set_ydata([yh, yh])
            try: state["patch"].remove()
            except Exception: pass
            state["patch"] = state["ax"].axhspan(min(yl, yh), max(yl, yh), alpha=0.12,
                                                   zorder=5.1, edgecolor="none", facecolor="tab:red")
            state["label"].set_position((float(np.nanmax(state["x"])), yc))
            trace = self._respes_constant_hv_trace(
                state["x"], hv, state.get("display_Z", np.empty((0, 0))),
                position, width,
            )
            state["trace_line"].set_data(state["x"], trace)
            state["trace_ax"].relim(); state["trace_ax"].autoscale_view(scalex=False, scaley=True)
        else:
            same_axis = ((state.get("energy_axis", "be") == "be" and state["type"] == "constant_be") or
                         (state.get("energy_axis", "be") == "ke" and state["type"] == "constant_ke"))
            center_x = (np.full(state["rows"], position, dtype=float) if same_axis
                        else hv - float(state.get("work_function", 4.5)) - position)
            low_x, high_x = center_x - half, center_x + half
            state["center_line"].set_data(center_x, centers)
            state["low_line"].set_data(low_x, centers)
            state["high_line"].set_data(high_x, centers)
            try: state["patch"].remove()
            except Exception: pass
            state["patch"] = state["ax"].fill_betweenx(
                centers, low_x, high_x, alpha=0.12, zorder=5.1, edgecolor="none", facecolor="tab:red")
            state["label"].set_position((float(center_x[-1]), float(centers[-1])))
            trace = self._respes_trace_values(
                state.get("source_x", state["x"]), hv,
                state.get("source_Z", np.empty((0, 0))), state["type"], position, width,
                state.get("work_function", 4.5), source_axis=state.get("source_axis", "be"),
            )
            state["trace_line"].set_data(hv, trace)
            state["trace_ax"].relim(); state["trace_ax"].autoscale_view(scalex=False, scaley=True)
        if notify and callable(state.get("callback")):
            try: state["callback"](position, width, False)
            except Exception: pass

    def _on_respes_cut_press(self, event):
        button = getattr(getattr(event, "button", None), "value", getattr(event, "button", None))
        if button not in (None, 1):
            return
        state = self._respes_cut_state
        if not state or getattr(self, "_map_norm_drag", None) is not None:
            return
        if event.inaxes not in state.get("event_axes", {state.get("ax")}) or event.x is None or event.y is None or event.xdata is None or event.ydata is None:
            return
        try:
            pos = float(state["position"]); width = float(state["width"]); ax = state["ax"]
            tol = 8.0
            if state["type"] == "constant_hv":
                hv = np.asarray(state["hv"], dtype=float); centers = np.asarray(state["centers"], dtype=float)
                order = np.argsort(hv)
                def hv_to_y(value): return float(np.interp(float(value), hv[order], centers[order]))
                yc = hv_to_y(pos); yl = hv_to_y(pos - 0.5 * width); yh = hv_to_y(pos + 0.5 * width)
                pc = ax.transData.transform((float(event.xdata), yc))[1]
                pl = ax.transData.transform((float(event.xdata), yl))[1]
                ph = ax.transData.transform((float(event.xdata), yh))[1]
                dl, dh, dc = abs(float(event.y)-pl), abs(float(event.y)-ph), abs(float(event.y)-pc)
                if min(dl, dh) <= tol: mode = "edge"
                elif dc <= max(tol, abs(ph-pl)/2.0 + 2.0): mode = "move"
                else: return
                y_now = float(event.ydata)
                hv_now = float(np.interp(y_now, centers[order], hv[order]))
                self._respes_cut_drag = {"mode": mode, "hv0": hv_now, "position0": pos, "width0": width}
                return

            row = int(np.clip(np.floor(float(event.ydata)), 0, state["rows"] - 1))
            hv_row = float(state["hv"][row])
            same_axis = ((state.get("energy_axis", "be") == "be" and state["type"] == "constant_be") or
                         (state.get("energy_axis", "be") == "ke" and state["type"] == "constant_ke"))
            center = pos if same_axis else hv_row - float(state.get("work_function", 4.5)) - pos
            low, high = center - 0.5 * width, center + 0.5 * width
            px = float(event.x)
            pc = ax.transData.transform((center, float(event.ydata)))[0]
            pl = ax.transData.transform((low, float(event.ydata)))[0]
            ph = ax.transData.transform((high, float(event.ydata)))[0]
            dl, dh, dc = abs(px-pl), abs(px-ph), abs(px-pc)
            if min(dl, dh) <= tol: mode = "edge"
            elif dc <= max(tol, abs(ph-pl)/2.0 + 2.0): mode = "move"
            else: return
            self._respes_cut_drag = {"mode": mode, "x0": float(event.xdata), "position0": pos,
                                     "width0": width, "row0": row}
        except Exception:
            self._respes_cut_drag = None

    def _on_respes_cut_motion(self, event):
        state, drag = self._respes_cut_state, self._respes_cut_drag
        if not state or not drag or event.inaxes not in state.get("event_axes", {state.get("ax")}):
            return
        try:
            if state["type"] == "constant_hv":
                if event.ydata is None: return
                hv = np.asarray(state["hv"], dtype=float); centers = np.asarray(state["centers"], dtype=float)
                order = np.argsort(centers)
                hv_now = float(np.interp(float(event.ydata), centers[order], hv[order]))
                if drag["mode"] == "move":
                    position = float(drag["position0"]) + hv_now - float(drag["hv0"])
                    position = float(np.clip(position, np.nanmin(hv), np.nanmax(hv)))
                    width = float(drag["width0"])
                else:
                    position = float(state["position"]); width = 2.0 * abs(hv_now - position)
                self._update_respes_cut_artists(position, width, notify=True)
                self.canvas.draw_idle(); return

            if event.xdata is None: return
            dx = float(event.xdata) - float(drag["x0"])
            same_axis = ((state.get("energy_axis", "be") == "be" and state["type"] == "constant_be") or
                         (state.get("energy_axis", "be") == "ke" and state["type"] == "constant_ke"))
            if drag["mode"] == "move":
                position = float(drag["position0"]) + dx if same_axis else float(drag["position0"]) - dx
                width = float(drag["width0"])
            else:
                row = int(np.clip(np.floor(float(event.ydata if event.ydata is not None else drag["row0"])), 0, state["rows"]-1))
                hv_row = float(state["hv"][row])
                center = (float(state["position"]) if same_axis else
                          hv_row - float(state.get("work_function", 4.5)) - float(state["position"]))
                width = 2.0 * abs(float(event.xdata) - center); position = float(state["position"])
            self._update_respes_cut_artists(position, width, notify=True)
            self.canvas.draw_idle()
        except Exception:
            pass

    def _on_respes_cut_release(self, _event):
        state, drag = self._respes_cut_state, self._respes_cut_drag
        self._respes_cut_drag = None
        if not state or not drag:
            return
        callback = state.get("callback")
        if callable(callback):
            try:
                callback(float(state["position"]), float(state["width"]), True)
            except Exception:
                pass

    def _plot_single_map_with_respes(
        self, payloads, image, flip_binding_energy, colors,
        cut_type="constant_be", position=None, width=None, cut_callback=None,
        energy_axis="be", work_function=4.5,
        norm_interval=None, norm_mode=None, norm_callback=None,
    ):
        """Render Simple ResPES map plus a dedicated intensity-vs-photon-energy cut trace."""
        try:
            self.fig.set_layout_engine(None)
        except Exception:
            try: self.fig.set_constrained_layout(False)
            except Exception: pass
        self.fig.clear()
        x, y, Z, title, xlabel = image[:5]
        cmap = image[5] if len(image) >= 6 else None
        x_arr = np.asarray(x, dtype=float).reshape(-1)
        Z_arr = np.asarray(Z, dtype=float)
        if Z_arr.ndim == 1: Z_arr = Z_arr.reshape(1, -1)
        elif Z_arr.ndim > 2: Z_arr = Z_arr.reshape(Z_arr.shape[0], -1)
        rows, cols = Z_arr.shape
        cols = min(cols, x_arr.size); Z_arr = Z_arr[:, :cols]; x_arr = x_arr[:cols]
        try:
            y_labels = np.asarray([float(v) for v in y], dtype=float)
            if y_labels.size != rows: raise ValueError
        except Exception:
            y_labels = np.arange(1, rows+1, dtype=float)
        secondary_y, secondary_ylabel = self._map_secondary_axis(image, rows)
        if secondary_y is None or "photon" not in secondary_ylabel.lower():
            # Defensive fallback; availability logic should prevent this path.
            secondary_y = np.arange(rows, dtype=float)
            secondary_ylabel = "Photon Energy [eV]"

        source_x = x_arr.copy()
        source_Z = Z_arr.copy()
        source_axis = self._respes_source_energy_axis(xlabel)
        energy_axis = "ke" if str(energy_axis).lower() == "ke" else "be"
        x_arr, Z_arr = source_x, source_Z
        if energy_axis != source_axis:
            if source_axis == "be" and energy_axis == "ke":
                display_x, display_Z = self._respes_map_to_ke(source_x, secondary_y, source_Z, work_function)
            else:
                display_x, display_Z = self._respes_map_to_be(source_x, secondary_y, source_Z, work_function)
            if display_x.size >= 2 and display_Z.shape[0] == rows:
                x_arr, Z_arr = display_x, display_Z
            else:
                energy_axis = source_axis
                x_arr, Z_arr = source_x, source_Z
        xlabel = "Kinetic Energy [eV]" if energy_axis == "ke" else "Binding Energy [eV]"

        gs = self.fig.add_gridspec(
            2, 1, height_ratios=(4.0, 1.35), left=0.125, right=0.875,
            bottom=0.13, top=0.94, hspace=0.20,
        )
        ax_map = self.fig.add_subplot(gs[0, 0]); self.ax = ax_map
        ax_trace = self.fig.add_subplot(gs[1, 0])
        ax_iteration = ax_map.twinx()
        map_image = ax_map.imshow(Z_arr, aspect="auto", origin="lower",
                      extent=[float(x_arr[0]), float(x_arr[-1]), 0.0, float(rows)], cmap=cmap)
        self._disable_map_artist_cursor_data(map_image)
        ax_map.set_title(title)
        # Unlike generic Lines/ROI, the lower ResPES panel uses photon energy
        # rather than the map X coordinate.  Therefore the map must keep its
        # own Binding-Energy scale visible.
        ax_map.set_xlabel(xlabel)
        ax_map.tick_params(axis="x", labelbottom=True)
        self._configure_map_y_axes(ax_map, ax_iteration, rows, y_labels,
                                   secondary_y, secondary_ylabel)
        self._set_map_coordinate_formatter(
            [ax_map, ax_iteration], x_arr, rows, xlabel, y_labels,
            secondary_y, secondary_ylabel, Z_arr,
        )
        ax_iteration.patch.set_visible(False)
        # twinx() otherwise becomes the topmost event-receiving Axes.  Keep the
        # image/cut Axes above it (with a transparent patch) so cut and
        # normalization dragging work in ResPES Simple view.
        try:
            ax_map.set_zorder(ax_iteration.get_zorder() + 1)
            ax_map.patch.set_visible(False)
        except Exception:
            pass

        if norm_interval is not None and energy_axis == source_axis:
            # The normalization interval is defined on the measured source X
            # coordinate.  After BE<->KE conversion that same source interval
            # becomes photon-energy dependent, so do not draw it as an incorrect
            # vertical band.  The normalized intensities are already present in Z.
            self._draw_map_normalization_band(ax_map, norm_interval, norm_mode, norm_callback)

        xlo, xhi = float(np.nanmin(x_arr)), float(np.nanmax(x_arr))
        if energy_axis == "be" and flip_binding_energy:
            ax_map.set_xlim(xhi, xlo)
        else:
            ax_map.set_xlim(xlo, xhi)

        if position is None:
            if cut_type == "constant_be":
                position = (float(np.nanmedian(source_x)) if source_axis == "be" else
                            float(np.nanmedian(secondary_y) - np.nanmedian(source_x) - float(work_function)))
            elif cut_type == "constant_ke":
                position = (float(np.nanmedian(source_x)) if source_axis == "ke" else
                            float(np.nanmedian(secondary_y) - np.nanmedian(source_x) - float(work_function)))
            else:
                position = float(np.nanmedian(secondary_y))
        if width is None:
            base = secondary_y if cut_type == "constant_hv" else x_arr
            diffs = np.abs(np.diff(np.sort(np.asarray(base, dtype=float))))
            width = max(float(np.nanmedian(diffs)) if diffs.size else 0.1, 0.01 if cut_type == "constant_hv" else 0.1)
        if cut_type == "constant_hv":
            trace = self._respes_constant_hv_trace(x_arr, secondary_y, Z_arr, position, width)
            trace_line = ax_trace.plot(x_arr, trace, linewidth=1.3)[0]
            ax_trace.set_xlabel(xlabel)
            if x_arr.size > 1:
                if energy_axis == "be" and flip_binding_energy:
                    ax_trace.set_xlim(float(np.nanmax(x_arr)), float(np.nanmin(x_arr)))
                else:
                    ax_trace.set_xlim(float(np.nanmin(x_arr)), float(np.nanmax(x_arr)))
        else:
            trace = self._respes_trace_values(
                source_x, secondary_y, source_Z, cut_type, position, width,
                work_function, source_axis=source_axis,
            )
            trace_line = ax_trace.plot(secondary_y, trace, linewidth=1.3)[0]
            ax_trace.set_xlabel(secondary_ylabel)
            ax_trace.set_xlim(float(np.nanmin(secondary_y)), float(np.nanmax(secondary_y)))
        ax_trace.set_ylabel("Intensity")
        ax_trace.grid(True, linewidth=1.0, alpha=0.4)
        try:
            fmt = ScalarFormatter(useMathText=True); fmt.set_scientific(True); fmt.set_powerlimits((0,0))
            ax_trace.yaxis.set_major_formatter(fmt)
        except Exception:
            pass
        self._draw_respes_cut(
            ax_map, x_arr, secondary_y, rows, cut_type, position, width,
            ax_trace, trace_line, cut_callback, energy_axis=energy_axis,
            work_function=work_function, source_x=source_x, source_Z=source_Z,
            source_axis=source_axis, display_Z=Z_arr, trace_x_label=xlabel,
        )
        self._respes_cut_state["Z"] = Z_arr
        self._respes_cut_state["title"] = str(title)
        self._respes_cut_state["event_axes"] = {ax_map, ax_iteration}
        self.canvas.draw_idle()
        return []
