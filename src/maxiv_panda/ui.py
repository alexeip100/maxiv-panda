from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from PyQt6.QtCore import Qt, QTimer, QPoint, QEvent, QRect
from PyQt6.QtGui import QColor, QIcon, QPixmap, QKeySequence, QTextDocument, QAction, QShortcut, QCursor
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QProgressBar,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QTabWidget,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QApplication,
    QLineEdit,
    QSpinBox,
    QStyle,
    QStyleOptionTab,
    QStyleOptionViewItem,
    QStylePainter,
    QToolButton,
    QToolTip,
    QColorDialog,
)
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import ScalarFormatter, FuncFormatter

from .loaded_tree import LoadedTreeController
from .loaders import filter_for_kind, open_files_dialog, parse_file
from .log_utils import get_logger, log_noncritical_error
from .plot_controller import PlotSelectionController
from .processed_controller import ProcessedController
from .selection_tree import SelectedTreeManager
from .energy_utils import default_flip_for_energy_scale, normalize_energy_xlabel
from .version import __date__, __version__
from .icon import application_icon
from .utils.help_text import get_usage_html
from .utils.colors import mpl_color_to_hex
from .widgets.help_browser import HelpBrowser
from .ui_actions_mixin import UiActionsMixin
from .ui_source_reload_mixin import UiSourceReloadMixin
from .ui_raw_data_mixin import UiRawDataMixin
from .ui_processed_data_mixin import UiProcessedDataMixin
from .ui_map_plot_mixin import MapPlotMixin
from .colormap_dialog import choose_colormap
from .signal_identification.cross_section_reference import CrossSectionReferencePanel
from .signal_identification.binding_energy_reference import BindingEnergyReferencePanel
from .workflows.plotting import PlottedDataPanel
from .ui_style import current_ui_metrics, apply_control_metrics, register_layout_role, register_widget_role
from .intensity_units import COUNTS, CPS, time_per_spectrum_channel, scale_payload


@dataclass
class PlotPayload:
    """What a tree item represents for plotting."""

    title: str
    x: Any
    y: Any
    xlabel: str = "x"
    ylabel: str = "Intensity"
    energy_scale: str = "Unknown"  # "Binding" | "Kinetic" | "Unknown"
    metadata: dict[str, Any] | None = None


class LoadedFilesTreeWidget(QTreeWidget):
    """Left-hand tree that accepts file drops from the OS file manager."""

    def __init__(self, drop_callback, parent: QWidget | None = None):
        super().__init__(parent)
        self._drop_callback = drop_callback
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    @staticmethod
    def _extract_supported_paths(event) -> list[str]:
        try:
            urls = event.mimeData().urls()
        except Exception:
            return []
        paths: list[str] = []
        for url in urls:
            try:
                if not url.isLocalFile():
                    continue
                local = url.toLocalFile()
            except Exception:
                continue
            if not local:
                continue
            suffix = str(local).lower()
            if suffix.endswith('.txt') or suffix.endswith('.ibw') or suffix.endswith('.xy'):
                paths.append(local)
        return paths

    def dragEnterEvent(self, event) -> None:
        if self._extract_supported_paths(event):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if self._extract_supported_paths(event):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        paths = self._extract_supported_paths(event)
        if not paths:
            super().dropEvent(event)
            return
        try:
            self._drop_callback(paths)
            event.acceptProposedAction()
        except Exception as exc:
            log_noncritical_error('handling file drop', exc)
            event.ignore()


class PlotArea(MapPlotMixin, QWidget):
    """Central plotting area with standard matplotlib navigation (zoom/pan/home/save)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        # Let Matplotlib allocate only the space actually needed by plot
        # decorations (title, axis labels, tick labels, and twin/right axes).
        # Fixed subplot margins made ordinary spectra compact, but could clip
        # decorations in other representations -- notably the right-hand
        # iteration numbers in Map view.  Constrained layout keeps every
        # decoration inside the canvas while still maximizing the axes area.
        self.fig = Figure(constrained_layout=True)
        try:
            # Pads are in inches.  Keep them small, but non-zero so text is
            # never flush against (or clipped by) the canvas edge.
            self.fig.set_constrained_layout_pads(
                w_pad=0.08, h_pad=0.08, wspace=0.0, hspace=0.0
            )
        except Exception:
            # Matplotlib >=3.5 supports constrained layout; this fallback is
            # defensive for unusual downstream builds.
            pass
        self.canvas = FigureCanvas(self.fig)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.ax = self.fig.add_subplot(111)
        self.intensity_scale_callback = None
        self.file_drop_callback = None
        self.file_drop_enabled_callback = None
        self.map_palette_callback = None
        # Palette-discovery hint state.  The hint is dwell-triggered: mouse
        # motion over a map restarts a 1 s timer, so it appears only after the
        # pointer has actually come to rest on the image.  ``epoch`` is bumped
        # whenever the user changes map representation/tab, allowing the hint
        # to appear again on a later visit to Simple/Lines/ROI/Raw Data.
        self._map_palette_hint_seen: set[tuple[int, tuple[str, str]]] = set()
        self._map_palette_hint_epoch = 0
        self._map_palette_hint_pending: tuple[int, tuple[str, str]] | None = None
        self._map_palette_hint_dwell_timer = QTimer(self)
        self._map_palette_hint_dwell_timer.setSingleShot(True)
        self._map_palette_hint_dwell_timer.setInterval(1000)
        self._map_palette_hint_dwell_timer.timeout.connect(self._show_map_palette_hint_after_dwell)
        # The Matplotlib canvas is the actual widget under the cursor, so drag
        # events must be accepted there rather than only by the surrounding
        # PlotArea QWidget.  File loading is delegated back to MainWindow.
        self.canvas.setAcceptDrops(True)
        self.canvas.installEventFilter(self)
        self._intensity_axis_selector_enabled = False
        self._intensity_tooltip_visible = False
        self.canvas.mpl_connect("button_press_event", self._on_intensity_axis_double_click)
        self.canvas.mpl_connect("motion_notify_event", self._update_intensity_axis_tooltip)
        self.canvas.mpl_connect("figure_leave_event", self._hide_intensity_axis_tooltip)
        self.canvas.mpl_connect("button_press_event", self._on_map_palette_right_click)
        self.canvas.mpl_connect("motion_notify_event", self._maybe_show_map_palette_hint)
        self.canvas.mpl_connect("figure_leave_event", self._cancel_map_palette_hint_dwell)

        self._map_cross_state = None
        # Persistent per-map H/V cursor memory for MAP -> Lines.  This lives
        # outside the transient Matplotlib cross-section state so palette/view/tab
        # rebuilds can restore the last user-selected positions.
        self._map_lines_position_memory = {}
        self._map_lines_auto_scale_h = True
        self._map_lines_auto_scale_v = True
        self._map_drag_axis = None
        self._map_right_y_mode = "iteration"
        self._map_roi_state = None
        self._map_roi_drag = None
        self._map_norm_band_state = None
        self._map_norm_drag = None
        self._respes_cut_state = None
        self._respes_cut_drag = None
        # In Simple ResPES mode the specialised cut gets first refusal on a
        # click close to its line/boundaries; this keeps a wide normalization
        # band (notably Area normalization) from swallowing every map drag.
        self.canvas.mpl_connect("button_press_event", self._on_respes_cut_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_respes_cut_motion)
        self.canvas.mpl_connect("button_release_event", self._on_respes_cut_release)
        self.canvas.mpl_connect("button_press_event", self._on_map_norm_band_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_map_norm_band_motion)
        self.canvas.mpl_connect("button_release_event", self._on_map_norm_band_release)
        self.canvas.mpl_connect("button_press_event", self._on_map_cross_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_map_cross_motion)
        self.canvas.mpl_connect("button_release_event", self._on_map_cross_release)
        self.canvas.mpl_connect("button_press_event", self._on_map_roi_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_map_roi_motion)
        self.canvas.mpl_connect("button_release_event", self._on_map_roi_release)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self.clear("Load a TXT, IBW, or XY file to begin")








    def _event_is_2d_map(self, event) -> bool:
        """Return True when the pointer is over a displayed 2D image.

        Simple map view uses a transparent primary Axes above a twinned Axes
        that owns the image.  Matplotlib therefore reports the transparent
        Axes as ``event.inaxes`` even though the pointer is visibly over the
        image.  Test every overlapping Axes at the event pixel position so
        Raw Data and View -> Simple behave exactly like Lines/ROI.
        """
        if event is None:
            return False
        try:
            x = float(event.x)
            y = float(event.y)
        except Exception:
            return False
        try:
            for ax in self.fig.axes:
                if not getattr(ax, "images", None):
                    continue
                bbox = getattr(ax, "bbox", None)
                if bbox is not None and bbox.contains(x, y):
                    return True
        except Exception:
            return False
        return False

    def _map_palette_hint_key(self, event) -> tuple[str, str]:
        # Prefer the image-owning axes.  In Simple view event.inaxes may be a
        # transparent/twinned axes layered above the visible map.
        try:
            x = float(event.x)
            y = float(event.y)
            for ax in self.fig.axes:
                if not getattr(ax, "images", None):
                    continue
                bbox = getattr(ax, "bbox", None)
                if bbox is not None and bbox.contains(x, y):
                    return (str(ax.get_title() or ""), str(ax.get_xlabel() or ""))
        except Exception:
            pass
        ax = getattr(event, "inaxes", None)
        if ax is None:
            return ("", "")
        try:
            return (str(ax.get_title() or ""), str(ax.get_xlabel() or ""))
        except Exception:
            return ("", "")

    def reset_map_palette_hint_visit(self) -> None:
        """Start a fresh palette-hint visit after a representation/tab change."""
        self._map_palette_hint_epoch += 1
        self._cancel_map_palette_hint_dwell()

    def _cancel_map_palette_hint_dwell(self, event=None) -> None:
        try:
            self._map_palette_hint_dwell_timer.stop()
        except Exception:
            pass
        self._map_palette_hint_pending = None

    def _cursor_is_over_2d_map(self) -> bool:
        """Re-check the real cursor position when the dwell timer expires."""
        try:
            pos = self.canvas.mapFromGlobal(QCursor.pos())
            x = float(pos.x())
            y = float(self.canvas.height() - pos.y())
            for ax in self.fig.axes:
                if not getattr(ax, "images", None):
                    continue
                bbox = getattr(ax, "bbox", None)
                if bbox is not None and bbox.contains(x, y):
                    return True
        except Exception:
            pass
        return False

    def _show_map_palette_hint_after_dwell(self) -> None:
        pending = self._map_palette_hint_pending
        if pending is None or pending in self._map_palette_hint_seen:
            return
        if not self._cursor_is_over_2d_map():
            self._map_palette_hint_pending = None
            return
        self._map_palette_hint_seen.add(pending)
        self._map_palette_hint_pending = None
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
        """Arm the 1 s dwell hint while the pointer moves over a 2D map."""
        if not self._event_is_2d_map(event):
            self._cancel_map_palette_hint_dwell()
            return
        key = (self._map_palette_hint_epoch, self._map_palette_hint_key(event))
        if key in self._map_palette_hint_seen:
            self._cancel_map_palette_hint_dwell()
            return
        self._map_palette_hint_pending = key
        # QTimer.start() restarts an active single-shot timer.  Thus continuous
        # movement never displays the hint; it appears only after 1 s of rest.
        self._map_palette_hint_dwell_timer.start()

    def _on_map_palette_right_click(self, event) -> None:
        """Open the host's existing palette chooser on right-click inside a 2D map."""
        button = getattr(getattr(event, "button", None), "value", getattr(event, "button", None))
        if button != 3 or not self._event_is_2d_map(event):
            return
        callback = getattr(self, "map_palette_callback", None)
        if callable(callback):
            callback()

    def _hide_intensity_axis_tooltip(self, event=None) -> None:
        """Hide the transient Counts/CPS hint."""
        if not self._intensity_tooltip_visible:
            return
        try:
            QToolTip.hideText()
        except Exception:
            pass
        self._intensity_tooltip_visible = False

    def _update_intensity_axis_tooltip(self, event) -> None:
        """Show the Counts/CPS hint while hovering the 1D Intensity title."""
        over_label = False
        if self._intensity_axis_selector_enabled and event is not None:
            try:
                label = self.ax.yaxis.label
                renderer = self.canvas.get_renderer()
                bbox = label.get_window_extent(renderer=renderer).expanded(1.8, 1.45)
                over_label = bbox.contains(float(event.x), float(event.y))
            except Exception:
                over_label = False

        if not over_label:
            self._hide_intensity_axis_tooltip()
            return

        if self._intensity_tooltip_visible:
            return

        try:
            # Matplotlib mouse coordinates use a bottom-left origin while Qt
            # widgets use a top-left origin.  Show the tooltip explicitly at
            # the current label hover position; merely changing canvas.toolTip
            # during a Matplotlib motion event does not trigger Qt's native
            # tooltip timer on all platforms.
            x = int(round(float(event.x)))
            y = int(round(self.canvas.height() - float(event.y)))
            pos = self.canvas.mapToGlobal(QPoint(x + 12, y + 12))
            QToolTip.showText(
                pos,
                "Double-click the Intensity axis title to select Counts or CPS.",
                self.canvas,
            )
            self._intensity_tooltip_visible = True
        except Exception:
            self._intensity_tooltip_visible = False


    def _file_drop_enabled(self) -> bool:
        callback = self.file_drop_enabled_callback
        if callback is None:
            return True
        try:
            return bool(callback())
        except Exception:
            return False

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is self.canvas and event.type() in {
            QEvent.Type.DragEnter,
            QEvent.Type.DragMove,
            QEvent.Type.Drop,
        }:
            if not self._file_drop_enabled():
                event.ignore()
                return False
            paths = LoadedFilesTreeWidget._extract_supported_paths(event)
            if not paths:
                event.ignore()
                return False
            if event.type() == QEvent.Type.Drop:
                callback = self.file_drop_callback
                if callback is None:
                    event.ignore()
                    return False
                try:
                    callback(paths)
                    event.acceptProposedAction()
                    return True
                except Exception as exc:
                    log_noncritical_error('handling plot-area file drop', exc)
                    event.ignore()
                    return True
            event.acceptProposedAction()
            return True
        return super().eventFilter(watched, event)

    def _on_intensity_axis_double_click(self, event) -> None:
        """Open the Counts/CPS selector when the ordinary-spectrum Y title is double-clicked."""
        if not bool(getattr(event, "dblclick", False)) or not self._intensity_axis_selector_enabled:
            return
        if getattr(event, "button", 1) not in (1, None):
            return
        callback = getattr(self, "intensity_scale_callback", None)
        if not callable(callback):
            return
        try:
            label = self.ax.yaxis.label
            renderer = self.canvas.get_renderer()
            bbox = label.get_window_extent(renderer=renderer).expanded(1.6, 1.35)
            if bbox.contains(float(event.x), float(event.y)):
                callback()
        except Exception:
            return

    def clear(self, message: str = "") -> None:
        self._restore_toolbar_coordinate_font()
        # Explicitly tear down MAP-only Matplotlib widgets before removing
        # their axes from the figure.
        self._cleanup_map_roi_widgets()
        self._cleanup_map_lines_widgets()
        # Clear the full figure so any previous twin axes (for map iteration labels)
        # are removed as well.
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        self._intensity_axis_selector_enabled = False
        self.ax.set_xlabel("x")
        self.ax.set_ylabel("Intensity")
        if message:
            self.ax.text(
                0.5,
                0.5,
                message,
                transform=self.ax.transAxes,
                ha="center",
                va="center",
            )
        self.canvas.draw_idle()

    def plot_many(
        self,
        payloads: list[PlotPayload],
        flip_binding_energy: bool,
        colors: list[str] | None = None,
        # Image payloads are tuples:
        #   (x, y, Z, title, xlabel, cmap)
        # For backward compatibility we also accept 5-tuples without cmap.
        images: list[tuple[Any, Any, Any, str, str, Any] | tuple[Any, Any, Any, str, str]] | None = None,
        map_lines_enabled: bool = False,
        map_h_thickness: int = 1,
        map_v_thickness: int = 1,
        map_roi_enabled: bool = False,
        map_roi_spec: dict[str, float] | None = None,
        map_roi_callback: Any | None = None,
        map_roi_pass_callback: Any | None = None,
        map_animation_callback: Any | None = None,
        map_norm_interval: tuple[float, float] | None = None,
        map_norm_mode: str | None = None,
        map_norm_show_region: bool = False,
        map_norm_callback: Any | None = None,
        respes_enabled: bool = False,
        respes_cut_type: str = "constant_be",
        respes_position: float | None = None,
        respes_width: float | None = None,
        respes_callback: Any | None = None,
        respes_energy_axis: str = "be",
        respes_work_function: float = 4.5,
    ) -> list[Any]:
        """Plot multiple payloads at once.

        We intentionally avoid tight_layout() here because it may become extremely slow
        or hang on some Matplotlib builds when triggered frequently.
        """

        # Ordinary 1D plots use the normal application toolbar font.  MAP
        # rendering switches only its coordinate readout to fixed-width below.
        if not images:
            self._restore_toolbar_coordinate_font()

        # Persist the current Lines cursor positions before any redraw/view/tab
        # rebuild clears the transient Matplotlib cross-section artists.
        try:
            self._remember_map_lines_state()
        except Exception:
            pass

        # ROI and Lines use Matplotlib Button widgets in figure-overlay axes.
        # Disconnect those widgets *before* clearing/rebuilding the figure;
        # simply clearing their axes is not enough to remove canvas callbacks.
        self._cleanup_map_roi_widgets()
        self._cleanup_map_lines_widgets()

        # Ordinary plots use constrained layout so titles/ticks are never clipped.
        # Lines-mode maps temporarily switch to a fixed geometry below; restore
        # the automatic layout engine whenever a new ordinary render starts.
        try:
            self.fig.set_layout_engine("constrained")
            self.fig.set_constrained_layout_pads(
                w_pad=0.08, h_pad=0.08, wspace=0.0, hspace=0.0
            )
        except Exception:
            try:
                self.fig.set_constrained_layout(True)
            except Exception:
                pass

        # Clear the full figure to also remove any previous twin axes.
        self.fig.clear()
        self.ax = self.fig.add_subplot(111)
        if not payloads and not images:
            self.clear("Load a TXT, IBW, or XY file to begin")
            return []

        self._map_cross_state = None
        self._map_drag_axis = None
        self._map_roi_state = None
        self._map_roi_drag = None
        self._map_norm_band_state = None
        self._map_norm_drag = None
        self._respes_cut_state = None
        self._respes_cut_drag = None
        self._intensity_axis_selector_enabled = bool(payloads) and not bool(images)
        try:
            # Lines/ROI will install a right-axis switching hint only when a
            # genuine alternative Y coordinate is available.  Clear any hint
            # left by the previous map before dispatching the new view.
            self.canvas.setToolTip("")
        except Exception:
            pass
        if images and len(images) == 1:
            if respes_enabled and not map_lines_enabled and not map_roi_enabled:
                return self._plot_single_map_with_respes(
                    payloads, images[0], flip_binding_energy, colors,
                    cut_type=respes_cut_type, position=respes_position,
                    width=respes_width, cut_callback=respes_callback,
                    energy_axis=respes_energy_axis, work_function=respes_work_function,
                    norm_interval=map_norm_interval if map_norm_show_region else None,
                    norm_mode=map_norm_mode, norm_callback=map_norm_callback,
                )
            if map_roi_enabled:
                return self._plot_single_map_with_roi(
                    payloads, images[0], flip_binding_energy, colors,
                    roi_spec=map_roi_spec, roi_callback=map_roi_callback,
                    roi_pass_callback=map_roi_pass_callback,
                    norm_interval=map_norm_interval if map_norm_show_region else None,
                    norm_mode=map_norm_mode, norm_callback=map_norm_callback,
                )
            if map_lines_enabled:
                return self._plot_single_map_with_cross_sections(
                    payloads, images[0], flip_binding_energy, colors,
                    h_thickness=map_h_thickness, v_thickness=map_v_thickness,
                    animation_callback=map_animation_callback,
                    norm_interval=map_norm_interval if map_norm_show_region else None,
                    norm_mode=map_norm_mode, norm_callback=map_norm_callback,
                )

        # Axis labels/title: prefer a line payload if available, otherwise use image metadata.
        if payloads:
            first = payloads[0]
            self.ax.set_xlabel(normalize_energy_xlabel(first.xlabel, getattr(first, "energy_scale", "Unknown")))
            self.ax.set_ylabel(first.ylabel)
            self.ax.set_title(first.title)
        else:
            # images exist
            img0 = images[0]
            # Accept both 5- and 6-tuples: (x, y, Z, title, xlabel[, cmap])
            _x, _y, _Z, title, xlabel = img0[:5]
            self.ax.set_xlabel(xlabel)
            self.ax.set_ylabel("")
            self.ax.set_title(title)

        used_colors: list[Any] = []
        # Plot line payloads.
        for idx, p in enumerate(payloads):
            col = None
            if colors is not None and idx < len(colors):
                col = colors[idx]

            # If we're overlaying an Average curve on top of a colormap,
            # force it to be clearly visible (white, thicker).
            avg_overlay = False
            try:
                if images and ("average" in (p.title or "").lower()):
                    avg_overlay = True
            except Exception:
                avg_overlay = False

            if avg_overlay:
                line = self.ax.plot(p.x, p.y, color="white", linewidth=2.0)[0]
            elif col is not None:
                line = self.ax.plot(p.x, p.y, color=col)[0]
            else:
                line = self.ax.plot(p.x, p.y)[0]

            try:
                line.set_zorder(5)
            except Exception:
                pass

            # Default linewidth for non-average overlays
            if not avg_overlay:
                try:
                    line.set_linewidth(1.5)
                except Exception:
                    pass

            try:
                # Preserve Matplotlib's native color object.  In some
                # environments get_color() returns an RGB(A) tuple rather than
                # a string; stringifying that tuple makes it no longer a valid
                # Matplotlib color specification and can make Qt swatches vanish.
                used_colors.append(line.get_color())
            except Exception:
                used_colors.append("#000000")

        # Plot image payloads (colormaps) if requested.
        # Important: colormaps represent *iterations* (y-axis = iteration index),
        # while the left y-axis is reserved for intensity of any line overlays
        # (e.g., the Average curve).
        if images:
            # Create a right y-axis for iteration index.
            axr = self.ax.twinx()
            axr.set_ylabel('Iteration')
            # We'll place iteration labels at the *centers* of the image rows.
            # This is more intuitive than labeling the row boundaries.
            _map_tick_labels_single: list[int] | None = None
            _map_secondary_y_single = None
            _map_secondary_ylabel_single = ""
            _map_max_rows = 0
            # Ensure the colormap is drawn behind line overlays.
            try:
                axr.set_zorder(0)
                self.ax.set_zorder(1)
                self.ax.patch.set_alpha(0)
            except Exception:
                pass

            # images: list of (x, y, Z, title, xlabel, cmap)
            overall_ymin = None
            overall_ymax = None
            for img in images:
                x, y, Z, _title, _xlabel = img[:5]
                _cmap = img[5] if len(img) >= 6 else None
                try:
                    # Ensure Z is a proper 2D numeric array.
                    # If only a single iteration is selected, callers may
                    # provide a 1D vector or a list with one row; imshow() expects
                    # a 2D array.
                    import numpy as _np
                    Z_arr = _np.asarray(Z, dtype=float)
                    if Z_arr.ndim == 1:
                        Z_arr = Z_arr.reshape(1, -1)
                    elif Z_arr.ndim > 2:
                        # Flatten any higher dims defensively.
                        Z_arr = Z_arr.reshape(Z_arr.shape[0], -1)

                    rows = int(Z_arr.shape[0])
                    if rows > _map_max_rows:
                        _map_max_rows = rows
                    # If there's only one map, keep its iteration labels (y) so we can
                    # display them at stripe centers. For multiple simultaneous maps,
                    # a single shared right axis cannot show different label sets, so
                    # we fall back to 1..N.
                    if len(images) == 1:
                        try:
                            _map_tick_labels_single = [int(v) for v in y]
                        except Exception:
                            _map_tick_labels_single = None
                        sec_values, sec_label = self._map_secondary_axis(img, rows)
                        if sec_values is not None:
                            _map_secondary_y_single = sec_values
                            _map_secondary_ylabel_single = sec_label
                        else:
                            _map_secondary_y_single = None
                            _map_secondary_ylabel_single = ""

                    # extent expects [xmin, xmax, ymin, ymax]
                    # Use endpoints so that the *data orientation* matches the x-array order.
                    # (Using min/max breaks descending BE axes for imshow.)
                    x_arr = _np.asarray(x, dtype=float)
                    xmin, xmax = float(x_arr[0]), float(x_arr[-1])
                    # Use a 0..rows scale so that tick labels can be placed at row centers.
                    ymin, ymax = 0.0, float(rows)
                    im = axr.imshow(
                        Z_arr,
                        aspect="auto",
                        origin="lower",
                        extent=[xmin, xmax, ymin, ymax],
                        cmap=_cmap,
                    )
                    self._disable_map_artist_cursor_data(im)
                    try:
                        im.set_zorder(0)
                        im.set_alpha(0.85)
                    except Exception:
                        pass
                    if overall_ymin is None or ymin < overall_ymin:
                        overall_ymin = ymin
                    if overall_ymax is None or ymax > overall_ymax:
                        overall_ymax = ymax
                    # If there are no line payloads, hide left y ticks/label.
                    if not payloads:
                        self.ax.set_ylabel("")
                        self.ax.set_yticks([])
                except Exception:
                    pass

            if map_norm_show_region and map_norm_interval is not None:
                # In Simple map view the transparent primary Axes (self.ax)
                # sits above the twinned image/iteration Axes and therefore
                # receives mouse events.  Draw/register the interactive
                # normalization band on that same Axes so At-BE dragging works
                # exactly as it does in Lines and ROI.  Mixed map+line overlays
                # retain the image Axes for the normalization band.
                _norm_ax = self.ax if not payloads else axr
                self._draw_map_normalization_band(
                    _norm_ax, map_norm_interval, map_norm_mode, map_norm_callback
                )

            # Ensure all maps are visible if multiple regions are mapped.
            try:
                if _map_max_rows > 0:
                    if len(images) == 1 and _map_tick_labels_single and len(_map_tick_labels_single) == _map_max_rows:
                        iteration_labels = _map_tick_labels_single
                    else:
                        iteration_labels = list(range(1, _map_max_rows + 1))

                    if not payloads:
                        # Simple uses exactly the same physical-left / iteration-right
                        # mapping as Lines and ROI.  Both axes still use internal row
                        # coordinates; only their visible labels differ.
                        self._configure_map_y_axes(
                            self.ax, axr, _map_max_rows, iteration_labels,
                            _map_secondary_y_single, _map_secondary_ylabel_single,
                        )
                        self._set_map_coordinate_formatter(
                            [self.ax, axr], images[0][0], _map_max_rows, images[0][4],
                            iteration_labels, _map_secondary_y_single, _map_secondary_ylabel_single,
                            images[0][2],
                        )
                        self.ax.patch.set_visible(False)
                    else:
                        # Mixed map+line overlays retain the main intensity axis.
                        # Configure the iteration scale on the map axes, then add an
                        # outward physical scale only when the source provides one.
                        centers, tick_idx = self._map_tick_indices(_map_max_rows)
                        axr.set_ylim(0.0, float(_map_max_rows))
                        axr.set_yticks(centers[tick_idx])
                        axr.set_yticklabels([
                            self._format_map_axis_value(iteration_labels[i]) for i in tick_idx
                        ])
                        if (_map_secondary_y_single is not None
                                and len(_map_secondary_y_single) == _map_max_rows):
                            axl = axr.twinx()
                            axl.set_ylim(0.0, float(_map_max_rows))
                            axl.set_yticks(centers[tick_idx])
                            axl.set_yticklabels([
                                self._format_map_axis_value(_map_secondary_y_single[i])
                                for i in tick_idx
                            ])
                            axl.set_ylabel(_map_secondary_ylabel_single)
                            axl.yaxis.set_ticks_position("left")
                            axl.yaxis.set_label_position("left")
                            axl.spines["left"].set_position(("outward", 42))
                            axl.spines["left"].set_visible(True)
                            axl.spines["right"].set_visible(False)
                            axl.patch.set_visible(False)
            except Exception:
                pass

        # X-axis range management (critical when mixing maps + curves from different regions).
        # Matplotlib autoscaling on the main axis does not consider images drawn on twin axes,
        # so we must explicitly set the x-limits to include BOTH line payloads and map extents.
        current_xlabel = ""
        if payloads:
            current_xlabel = payloads[0].xlabel
        elif images:
            current_xlabel = images[0][4]
        # We treat Binding and Kinetic energy scales equally. The GUI provides an explicit
        # "Flip X axis" checkbox; if enabled, we flip regardless of label.

        try:
            import numpy as _np

            xs: list[float] = []
            for p in payloads:
                try:
                    xs_arr = _np.asarray(p.x, dtype=float)
                    xs.extend([float(_np.nanmin(xs_arr)), float(_np.nanmax(xs_arr))])
                except Exception:
                    pass
            if images:
                for img in images:
                    x, _y, _Z, _title, _xlabel = img[:5]
                    try:
                        x_arr = _np.asarray(x, dtype=float)
                        xs.extend([float(_np.nanmin(x_arr)), float(_np.nanmax(x_arr))])
                    except Exception:
                        pass

            if xs:
                xlo, xhi = float(min(xs)), float(max(xs))
                # IMPORTANT: do NOT use invert_xaxis() here because it toggles state and can
                # lead to double-flips when mixed with imshow(extent=...) for maps.
                if flip_binding_energy:
                    for _ax in self.fig.axes:
                        _ax.set_xlim(xhi, xlo)
                else:
                    for _ax in self.fig.axes:
                        _ax.set_xlim(xlo, xhi)
        except Exception as exc:
            log_noncritical_error("updating selected tree visibility after rebuild", exc, logger=self._logger)

        # Apply scientific notation only to an ordinary 1D intensity Y axis.
        # In a pure Simple/Raw 2D-map view ``self.ax`` is the map's visible
        # left Y axis (physical second dimension or mirrored Iteration).  Do not
        # replace its explicit row-label formatter with ScalarFormatter: doing
        # so turns an Iteration scale such as 1, 6, 11, ... into misleading
        # internal row coordinates such as 0.05, 0.55, ... ×10¹.
        try:
            _pure_map_view = bool(images and not payloads)
            if not _pure_map_view:
                formatter = ScalarFormatter(useMathText=True)
                formatter.set_scientific(True)
                formatter.set_powerlimits((0, 0))
                self.ax.yaxis.set_major_formatter(formatter)
                self.ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
        except Exception:
            pass

        self.canvas.draw_idle()
        return used_colors












class _SelectionAwareTabBar(QTabBar):
    """QTabBar that can display all tabs as inactive.

    Qt tab bars normally always paint one tab as selected.  The application has
    two visual tab groups controlling one page stack, so the inactive group must
    be able to show no selected tab at all.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selection_active = True

    def setSelectionActive(self, active: bool) -> None:  # noqa: N802 - Qt API spelling
        active = bool(active)
        if self._selection_active != active:
            self._selection_active = active
            self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt API spelling
        if self._selection_active:
            return super().paintEvent(event)

        painter = QStylePainter(self)
        option = QStyleOptionTab()
        for index in range(self.count()):
            # Hidden reference-page tabs remain part of the main QTabWidget
            # page stack, but must not be painted by this custom inactive-state
            # renderer.  QTabBar's native paint path already skips them; our
            # manual loop must do the same.
            if hasattr(self, "isTabVisible") and not self.isTabVisible(index):
                continue
            self.initStyleOption(option, index)
            if not option.rect.isValid() or option.rect.isEmpty():
                continue
            option.state &= ~QStyle.StateFlag.State_Selected
            painter.drawControl(QStyle.ControlElement.CE_TabBarTab, option)


class _SeparatedReferenceTabBar(_SelectionAwareTabBar):
    """Main tab bar showing only the data-workflow tabs.

    Reference-page selectors live in the QTabWidget top-right corner.  Keeping
    them out of this bar avoids making the tab bar's size hint depend on the
    surrounding window width (which can create an unbounded resize loop).
    """

    FIRST_REFERENCE_INDEX = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUsesScrollButtons(False)

    def tabSizeHint(self, index):  # noqa: N802 - Qt API spelling
        hint = super().tabSizeHint(index)
        if index >= self.FIRST_REFERENCE_INDEX:
            hint.setWidth(0)
        return hint

    def minimumTabSizeHint(self, index):  # noqa: N802 - Qt API spelling
        hint = super().minimumTabSizeHint(index)
        if index >= self.FIRST_REFERENCE_INDEX:
            hint.setWidth(0)
        return hint


class MainWindow(UiProcessedDataMixin, UiRawDataMixin, UiSourceReloadMixin, UiActionsMixin, QMainWindow):
    """Starter GUI for PANDA.

    - Same initial geometry as flexpes_nexafs reference.
    - Left: one-row controls (Load menu + Close all) and a tree.
    - Center: matplotlib plot area with standard navigation.
    """

    ROLE_PAYLOAD = Qt.ItemDataRole.UserRole + 1
    ROLE_KEY = Qt.ItemDataRole.UserRole + 2
    ROLE_REGION = Qt.ItemDataRole.UserRole + 3
    ROLE_META = Qt.ItemDataRole.UserRole + 4
    ROLE_FILE = Qt.ItemDataRole.UserRole + 5

    def __init__(self):
        super().__init__()
        self._logger = get_logger()
        self.setWindowTitle("PANDA")
        icon = application_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        # Reference geometry from flexpes_nexafs
        self.setGeometry(50, 50, 1650, 800)
        try:
            screen = self.screen()
            if screen is not None:
                ag = screen.availableGeometry()
                self.move(ag.left() + 50, ag.top() + 50)
        except Exception:
            pass

        self._raw_intensity_mode = COUNTS
        self._processed_intensity_mode = COUNTS

        central = QWidget(self)
        self.setCentralWidget(central)
        ui_metrics = current_ui_metrics()

        root_layout = QVBoxLayout(central)
        register_layout_role(root_layout, "panel")
        root_layout.setContentsMargins(
            ui_metrics.panel_margin, ui_metrics.panel_margin,
            ui_metrics.panel_margin, ui_metrics.panel_margin,
        )
        root_layout.setSpacing(ui_metrics.layout_spacing)

        splitter = QSplitter(Qt.Orientation.Horizontal, central)
        splitter.setChildrenCollapsible(False)
        root_layout.addWidget(splitter, 1)

        # -----------------
        # Left panel
        # -----------------
        left_panel = QWidget(splitter)
        left_layout = QVBoxLayout(left_panel)
        register_layout_role(left_layout, "plain")
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(ui_metrics.layout_spacing)

        # Top controls (ONE ROW)
        controls = QWidget(left_panel)
        ctl = QHBoxLayout(controls)
        register_layout_role(ctl, "plain")
        ctl.setContentsMargins(0, 0, 0, 0)
        ctl.setSpacing(ui_metrics.layout_spacing)

        # Compact global Settings entry point.  Keep it icon-only so it does
        # not compete for horizontal space with the primary file controls.
        self.btn_settings = QToolButton(controls)
        self.btn_settings.setText("⚙")
        self.btn_settings.setToolTip("Settings")
        self.btn_settings.setAccessibleName("Settings")
        self.btn_settings.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        register_widget_role(self.btn_settings, "settings_button")
        self.btn_settings.setFixedSize(ui_metrics.standard_control_height, ui_metrics.standard_control_height)
        self.btn_settings.clicked.connect(self.show_settings)

        # Primary file/session menu. Drag-and-drop remains the quickest way
        # to load source data; this menu provides explicit loaders and the
        # session entry points.
        self.btn_load = QPushButton("File", controls)
        self.btn_load.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        load_menu = QMenu(self.btn_load)
        load_data_menu = load_menu.addMenu("Load data...")
        self.act_txt = QAction("TXT", self)
        self.act_ibw = QAction("IBW", self)
        self.act_xy = QAction("XY (SPECS Prodigy)", self)
        self.act_txt.triggered.connect(lambda: self._load_file("TXT"))
        self.act_ibw.triggered.connect(lambda: self._load_file("IBW"))
        self.act_xy.triggered.connect(lambda: self._load_file("XY"))
        load_data_menu.addAction(self.act_txt)
        load_data_menu.addAction(self.act_ibw)
        load_data_menu.addAction(self.act_xy)
        load_menu.addSeparator()
        self.act_open_session = load_menu.addAction("Open session...")
        self.act_save_session = load_menu.addAction("Save session...")
        self.act_open_session.triggered.connect(self._open_session)
        self.act_save_session.triggered.connect(self._save_session)
        load_menu.addSeparator()
        self.act_exit = load_menu.addAction("Exit")
        self.act_exit.triggered.connect(self.close)
        # QPushButton+setMenu gives the "Help button" style dropdown behavior.
        self.btn_load.setMenu(load_menu)

        self.btn_close_all = QPushButton("Close all", controls)
        self.btn_close_all.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_close_all.clicked.connect(self.close_all)

        self.btn_clear_all = QPushButton("Clear all", controls)
        self.btn_clear_all.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_clear_all.clicked.connect(self.clear_all)

        self.btn_help = QPushButton("Help", controls)
        self.btn_help.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.help_menu = QMenu(self.btn_help)
        self.act_help_controls = self.help_menu.addAction("What is what?")
        self.act_help_howto = self.help_menu.addAction("How to?")
        self.act_help_whats_new = self.help_menu.addAction("What's new?")
        self.help_menu.addSeparator()
        self.act_help_about = self.help_menu.addAction("About")
        self.btn_help.setMenu(self.help_menu)
        self.act_help_controls.triggered.connect(lambda: self.show_usage_info(md_filename="usage_controls.md", window_title="Help — What is what?"))
        self.act_help_howto.triggered.connect(lambda: self.show_usage_info(md_filename="usage_workflows.md", window_title="Help — How to?"))
        self.act_help_whats_new.triggered.connect(lambda: self.show_usage_info(md_filename="whats_new.md", window_title="Help — What's new?"))
        self.act_help_about.triggered.connect(self.show_about_info)

        ctl.addWidget(self.btn_settings)
        ctl.addWidget(self.btn_load)
        ctl.addWidget(self.btn_close_all)
        ctl.addWidget(self.btn_clear_all)
        ctl.addWidget(self.btn_help)

        left_layout.addWidget(controls, 0)

        # Folder path label (like flexpes_nexafs' "No file open" label)
        self.folder_label = QLabel("No folder selected", left_panel)
        self.folder_label.setWordWrap(True)
        try:
            self.folder_label.setStyleSheet("color: palette(mid);")
        except Exception:
            pass
        left_layout.addWidget(self.folder_label, 0)

        # Tree
        self.tree = LoadedFilesTreeWidget(self._load_dropped_files, left_panel)
        register_widget_role(self.tree, "loaded_tree")
        self.tree.setHeaderLabels(["File structure"])
        self.tree.setMinimumWidth(ui_metrics.loaded_tree_min_width)
        try:
            from PyQt6.QtWidgets import QHeaderView  # type: ignore
            self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        except Exception:
            pass
        # We rely on per-curve checkboxes rather than selection for plotting.
        self.tree.itemChanged.connect(self._on_loaded_tree_item_changed)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_loaded_tree_context_menu)
        self._metadata_dialogs = set()
        self._live_monitor_windows: dict[tuple[str, int], object] = {}
        left_layout.addWidget(self.tree, 1)

        self.loading_status = QWidget(left_panel)
        self.loading_status.setVisible(False)
        _loading_row = QHBoxLayout(self.loading_status)
        _loading_row.setContentsMargins(0, 0, 0, 0)
        _loading_row.setSpacing(ui_metrics.layout_spacing)
        self.loading_progress = QProgressBar(self.loading_status)
        register_widget_role(self.loading_progress, "progress")
        self.loading_progress.setRange(0, 0)
        self.loading_progress.setTextVisible(False)
        self.loading_progress.setFixedWidth(90)
        self.loading_progress.setFixedHeight(ui_metrics.progress_bar_height)
        self.loading_label = QLabel("Loading...", self.loading_status)
        try:
            self.loading_label.setStyleSheet("color: palette(mid);")
        except Exception:
            pass
        _loading_row.addWidget(self.loading_progress, 0)
        _loading_row.addWidget(self.loading_label, 0)
        _loading_row.addStretch(1)
        left_layout.addWidget(self.loading_status, 0)

        self._files_root = QTreeWidgetItem(["Loaded files"])  # top-level root
        self._files_root.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.tree.addTopLevelItem(self._files_root)
        self._files_root.setExpanded(True)

        # -----------------
        # Right panel: tabs
        #   - Raw Data: plot + selected curves tree + raw-specific controls
        #   - Processed Data: plot + selected curves tree + processed-specific controls
        #
        # IMPORTANT: plot + selected-tree must be the same objects in both tabs.
        # We therefore host them in a single shared splitter and *move* it between
        # tab pages on demand.
        # -----------------
        tabs = QTabWidget(splitter)
        tabs.setTabBar(_SeparatedReferenceTabBar(tabs))
        tabs.tabBar().setExpanding(False)
        # Keep a reference so processing-only UI features (e.g. normalization) can
        # reliably check which tab is active.
        self.tabs = tabs

        # Shared data view: plot + selected-curves tree (resizable divider)
        self.data_view_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.data_view_splitter.setChildrenCollapsible(False)

        # Plot container (no tab-specific controls here; tabs provide those rows).
        plot_container = QWidget(self.data_view_splitter)
        plot_layout = QHBoxLayout(plot_container)
        # The shared Raw/Processed plot should consume every pixel available
        # inside its side of the splitter.  A narrow, normally hidden side
        # panel is reserved for specialised Simple-map workflows such as
        # ResPES analysis; it never affects Raw Data or ordinary map views.
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(4)
        self.plot_area = PlotArea(plot_container)
        self.plot_area.intensity_scale_callback = self._show_intensity_scale_selector
        self.plot_area.map_palette_callback = self._choose_active_map_cmap
        self.plot_area.file_drop_callback = self._load_dropped_files
        self.plot_area.file_drop_enabled_callback = lambda: not self._is_processed_tab_active()
        plot_layout.addWidget(self.plot_area, 1)
        self.respes_side_panel = QWidget(plot_container)
        self.respes_side_panel.setVisible(False)
        # Do not give the normally hidden ResPES controls a hard minimum width.
        # On macOS, making this child visible can otherwise propagate the added
        # minimum width through the layout and resize even a maximized main
        # window.  Keep the hard minimum at zero so showing the panel cannot enlarge the
        # top-level window, but retain a Preferred horizontal size policy so
        # the visible panel receives its natural width instead of collapsing
        # to zero. The existing plot allocation is redistributed when ResPES
        # is shown.
        self.respes_side_panel.setMinimumWidth(0)
        self.respes_side_panel.setMaximumWidth(190)
        self.respes_side_panel.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        plot_layout.addWidget(self.respes_side_panel, 0)

        # Selected curves tree (right side; shared between tabs)
        self.selected_tree = QTreeWidget(self.data_view_splitter)
        register_widget_role(self.selected_tree, "selected_tree")
        self.selected_tree.setColumnCount(2)
        self.selected_tree.setHeaderLabels(["Selected curves", ""]) 
        # Keep the deliberately prominent MAP button fully visible without
        # widening the Selected curves pane: the label column stretches while
        # the MAP column has a stable width, so the vertical scrollbar cannot
        # steal space from the button.
        self.selected_tree.setMinimumWidth(ui_metrics.selected_tree_min_width)
        try:
            from PyQt6.QtWidgets import QHeaderView  # type: ignore
            hdr = self.selected_tree.header()
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            hdr.setStretchLastSection(False)
            try:
                hdr.setMinimumSectionSize(35)
            except Exception:
                pass
            self.selected_tree.setColumnWidth(1, 82)
        except Exception:
            pass
        self.selected_tree.itemChanged.connect(self._on_selected_tree_item_changed)
        self._last_selected_tree_press = None
        try:
            self.selected_tree.itemPressed.connect(self._on_selected_tree_item_pressed)
        except Exception:
            pass
        # Raw Data and Processed Data share this Selected curves tree.  Expose
        # curve-color editing here so color choice is available upstream of
        # Plotted Data and is independent of the route used to select a curve.
        self.selected_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.selected_tree.customContextMenuRequested.connect(self._show_selected_tree_context_menu)
        # Handle color-swatch double-clicks from the viewport mouse event itself.
        # itemDoubleClicked does not provide the click coordinates and using the
        # later global cursor position proved unreliable on Windows/Qt6.
        self.selected_tree.viewport().installEventFilter(self)

        self.data_view_splitter.addWidget(plot_container)
        self.data_view_splitter.addWidget(self.selected_tree)
        self.data_view_splitter.setStretchFactor(0, 1)
        self.data_view_splitter.setStretchFactor(1, 0)
        self.data_view_splitter.setSizes([1050, 350])

        # ---- Raw Data tab
        self._build_raw_data_tab(tabs)

        # ---- Processed Data tab
        self._build_processed_data_tab(tabs)

        # ---- Plotted Data tab
        # Construct advanced panels during startup so their first use is
        # immediate rather than paying a one-off lazy-initialization delay.
        self._plotted_data_host = QWidget(tabs)
        self._plotted_data_host_layout = QVBoxLayout(self._plotted_data_host)
        self._plotted_data_host_layout.setContentsMargins(0, 0, 0, 0)
        self._plotted_data_host_layout.setSpacing(0)
        self.plotted_data_panel = PlottedDataPanel(self._plotted_data_host)
        self.plotted_data_panel.set_default_directory(
            getattr(self, "_current_data_directory", None)
        )
        self._plotted_data_host_layout.addWidget(self.plotted_data_panel)
        plotted_data_index = tabs.addTab(self._plotted_data_host, "Plotted Data")

        # ---- Standalone reference tabs. Their page tabs are hidden in the
        # main tab bar and mirrored by compact selectors in the top-right corner.
        self._cross_section_reference_host = QWidget(tabs)
        self._cross_section_reference_host_layout = QVBoxLayout(self._cross_section_reference_host)
        self._cross_section_reference_host_layout.setContentsMargins(0, 0, 0, 0)
        self._cross_section_reference_host_layout.setSpacing(0)
        self.cross_section_reference_panel = CrossSectionReferencePanel(self._cross_section_reference_host)
        self._cross_section_reference_host_layout.addWidget(self.cross_section_reference_panel)
        cross_sections_index = tabs.addTab(self._cross_section_reference_host, "Cross sections")

        self._binding_energy_reference_host = QWidget(tabs)
        self._binding_energy_reference_host_layout = QVBoxLayout(self._binding_energy_reference_host)
        self._binding_energy_reference_host_layout.setContentsMargins(0, 0, 0, 0)
        self._binding_energy_reference_host_layout.setSpacing(0)
        self.binding_energy_reference_panel = BindingEnergyReferencePanel(self._binding_energy_reference_host)
        self._binding_energy_reference_host_layout.addWidget(self.binding_energy_reference_panel)
        binding_energies_index = tabs.addTab(self._binding_energy_reference_host, "Binding energies")

        # Hide the real reference-page tabs from the main tab bar.  Using
        # setTabVisible() prevents their labels from being painted at zero width
        # (which previously left stray text over the Plotted Data selector).
        if hasattr(tabs, "setTabVisible"):
            tabs.setTabVisible(cross_sections_index, False)
            tabs.setTabVisible(binding_energies_index, False)
        else:  # Compatibility fallback for older Qt builds.
            tabs.setTabText(cross_sections_index, "")
            tabs.setTabText(binding_energies_index, "")
            tabs.setTabEnabled(cross_sections_index, False)
            tabs.setTabEnabled(binding_energies_index, False)

        # A real secondary QTabBar gives the reference selectors the same
        # platform-native outline and selected-tab appearance as the data tabs,
        # while remaining independent of the main tab bar's size calculations.
        self.reference_tab_bar = _SelectionAwareTabBar(tabs)
        self.reference_tab_bar.setObjectName("referenceTabBar")
        self.reference_tab_bar.setShape(tabs.tabBar().shape())
        self.reference_tab_bar.setDocumentMode(tabs.documentMode())
        self.reference_tab_bar.setDrawBase(False)
        self.reference_tab_bar.setExpanding(False)
        self.reference_tab_bar.setUsesScrollButtons(False)
        self.reference_tab_bar.addTab("Cross sections")
        self.reference_tab_bar.addTab("Binding energies")
        self.reference_tab_bar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        tabs.setCornerWidget(self.reference_tab_bar, Qt.Corner.TopRightCorner)

        def _activate_reference_page(reference_index: int) -> None:
            page_index = (
                cross_sections_index
                if reference_index == 0
                else binding_energies_index
            )
            tabs.setCurrentIndex(page_index)

        # ``currentChanged`` is not emitted when the user clicks the tab that
        # already owns the secondary bar's current index.  This matters while
        # the reference group is visually inactive: Cross sections is index 0
        # by default, so its first click from a data page must still activate
        # the corresponding page.
        self.reference_tab_bar.currentChanged.connect(_activate_reference_page)
        self.reference_tab_bar.tabBarClicked.connect(_activate_reference_page)

        def _sync_reference_selectors(index: int) -> None:
            reference_active = index in (cross_sections_index, binding_energies_index)
            self.reference_tab_bar.blockSignals(True)
            try:
                if index == cross_sections_index:
                    self.reference_tab_bar.setCurrentIndex(0)
                elif index == binding_energies_index:
                    self.reference_tab_bar.setCurrentIndex(1)
                self.reference_tab_bar.setSelectionActive(reference_active)
                tabs.tabBar().setSelectionActive(not reference_active)
            finally:
                self.reference_tab_bar.blockSignals(False)

        tabs.currentChanged.connect(_sync_reference_selectors)
        _sync_reference_selectors(tabs.currentIndex())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([max(360, ui_metrics.loaded_tree_min_width + 80), 1200])

        # Internal mapping for selected curves
        self._selected_by_key: dict[str, QTreeWidgetItem] = {}
        self._selected_region_items: dict[tuple[str, str], QTreeWidgetItem] = {}

        # Persistent per-curve colors (so colors don't change when curves are removed).
        self._curve_color_map: dict[str, str] = {}
        self._next_color_index: int = 0
        self._selected_rebuild_pending: bool = False
        self._selected_rebuild_generation: int = 0
        self._session_restore_in_progress: bool = False
        # Fitting state retained independently of whether fit dialogs are open.
        self._fit_session_registry: dict[str, Any] = {"single": {}, "batch": {}}
        self._selected_plot_update_pending: bool = False
        self._selection_loading_visible: bool = False

        # CurveID generator for processed curves (e.g., after applying energy calibration)
        self._next_curve_id: int = 1

        # Store full iteration stacks per (file_name, region_name) for colormap view.
        # (x, Ymatrix, xlabel)
        self._region_iteration_stack: dict[tuple[str, str], tuple[Any, Any, str]] = {}
        # Track map toggles per selected-tree region item.
        # Mapping of (file, region) -> map toggle button.
        self._region_map_buttons: dict[tuple[str, str], Any] = {}

        # Track colormap choice per (file, region)
        self._region_cmap: dict[tuple[str, str], str] = {}

        self._loaded_tree_controller = LoadedTreeController(
            tree=self.tree,
            files_root=self._files_root,
            role_payload=self.ROLE_PAYLOAD,
            role_key=self.ROLE_KEY,
            role_region=self.ROLE_REGION,
            role_file=self.ROLE_FILE,
            role_meta=self.ROLE_META,
            payload_factory=PlotPayload,
            region_iteration_stack=self._region_iteration_stack,
        )
        self._selected_tree_manager = SelectedTreeManager(
            selected_tree=self.selected_tree,
            role_payload=self.ROLE_PAYLOAD,
            role_key=self.ROLE_KEY,
            role_region=self.ROLE_REGION,
            role_meta=self.ROLE_META,
            role_file=self.ROLE_FILE,
            region_items=self._selected_region_items,
            selected_by_key=self._selected_by_key,
            region_map_buttons=self._region_map_buttons,
            region_cmap=self._region_cmap,
            map_toggle_callback=self._on_region_map_toggled,
            choose_cmap_callback=self._choose_region_cmap,
        )
        self._plot_selection_controller = PlotSelectionController(self)

        # Track which kind of files are currently loaded (TXT or IBW).
        self._loaded_kind: str | None = None
        apply_control_metrics(self)
        self._update_load_menu_state()


    def _ensure_plotted_data_panel(self):
        return self.plotted_data_panel

    def _ensure_cross_section_reference_panel(self):
        return self.cross_section_reference_panel

    def _ensure_binding_energy_reference_panel(self):
        return self.binding_energy_reference_panel

    def _selected_target_region(self) -> str:
        try:
            return self.combo_all_region.currentText().strip()
        except Exception:
            return ''

    # --------------------------
    # Actions
    # --------------------------

    


















    def _show_selection_loading(self) -> None:
        if self._selection_loading_visible:
            return
        self._selection_loading_visible = True
        try:
            self.loading_status.setVisible(True)
        except Exception:
            pass
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        except Exception:
            pass
        try:
            QApplication.processEvents()
        except Exception:
            pass

    def _hide_selection_loading(self) -> None:
        if not self._selection_loading_visible:
            return
        self._selection_loading_visible = False
        try:
            self.loading_status.setVisible(False)
        except Exception:
            pass
        try:
            QApplication.restoreOverrideCursor()
        except Exception:
            pass

    def _schedule_rebuild_selected_from_loaded(self) -> None:
        # Session restore reconstructs the Selected workspace explicitly.  Do not
        # queue raw-only rebuilds while that transaction is in progress.
        if bool(getattr(self, "_session_restore_in_progress", False)):
            return
        if self._selected_rebuild_pending:
            return
        self._selected_rebuild_pending = True
        self._selected_rebuild_generation = int(getattr(self, "_selected_rebuild_generation", 0)) + 1
        generation = self._selected_rebuild_generation
        self._show_selection_loading()
        QTimer.singleShot(0, lambda g=generation: self._flush_rebuild_selected_from_loaded(g))

    def _flush_rebuild_selected_from_loaded(self, generation: int | None = None) -> None:
        # A bool alone cannot invalidate a queued callback safely: a stale timer
        # can run after a newer rebuild has set the bool True again.  The captured
        # generation identifies the exact request that owns this callback.
        current_generation = int(getattr(self, "_selected_rebuild_generation", 0))
        if generation is not None and int(generation) != current_generation:
            return
        if bool(getattr(self, "_session_restore_in_progress", False)):
            return
        if not bool(getattr(self, "_selected_rebuild_pending", False)):
            self._hide_selection_loading()
            return
        self._selected_rebuild_pending = False
        try:
            self._rebuild_selected_from_loaded()
        finally:
            self._hide_selection_loading()

    def _rebuild_selected_from_loaded(self) -> None:
        """Rebuild Selected curves from Loaded files without losing derived curves.

        Persistent processed children (currently E-calibrated spectra) are derived
        from raw Selected items and must survive an otherwise harmless raw-tree
        rebuild.  Keep them iff their ``source_key`` is still selected, then
        reattach them to the rebuilt raw source's actual parent.
        """
        checked_leaves = [it for it in self._iter_curve_leaves() if it.checkState(0) == Qt.CheckState.Checked]

        # Snapshot persistent processed children before rebuild_from_loaded()
        # clears the Selected tree and its key registry.  This makes the rebuild
        # idempotent with respect to energy calibration and removes a long-lived
        # race where a late raw selection refresh could silently erase E-cal data.
        processed_state = []
        try:
            for key, item in list(getattr(self, "_selected_by_key", {}).items()):
                meta = item.data(0, self.ROLE_META)
                if not (isinstance(meta, dict) and bool(meta.get("processed", False))):
                    continue
                source_key = meta.get("source_key")
                if not isinstance(source_key, str) or not source_key:
                    continue
                processed_state.append({
                    "key": str(key),
                    "display": str(item.text(0)),
                    "payload": item.data(0, self.ROLE_PAYLOAD),
                    "meta": dict(meta),
                    "source_file": str(item.data(0, self.ROLE_FILE) or ""),
                    "region_name": str(item.data(0, self.ROLE_REGION) or ""),
                    "checked": item.checkState(0),
                    "source_key": source_key,
                })
        except Exception as exc:
            log_noncritical_error("capturing processed curves before selected-tree rebuild", exc, logger=self._logger)

        try:
            ecal_toggle_checked = bool(self.btn_e_cal_toggle.isChecked())
        except Exception:
            ecal_toggle_checked = False

        self.selected_tree.setUpdatesEnabled(False)
        self.selected_tree.blockSignals(True)
        try:
            self._selected_tree_manager.rebuild_from_loaded(
                loaded_items=checked_leaves,
                all_in_region_enabled=bool(self.cb_all_in_region.isChecked()),
                target_region=self._selected_target_region(),
            )

            # Reattach each persistent derivative to the canonical parent of its
            # rebuilt raw source.  If the source is no longer selected, dropping
            # the derivative is intentional.
            for row in processed_state:
                raw_item = getattr(self, "_selected_by_key", {}).get(row["source_key"])
                if raw_item is None:
                    continue
                raw_parent = raw_item.parent()
                try:
                    region_key = self._selected_tree_manager._region_key_for_parent(raw_parent)
                except Exception:
                    region_key = None
                parent_file = row["source_file"]
                if isinstance(region_key, tuple) and region_key:
                    parent_file = str(region_key[0])
                region_name = row["region_name"] or str(raw_item.data(0, self.ROLE_REGION) or "")
                restored = self._selected_tree_manager.add_selected_leaf(
                    parent_file=parent_file,
                    region_name=region_name,
                    display=row["display"],
                    key=row["key"],
                    payload=row["payload"],
                    meta=row["meta"],
                    source_file=row["source_file"],
                )
                restored.setCheckState(0, row["checked"])
        finally:
            self.selected_tree.blockSignals(False)
            self.selected_tree.setUpdatesEnabled(True)
            try:
                self.selected_tree.viewport().update()
            except Exception:
                pass

        try:
            cur_is_processed_tab = self._is_processed_tab_active()
            has_processed = self._has_any_processed_curves()
            show_processed = bool(cur_is_processed_tab and has_processed and ecal_toggle_checked)
            self._update_selected_tree_visibility(show_processed=show_processed)
            # Rebuilding the tree recreates the per-region Map buttons (unchecked
            # by default), so make sure the Processed controls return to 1D mode.
            self._sync_processed_controls_for_map_mode()
        except Exception as exc:
            log_noncritical_error("updating selected tree visibility after rebuild", exc, logger=self._logger)

        self._update_plot_from_selected()

    def _add_txt_to_tree(self, parsed: Any, snapshot: Any = None) -> None:
        self._loaded_tree_controller.add_parsed_to_tree(parsed, snapshot=snapshot)

    # --------------------------
    # Curve selection logic
    # --------------------------
    def _show_loaded_tree_context_menu(self, pos) -> None:
        """Show context actions for metadata-bearing Raw Data tree entries."""
        try:
            item = self.tree.itemAt(pos)
        except Exception:
            item = None
        if item is None:
            return
        metadata = item.data(0, self.ROLE_META)
        if not isinstance(metadata, dict) or not metadata.get("metadata_scope"):
            return
        menu = QMenu(self.tree)
        action = menu.addAction("Show metadata")
        live_action = None
        live_region_actions: dict[object, tuple[int, str]] = {}
        file_path = str(metadata.get("file_path", "") or "")
        reload_action = None
        metadata_scope = str(metadata.get("metadata_scope", ""))
        if metadata_scope == "file":
            reload_action = menu.addAction("Reload from disk")
            if file_path.lower().endswith(".ibw"):
                live_action = menu.addAction("Open live monitor")
            elif file_path.lower().endswith(".txt"):
                # Use the already-loaded snapshot tree to build the region menu.
                # The on-disk TXT may be in the middle of an analyzer rewrite
                # exactly when the user opens this menu, so reparsing it here
                # would make the available monitor targets unnecessarily fragile.
                regions: list[tuple[int, str]] = []
                for region_pos in range(item.childCount()):
                    region_item = item.child(region_pos)
                    region_meta = region_item.data(0, self.ROLE_META)
                    if not isinstance(region_meta, dict):
                        continue
                    if str(region_meta.get("metadata_scope", "")) != "region":
                        continue
                    region_name = str(
                        region_meta.get("region_name") or region_item.text(0) or f"Region {region_pos + 1}"
                    ).strip()
                    regions.append((region_pos, region_name))
                if len(regions) > 1:
                    live_menu = menu.addMenu("Open live monitor")
                    for region_index, region_name in regions:
                        label = f"{region_name} (Region {region_index + 1})"
                        region_action = live_menu.addAction(label)
                        live_region_actions[region_action] = (region_index, region_name)
                else:
                    live_action = menu.addAction("Open live monitor")
                    if regions:
                        live_region_actions[live_action] = regions[0]
        elif metadata_scope == "region" and file_path.lower().endswith((".ibw", ".txt")):
            # Region nodes are the format-independent Live Monitor target.
            # The parser stores region_index as 1-based metadata, while the
            # live-monitor stack uses a 0-based index.  Prefer the node's
            # actual sibling position so this remains correct for restored
            # snapshots and any future parser representation.
            parent = item.parent()
            region_index = parent.indexOfChild(item) if parent is not None else 0
            region_name = str(metadata.get("region_name") or item.text(0) or f"Region {region_index + 1}").strip()
            live_action = menu.addAction("Open live monitor")
            live_region_actions[live_action] = (max(0, int(region_index)), region_name)
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen is action:
            self._show_tree_item_metadata(item)
        elif reload_action is not None and chosen is reload_action:
            self._reload_loaded_file_item(item)
        elif chosen in live_region_actions:
            region_index, region_name = live_region_actions[chosen]
            self._open_live_monitor(file_path, region_index=region_index, region_name=region_name)
        elif live_action is not None and chosen is live_action:
            self._open_live_monitor(file_path)

    def _open_live_monitor(
        self,
        file_path: str,
        *,
        region_index: int = 0,
        region_name: str | None = None,
    ) -> None:
        path = str(file_path or "").strip()
        if not path:
            return
        monitor_key = (path, max(0, int(region_index)))
        existing = self._live_monitor_windows.get(monitor_key)
        if existing is not None:
            try:
                if existing.isMinimized():
                    existing.showNormal()
                else:
                    existing.show()
                existing.raise_()
                existing.activateWindow()
                return
            except Exception:
                self._live_monitor_windows.pop(monitor_key, None)
        try:
            from .live_monitor.window import LiveMapWindow
            # Keep the monitor as an independent top-level window so it can be
            # minimized or left behind the main PANDA window.  Its explicit
            # reload action delegates back to the same provenance-aware policy
            # as the Loaded files context menu.
            window = LiveMapWindow(
                path,
                reload_latest_callback=lambda p=path: self._reload_source_path_with_policy(p),
                flip_x=bool(self.cb_flip_be.isChecked()),
                region_index=monitor_key[1],
                region_name=region_name,
            )
            # Keep the Live Monitor X direction synchronized with the same
            # Flip X axis control used by the main PANDA plot.
            self.cb_flip_be.toggled.connect(window.set_flip_x)
            self._live_monitor_windows[monitor_key] = window
            window.destroyed.connect(
                lambda *_args, key=monitor_key: self._live_monitor_windows.pop(key, None)
            )
            window.show()
            window.raise_()
            window.activateWindow()
        except Exception as exc:
            log_noncritical_error("opening live monitor", exc, logger=self._logger)

    def _show_tree_item_metadata(self, item: QTreeWidgetItem) -> None:
        metadata = item.data(0, self.ROLE_META)
        if not isinstance(metadata, dict):
            return
        try:
            from .widgets.metadata_dialog import MetadataDialog
            dialog = MetadataDialog(dict(metadata), self)
            label = str(item.text(0) or "").strip()
            if label:
                dialog.setWindowTitle(f"Metadata - {label}")
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            self._metadata_dialogs.add(dialog)
            dialog.destroyed.connect(lambda *_args, d=dialog: self._metadata_dialogs.discard(d))
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
        except Exception as exc:
            log_noncritical_error("showing metadata", exc, logger=self._logger)

    def _on_loaded_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0:
            return

        payload = item.data(0, self.ROLE_PAYLOAD)
        key_display = item.data(0, self.ROLE_KEY)
        region_name = item.data(0, self.ROLE_REGION)

        # Branch items like "Iterations" can toggle many child leaves at once.
        # Rebuild the selected tree once after the whole checkbox cascade finishes.
        if not isinstance(payload, PlotPayload) or not isinstance(key_display, tuple) or not isinstance(region_name, str):
            try:
                if item.childCount() > 0:
                    self._schedule_rebuild_selected_from_loaded()
            except Exception as exc:
                log_noncritical_error("scheduling selected-tree rebuild from branch toggle", exc, logger=self._logger)
            return

        # Large SPECS .xy regions deliberately keep their Iterations subtree
        # lazy.  Toggling the already-computed Average must therefore remain a
        # cheap one-leaf operation: a full Selected-tree rebuild would walk and
        # reconstruct unrelated selection state and can become very slow for
        # 1000+ spectrum source regions even though no iteration materialization
        # is required.  Keep TXT/IBW and all other leaves on the established
        # rebuild path; only the large-XY Average uses the existing incremental
        # synchronizer.
        try:
            meta = item.data(0, self.ROLE_META)
            source_meta = meta.get("source_metadata") if isinstance(meta, dict) else None
            is_large_xy_average = (
                isinstance(meta, dict)
                and str(meta.get("kind") or "").lower() == "average"
                and int(meta.get("n_traces") or 0) >= self._loaded_tree_controller.XY_LAZY_ITERATION_THRESHOLD
                and isinstance(source_meta, dict)
                and str(source_meta.get("Format") or "") == "SPECS Prodigy XY"
            )
        except Exception:
            is_large_xy_average = False

        if is_large_xy_average:
            try:
                self._selected_tree_manager.sync_loaded_leaf(
                    loaded_item=item,
                    checked=item.checkState(0) == Qt.CheckState.Checked,
                    all_in_region_enabled=bool(self.cb_all_in_region.isChecked()),
                    target_region=self._selected_target_region(),
                )
                self._update_plot_from_selected()
                show_processed = bool(self._is_processed_tab_active() and self._has_any_processed_curves())
                self._update_selected_tree_visibility(show_processed=show_processed)
                self._sync_processed_controls_for_map_mode()
                return
            except Exception as exc:
                log_noncritical_error(
                    "updating large XY Average selection incrementally", exc, logger=self._logger
                )

        self._schedule_rebuild_selected_from_loaded()

    def _schedule_update_plot_from_selected(self) -> None:
        """Coalesce selected-tree visibility changes into one redraw.

        Checking/unchecking a region group with hundreds of child spectra makes
        Qt emit itemChanged for many children. Redrawing the Matplotlib plot for
        every child is very slow, so we schedule a single redraw after the
        checkbox cascade has finished.
        """
        if self._selected_plot_update_pending:
            return
        self._selected_plot_update_pending = True
        QTimer.singleShot(0, self._flush_update_plot_from_selected)

    def _flush_update_plot_from_selected(self) -> None:
        self._selected_plot_update_pending = False
        self._update_plot_from_selected()

    def _on_selected_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        # Visibility checkbox toggles plotting.
        if column != 0:
            return

        # If the user checks a region group while its map mode is active,
        # deactivate map mode (requested behavior).
        if item.parent() is None:
            region_name = str(item.data(0, self.ROLE_REGION) or item.text(0))
            file_name = item.data(0, self.ROLE_FILE)
            rkey = (file_name, region_name) if isinstance(file_name, str) else None
            btn = self._region_map_buttons.get(rkey) if rkey is not None else None
            try:
                region_state = item.checkState(0)
            except Exception:
                region_state = Qt.CheckState.Checked
            if btn is not None:
                # Only treat this as an explicit user action if the user actually
                # clicked this region item's checkbox. Otherwise, the region state
                # may have changed due to Qt tri-state propagation from children
                # (e.g. when toggling the Average curve), and we must NOT switch
                # off map mode.
                pressed = self._last_selected_tree_press
                user_clicked_this = (pressed is not None and pressed[0] is item and pressed[1] == 0)
                try:
                    if user_clicked_this and btn.isChecked() and region_state != Qt.CheckState.Unchecked:
                        # Turn off map and restore iteration curve controls.
                        self.selected_tree.blockSignals(True)
                        try:
                            btn.setChecked(False)
                        finally:
                            self.selected_tree.blockSignals(False)
                        self._on_region_map_toggled(item, False)
                except Exception:
                    pass

            # Clear after handling to avoid accidental reuse.
            self._last_selected_tree_press = None

        # Region group items are tri-state, so Qt will propagate changes to children
        # and show a partial (half-checked) state automatically when children differ.
        # A group toggle may emit hundreds of itemChanged signals; redraw only once
        # after the cascade has completed.
        self._schedule_update_plot_from_selected()

    def _on_selected_tree_item_pressed(self, item: QTreeWidgetItem, column: int) -> None:
        """Record what the user clicked in the selected tree.

        We use this to distinguish direct checkbox clicks on a region group from
        implicit changes due to tri-state propagation when children change.
        """
        self._last_selected_tree_press = (item, column)

    def _selected_tree_color_swatch_rect(self, item: QTreeWidgetItem, column: int) -> QRect:
        """Return the painted color-icon rectangle for one selected-curve row."""
        if column != 0 or item is None or item.parent() is None:
            return QRect()
        try:
            index = self.selected_tree.indexFromItem(item, column)
            if not index.isValid():
                return QRect()
            option = QStyleOptionViewItem()
            option.rect = self.selected_tree.visualRect(index)
            option.widget = self.selected_tree
            self.selected_tree.itemDelegate(index).initStyleOption(option, index)
            return self.selected_tree.style().subElementRect(
                QStyle.SubElement.SE_ItemViewItemDecoration,
                option,
                self.selected_tree.viewport(),
            )
        except Exception:
            return QRect()

    def _selected_tree_checkbox_rect(self, item: QTreeWidgetItem, column: int) -> QRect:
        """Return the painted checkbox rectangle for one selected-curve row."""
        if column != 0 or item is None:
            return QRect()
        try:
            index = self.selected_tree.indexFromItem(item, column)
            if not index.isValid():
                return QRect()
            option = QStyleOptionViewItem()
            option.rect = self.selected_tree.visualRect(index)
            option.widget = self.selected_tree
            self.selected_tree.itemDelegate(index).initStyleOption(option, index)
            return self.selected_tree.style().subElementRect(
                QStyle.SubElement.SE_ItemViewItemCheckIndicator,
                option,
                self.selected_tree.viewport(),
            )
        except Exception:
            return QRect()

    def _selected_tree_viewport_double_click(self, event) -> bool:
        """Open the color chooser when a selected curve row is double-clicked.

        Any left-button double-click on an individual curve row opens the color
        chooser, except a double-click on the checkbox itself.  Group rows are
        intentionally ignored.  This is more robust than trying to hit-test the
        small painted color swatch across Qt/Windows DPI and style variations.
        """
        try:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            pos = event.position().toPoint()
            item = self.selected_tree.itemAt(pos)
            if item is None or item.parent() is None:
                return False
            index = self.selected_tree.indexAt(pos)
            if not index.isValid() or index.column() != 0:
                return False
            key = item.data(0, self.ROLE_KEY)
            payload = item.data(0, self.ROLE_PAYLOAD)
            if not isinstance(key, str) or not key or not isinstance(payload, PlotPayload):
                return False

            checkbox = self._selected_tree_checkbox_rect(item, 0)
            if checkbox.isValid() and not checkbox.isEmpty() and checkbox.contains(pos):
                return False

            self._choose_selected_curve_color(item)
            return True
        except Exception:
            return False

    def eventFilter(self, watched, event):  # noqa: N802
        if watched is getattr(self, "selected_tree", None).viewport() if hasattr(self, "selected_tree") else False:
            if event.type() == QEvent.Type.MouseButtonDblClick:
                if self._selected_tree_viewport_double_click(event):
                    return True
        return super().eventFilter(watched, event)

    def _show_selected_tree_context_menu(self, pos: QPoint) -> None:
        """Offer curve-specific display actions in Raw/Processed Selected curves."""
        item = self.selected_tree.itemAt(pos)
        if item is None or item.parent() is None:
            return
        key = item.data(0, self.ROLE_KEY)
        payload = item.data(0, self.ROLE_PAYLOAD)
        if not isinstance(key, str) or not key or not isinstance(payload, PlotPayload):
            return

        menu = QMenu(self.selected_tree)
        color_action = menu.addAction("Choose curve color...")
        chosen = menu.exec(self.selected_tree.viewport().mapToGlobal(pos))
        if chosen is color_action:
            self._choose_selected_curve_color(item)

    def _choose_selected_curve_color(self, item: QTreeWidgetItem) -> None:
        """Choose and apply the persistent Raw/Processed color of one curve."""
        key = item.data(0, self.ROLE_KEY)
        if not isinstance(key, str) or not key:
            return

        current = self._curve_color_map.get(key, "#1f77b4")
        try:
            initial = QColor(mpl_color_to_hex(current))
        except Exception:
            initial = QColor("#1f77b4")
        color = QColorDialog.getColor(initial, self, "Choose curve color")
        if not color.isValid():
            return

        self._curve_color_map[key] = color.name()
        # Update the tree swatch immediately even when this curve is currently
        # unchecked; the normal plot refresh will keep it synchronized later.
        try:
            pix = QPixmap(12, 12)
            pix.fill(color)
            item.setIcon(0, QIcon(pix))
        except Exception:
            pass
        self._update_plot_from_selected()

    def _ensure_selected_region(self, file_name: str, region_name: str) -> QTreeWidgetItem:
        """Ensure a region group exists in the selected-curves tree."""
        return self._selected_tree_manager.ensure_region(file_name, region_name)

    def _choose_region_cmap(self, file_name: str, region_name: str) -> None:
        """Choose a colormap using visual gradient previews."""
        key = (file_name, region_name)
        current = self._region_cmap.get(key, 'terrain')
        choice = choose_colormap(self, current)
        if not choice:
            return
        self._region_cmap[key] = str(choice)
        self._update_plot_from_selected()

    def _on_region_map_toggled(self, region_item: QTreeWidgetItem, checked: bool) -> None:
        """Handle the map toggle only when a valid 2D map can actually be built.

        MAP is a representation of a coherent iteration dataset, not an arbitrary
        collection of similarly named spectra.  If construction fails (for example
        because too few iteration curves remain checked), immediately return the
        toggle to its off state and keep the ordinary spectra controls/plot.
        """
        if checked:
            controller = getattr(self, '_plot_selection_controller', None)
            valid_map = False
            if controller is not None:
                try:
                    valid_map = bool(controller.collect_selection().images)
                except Exception:
                    valid_map = False
            if not valid_map:
                region_name = str(region_item.data(0, self.ROLE_REGION) or region_item.text(0))
                file_name = region_item.data(0, self.ROLE_FILE)
                rkey = (file_name, region_name) if isinstance(file_name, str) else None
                btn = self._region_map_buttons.get(rkey) if rkey is not None else None
                if btn is not None:
                    try:
                        btn.blockSignals(True)
                        btn.setChecked(False)
                    finally:
                        btn.blockSignals(False)
                try:
                    self._sync_processed_controls_for_map_mode()
                except Exception:
                    pass
                self._update_plot_from_selected()
                return

        try:
            self._sync_processed_controls_for_map_mode()
        except Exception:
            pass
        self._update_plot_from_selected()

    def _current_intensity_mode(self) -> str:
        return self._processed_intensity_mode if self._is_processed_tab_active() else self._raw_intensity_mode

    def _set_current_intensity_mode(self, mode: str) -> None:
        mode = CPS if str(mode).lower() == CPS else COUNTS
        if self._is_processed_tab_active():
            self._processed_intensity_mode = mode
        else:
            self._raw_intensity_mode = mode

    def _show_intensity_scale_selector(self) -> None:
        """Show the compact Counts/CPS selector for Raw/Processed 1D spectra."""
        menu = QMenu(self)
        current = self._current_intensity_mode()
        act_counts = menu.addAction("Counts")
        act_cps = menu.addAction("CPS")
        for action, mode in ((act_counts, COUNTS), (act_cps, CPS)):
            action.setCheckable(True)
            action.setChecked(current == mode)
        chosen = menu.exec(QCursor.pos())
        if chosen is None:
            return
        requested = CPS if chosen is act_cps else COUNTS
        if requested == current:
            return
        if requested == CPS:
            controller = getattr(self, "_plot_selection_controller", None)
            if controller is not None:
                selection = controller.collect_selection()
                if selection.images:
                    return
                missing = self._missing_cps_items(selection.items_in_order)
                if missing:
                    QMessageBox.warning(
                        self,
                        "CPS unavailable",
                        "Counts per second cannot be shown because 'Time per Spectrum Channel' "
                        f"is missing or invalid for: {', '.join(missing[:5])}" +
                        (" ..." if len(missing) > 5 else ""),
                        QMessageBox.StandardButton.Ok,
                    )
                    return
        self._set_current_intensity_mode(requested)
        self._update_plot_from_selected()

    def _missing_cps_items(self, items_in_order: list[tuple[Any, str]]) -> list[str]:
        missing: list[str] = []
        for item, _key in items_in_order:
            try:
                meta = item.data(0, self.ROLE_META)
            except Exception:
                meta = None
            if time_per_spectrum_channel(meta) is None:
                try:
                    missing.append(str(item.text(0) or "curve"))
                except Exception:
                    missing.append("curve")
        return missing

    def _apply_intensity_mode_to_payloads(
        self, payloads: list[PlotPayload], items_in_order: list[tuple[Any, str]], mode: str
    ) -> tuple[list[PlotPayload], list[str]]:
        if str(mode).lower() != CPS:
            return payloads, []
        scaled: list[PlotPayload] = []
        missing: list[str] = []
        for payload, item_info in zip(payloads, items_in_order):
            item = item_info[0]
            try:
                meta = item.data(0, self.ROLE_META)
            except Exception:
                meta = None
            seconds = time_per_spectrum_channel(meta)
            if seconds is None:
                try:
                    missing.append(str(item.text(0) or getattr(payload, "title", "curve")))
                except Exception:
                    missing.append(str(getattr(payload, "title", "curve")))
                continue
            scaled.append(scale_payload(payload, seconds=seconds, mode=CPS))
        if missing:
            return payloads, missing
        return scaled, []

    def _update_plot_from_selected(self) -> None:
        controller = getattr(self, '_plot_selection_controller', None)
        if controller is None:
            return

        selection = controller.collect_selection()
        payloads = list(selection.payloads)
        items_in_order = list(selection.items_in_order)
        images = list(selection.images)

        title = controller.compute_title()
        if payloads and title:
            first = payloads[0]
            payloads[0] = PlotPayload(
                title=title,
                x=first.x,
                y=first.y,
                xlabel=first.xlabel,
                ylabel=first.ylabel,
                energy_scale=getattr(first, "energy_scale", "Unknown"),
                metadata=dict(getattr(first, "metadata", {}) or {}),
            )

        color_list = controller.build_color_list(items_in_order)

        # Auto-default flip state based on energy scale, unless the user has manually changed it.
        if not self._flip_user_set:
            scales = set()
            for p in payloads:
                es = str(getattr(p, "energy_scale", "Unknown"))
                if es and es != "Unknown":
                    scales.add(es)
            if len(scales) == 1:
                es = next(iter(scales))
                try:
                    self._auto_setting_flip = True
                    flip_default = default_flip_for_energy_scale(es)
                    if flip_default is not None:
                        self.cb_flip_be.setChecked(flip_default)
                finally:
                    self._auto_setting_flip = False


        # Determine map context before applying normalization.  The established
        # 1D normalization and the new map normalization are deliberately
        # independent: when a Processed 2D map is active, its own selector owns
        # normalization and the hidden 1D checkbox must not double-normalize it.
        try:
            processed_map = bool(images) and bool(self._is_processed_tab_active())
        except Exception:
            processed_map = False

        # Counts/CPS is a spectra-only representation.  Maps always use the
        # underlying count arrays, even when Processed Data is currently shown
        # in CPS.
        if not images and payloads:
            mode = self._current_intensity_mode()
            payloads_scaled, missing_cps = self._apply_intensity_mode_to_payloads(
                payloads, items_in_order, mode
            )
            if missing_cps and mode == CPS:
                self._set_current_intensity_mode(COUNTS)
                QMessageBox.warning(
                    self,
                    "CPS unavailable",
                    "Counts per second cannot be shown because 'Time per Spectrum Channel' "
                    f"is missing or invalid for: {', '.join(missing_cps[:5])}" +
                    (" ..." if len(missing_cps) > 5 else ""),
                    QMessageBox.StandardButton.Ok,
                )
            else:
                payloads = payloads_scaled

        # Intensity normalization for ordinary 1D Processed Data only.
        processed_controller = getattr(self, '_processed_controller', None)
        if processed_controller is not None and not processed_map:
            payloads_result, _norm_applied = processed_controller.apply_normalization_if_enabled(payloads, items_in_order)
            if payloads_result is None:
                return
            payloads = payloads_result

        # Map-specific normalization is a reversible display/analysis transform.
        # It feeds the image, Lines/ROI traces and trace CSV export, but does not
        # modify the stored 1D processed spectra.
        if processed_map:
            map_norm = getattr(self, "_apply_map_normalization", None)
            if callable(map_norm):
                images = list(map_norm(images))

        if processed_map:
            try:
                self._update_respes_availability()
            except Exception:
                pass

        # Crosshair/profile lines are a Processed Data map workflow only.
        # Raw Data map view must remain a plain full-size 2D image even though
        # Raw and Processed tabs share the same plot widget.
        map_lines_enabled = False
        map_roi_enabled = False
        try:
            map_lines_enabled = processed_map and bool(
                getattr(self, "rb_map_lines", None) and self.rb_map_lines.isChecked()
            )
            map_roi_enabled = processed_map and bool(
                getattr(self, "rb_map_roi", None) and self.rb_map_roi.isChecked()
            )
        except Exception:
            map_lines_enabled = False
            map_roi_enabled = False

        # Lines-view binning mirrors the batch-fitting algorithm: consecutive
        # complete groups are averaged and an incomplete trailing group is
        # discarded.  Apply it after row-wise map normalization so the Lines
        # map and extracted traces represent exactly what the user sees.
        if map_lines_enabled:
            apply_lines_binning = getattr(self, "_apply_map_lines_binning", None)
            if callable(apply_lines_binning):
                images = list(apply_lines_binning(images))

        used_colors = self.plot_area.plot_many(
            payloads,
            flip_binding_energy=bool(self.cb_flip_be.isChecked()),
            colors=color_list,
            images=images,
            map_lines_enabled=map_lines_enabled,
            map_h_thickness=int(getattr(getattr(self, "sb_map_h_thickness", None), "value", lambda: 1)()),
            map_v_thickness=int(getattr(getattr(self, "sb_map_v_thickness", None), "value", lambda: 1)()),
            map_roi_enabled=map_roi_enabled,
            map_roi_spec=getattr(self, "_map_roi_spec", None),
            map_roi_callback=getattr(self, "_on_map_roi_changed_from_plot", None),
            map_roi_pass_callback=getattr(self, "_pass_map_roi_to_plotting", None),
            map_animation_callback=getattr(self, "_open_map_lines_animation_dialog", None),
            map_norm_interval=(
                getattr(self, "_map_norm_active_interval", None) if processed_map else None
            ),
            map_norm_mode=getattr(self, "_map_norm_mode", None) if processed_map else None,
            map_norm_show_region=bool(
                processed_map and getattr(self, "_map_norm_show_region", False)
            ),
            map_norm_callback=(
                getattr(self, "_on_map_norm_band_changed_from_plot", None) if processed_map else None
            ),
            respes_enabled=bool(
                processed_map and getattr(self, "_respes_is_active_for_current_view", lambda: False)()
            ),
            respes_cut_type=getattr(self, "_respes_cut_type", "constant_be"),
            respes_position=getattr(self, "_respes_cut_position", None),
            respes_width=getattr(self, "_respes_cut_width", None),
            respes_callback=getattr(self, "_on_respes_cut_changed_from_plot", None),
            respes_energy_axis=getattr(self, "_respes_energy_axis", "be"),
            respes_work_function=float(getattr(self, "_respes_work_function", 4.5)),
        )
        self._apply_curve_color_icons(items_in_order, used_colors)

        signal_controller = getattr(self, "_signal_identification", None)
        raw_identification_view = False
        try:
            raw_identification_view = bool(
                getattr(self, "tabs", None) is not None
                and getattr(self, "raw_data_tab", None) is not None
                and self.tabs.currentWidget() is self.raw_data_tab
            )
        except Exception:
            raw_identification_view = False

        if signal_controller is not None:
            # Signal identification is a Raw Data overlay.  Processed Data shares
            # the same Matplotlib axes, so plot_many() above naturally removes the
            # artists there; deliberately leave the controller/cache untouched so
            # returning to Raw Data restores the existing assignments without a
            # needless re-identification pass.
            if raw_identification_view:
                signal_controller.refresh_availability()
                signal_controller.draw_annotations()
        elif raw_identification_view:
            refresh_signal_controls = getattr(self, "_refresh_signal_identification_availability", None)
            if callable(refresh_signal_controls):
                refresh_signal_controls()

        # If the non-modal Lines animation controller is open, a map redraw may
        # have replaced its sampled coordinate arrays.  Refresh it and stop any
        # in-flight playback rather than letting stale frame indices run on a
        # newly selected map.
        animation_dialog = getattr(self, "_map_animation_dialog", None)
        if animation_dialog is not None:
            try:
                animation_dialog.refresh_context(stop=True, preserve_custom=True)
            except Exception:
                pass

        # Update suggested default normalization energy when normalization is OFF.
        processed_controller = getattr(self, '_processed_controller', None)
        if processed_controller is not None:
            processed_controller.update_norm_default_from_payloads(payloads)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API spelling
        """Close every PANDA top-level window, then terminate the application."""
        if bool(getattr(self, "_application_shutdown_in_progress", False)):
            event.accept()
            return
        self._application_shutdown_in_progress = True
        app = QApplication.instance()
        if app is not None:
            for widget in list(app.topLevelWidgets()):
                if widget is self:
                    continue
                try:
                    widget.close()
                except Exception:
                    pass
        event.accept()
        if app is not None:
            QTimer.singleShot(0, app.quit)

    def _apply_curve_color_icons(self, items: list[tuple[QTreeWidgetItem, str]], colors: list[Any]) -> None:
        """Add a small colored square icon to each selected curve item."""
        self.selected_tree.blockSignals(True)
        try:
            for (it, _key), col in zip(items, colors):
                try:
                    pix = QPixmap(12, 12)
                    pix.fill(QColor(mpl_color_to_hex(col)))
                    it.setIcon(0, QIcon(pix))
                except Exception:
                    # If QColor can't parse, just skip.
                    pass
        finally:
            self.selected_tree.blockSignals(False)







