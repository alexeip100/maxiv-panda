from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
from PyQt6.QtCore import Qt, QRect, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QToolTip,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from ..colormap_dialog import choose_colormap
from .controller import LiveFileMonitorController
from .core import LiveMapUpdate, MonitorTiming
from .lines_view import LiveLinesView


class LiveMapWindow(QDialog):
    """Dedicated non-modal viewer for one growing analyzer file."""

    _TIMING_OPTIONS = (
        ("Auto", None),
        ("1 s", 1.0),
        ("2 s", 2.0),
        ("5 s", 5.0),
        ("10 s", 10.0),
    )

    def __init__(
        self,
        path: str | Path,
        parent: QWidget | None = None,
        *,
        reload_latest_callback: Callable[[], bool] | None = None,
        flip_x: bool = False,
        region_index: int = 0,
        region_name: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.path = Path(path)
        self._reload_latest_callback = reload_latest_callback
        self.region_index = max(0, int(region_index))
        self.region_name = str(region_name or "").strip()
        self._flip_x = bool(flip_x)
        self._xlabel = "Energy [eV]"
        # Use normal top-level-window semantics.  The Live Monitor can be
        # minimized or left behind PANDA while it keeps monitoring.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        # A parentless live monitor must not keep PANDA running after the main
        # window is closed.
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        title = f"Live monitor — {self.path.name}"
        if self.region_name:
            title += f" — {self.region_name}"
        self.setWindowTitle(title)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.resize(900, 650)

        self._spectra: np.ndarray | None = None
        self._x: np.ndarray | None = None
        self._second_axis: np.ndarray | None = None
        self._second_axis_label = ""
        self._cmap = "terrain"
        self._palette_hint_shown = False
        self._palette_hint_pending = False
        self._palette_hint_dwell_timer = QTimer(self)
        self._palette_hint_dwell_timer.setSingleShot(True)
        self._palette_hint_dwell_timer.setInterval(1000)
        self._palette_hint_dwell_timer.timeout.connect(self._show_palette_hint_after_dwell)
        self._controller = LiveFileMonitorController(
            self.path, region_index=self.region_index, parent=self
        )
        self._running = True

        self._build_ui()
        self._connect_controller()
        self._controller.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.figure = Figure(constrained_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        # Match the main MAP toolbar: fixed-width coordinate text prevents
        # BE/PhE/intensity fields from shifting horizontally on macOS.
        try:
            from PyQt6.QtGui import QFontDatabase
            default = self.toolbar.locLabel.font()
            fixed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
            try:
                if default.pointSizeF() > 0:
                    fixed.setPointSizeF(default.pointSizeF())
            except Exception:
                pass
            self.toolbar.locLabel.setFont(fixed)
            try:
                from PyQt6.QtCore import Qt
                self.toolbar.locLabel.setAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                self.toolbar.locLabel.setContentsMargins(14, 0, 0, 0)
            except Exception:
                pass
        except Exception:
            pass
        self.ax = self.figure.add_subplot(111)
        self._image = None
        self._colorbar = None
        self._lines_view = LiveLinesView(self.figure, self.canvas)
        self.canvas.mpl_connect("button_press_event", self._on_map_palette_right_click)
        self.canvas.mpl_connect("motion_notify_event", self._maybe_show_map_palette_hint)
        self.canvas.mpl_connect("figure_leave_event", self._cancel_palette_hint_dwell)
        self.ax.set_title("Waiting for live data…")
        info_row = QHBoxLayout()
        self.lbl_spectra = QLabel("Spectra: 0", self)
        self.lbl_last_update = QLabel("Last update: —", self)
        self.lbl_status = QLabel(self)
        self._on_status("Monitoring")
        info_row.addWidget(self.lbl_spectra)
        info_row.addSpacing(18)
        info_row.addWidget(self.lbl_last_update)
        info_row.addStretch(1)
        info_row.addWidget(self.lbl_status)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Update:", self))
        self.combo_timing = QComboBox(self)
        for label, seconds in self._TIMING_OPTIONS:
            self.combo_timing.addItem(label, seconds)
        self.combo_timing.setCurrentIndex(0)
        self.combo_timing.currentIndexChanged.connect(self._on_timing_changed)
        controls.addWidget(self.combo_timing)

        self.lbl_timing = QLabel("Checked every 0.5 s · Settle for 0.75 s · learning spectrum interval…", self)
        self.lbl_timing.setToolTip(
            "Checked every is how often PANDA inspects file size/modification time. "
            "Settle for is the quiet period required after a detected change before PANDA reads a snapshot. "
            "New spectrum every is the observed interval between successful acquisition updates once Auto has learned it."
        )
        controls.addWidget(self.lbl_timing)

        # Palette is changed directly from the 2D map with a right-click.

        controls.addSpacing(8)
        controls.addWidget(QLabel("H thickness", self))
        self.sb_h_thickness = QSpinBox(self)
        self.sb_h_thickness.setRange(1, 25)
        self.sb_h_thickness.setSingleStep(2)
        self.sb_h_thickness.setValue(1)
        self.sb_h_thickness.setKeyboardTracking(False)
        self.sb_h_thickness.setFixedWidth(48)
        self.sb_h_thickness.setToolTip(
            "Odd number of map rows averaged symmetrically for the horizontal trace (1, 3, 5, …, 25)."
        )
        self.sb_h_thickness.valueChanged.connect(self._on_trace_thickness_changed)
        controls.addWidget(self.sb_h_thickness)
        controls.addWidget(QLabel("V thickness", self))
        self.sb_v_thickness = QSpinBox(self)
        self.sb_v_thickness.setRange(1, 25)
        self.sb_v_thickness.setSingleStep(2)
        self.sb_v_thickness.setValue(1)
        self.sb_v_thickness.setKeyboardTracking(False)
        self.sb_v_thickness.setFixedWidth(48)
        self.sb_v_thickness.setToolTip(
            "Odd number of map columns averaged symmetrically for the vertical trace (1, 3, 5, …, 25)."
        )
        self.sb_v_thickness.valueChanged.connect(self._on_trace_thickness_changed)
        controls.addWidget(self.sb_v_thickness)
        controls.addStretch(1)

        self.btn_reload_latest = QPushButton("Reload latest snapshot", self)
        self.btn_reload_latest.setToolTip(
            "Load the current file contents into Raw Data using PANDA's normal reload/provenance policy."
        )
        self.btn_reload_latest.setEnabled(callable(self._reload_latest_callback))
        self.btn_reload_latest.clicked.connect(self._reload_latest_snapshot)
        controls.addWidget(self.btn_reload_latest)

        self.btn_start_stop = QPushButton("Stop", self)
        self.btn_start_stop.clicked.connect(self._toggle_monitoring)
        controls.addWidget(self.btn_start_stop)
        self.btn_close = QPushButton("Close", self)
        self.btn_close.clicked.connect(self.close)
        controls.addWidget(self.btn_close)

        # Keep interactive controls close to the plot/navigation tools.  The
        # bottom of the Live Monitor is reserved for diagnostics/status only.
        layout.addLayout(controls)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, 1)
        layout.addLayout(info_row)

    def _cancel_palette_hint_dwell(self, event=None) -> None:
        try:
            self._palette_hint_dwell_timer.stop()
        except Exception:
            pass
        self._palette_hint_pending = False

    def _cursor_is_over_live_map(self) -> bool:
        if self._lines_view is None or self._lines_view.image is None:
            return False
        try:
            pos = self.canvas.mapFromGlobal(QCursor.pos())
            x = float(pos.x())
            y = float(self.canvas.height() - pos.y())
            return bool(self._lines_view.ax_map.bbox.contains(x, y))
        except Exception:
            return False

    def _show_palette_hint_after_dwell(self) -> None:
        if self._palette_hint_shown or not self._palette_hint_pending:
            return
        if not self._cursor_is_over_live_map():
            self._palette_hint_pending = False
            return
        self._palette_hint_shown = True
        self._palette_hint_pending = False
        try:
            QToolTip.showText(
                QCursor.pos(),
                "Right-click to change palette",
                self.canvas,
                QRect(),
                5000,
            )
        except Exception:
            pass

    def _maybe_show_map_palette_hint(self, event) -> None:
        if self._palette_hint_shown or self._lines_view is None:
            return
        if event is None or event.inaxes is not self._lines_view.ax_map or self._lines_view.image is None:
            self._cancel_palette_hint_dwell()
            return
        self._palette_hint_pending = True
        # Restart on every motion; only a full second without movement reveals
        # the five-second discovery hint.
        self._palette_hint_dwell_timer.start()

    def _on_map_palette_right_click(self, event) -> None:
        if self._lines_view is None:
            return
        button = getattr(getattr(event, "button", None), "value", getattr(event, "button", None))
        if button == 3 and event.inaxes is self._lines_view.ax_map and self._lines_view.image is not None:
            self._choose_cmap()

    def _connect_controller(self) -> None:
        self._controller.update_ready.connect(self._on_update)
        self._controller.timing_changed.connect(self._on_timing_info)
        self._controller.status_changed.connect(self._on_status)

    def _on_timing_changed(self, index: int) -> None:
        seconds = self.combo_timing.itemData(index)
        if seconds is None:
            self._controller.set_auto()
        else:
            self._controller.set_fixed_interval(float(seconds))

    def _on_timing_info(self, timing: MonitorTiming) -> None:
        text = (
            f"Checked every {timing.poll_interval_s:.2g} s · "
            f"Settle for {timing.settle_interval_s:.2g} s"
        )
        if timing.mode == "auto":
            if timing.learning or timing.learned_cadence_s is None:
                text += " · learning spectrum interval…"
            else:
                text += f" · New spectrum every {timing.learned_cadence_s:.2g} s"
        elif timing.learned_cadence_s is not None:
            text += f" · New spectrum every {timing.learned_cadence_s:.2g} s"
        self.lbl_timing.setText(text)

    def set_flip_x(self, checked: bool) -> None:
        self._flip_x = bool(checked)
        if self._lines_view is not None:
            self._lines_view.set_flip_x(self._flip_x)
        else:
            self._apply_x_axis_style()
            self.canvas.draw_idle()

    def _on_trace_thickness_changed(self, _value: int) -> None:
        if self._lines_view is None:
            return
        self._lines_view.set_thickness(
            self.sb_h_thickness.value(), self.sb_v_thickness.value()
        )

    def _on_status(self, status: str) -> None:
        colors = {
            "Monitoring": "#2e8b57",
            "Stopped": "#c62828",
            "Acquisition appears stopped": "#cc7000",
        }
        color = colors.get(status)
        if color:
            self.lbl_status.setText(
                f"Status: <b><span style=\"color:{color};\">{status}</span></b>"
            )
        else:
            self.lbl_status.setText(f"Status: <b>{status}</b>")

    def _choose_cmap(self) -> None:
        cmap = choose_colormap(self, current=self._cmap)
        if not cmap:
            return
        self._cmap = str(cmap)
        if self._lines_view is not None:
            self._lines_view.set_cmap(self._cmap)
        elif self._image is not None:
            self._image.set_cmap(self._cmap)
            self.canvas.draw_idle()

    def _reload_latest_snapshot(self) -> None:
        callback = self._reload_latest_callback
        if not callable(callback):
            return
        try:
            reloaded = bool(callback())
        except Exception:
            reloaded = False
        if reloaded:
            # Keep the status line reserved for acquisition state; the reload
            # action must not hide Monitoring/Stopped/idle information.
            pass

    def _toggle_monitoring(self) -> None:
        if self._running:
            self._controller.stop()
            self._running = False
            self.btn_start_stop.setText("Start")
        else:
            self._controller.start()
            self._running = True
            self.btn_start_stop.setText("Stop")

    def _on_update(self, update: LiveMapUpdate) -> None:
        new_rows = np.asarray(update.new_spectra, dtype=float)
        if new_rows.ndim != 2 or new_rows.shape[0] < 1:
            return
        x = np.asarray(update.x, dtype=float)
        self._xlabel = str(update.xlabel or "Energy [eV]")

        if update.reset or self._spectra is None or self._x is None:
            self._x = x.copy()
            self._spectra = new_rows.copy()
            self._second_axis = (
                None if update.second_axis is None else np.asarray(update.second_axis, dtype=float).copy()
            )
            self._second_axis_label = str(update.second_axis_label or "")
            self._rebuild_image()
        else:
            if self._x.shape != x.shape or not np.allclose(self._x, x, rtol=1e-9, atol=1e-10, equal_nan=True):
                return
            self._spectra = np.vstack([self._spectra, new_rows])
            if update.second_axis_label:
                self._second_axis_label = str(update.second_axis_label)
            if update.second_axis is not None:
                new_axis = np.asarray(update.second_axis, dtype=float)
                if self._second_axis is None:
                    # If the physical second-axis appeared only after the first
                    # spectrum, reconstruct the missing prefix as scan numbers.
                    prefix_n = self._spectra.shape[0] - new_axis.size
                    self._second_axis = np.arange(1, prefix_n + 1, dtype=float)
                self._second_axis = np.concatenate([self._second_axis, new_axis])
            elif self._second_axis is not None:
                start = self._second_axis.size + 1
                self._second_axis = np.concatenate(
                    [self._second_axis, np.arange(start, start + new_rows.shape[0], dtype=float)]
                )
            self._update_image_data()

        self.lbl_spectra.setText(f"Spectra: {int(update.total_spectra)}")
        self.lbl_last_update.setText(f"Last update: {datetime.now().strftime('%H:%M:%S')}")

    def _display_y(self) -> np.ndarray:
        n = 0 if self._spectra is None else int(self._spectra.shape[0])
        if self._second_axis is not None and self._second_axis.size == n:
            return np.asarray(self._second_axis, dtype=float)
        return np.arange(1, n + 1, dtype=float)

    @staticmethod
    def _axis_extent(values: np.ndarray) -> tuple[float, float]:
        vals = np.asarray(values, dtype=float)
        if vals.size == 0:
            return 0.5, 1.5
        if vals.size == 1:
            return float(vals[0] - 0.5), float(vals[0] + 0.5)
        first_step = vals[1] - vals[0]
        last_step = vals[-1] - vals[-2]
        return float(vals[0] - first_step / 2.0), float(vals[-1] + last_step / 2.0)

    def _image_extent(self) -> tuple[float, float, float, float]:
        assert self._x is not None
        y = self._display_y()
        x0, x1 = self._axis_extent(self._x)
        y0, y1 = self._axis_extent(y)
        return x0, x1, y0, y1

    def _rebuild_image(self) -> None:
        if self._spectra is None or self._x is None:
            return
        plot_title = self.path.name
        if self.region_name:
            plot_title += f" — {self.region_name}"
        self._lines_view.cmap = self._cmap
        self._lines_view.flip_x = self._flip_x
        self._lines_view.set_thickness(
            self.sb_h_thickness.value(), self.sb_v_thickness.value()
        )
        self._lines_view.set_data(
            self._x, self._spectra, second_axis=self._second_axis,
            second_axis_label=self._second_axis_label,
            xlabel=self._xlabel, title=plot_title, reset=True,
        )
        self.ax = self._lines_view.ax_map
        self._image = self._lines_view.image

    def _update_image_data(self) -> None:
        if self._spectra is None or self._x is None:
            return
        plot_title = self.path.name
        if self.region_name:
            plot_title += f" — {self.region_name}"
        self._lines_view.cmap = self._cmap
        self._lines_view.flip_x = self._flip_x
        self._lines_view.set_data(
            self._x, self._spectra, second_axis=self._second_axis,
            second_axis_label=self._second_axis_label,
            xlabel=self._xlabel, title=plot_title, reset=False,
        )
        self.ax = self._lines_view.ax_map
        self._image = self._lines_view.image


    def _apply_x_axis_style(self) -> None:
        if self._lines_view is not None:
            self._lines_view.set_flip_x(self._flip_x)
            return
        if self._x is None or self._x.size == 0 or self.ax is None:
            return
        finite = self._x[np.isfinite(self._x)]
        if finite.size == 0:
            return
        lo = float(np.min(finite))
        hi = float(np.max(finite))
        self.ax.set_xlabel(self._xlabel)
        self.ax.set_xlim(hi, lo) if self._flip_x else self.ax.set_xlim(lo, hi)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API spelling
        try:
            self._controller.shutdown()
        finally:
            super().closeEvent(event)
