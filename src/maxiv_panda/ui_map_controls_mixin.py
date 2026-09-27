from __future__ import annotations

"""State and actions for the Processed Data 2D-map control strip.

The widget construction remains with the Processed Data tab, but the sizeable
normalization/ROI/export workflow is isolated here from unrelated 1D controls.
"""

from PyQt6.QtCore import Qt, QLocale
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDoubleSpinBox, QFormLayout, QLabel,
    QPushButton, QHBoxLayout, QVBoxLayout, QWidget, QGroupBox,
)
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox


class UiMapControlsMixin:
    def _sync_map_analysis_control_visibility(self) -> tuple[bool, bool]:
        """Apply the Simple/Lines/ROI control-strip visibility contract.

        This is intentionally separate from the redraw handler because PANDA
        sometimes changes the hidden radio-button state programmatically with
        signals blocked (for example, when a fresh Processed Data map starts in
        Simple view).  Keeping visibility synchronization callable on its own
        prevents controls from the previously active map representation from
        leaking into the new one.
        """
        roi_active = bool(getattr(self, "rb_map_roi", None) and self.rb_map_roi.isChecked())
        lines_active = bool(getattr(self, "rb_map_lines", None) and self.rb_map_lines.isChecked())

        roi_controls = getattr(self, "_map_roi_controls", None)
        if roi_controls is not None:
            roi_controls.setVisible(roi_active)

        trace_controls = getattr(self, "_map_trace_add_controls", None)
        if trace_controls is not None:
            trace_controls.setVisible(lines_active or roi_active)

        bin_controls = getattr(self, "_map_lines_binning_controls", None)
        if bin_controls is not None:
            bin_controls.setVisible(lines_active)

        return lines_active, roi_active

    def _on_map_analysis_mode_changed(self, _checked=False) -> None:
        # Radio-button switches emit one False and one True signal; redraw only
        # for the newly activated mode.
        if not bool(_checked):
            return
        try:
            self.plot_area.reset_map_palette_hint_visit()
        except Exception:
            pass
        lines_active, roi_active = self._sync_map_analysis_control_visibility()
        if not lines_active:
            dlg = getattr(self, "_map_animation_dialog", None)
            if dlg is not None:
                try:
                    dlg.close()
                except Exception:
                    pass
                self._map_animation_dialog = None

        # On the first Lines -> ROI transition, start at the current crosshair
        # position.  PlotArea will fill in sensible default widths and clamp
        # everything to the actual map bounds.
        if roi_active and getattr(self, "_map_roi_spec", None) is None:
            try:
                state = getattr(self.plot_area, "_map_cross_state", None)
                if state:
                    y_labels = state.get("y_labels", [])
                    row = int(state.get("row", 0))
                    y_center = float(y_labels[row]) if row < len(y_labels) else float(row + 1)
                    self._map_roi_spec = {
                        "x_center": float(state["x"][int(state.get("col", 0))]),
                        "y_center": y_center,
                    }
            except Exception:
                self._map_roi_spec = None
        self._update_respes_availability()
        self._update_plot_from_selected()

    def _on_map_lines_binning_changed(self, *_args) -> None:
        """Redraw the Lines map when its batch-style binning settings change."""
        self._update_plot_from_selected()

    @staticmethod
    def _odd_map_line_thickness(value: int) -> int:
        """Clamp a requested Lines averaging thickness to 1, 3, ..., 25."""
        value = max(1, min(25, int(value)))
        if value % 2 == 0:
            value = min(25, value + 1)
        return value

    def _normalize_map_lines_thickness_spin(self, spin, orientation: str) -> None:
        """Reject typed even values while keeping QSpinBox keyboard entry convenient."""
        try:
            value = self._odd_map_line_thickness(spin.value())
            if int(spin.value()) != value:
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
            self._on_map_lines_thickness_value_changed(orientation)
        except Exception:
            return

    def _on_map_lines_thickness_value_changed(self, _orientation: str = "") -> None:
        """Update Lines profiles immediately without rebuilding the 2D map."""
        try:
            h = self._odd_map_line_thickness(self.sb_map_h_thickness.value())
            v = self._odd_map_line_thickness(self.sb_map_v_thickness.value())
            updater = getattr(self.plot_area, "update_map_lines_averaging", None)
            if callable(updater):
                updater(h, v)
            dlg = getattr(self, "_map_animation_dialog", None)
            if dlg is not None:
                try:
                    dlg.external_thickness_changed()
                except Exception:
                    pass
        except Exception:
            return

    def _open_map_lines_animation_dialog(self) -> None:
        """Open (or raise) the non-modal MAP -> Lines animation controller."""
        try:
            if not (getattr(self, "rb_map_lines", None) and self.rb_map_lines.isChecked()):
                return
            state = getattr(self.plot_area, "_map_cross_state", None)
            if not state:
                return
            dlg = getattr(self, "_map_animation_dialog", None)
            if dlg is None:
                from .widgets.map_animation_dialog import MapAnimationDialog
                dlg = MapAnimationDialog(
                    self,
                    context_provider=self.plot_area.map_lines_animation_context,
                    move_callback=lambda line, position: self.plot_area.set_map_lines_cursor_position(
                        line, position, redraw=True
                    ),
                    video_export_callback=self._export_map_lines_video,
                )
                dlg.finished.connect(self._on_map_animation_dialog_closed)
                self._map_animation_dialog = dlg
            else:
                try:
                    dlg.refresh_context(stop=False, preserve_custom=True)
                except Exception:
                    pass
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            return

    def _on_map_animation_dialog_closed(self, *_args) -> None:
        self._map_animation_dialog = None

    def _export_map_lines_video(
        self, path: str, segments, fps: int, progress_callback
    ) -> tuple[bool, str]:
        """Render the current Lines Matplotlib figure to an H.264 MP4 file.

        The frame source is the existing Matplotlib canvas, so the exported
        area is exactly the figure that the toolbar's Save figure action would
        save: the 2D map plus both side traces, excluding Qt overlay controls.

        ``segments`` is a sequence of dictionaries.  Each segment describes one
        H or V sweep with keys such as ``orientation``, ``positions``,
        ``cycle_numbers``, ``cycles`` and ``label``.  This allows combined
        exports such as H then V to be written into a single MP4.
        """
        import os
        import shutil
        import subprocess

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return False, (
                "FFmpeg was not found. Install it in the active conda environment, for example:\n\n"
                "conda install -c conda-forge ffmpeg"
            )
        segments = [dict(seg) for seg in (segments or []) if seg]
        if not segments:
            return False, "No animation frames are available."
        fps = max(1, int(fps))
        plot_area = getattr(self, "plot_area", None)
        canvas = getattr(plot_area, "canvas", None)
        if plot_area is None or canvas is None:
            return False, "The Lines plot is not available."

        state = getattr(plot_area, "_map_cross_state", None) or {}
        restore_h = float(state.get("animation_h_position", int(state.get("row", 0))))
        restore_v = float(state.get("animation_v_position", int(state.get("col", 0))))
        proc = None
        canceled = False
        total = sum(len(list(seg.get("positions", []))) for seg in segments)
        if total <= 0:
            return False, "No animation frames are available."
        try:
            first_seg = segments[0]
            first_positions = [float(v) for v in (first_seg.get("positions") or [])]
            first_orientation = str(first_seg.get("orientation") or "h")
            if not first_positions:
                return False, "No animation frames are available."
            plot_area.set_map_lines_cursor_position(first_orientation, first_positions[0], redraw=False)
            canvas.draw()
            rgba = canvas.buffer_rgba()
            try:
                height, width = int(rgba.shape[0]), int(rgba.shape[1])
            except Exception:
                width, height = canvas.get_width_height()
            if width <= 0 or height <= 0:
                return False, "Could not determine the video frame size."

            cmd = [
                ffmpeg, "-y", "-loglevel", "error",
                "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgba",
                "-s", f"{int(width)}x{int(height)}", "-r", str(fps), "-i", "-",
                "-an", "-vcodec", "libx264", "-preset", "medium", "-crf", "18",
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(path),
            ]
            kwargs = {
                "stdin": subprocess.PIPE,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.PIPE,
            }
            if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(cmd, **kwargs)

            global_frame = 0
            for seg in segments:
                orientation = str(seg.get("orientation") or "h")
                positions = [float(v) for v in (seg.get("positions") or [])]
                cycle_numbers = [int(v) for v in (seg.get("cycle_numbers") or [])]
                cycles = max(1, int(seg.get("cycles", 1)))
                label = str(seg.get("label") or ("H" if orientation.lower().startswith("h") else "V"))
                for local_frame, position in enumerate(positions, start=1):
                    cycle_no = cycle_numbers[min(local_frame - 1, len(cycle_numbers) - 1)] if cycle_numbers else 1
                    if not progress_callback(global_frame, label, cycle_no, cycles):
                        canceled = True
                        break
                    plot_area.set_map_lines_cursor_position(orientation, position, redraw=False)
                    canvas.draw()
                    frame = bytes(canvas.buffer_rgba())
                    if proc.stdin is None:
                        raise RuntimeError("FFmpeg input pipe is unavailable.")
                    proc.stdin.write(frame)
                    global_frame += 1
                    if not progress_callback(global_frame, label, cycle_no, cycles):
                        canceled = True
                        break
                if canceled:
                    break

            if canceled:
                if proc.stdin is not None:
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except Exception:
                    proc.kill()
                    proc.wait()
                try:
                    os.remove(path)
                except OSError:
                    pass
                return False, "Canceled"

            if proc.stdin is not None:
                proc.stdin.close()
            stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            code = proc.wait()
            if code != 0:
                try:
                    os.remove(path)
                except OSError:
                    pass
                return False, stderr.strip() or f"FFmpeg exited with code {code}."
            return True, ""
        except Exception as exc:
            if proc is not None:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:
                    pass
            try:
                os.remove(path)
            except OSError:
                pass
            return False, str(exc)
        finally:
            try:
                plot_area.set_map_lines_cursor_position("h", restore_h, redraw=False)
                plot_area.set_map_lines_cursor_position("v", restore_v, redraw=True)
            except Exception:
                pass

    def _map_lines_binning_active(self) -> bool:
        """Return whether Lines-view binning changes the displayed rows."""
        try:
            return int(self.sb_map_bin_size.value()) > 1
        except Exception:
            return False

    def _apply_map_lines_binning(self, images):
        """Apply consecutive complete-bin averaging to Lines-view map rows.

        The operation is display/analysis-only, exactly like map normalization:
        stored 1D spectra and the Simple/ROI map views are left untouched.
        """
        from .map_binning import bin_map_image

        images = list(images or [])
        info = getattr(self, "lab_map_binning_info", None)
        spin = getattr(self, "sb_map_bin_size", None)
        if not images:
            if info is not None:
                info.clear()
                info.setVisible(False)
            return images

        total_rows = 0
        for image in images:
            try:
                import numpy as np
                Z = np.asarray(image[2])
                total_rows += int(Z.shape[0]) if Z.ndim >= 2 else 1
            except Exception:
                pass

        # Keep the same practical constraint as batch fitting: bin size cannot
        # exceed the number of currently selected/effective source spectra.
        if spin is not None:
            maximum = max(1, int(total_rows))
            try:
                spin.blockSignals(True)
                spin.setMaximum(maximum)
                if spin.value() > maximum:
                    spin.setValue(maximum)
            finally:
                spin.blockSignals(False)

        if not self._map_lines_binning_active():
            if info is not None:
                info.clear()
                info.setVisible(False)
            return images

        bin_size = max(1, int(self.sb_map_bin_size.value()))
        out = []
        effective_total = 0
        discarded_total = 0
        for image in images:
            binned, original, effective, discarded = bin_map_image(tuple(image), bin_size)
            if effective > 0:
                out.append(binned)
            effective_total += int(effective)
            discarded_total += int(discarded)
        if info is not None:
            # Preserve the established user-facing status text.  The QLabel is
            # given an Ignored horizontal size policy when it is constructed so
            # this changing text cannot increase the main window minimum width
            # (important on macOS); it simply uses whatever row space is free.
            info.setText(
                f"{total_rows} → {effective_total} binned"
                + (f" (+{discarded_total} discarded)" if discarded_total else "")
            )
            info.setVisible(True)
        return out

    def _current_map_normalization_mode(self) -> str:
        combo = getattr(self, "cb_map_normalization", None)
        if combo is None:
            return "none"
        try:
            return str(combo.currentData() or "none")
        except Exception:
            return "none"

    def _map_axis_defaults(self) -> tuple[float | None, float | None, float | None, float | None]:
        """Return (reference BE, axis low, axis high, default width in eV)."""
        try:
            selection = self._plot_selection_controller.collect_selection()
            if not selection.images:
                return None, None, None, None
            import numpy as np
            image = selection.images[0]
            x = np.asarray(image[0], dtype=float)
            x = x[np.isfinite(x)]
            if x.size < 2:
                return None, None, None, None
            low = float(np.min(x)); high = float(np.max(x))
            diffs = np.abs(np.diff(np.sort(x)))
            diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
            step = float(np.median(diffs)) if diffs.size else max(high - low, 1.0)
            width = min(max(step, 0.01 * max(high - low, step)), max(high - low, step))
            xlabel = str(image[4] if len(image) > 4 else "")
            # Keep the established intent of normalizing at an energy edge, but
            # centre the absolute-width interval just inside that edge so the
            # complete requested range is genuinely present in the spectrum.
            if "kinetic" in xlabel.lower():
                default = high - 0.5 * width
            else:
                default = low + 0.5 * width
            return float(default), low, high, float(width)
        except Exception:
            return None, None, None, None

    def _map_normalization_context_key(self):
        """Return a stable identity for the currently displayed map dataset.

        The key deliberately uses the source file/region rather than only the
        energy limits.  Two datasets can have identical axes but must still
        receive their own normalization defaults.  Changing the subset of
        checked iterations within the same dataset does not reset the settings.
        """
        try:
            regions = []
            for i in range(self.selected_tree.topLevelItemCount()):
                region_item = self.selected_tree.topLevelItem(i)
                if region_item is None or region_item.isHidden():
                    continue
                region_name = str(region_item.data(0, self.ROLE_REGION) or region_item.text(0))
                file_name = region_item.data(0, self.ROLE_FILE)
                region_key = (file_name, region_name) if isinstance(file_name, str) else None
                btn = self._region_map_buttons.get(region_key) if region_key is not None else None
                if btn is None or not btn.isChecked():
                    continue
                has_checked_iteration = False
                for j in range(region_item.childCount()):
                    ch = region_item.child(j)
                    if ch is None or ch.isHidden() or ch.checkState(0) != Qt.CheckState.Checked:
                        continue
                    meta = ch.data(0, self.ROLE_META)
                    if isinstance(meta, dict) and isinstance(meta.get("iteration"), int):
                        has_checked_iteration = True
                        break
                if has_checked_iteration:
                    regions.append((str(file_name or ""), region_name))
            return tuple(regions) if regions else None
        except Exception:
            return None

    def _remember_map_norm_dialog_position(self) -> None:
        """Remember the normalization editor position for later reopening."""
        dialog = getattr(self, "_map_norm_dialog", None)
        if dialog is None:
            return
        try:
            self._map_norm_dialog_pos = dialog.pos()
        except Exception:
            pass

    def _hide_map_normalization_dialog(self) -> None:
        """Hide the normalization editor without losing the user's placement."""
        dialog = getattr(self, "_map_norm_dialog", None)
        if dialog is None:
            return
        self._remember_map_norm_dialog_position()
        dialog.hide()

    def _restore_map_norm_dialog_position(self) -> None:
        """Restore the last user-selected editor position, if one is known."""
        dialog = getattr(self, "_map_norm_dialog", None)
        pos = getattr(self, "_map_norm_dialog_pos", None)
        if dialog is None or pos is None:
            return
        try:
            dialog.move(pos)
        except Exception:
            pass

    def _reset_map_normalization_context(self, *, close_dialog: bool = False) -> None:
        """Forget dataset-specific map-normalization defaults/settings."""
        self._map_norm_context_key = None
        self._map_norm_be = None
        self._map_norm_width_ev = None
        self._map_norm_area_low = None
        self._map_norm_area_high = None
        self._map_norm_active_interval = None
        self._map_norm_show_region = True
        if close_dialog:
            dialog = getattr(self, "_map_norm_dialog", None)
            if dialog is not None and dialog.isVisible():
                self._hide_map_normalization_dialog()

    def _ensure_map_normalization_defaults(self) -> None:
        context_key = self._map_normalization_context_key()
        previous_key = getattr(self, "_map_norm_context_key", None)
        # A changed map selection is a new normalization context.  Re-seed all
        # defaults from that dataset instead of carrying values from the old one.
        if context_key != previous_key:
            self._map_norm_context_key = context_key
            self._map_norm_be = None
            self._map_norm_width_ev = None
            self._map_norm_area_low = None
            self._map_norm_area_high = None
            self._map_norm_active_interval = None
            self._map_norm_show_region = True
        default_be, low, high, default_width = self._map_axis_defaults()
        if context_key is None:
            return
        if default_be is not None and self._map_norm_be is None:
            self._map_norm_be = float(default_be)
        if default_width is not None and self._map_norm_width_ev is None:
            self._map_norm_width_ev = float(default_width)
        if low is not None and high is not None:
            if self._map_norm_area_low is None:
                self._map_norm_area_low = float(low)
            if self._map_norm_area_high is None:
                self._map_norm_area_high = float(high)

    def _current_map_norm_interval(self) -> tuple[float, float] | None:
        mode = self._current_map_normalization_mode()
        try:
            if mode == "at_be":
                if self._map_norm_be is None or self._map_norm_width_ev is None:
                    return None
                half = 0.5 * abs(float(self._map_norm_width_ev))
                return float(self._map_norm_be) - half, float(self._map_norm_be) + half
            if mode == "area":
                if self._map_norm_area_low is None or self._map_norm_area_high is None:
                    return None
                return tuple(sorted((float(self._map_norm_area_low), float(self._map_norm_area_high))))
        except Exception:
            return None
        return None

    def _on_map_normalization_changed(self, _index: int = -1) -> None:
        self._map_norm_mode = self._current_map_normalization_mode()
        self._ensure_map_normalization_defaults()
        dialog = getattr(self, "_map_norm_dialog", None)
        if self._map_norm_mode == "none":
            # None has no configurable parameters.  If a normalization editor
            # is open, close it instead of rebuilding it into an empty dialog.
            if dialog is not None and dialog.isVisible():
                self._hide_map_normalization_dialog()
        elif dialog is not None and dialog.isVisible():
            self._populate_map_normalization_dialog()
        self._update_plot_from_selected()
        # Selecting a normalization method is itself an intent to configure it.
        # Open the corresponding non-modal editor immediately.
        if self._map_norm_mode != "none":
            self._show_map_normalization_settings()


    def _on_map_normalization_activated(self, _index: int = -1) -> None:
        """Reopen settings when the current non-None normalization entry is chosen."""
        if self._current_map_normalization_mode() != "none":
            self._show_map_normalization_settings()

    def _show_map_normalization_settings(self) -> None:
        if self._current_map_normalization_mode() == "none":
            return
        self._ensure_map_normalization_defaults()
        if self._map_norm_dialog is None:
            dialog = QDialog(self)
            dialog.setModal(False)
            dialog.setMinimumWidth(390)
            self._map_norm_dialog = dialog
            # Also remember placement when the title-bar close button is used.
            dialog.finished.connect(lambda _result: self._remember_map_norm_dialog_position())
        self._populate_map_normalization_dialog()
        self._restore_map_norm_dialog_position()
        self._map_norm_dialog.show()
        self._restore_map_norm_dialog_position()
        self._map_norm_dialog.raise_()
        self._map_norm_dialog.activateWindow()

    def _populate_map_normalization_dialog(self) -> None:
        dialog = getattr(self, "_map_norm_dialog", None)
        if dialog is None:
            return
        old = dialog.layout()
        if old is not None:
            def _clear_layout(layout) -> None:
                # Recursively remove every widget from the old dialog layout.
                # In particular, the bottom button row is itself a nested
                # QHBoxLayout; clearing only top-level widgets leaves its
                # Reset/Close buttons alive and they can reappear at stale
                # geometry when the dialog is repopulated.
                while layout.count():
                    item = layout.takeAt(0)
                    child_layout = item.layout()
                    if child_layout is not None:
                        _clear_layout(child_layout)
                        child_layout.deleteLater()
                        continue
                    widget = item.widget()
                    if widget is not None:
                        widget.hide()
                        widget.setParent(None)
                        widget.deleteLater()

            _clear_layout(old)
            QWidget().setLayout(old)

        mode = self._current_map_normalization_mode()
        title = "Normalization at binding energy" if mode == "at_be" else "Area normalization"
        dialog.setWindowTitle(title)
        root = QVBoxLayout(dialog)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(9)

        _default_be, axis_low, axis_high, _default_width = self._map_axis_defaults()
        if axis_low is not None and axis_high is not None:
            available = QLabel(f"Available energy range:  {axis_low:g} – {axis_high:g} eV", dialog)
            available.setStyleSheet("color: palette(mid);")
            root.addWidget(available)

        form_holder = QWidget(dialog)
        form = QFormLayout(form_holder)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        c_locale = QLocale.c()

        def spin(value: float, decimals: int = 3, suffix: str = " eV") -> QDoubleSpinBox:
            sb = QDoubleSpinBox(dialog)
            sb.setLocale(c_locale)
            sb.setDecimals(decimals)
            sb.setRange(-1.0e9, 1.0e9)
            sb.setKeyboardTracking(False)
            sb.setSingleStep(0.1)
            sb.setValue(float(value))
            sb.setSuffix(suffix)
            sb.setMinimumWidth(135)
            return sb

        if mode == "at_be":
            be = spin(float(self._map_norm_be if self._map_norm_be is not None else 0.0))
            width = spin(float(self._map_norm_width_ev if self._map_norm_width_ev is not None else 1.0))
            width.setRange(1.0e-9, 1.0e9)
            be.setToolTip("Centre energy of the normalization interval.")
            width.setToolTip("Absolute averaging width in eV.")
            form.addRow("Reference BE:", be)
            form.addRow("Averaging width:", width)
            self._map_norm_dialog_be = be
            self._map_norm_dialog_width = width
            be.valueChanged.connect(lambda value: self._set_map_norm_parameter("be", value))
            width.valueChanged.connect(lambda value: self._set_map_norm_parameter("width", value))
            description = QLabel(
                "Each spectrum is divided by its mean intensity within the selected energy interval.", dialog
            )
        elif mode == "area":
            low = spin(float(self._map_norm_area_low if self._map_norm_area_low is not None else 0.0))
            high = spin(float(self._map_norm_area_high if self._map_norm_area_high is not None else 0.0))
            low.setToolTip("Lower energy limit used for the row area.")
            high.setToolTip("Upper energy limit used for the row area.")
            form.addRow("From:", low)
            form.addRow("To:", high)
            self._map_norm_dialog_area_low = low
            self._map_norm_dialog_area_high = high
            low.valueChanged.connect(lambda value: self._set_map_norm_parameter("area_low", value))
            high.valueChanged.connect(lambda value: self._set_map_norm_parameter("area_high", value))
            description = QLabel(
                "Each spectrum is divided by its integrated intensity within the selected energy interval.", dialog
            )
        else:
            root.addWidget(QLabel("No normalization settings are required.", dialog))
            return

        root.addWidget(form_holder)
        self._map_norm_dialog_actual = QLabel(dialog)
        self._map_norm_dialog_actual.setStyleSheet("font-weight: 600;")
        root.addWidget(self._map_norm_dialog_actual)
        description.setWordWrap(True)
        description.setStyleSheet("color: palette(mid);")
        root.addWidget(description)

        show_region = QCheckBox("Show normalization range on map", dialog)
        show_region.setChecked(bool(self._map_norm_show_region))
        show_region.toggled.connect(self._on_map_norm_show_region_changed)
        self._map_norm_dialog_show_region = show_region
        root.addWidget(show_region)

        buttons = QHBoxLayout()
        reset = QPushButton("Reset", dialog)
        reset.setToolTip("Restore the default normalization settings for the current map.")
        close = QPushButton("Close", dialog)
        # Do not let Return/Enter in a QDoubleSpinBox activate one of the
        # dialog push buttons.  The spin box must be free to commit typed
        # values without accidentally invoking Reset (Qt auto-default).
        for button in (reset, close):
            button.setAutoDefault(False)
            button.setDefault(False)
        close.clicked.connect(self._hide_map_normalization_dialog)
        reset.clicked.connect(self._reset_map_normalization_settings)
        buttons.addWidget(reset)
        buttons.addStretch(1)
        buttons.addWidget(close)
        root.addLayout(buttons)
        self._refresh_map_norm_dialog_summary()

    def _refresh_map_norm_dialog_summary(self) -> None:
        label = getattr(self, "_map_norm_dialog_actual", None)
        if label is None:
            return
        interval = self._current_map_norm_interval()
        if interval is None:
            label.setText("Actual range: unavailable")
            return
        low, high = interval
        if self._current_map_normalization_mode() == "area":
            label.setText(f"Selected range:  {low:g} – {high:g} eV    (width {high-low:g} eV)")
        else:
            label.setText(f"Actual range:  {low:g} – {high:g} eV")

    def _restore_map_norm_dialog_value(self, key: str, value: float) -> None:
        """Restore one normalization editor without firing its callback again."""
        attr = {
            "be": "_map_norm_dialog_be",
            "width": "_map_norm_dialog_width",
            "area_low": "_map_norm_dialog_area_low",
            "area_high": "_map_norm_dialog_area_high",
        }.get(key)
        widget = getattr(self, attr, None) if attr else None
        if widget is None:
            return
        widget.blockSignals(True)
        try:
            widget.setValue(float(value))
        finally:
            widget.blockSignals(False)
        self._refresh_map_norm_dialog_summary()

    def _validate_map_norm_candidate(self, key: str, value: float) -> tuple[bool, str]:
        """Validate a prospective map-normalization setting before committing it."""
        import numpy as np
        from .workflows.normalization.logic import (
            normalize_map_rows_at_energy, normalize_map_rows_by_area,
        )

        be = float(self._map_norm_be if self._map_norm_be is not None else 0.0)
        width = float(self._map_norm_width_ev if self._map_norm_width_ev is not None else 0.0)
        area_low = float(self._map_norm_area_low if self._map_norm_area_low is not None else 0.0)
        area_high = float(self._map_norm_area_high if self._map_norm_area_high is not None else 0.0)
        if key == "be":
            be = float(value)
        elif key == "width":
            width = float(value)
        elif key == "area_low":
            area_low = float(value)
        elif key == "area_high":
            area_high = float(value)

        try:
            selection = self._plot_selection_controller.collect_selection()
            images = list(selection.images or [])
            if not images:
                return False, "No 2D map spectra are currently available."

            mode = self._current_map_normalization_mode()
            for image in images:
                x = np.asarray(image[0], dtype=float)
                z = np.asarray(image[2], dtype=float)
                finite_x = x[np.isfinite(x)]
                if finite_x.size < 2:
                    raise ValueError("The map energy axis is unavailable.")
                xmin = float(np.min(finite_x))
                xmax = float(np.max(finite_x))

                if mode == "at_be":
                    if not (xmin <= be <= xmax):
                        raise ValueError(
                            f"The normalization BE must lie within the spectral range "
                            f"{xmin:g} to {xmax:g} eV."
                        )
                    if width <= 0.0:
                        raise ValueError("The averaging width must be greater than zero.")
                    lo = be - 0.5 * width
                    hi = be + 0.5 * width
                    if lo < xmin or hi > xmax:
                        raise ValueError(
                            f"The complete averaging interval ({lo:g} to {hi:g} eV) must lie "
                            f"within the spectral range {xmin:g} to {xmax:g} eV."
                        )
                    normalize_map_rows_at_energy(x, z, be, width)
                elif mode == "area":
                    lo, hi = sorted((area_low, area_high))
                    if lo < xmin or hi > xmax:
                        raise ValueError(
                            f"Both area limits must lie within the spectral range "
                            f"{xmin:g} to {xmax:g} eV."
                        )
                    if hi <= lo:
                        raise ValueError("The area-normalization range must have a non-zero width.")
                    normalize_map_rows_by_area(x, z, area_low, area_high)
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def _set_map_norm_parameter(self, key: str, value: float) -> None:
        old_values = {
            "be": float(self._map_norm_be if self._map_norm_be is not None else 0.0),
            "width": float(self._map_norm_width_ev if self._map_norm_width_ev is not None else 0.0),
            "area_low": float(self._map_norm_area_low if self._map_norm_area_low is not None else 0.0),
            "area_high": float(self._map_norm_area_high if self._map_norm_area_high is not None else 0.0),
        }
        valid, message = self._validate_map_norm_candidate(key, float(value))
        if not valid:
            QMessageBox.warning(
                self, "Invalid normalization range",
                f"The requested normalization setting cannot be used:\n{message}\n\n"
                "The previous valid setting has been restored.",
                QMessageBox.StandardButton.Ok,
            )
            self._restore_map_norm_dialog_value(key, old_values[key])
            return

        if key == "be":
            self._map_norm_be = float(value)
        elif key == "width":
            self._map_norm_width_ev = float(value)
        elif key == "area_low":
            self._map_norm_area_low = float(value)
        elif key == "area_high":
            self._map_norm_area_high = float(value)
        self._refresh_map_norm_dialog_summary()
        self._update_plot_from_selected()

    def _on_map_norm_band_changed_from_plot(self, interval, final: bool = False) -> None:
        """Synchronize an interactively edited normalization band with the GUI."""
        mode = self._current_map_normalization_mode()
        if mode not in {"at_be", "area"} or interval is None:
            return
        try:
            low, high = sorted((float(interval[0]), float(interval[1])))
            if not high > low:
                return
            if mode == "at_be":
                be = 0.5 * (low + high)
                width = high - low
                self._map_norm_be = be
                self._map_norm_width_ev = width
                updates = (("_map_norm_dialog_be", be), ("_map_norm_dialog_width", width))
            else:
                self._map_norm_area_low = low
                self._map_norm_area_high = high
                updates = (("_map_norm_dialog_area_low", low), ("_map_norm_dialog_area_high", high))
            for attr, value in updates:
                widget = getattr(self, attr, None)
                if widget is not None:
                    widget.blockSignals(True)
                    try:
                        widget.setValue(float(value))
                    finally:
                        widget.blockSignals(False)
            self._refresh_map_norm_dialog_summary()
            # During the drag only the band/dialog are updated, so the mouse
            # interaction remains continuous.  Recompute the normalized map
            # once on release using the final interval.
            if final:
                self._update_plot_from_selected()
        except Exception:
            return

    def _on_map_norm_show_region_changed(self, checked: bool) -> None:
        self._map_norm_show_region = bool(checked)
        self._update_plot_from_selected()

    def _reset_map_normalization_settings(self) -> None:
        default_be, low, high, default_width = self._map_axis_defaults()
        mode = self._current_map_normalization_mode()
        if mode == "at_be" and default_be is not None and default_width is not None:
            self._map_norm_be = float(default_be)
            self._map_norm_width_ev = float(default_width)
        elif mode == "area" and low is not None and high is not None:
            self._map_norm_area_low = float(low)
            self._map_norm_area_high = float(high)
        self._map_norm_show_region = True
        self._populate_map_normalization_dialog()
        self._update_plot_from_selected()

    def _apply_map_normalization(self, images):
        """Return display-only normalized map images for Processed Data."""
        mode = self._current_map_normalization_mode()
        self._map_norm_active_interval = None
        if mode == "none" or not images:
            return images
        self._ensure_map_normalization_defaults()
        from .workflows.normalization.logic import (
            normalize_map_rows_at_energy, normalize_map_rows_by_area,
        )
        import numpy as np
        normalized = []
        active_interval = None
        try:
            for image in images:
                x, y, Z, title, xlabel = image[:5]
                cmap = image[5] if len(image) > 5 else "terrain"
                Z_arr = np.asarray(Z, dtype=float)
                if mode == "at_be":
                    if self._map_norm_be is None or self._map_norm_width_ev is None:
                        raise ValueError("No normalization energy interval is available.")
                    Z_new, interval = normalize_map_rows_at_energy(
                        np.asarray(x, dtype=float), Z_arr, float(self._map_norm_be),
                        float(self._map_norm_width_ev),
                    )
                elif mode == "area":
                    if self._map_norm_area_low is None or self._map_norm_area_high is None:
                        raise ValueError("No area-normalization interval is available.")
                    Z_new = normalize_map_rows_by_area(
                        np.asarray(x, dtype=float), Z_arr,
                        float(self._map_norm_area_low), float(self._map_norm_area_high),
                    )
                    interval = tuple(sorted((float(self._map_norm_area_low), float(self._map_norm_area_high))))
                else:
                    Z_new = Z_arr
                    interval = None
                if active_interval is None and interval is not None:
                    active_interval = tuple(interval)
                # Preserve any map metadata beyond the core six fields.  In
                # particular, resonant-PES maps carry the physical second-
                # dimension values and label as fields 7/8 (e.g. photon
                # energy).  Rebuilding a six-tuple here used to silently drop
                # that metadata whenever map normalization was active.
                normalized.append((x, y, Z_new, title, xlabel, cmap, *image[6:]))
        except Exception as exc:
            QMessageBox.warning(
                self, "Map normalization not applied",
                f"The selected map normalization could not be applied:\n{exc}\n\n"
                "The normalization mode has been kept unchanged.",
                QMessageBox.StandardButton.Ok,
            )
            return images
        self._map_norm_active_interval = active_interval
        return normalized

    def _on_map_roi_numeric_changed(self) -> None:
        if not bool(getattr(self, "rb_map_roi", None) and self.rb_map_roi.isChecked()):
            return
        previous = dict(getattr(self, "_map_roi_spec", None) or {})
        spec = {
            "x_center": float(self.sb_map_roi_x_center.value()),
            "x_width": float(self.sb_map_roi_x_width.value()),
            "y_center": float(self.sb_map_roi_y_center.value()),
            "y_width": float(self.sb_map_roi_y_width.value()),
        }
        # Preserve an active full-extent toggle when the user edits only the
        # orthogonal dimension.  Editing X explicitly releases Full width;
        # editing Y explicitly releases Full height.
        sender = self.sender()
        x_widgets = (self.sb_map_roi_x_center, self.sb_map_roi_x_width)
        y_widgets = (self.sb_map_roi_y_center, self.sb_map_roi_y_width)
        if sender not in x_widgets:
            for key in ("_full_w_active", "_full_w_saved"):
                if key in previous:
                    spec[key] = previous[key]
        if sender not in y_widgets:
            for key in ("_full_h_active", "_full_h_saved"):
                if key in previous:
                    spec[key] = previous[key]
        self._map_roi_spec = spec
        # A numerical edit is infrequent; rebuilding the map makes validation
        # and snapping identical to the mouse path.
        self._update_plot_from_selected()

    def _on_map_roi_changed_from_plot(self, spec: dict) -> None:
        """Synchronise ROI spin boxes after plot creation or mouse dragging."""
        if not spec:
            return
        self._map_roi_spec = dict(spec)
        widgets = (
            (getattr(self, "sb_map_roi_x_center", None), spec.get("x_center")),
            (getattr(self, "sb_map_roi_x_width", None), spec.get("x_width")),
            (getattr(self, "sb_map_roi_y_center", None), spec.get("y_center")),
            (getattr(self, "sb_map_roi_y_width", None), spec.get("y_width")),
        )
        for widget, value in widgets:
            if widget is None or value is None:
                continue
            try:
                widget.blockSignals(True)
                widget.setValue(float(value))
            finally:
                widget.blockSignals(False)


    def _pass_map_roi_to_plotting(self) -> None:
        """Pass the spectra inside the current MAP ROI to Plotted Data.

        The ROI is a true two-dimensional selection: its Y extent selects which
        source spectra are copied, while its X extent truncates every copied
        spectrum.  Intensities are taken from the currently displayed map so an
        active map-normalization mode is preserved.  Source spectra themselves
        are never modified.
        """
        import copy
        import numpy as np

        state = getattr(getattr(self, "plot_area", None), "_map_roi_state", None)
        if not state:
            QMessageBox.information(
                self, "No ROI", "Select a ROI in MAP view first.",
                QMessageBox.StandardButton.Ok,
            )
            return

        try:
            xi = np.asarray(state.get("xidx", []), dtype=int)
            yi = np.asarray(state.get("yidx", []), dtype=int)
            x_map = np.asarray(state.get("x", []), dtype=float)
            z_map = np.asarray(state.get("Z", []), dtype=float)
        except Exception:
            xi = yi = np.asarray([], dtype=int)
            x_map = np.asarray([], dtype=float)
            z_map = np.asarray([], dtype=float)

        if (
            xi.size == 0 or yi.size == 0 or x_map.size == 0 or z_map.ndim != 2
            or np.any(xi < 0) or np.any(xi >= x_map.size)
            or np.any(yi < 0) or np.any(yi >= z_map.shape[0])
        ):
            QMessageBox.information(
                self, "Empty ROI", "The current ROI does not contain plottable data.",
                QMessageBox.StandardButton.Ok,
            )
            return

        # Reconstruct the row-to-tree-item order exactly as collect_selection()
        # builds a MAP: checked iterations sorted by their iteration number.
        map_rows = []
        region_item_for_rows = None
        for i in range(self.selected_tree.topLevelItemCount()):
            region_item = self.selected_tree.topLevelItem(i)
            if region_item is None:
                continue
            try:
                if region_item.isHidden():
                    continue
            except Exception:
                pass
            region_name = str(region_item.data(0, self.ROLE_REGION) or region_item.text(0))
            file_name = region_item.data(0, self.ROLE_FILE)
            region_key = (file_name, region_name) if isinstance(file_name, str) else None
            button = self._region_map_buttons.get(region_key) if region_key is not None else None
            try:
                map_enabled = bool(button is not None and button.isChecked())
            except Exception:
                map_enabled = False
            if not map_enabled:
                continue

            rows_here = []
            for j in range(region_item.childCount()):
                item = region_item.child(j)
                if item is None:
                    continue
                try:
                    if item.isHidden() or item.checkState(0) != Qt.CheckState.Checked:
                        continue
                except Exception:
                    continue
                meta = item.data(0, self.ROLE_META)
                if not isinstance(meta, dict):
                    continue
                iteration = meta.get("iteration")
                if isinstance(iteration, int):
                    rows_here.append((iteration, item))
            rows_here.sort(key=lambda entry: entry[0])
            if rows_here:
                map_rows = rows_here
                region_item_for_rows = region_item
                break

        if not map_rows or int(np.max(yi)) >= len(map_rows):
            QMessageBox.warning(
                self, "ROI could not be passed",
                "The displayed map rows could not be matched to the selected spectra.",
                QMessageBox.StandardButton.Ok,
            )
            return

        from .workflows.plotting.model import source_aware_curve_title

        x_roi = np.asarray(x_map[xi], dtype=float).copy()
        derived_payloads = []
        x_min = float(np.nanmin(x_roi))
        x_max = float(np.nanmax(x_roi))
        for map_row_index in yi:
            _iteration, item = map_rows[int(map_row_index)]
            source_payload = item.data(0, self.ROLE_PAYLOAD)
            if source_payload is None:
                continue

            try:
                file_name = str(region_item_for_rows.data(0, self.ROLE_FILE) or "")
            except Exception:
                file_name = ""
            base_title = str(
                getattr(source_payload, "title", "") or item.text(0) or "Curve"
            )
            title = source_aware_curve_title(base_title, file_name)
            if not title.endswith(" [ROI]"):
                title = f"{title} [ROI]"

            # A shallow copy preserves any future payload extensions while the
            # copied arrays guarantee complete independence from the source.
            payload = copy.copy(source_payload)
            payload.title = title
            payload.x = x_roi.copy()
            payload.y = np.asarray(z_map[int(map_row_index), xi], dtype=float).copy()
            metadata = dict(getattr(source_payload, "metadata", {}) or {})
            metadata.update({
                "derived_type": "roi",
                "ROI X range": f"{x_min:.12g}..{x_max:.12g}",
                "source_title": base_title,
            })
            try:
                y_labels = np.asarray(state.get("y_labels", []), dtype=float)
                if y_labels.size > int(map_row_index):
                    metadata["ROI row coordinate"] = f"{float(y_labels[int(map_row_index)]):.12g}"
            except Exception:
                pass
            payload.metadata = metadata
            derived_payloads.append(payload)

        if not derived_payloads:
            QMessageBox.information(
                self, "Nothing to pass", "The current ROI contains no selected spectra.",
                QMessageBox.StandardButton.Ok,
            )
            return

        plotted_panel = self._ensure_plotted_data_panel()
        plotted_panel.add_curves(derived_payloads)
        self.tabs.setCurrentWidget(self._plotted_data_host)

    # ------------------------------------------------------------------
    # ResPES Simple-view analysis
    # ------------------------------------------------------------------
    def _build_respes_side_panel(self) -> None:
        panel = getattr(self, "respes_side_panel", None)
        if panel is None:
            return
        old = panel.layout()
        if old is not None:
            while old.count():
                item = old.takeAt(0)
                w = item.widget()
                if w is not None:
                    w.deleteLater()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)

        from PyQt6.QtWidgets import QComboBox

        # Map representation controls are deliberately separated from the cut
        # controls below.  Energy-axis selection changes how the map is drawn;
        # it does not define a ResPES cut.
        axis_group = QGroupBox("Map energy axis", panel)
        axis_group.setObjectName("ResPESEnergyAxisGroup")
        axis_layout = QVBoxLayout(axis_group)
        axis_layout.setContentsMargins(7, 7, 7, 7)
        axis_layout.setSpacing(5)
        axis_form = QFormLayout()
        axis_form.setContentsMargins(0, 0, 0, 0)
        axis_form.setSpacing(5)

        self.cb_respes_energy_axis = QComboBox(axis_group)
        self.cb_respes_energy_axis.addItem("Binding energy (BE)", "be")
        self.cb_respes_energy_axis.addItem("Kinetic energy (KE)", "ke")
        self.cb_respes_energy_axis.setToolTip(
            "Redraw the ResPES map on a binding-energy or kinetic-energy horizontal axis."
        )
        axis_form.addRow("Energy axis", self.cb_respes_energy_axis)

        self.sb_respes_work_function = QDoubleSpinBox(axis_group)
        self.sb_respes_work_function.setLocale(QLocale.c())
        self.sb_respes_work_function.setDecimals(2)
        self.sb_respes_work_function.setRange(2.5, 6.5)
        self.sb_respes_work_function.setValue(4.5)
        self.sb_respes_work_function.setSingleStep(0.05)
        self.sb_respes_work_function.setSuffix(" eV")
        # Do not rebuild the map for every digit typed or every intermediate
        # spin-box value.  With keyboard tracking off, typed edits redraw only when committed
        # (Enter / focus change), while the spin arrows still redraw immediately.
        self.sb_respes_work_function.setKeyboardTracking(False)
        self.sb_respes_work_function.setToolTip(
            "Analyzer work function for KE = hν - BE - Φ. Allowed range: 2.50–6.50 eV. "
            "Press Enter (or leave the field) to apply a typed value and redraw the KE map."
        )
        axis_form.addRow("Analyzer WF", self.sb_respes_work_function)
        axis_layout.addLayout(axis_form)
        layout.addWidget(axis_group)

        # Everything in this group defines, edits, or stores a ResPES cut.
        cuts_group = QGroupBox("ResPES cuts", panel)
        cuts_group.setObjectName("ResPESCutsGroup")
        cuts_layout = QVBoxLayout(cuts_group)
        cuts_layout.setContentsMargins(7, 7, 7, 7)
        cuts_layout.setSpacing(5)

        self.cb_respes_cut_type = QComboBox(cuts_group)
        self.cb_respes_cut_type.addItem("Constant BE", "constant_be")
        self.cb_respes_cut_type.addItem("Constant KE", "constant_ke")
        self.cb_respes_cut_type.addItem("Constant PhE", "constant_hv")
        self.cb_respes_cut_type.setToolTip(
            "Constant BE follows a non-dispersing photoemission feature; Constant KE follows a fixed-kinetic-energy trajectory; "
            "Constant PhE extracts a spectrum at a selected excitation energy."
        )
        cuts_layout.addWidget(self.cb_respes_cut_type)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(5)
        self.lbl_respes_position = QLabel("BE", cuts_group)
        self.sb_respes_position = QDoubleSpinBox(cuts_group)
        self.sb_respes_position.setLocale(QLocale.c())
        self.sb_respes_position.setDecimals(3)
        self.sb_respes_position.setRange(-1.0e6, 1.0e6)
        self.sb_respes_position.setKeyboardTracking(True)
        self.sb_respes_position.setSuffix(" eV")
        self.sb_respes_position.setSingleStep(0.1)
        form.addRow(self.lbl_respes_position, self.sb_respes_position)

        self.sb_respes_width = QDoubleSpinBox(cuts_group)
        self.sb_respes_width.setLocale(QLocale.c())
        self.sb_respes_width.setDecimals(3)
        self.sb_respes_width.setRange(0.0, 1.0e6)
        self.sb_respes_width.setKeyboardTracking(True)
        self.sb_respes_width.setSuffix(" eV")
        self.sb_respes_width.setSingleStep(0.05)
        form.addRow("Width", self.sb_respes_width)
        cuts_layout.addLayout(form)

        note = QLabel("Drag the band on the map; drag an edge to change width.", cuts_group)
        note.setWordWrap(True)
        try:
            note.setStyleSheet("color: palette(mid);")
        except Exception:
            pass
        cuts_layout.addWidget(note)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(5)
        self.btn_respes_add_trace = QPushButton("Plot trace", cuts_group)
        self.btn_respes_add_trace.setToolTip(
            "Plot the current cut trace in the ResPES comparison window."
        )
        self.btn_respes_add_trace.clicked.connect(self._add_respes_trace_to_comparison)
        action_row.addWidget(self.btn_respes_add_trace)
        cuts_layout.addLayout(action_row)
        layout.addWidget(cuts_group)

        # Keep workflow grouping visually consistent with the compact
        # Normalization controls used elsewhere in Processed Data.
        group_style = """
        QGroupBox#ResPESEnergyAxisGroup, QGroupBox#ResPESCutsGroup {
            border: 1px solid palette(mid);
            border-radius: 5px;
            margin-top: 7px;
            padding-top: 2px;
        }
        QGroupBox#ResPESEnergyAxisGroup::title, QGroupBox#ResPESCutsGroup::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 8px;
            padding: 0 3px;
            color: palette(window-text);
            font-weight: 600;
        }
        """
        axis_group.setStyleSheet(group_style)
        cuts_group.setStyleSheet(group_style)

        layout.addStretch(1)
        panel.setVisible(False)

        self.cb_respes_energy_axis.currentIndexChanged.connect(self._on_respes_energy_axis_changed)
        self.sb_respes_work_function.valueChanged.connect(self._on_respes_work_function_changed)
        self.cb_respes_cut_type.currentIndexChanged.connect(self._on_respes_cut_type_changed)
        # ResPES cut controls are exploratory controls: update the overlay/trace
        # immediately while typing or stepping rather than waiting for Enter.
        self.sb_respes_position.valueChanged.connect(self._on_respes_numeric_changed)
        self.sb_respes_width.valueChanged.connect(self._on_respes_numeric_changed)

    @staticmethod
    def _is_photon_energy_label(label: str) -> bool:
        text = str(label or "").strip().lower().replace("_", " ")
        return ("photon" in text and "energy" in text) or text in {"hv", "hν", "hnu"}

    @staticmethod
    def _respes_source_energy_axis(image) -> str:
        """Infer whether the measured ResPES map X coordinate is BE or KE."""
        try:
            xlabel = str(image[4] or "") if len(image) >= 5 else ""
        except Exception:
            xlabel = ""
        low = xlabel.lower()
        if "kinetic" in low or " ke" in f" {low}":
            return "ke"
        return "be"

    @staticmethod
    def _respes_default_cut_position(x, hv, cut_type: str, source_axis: str, work_function: float) -> float:
        import numpy as np
        source_axis = "ke" if str(source_axis).lower() == "ke" else "be"
        if cut_type == "constant_hv":
            return float(np.nanmedian(hv))
        requested_axis = "ke" if cut_type == "constant_ke" else "be"
        if requested_axis == source_axis:
            return float(np.nanmedian(x))
        return float(np.nanmedian(hv) - float(work_function) - np.nanmedian(x))

    def _respes_map_context(self):
        """Return current single-map ResPES context or None.

        Context is deliberately derived from the actual selected map payload,
        so the button exists only when the physical second dimension is photon
        energy and the current representation is a single 2D map.
        """
        try:
            selection = self._plot_selection_controller.collect_selection()
            if len(selection.images) != 1:
                return None
            image = selection.images[0]
            sec = image[6] if len(image) >= 7 else None
            label = str(image[7] or "") if len(image) >= 8 else ""
            if sec is None or not self._is_photon_energy_label(label):
                return None
            import numpy as np
            x = np.asarray(image[0], dtype=float).reshape(-1)
            hv = np.asarray(sec, dtype=float).reshape(-1)
            Z = np.asarray(image[2], dtype=float)
            if Z.ndim == 1:
                Z = Z.reshape(1, -1)
            if x.size < 2 or hv.size != Z.shape[0]:
                return None
            key = self._map_normalization_context_key()
            return image, x, hv, key
        except Exception:
            return None

    def _ensure_respes_defaults(self) -> bool:
        ctx = self._respes_map_context()
        if ctx is None:
            return False
        _image, x, hv, key = ctx
        try:
            import numpy as np
            if key != getattr(self, "_respes_dataset_key", None):
                self._respes_dataset_key = key
                xlo, xhi = float(np.nanmin(x)), float(np.nanmax(x))
                xstep = float(np.nanmedian(np.abs(np.diff(x))))
                if not np.isfinite(xstep) or xstep <= 0:
                    xstep = max(abs(xhi - xlo) / max(x.size - 1, 1), 0.01)
                self._respes_cut_width = max(xstep, 0.10)
                self._respes_cut_type = "constant_be"
                self._respes_energy_axis = getattr(self, "_respes_energy_axis", "be") or "be"
                self._respes_work_function = float(getattr(self, "_respes_work_function", 4.5) or 4.5)
                source_axis = self._respes_source_energy_axis(_image)
                self._respes_cut_position = self._respes_default_cut_position(
                    x, hv, self._respes_cut_type, source_axis, self._respes_work_function
                )
            if self._respes_cut_width is None:
                self._respes_cut_width = 0.10
            if self._respes_cut_position is None:
                self._respes_cut_position = float(np.nanmedian(x))
            return True
        except Exception:
            return False

    def _sync_respes_controls(self) -> None:
        if not self._ensure_respes_defaults():
            return
        axis_combo = getattr(self, "cb_respes_energy_axis", None)
        if axis_combo is not None:
            idx = axis_combo.findData(getattr(self, "_respes_energy_axis", "be"))
            if idx >= 0 and axis_combo.currentIndex() != idx:
                axis_combo.blockSignals(True); axis_combo.setCurrentIndex(idx); axis_combo.blockSignals(False)
        wf = getattr(self, "sb_respes_work_function", None)
        energy_axis = getattr(self, "_respes_energy_axis", "be")
        if wf is not None:
            wf.blockSignals(True); wf.setValue(float(getattr(self, "_respes_work_function", 4.5))); wf.blockSignals(False)
            # Φ is needed whenever BE and KE are related, including a BE cut on
            # a measured KE map (or vice versa), so keep it editable in both views.
            wf.setEnabled(True)
        combo = getattr(self, "cb_respes_cut_type", None)
        if combo is not None:
            idx = combo.findData(getattr(self, "_respes_cut_type", "constant_be"))
            if idx >= 0 and combo.currentIndex() != idx:
                combo.blockSignals(True); combo.setCurrentIndex(idx); combo.blockSignals(False)
        cut_type = getattr(self, "_respes_cut_type", "constant_be")
        label = getattr(self, "lbl_respes_position", None)
        if label is not None:
            label.setText("BE" if cut_type == "constant_be" else ("KE" if cut_type == "constant_ke" else "hν"))
        pos = getattr(self, "sb_respes_position", None)
        width = getattr(self, "sb_respes_width", None)
        if pos is not None:
            pos.blockSignals(True); pos.setValue(float(self._respes_cut_position)); pos.blockSignals(False)
        if width is not None:
            width.blockSignals(True); width.setValue(float(self._respes_cut_width)); width.blockSignals(False)

    def _reset_respes_context(self) -> None:
        """Return the ResPES controls/cut state to a clean session."""
        button = getattr(self, "btn_respes_analysis", None)
        if button is not None:
            try:
                button.blockSignals(True)
                button.setChecked(False)
            finally:
                button.blockSignals(False)
            button.setVisible(False)
        panel = getattr(self, "respes_side_panel", None)
        if panel is not None:
            panel.setVisible(False)
        self._respes_dataset_key = None
        self._respes_cut_type = "constant_be"
        self._respes_cut_position = None
        self._respes_cut_width = None
        self._respes_energy_axis = "be"
        self._respes_work_function = 4.5
        try:
            self.plot_area._respes_cut_state = None
            self.plot_area._respes_cut_drag = None
        except Exception:
            pass

    def _update_respes_availability(self) -> None:
        button = getattr(self, "btn_respes_analysis", None)
        panel = getattr(self, "respes_side_panel", None)
        if button is None:
            return
        simple = bool(getattr(self, "rb_map_none", None) and self.rb_map_none.isChecked())
        # ResPES belongs strictly to Processed Data.  Raw and Processed share
        # the same plot container, so eligibility must include the active tab
        # rather than relying only on map content/state.
        processed_active = bool(getattr(self, "_is_processed_tab_active", lambda: False)())
        eligible = bool(processed_active and simple and self._respes_map_context() is not None)
        button.setVisible(eligible)
        if eligible:
            self._ensure_respes_defaults()
            self._sync_respes_controls()
        # Option A: changing to Lines/ROI only hides the specialised workflow;
        # checked state and cut parameters are retained for return to Simple.
        if panel is not None:
            panel.setVisible(bool(eligible and button.isChecked()))

    def _respes_is_active_for_current_view(self) -> bool:
        button = getattr(self, "btn_respes_analysis", None)
        simple = bool(getattr(self, "rb_map_none", None) and self.rb_map_none.isChecked())
        return bool(simple and button is not None and button.isVisible() and button.isChecked())

    def _on_respes_analysis_toggled(self, checked: bool) -> None:
        self._ensure_respes_defaults()
        panel = getattr(self, "respes_side_panel", None)
        if panel is not None:
            panel.setVisible(bool(checked and self._respes_map_context() is not None and
                                  getattr(self, "rb_map_none", None) and self.rb_map_none.isChecked()))
        self._sync_respes_controls()
        self._update_plot_from_selected()

    def _on_respes_cut_type_changed(self, _index: int = -1) -> None:
        combo = getattr(self, "cb_respes_cut_type", None)
        if combo is None:
            return
        self._respes_cut_type = str(combo.currentData() or "constant_be")
        # Re-seed the position for the new coordinate convention only if the
        # existing value is outside a sensible range for the current map.
        ctx = self._respes_map_context()
        if ctx is not None:
            _image, x, hv, _key = ctx
            import numpy as np
            source_axis = self._respes_source_energy_axis(_image)
            self._respes_cut_position = self._respes_default_cut_position(
                x, hv, self._respes_cut_type, source_axis,
                float(getattr(self, "_respes_work_function", 4.5)),
            )
            if self._respes_cut_type == "constant_hv":
                diffs = np.abs(np.diff(np.sort(hv[np.isfinite(hv)])))
                diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
                if diffs.size:
                    self._respes_cut_width = max(float(np.nanmedian(diffs)), 0.01)
        self._sync_respes_controls()
        self._update_plot_from_selected()

    def _on_respes_energy_axis_changed(self, _index: int = -1) -> None:
        combo = getattr(self, "cb_respes_energy_axis", None)
        if combo is None:
            return
        self._respes_energy_axis = str(combo.currentData() or "be")
        self._sync_respes_controls()
        self._update_plot_from_selected()

    def _on_respes_work_function_changed(self, _value=None) -> None:
        try:
            self._respes_work_function = float(self.sb_respes_work_function.value())
        except Exception:
            return
        # A constant-KE cut is defined in the same physical KE convention, so
        # changing Φ must update both the map and its cut overlay/trace.
        self._sync_respes_controls()
        self._update_plot_from_selected()

    def _on_respes_numeric_changed(self, _value=None) -> None:
        try:
            self._respes_cut_position = float(self.sb_respes_position.value())
            self._respes_cut_width = max(0.0, float(self.sb_respes_width.value()))
        except Exception:
            return
        self._update_plot_from_selected()

    def _on_respes_cut_changed_from_plot(self, position: float, width: float, commit: bool = False) -> None:
        self._respes_cut_position = float(position)
        self._respes_cut_width = max(0.0, float(width))
        self._sync_respes_controls()
        if commit:
            self._update_plot_from_selected()

    @staticmethod
    def _comparison_axis_identity(label: str) -> tuple[str, str | None]:
        """Infer a stable generic axis identity from a display label."""
        text = str(label or "").strip()
        low = text.lower()
        unit = None
        if "[" in text and "]" in text:
            try:
                unit = text.rsplit("[", 1)[1].split("]", 1)[0].strip() or None
            except Exception:
                unit = None
        if "binding" in low and "energy" in low:
            return "binding_energy", unit or "eV"
        if "kinetic" in low and "energy" in low:
            return "kinetic_energy", unit or "eV"
        if "photon" in low and "energy" in low:
            return "photon_energy", unit or "eV"
        if "temperature" in low:
            return "temperature", unit
        if "time" in low:
            return "time", unit
        if "pressure" in low:
            return "pressure", unit
        if "iteration" in low:
            return "iteration", unit
        return low.replace(" ", "_") or "x", unit

    def _map_trace_normalization_metadata(self) -> dict:
        mode = self._current_map_normalization_mode()
        if mode == "at_be":
            return {
                "Normalization": "At BE",
                "Normalization detail": f"BE={self._map_norm_be}; width={self._map_norm_width_ev} eV",
            }
        if mode == "area":
            return {
                "Normalization": "Area",
                "Normalization detail": f"range={self._map_norm_area_low}..{self._map_norm_area_high} eV",
            }
        return {"Normalization": "None"}

    def _current_map_trace_snapshot(self, orientation: str):
        """Snapshot the currently displayed Lines/ROI trace for comparison."""
        import numpy as np
        from .trace_comparison import ComparisonTrace

        orientation = str(orientation or "").lower()
        if orientation not in ("horizontal", "vertical"):
            return None
        lines_active = bool(getattr(self, "rb_map_lines", None) and self.rb_map_lines.isChecked())
        roi_active = bool(getattr(self, "rb_map_roi", None) and self.rb_map_roi.isChecked())
        state = getattr(self.plot_area, "_map_cross_state", None) if lines_active else (
            getattr(self.plot_area, "_map_roi_state", None) if roi_active else None
        )
        if not state:
            return None

        metadata = {
            "Dataset": str(state.get("title") or ""),
            "Source": "Lines" if lines_active else "ROI",
            "Trace": "Horizontal" if orientation == "horizontal" else "Vertical",
        }
        metadata.update(self._map_trace_normalization_metadata())
        if lines_active and self._map_lines_binning_active():
            try:
                metadata["Binning"] = f"Bin size {int(self.sb_map_bin_size.value())}"
            except Exception:
                pass
        if lines_active:
            try:
                metadata["H thickness"] = int(state.get("h_thickness", 1))
                metadata["V thickness"] = int(state.get("v_thickness", 1))
            except Exception:
                pass

        trace_label = ""
        if orientation == "horizontal":
            line = state.get("bottom_line")
            if line is None:
                return None
            x = np.asarray(line.get_xdata(), dtype=float).reshape(-1)
            y = np.asarray(line.get_ydata(), dtype=float).reshape(-1)
            x_label = str(state.get("xlabel") or "X")
            if lines_active:
                row = int(state.get("row", 0))
                try:
                    trace_label = f"Trace at {state['y_cursor_caption'](row)}"
                except Exception:
                    trace_label = ""
                sec = state.get("secondary_y")
                if sec is not None:
                    sec_arr = np.asarray(sec, dtype=float).reshape(-1)
                    if row < sec_arr.size:
                        metadata["Selected Y"] = f"{sec_arr[row]:.12g}"
                        metadata["Selected Y axis"] = str(state.get("secondary_ylabel") or "Y")
                else:
                    labels = np.asarray(state.get("y_labels", []), dtype=float).reshape(-1)
                    if row < labels.size:
                        metadata["Selected iteration"] = f"{labels[row]:.12g}"
            else:
                xi = np.asarray(state.get("xidx", []), dtype=int)
                yi = np.asarray(state.get("yidx", []), dtype=int)
                xfull = np.asarray(state.get("x", []), dtype=float)
                yfull = np.asarray(state.get("y_labels", []), dtype=float)
                if xi.size:
                    metadata["ROI X range"] = f"{np.nanmin(xfull[xi]):.12g}..{np.nanmax(xfull[xi]):.12g}"
                if yi.size:
                    metadata["ROI Y range"] = f"{np.nanmin(yfull[yi]):.12g}..{np.nanmax(yfull[yi]):.12g}"
        else:
            line = state.get("right_line")
            if line is None:
                return None
            # The right trace is plotted as intensity vs row position.  For a
            # stored comparison trace, make the physical/iteration coordinate
            # the X axis and intensity the Y axis.
            y = np.asarray(line.get_xdata(), dtype=float).reshape(-1)
            if roi_active:
                yi = np.asarray(state.get("yidx", []), dtype=int)
            else:
                yi = np.arange(int(state.get("rows", y.size)), dtype=int)
            sec = state.get("secondary_y")
            use_secondary = (
                str(state.get("right_y_mode", "iteration")) == "secondary"
                and sec is not None
                and self.plot_area._has_meaningful_secondary_y(
                    sec, str(state.get("secondary_ylabel") or ""), int(state.get("rows", len(yi)))
                )
            )
            if use_secondary:
                sec_arr = np.asarray(sec, dtype=float).reshape(-1)
                x = sec_arr[yi]
                x_label = str(state.get("secondary_ylabel") or "Y")
            else:
                labels = np.asarray(state.get("y_labels", []), dtype=float).reshape(-1)
                x = labels[yi]
                x_label = "Iteration"
            if lines_active:
                col = int(state.get("col", 0))
                try:
                    trace_label = f"Trace at {state['x_cursor_caption'](col)}"
                except Exception:
                    trace_label = ""
                xfull = np.asarray(state.get("x", []), dtype=float).reshape(-1)
                if col < xfull.size:
                    metadata["Selected X"] = f"{xfull[col]:.12g}"
                    metadata["Selected X axis"] = str(state.get("xlabel") or "X")
            else:
                xi = np.asarray(state.get("xidx", []), dtype=int)
                xfull = np.asarray(state.get("x", []), dtype=float)
                yfull = np.asarray(state.get("y_labels", []), dtype=float)
                if xi.size:
                    metadata["ROI X range"] = f"{np.nanmin(xfull[xi]):.12g}..{np.nanmax(xfull[xi]):.12g}"
                if yi.size:
                    metadata["ROI Y range"] = f"{np.nanmin(yfull[yi]):.12g}..{np.nanmax(yfull[yi]):.12g}"

        if x.size == 0 or y.size != x.size:
            return None
        quantity, unit = self._comparison_axis_identity(x_label)
        # Preserve the source-map X direction in the comparison plot.  This is
        # particularly important for XPS Binding Energy, conventionally shown
        # decreasing from left to right.
        invert_x = bool(orientation == "horizontal" and x.size > 1 and x[0] > x[-1])
        return ComparisonTrace(
            x=x, y=y, x_label=x_label, y_label="Intensity",
            x_quantity=quantity, x_unit=unit, invert_x=invert_x,
            label=trace_label, metadata=metadata,
        )

    def _add_snapshot_to_comparison(self, snapshot, *, title="Trace comparison", basename="trace_comparison.csv") -> None:
        if snapshot is None:
            QMessageBox.warning(self, "Trace comparison", "No map trace is currently available.")
            return
        window = self._trace_comparison_window_instance()
        try:
            window.add_trace(snapshot)
        except ValueError as exc:
            # One comparison plot must have one meaningful X quantity.  Offer a
            # deliberate session replacement rather than silently mixing axes.
            answer = QMessageBox.question(
                self, "Trace comparison",
                f"{exc}\n\nClear the current comparison and start a new one with this trace?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            window.clear_traces()
            window.add_trace(snapshot)
        window.setWindowTitle(title)
        window.set_export_basename(basename)

    def _add_map_trace_to_comparison(self, orientation: str) -> None:
        snapshot = self._current_map_trace_snapshot(orientation)
        try:
            self._add_snapshot_to_comparison(snapshot, title="Trace comparison", basename="trace_comparison.csv")
        except Exception as exc:
            QMessageBox.critical(self, "Trace comparison", f"Could not add the map trace:\n{exc}")

    def _current_respes_trace_snapshot(self):
        """Return a generic immutable snapshot of the displayed ResPES cut trace."""
        import numpy as np
        from .trace_comparison import ComparisonTrace

        if not self._respes_is_active_for_current_view():
            return None
        state = getattr(self.plot_area, "_respes_cut_state", None)
        if not state:
            return None
        trace_line = state.get("trace_line")
        if trace_line is None:
            return None
        x_values = np.asarray(trace_line.get_xdata(), dtype=float).reshape(-1)
        values = np.asarray(trace_line.get_ydata(), dtype=float).reshape(-1)
        if x_values.size == 0 or values.size != x_values.size:
            return None

        cut_type = str(state.get("type", getattr(self, "_respes_cut_type", "constant_be")))
        position = float(state.get("position", self._respes_cut_position))
        width = float(state.get("width", self._respes_cut_width))
        norm_mode = self._current_map_normalization_mode()
        cut_name = {
            "constant_be": "Constant BE",
            "constant_ke": "Constant KE",
            "constant_hv": "Constant PhE",
        }.get(cut_type, cut_type)
        center_name = {
            "constant_be": "BE center",
            "constant_ke": "KE center",
            "constant_hv": "Photon energy center",
        }.get(cut_type, "Center")
        metadata = {
            "Dataset": str(state.get("title") or ""),
            "Source": "ResPES cut",
            "Cut type": cut_name,
            center_name: f"{position:.12g} eV",
            "Analyzer work function": f"{float(state.get('work_function', getattr(self, '_respes_work_function', 4.5))):.12g} eV",
            "Map energy axis": "KE" if str(state.get("energy_axis", getattr(self, "_respes_energy_axis", "be"))) == "ke" else "BE",
            "Width": f"{width:.12g} eV",
        }
        if norm_mode == "at_be":
            metadata["Normalization"] = "At BE"
            metadata["Normalization detail"] = (
                f"BE={self._map_norm_be}; width={self._map_norm_width_ev} eV"
            )
        elif norm_mode == "area":
            metadata["Normalization"] = "Area"
            metadata["Normalization detail"] = (
                f"range={self._map_norm_area_low}..{self._map_norm_area_high} eV"
            )
        else:
            metadata["Normalization"] = "None"

        if cut_type == "constant_hv":
            x_label = str(state.get("trace_x_label") or ("Kinetic Energy [eV]" if state.get("energy_axis") == "ke" else "Binding Energy [eV]"))
            quantity, unit = self._comparison_axis_identity(x_label)
            invert_x = bool(x_values.size > 1 and x_values[0] > x_values[-1])
        else:
            x_label = "Photon Energy [eV]"
            quantity, unit, invert_x = "photon_energy", "eV", False
        # Match Lines extraction: give every extracted trace a coordinate-aware
        # default name instead of falling back to generic ``Trace N`` labels.
        coordinate_name = {
            "constant_be": "BE",
            "constant_ke": "KE",
            "constant_hv": "PhE",
        }.get(cut_type, cut_name)
        trace_label = f"Trace at {coordinate_name} = {position:.3f} eV"

        return ComparisonTrace(
            x=x_values,
            y=values,
            x_label=x_label,
            y_label="Intensity",
            x_quantity=quantity,
            x_unit=unit,
            invert_x=invert_x,
            label=trace_label,
            metadata=metadata,
        )

    def _trace_comparison_window_instance(self):
        """Return the application-level, producer-agnostic trace comparison window."""
        window = getattr(self, "_trace_comparison_window", None)
        if window is None:
            from .ui_trace_comparison import TraceComparisonWindow
            window = TraceComparisonWindow()
            self._trace_comparison_window = window
        return window

    def _add_respes_trace_to_comparison(self) -> None:
        snapshot = self._current_respes_trace_snapshot()
        if snapshot is None:
            QMessageBox.warning(self, "ResPES comparison", "No ResPES cut trace is currently available.")
            return
        try:
            self._add_snapshot_to_comparison(
                snapshot, title="ResPES trace comparison",
                basename="respes_trace_comparison.csv",
            )
        except Exception as exc:
            QMessageBox.critical(self, "ResPES comparison", f"Could not add the ResPES trace:\n{exc}")

    def _terminate_trace_comparison_session(self) -> None:
        window = getattr(self, "_trace_comparison_window", None)
        if window is not None:
            try:
                window.terminate_session()
            except Exception:
                pass
