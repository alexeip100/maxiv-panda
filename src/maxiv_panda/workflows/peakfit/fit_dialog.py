from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMenu,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QTabWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT
from matplotlib.figure import Figure

from . import fit_plotting, fit_widgets
from ...log_utils import get_logger, log_noncritical_error
from .fit_dialog_curve_mixin import FitDialogCurveMixin
from .fit_dialog_background_mixin import FitDialogBackgroundMixin
from .fit_dialog_component_display_mixin import FitDialogComponentDisplayMixin
from .fit_dialog_peak_interaction_mixin import FitDialogPeakInteractionMixin
from .fit_dialog_doublet_mixin import FitDialogDoubletMixin
from .fit_dialog_constraints_mixin import FitDialogConstraintsMixin
from .fit_dialog_io_mixin import FitDialogIOMixin
from .fit_dialog_state_mixin import FitDialogStateMixin
from .fit_dialog_fit_mixin import FitDialogFitMixin
from .fit_dialog_results_mixin import FitDialogResultsMixin
from .fit_range import FitDialogRangeMixin


class _FitNavigationToolbar(NavigationToolbar2QT):
    """Matplotlib toolbar adapted for the embedded single-fit plot.

    Some Windows/Qt combinations expose QToolBar's private overflow/extension
    button even when the toolbar actions fit.  When the QToolBar is embedded as
    an ordinary widget (rather than docked in a QMainWindow), that button can
    appear as a small stray control at the far left of the Matplotlib toolbar.
    Keep the normal Matplotlib actions, but suppress that Qt-internal control.
    """

    def __init__(self, canvas, parent=None):
        # Keep Matplotlib's standard live x/y coordinate readout.  The Qt
        # overflow/extension control is suppressed separately below, so there is
        # no need to disable the useful coordinate label.
        super().__init__(canvas, parent, coordinates=True)
        self.setMovable(False)
        self.setFloatable(False)
        # On some Windows 11 Qt styles the QToolBar handle is still painted
        # even for a non-movable toolbar embedded in a normal QWidget.  It
        # appears as a tiny horizontal slider/grip immediately before the
        # Matplotlib Home button.  Remove that sub-control at the style level
        # instead of relying on setMovable(False).
        self.setStyleSheet(
            "QToolBar { border: 0px; margin: 0px; padding: 0px; }"
            "QToolBar::handle { image: none; width: 0px; margin: 0px; padding: 0px; }"
        )
        try:
            self.setAllowedAreas(Qt.ToolBarArea.NoToolBarArea)
        except Exception:
            pass
        self._hide_extension_button()
        QTimer.singleShot(0, self._hide_extension_button)

    def _hide_extension_button(self):
        try:
            btn = self.findChild(QToolButton, "qt_toolbar_ext_button")
            if btn is not None:
                btn.setVisible(False)
                btn.setEnabled(False)
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Qt may update overflow state after the resize event has returned.
        QTimer.singleShot(0, self._hide_extension_button)


def _iter_visible_checked_curve_keys(mw) -> List[str]:
    """Return selected curve keys consistent with what is currently shown/plotted."""
    keys: List[str] = []
    tree = getattr(mw, "selected_tree", None)
    if tree is None:
        return keys

    role_key = getattr(mw, "ROLE_KEY", Qt.ItemDataRole.UserRole + 1)

    root = tree.invisibleRootItem()
    for i in range(root.childCount()):
        grp = root.child(i)
        if grp.isHidden():
            continue
        for j in range(grp.childCount()):
            leaf = grp.child(j)
            if leaf.isHidden():
                continue
            if leaf.checkState(0) != Qt.CheckState.Checked:
                continue
            kd = leaf.data(0, role_key)
            # ROLE_KEY is often (key, display) tuple
            if isinstance(kd, tuple) and kd:
                kd = kd[0]
            if isinstance(kd, str) and kd:
                keys.append(kd)
    return keys


def _populate_curve_tree(mw, tree: QTreeWidget) -> None:
    """Populate the dialog's curve list with checkboxes, similar to Processed selection."""
    tree.clear()
    tree.setHeaderLabels(["Curves"])
    tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

    keys = _iter_visible_checked_curve_keys(mw)
    if not keys:
        # If nothing is checked, show visible (checked or not) as a fallback
        tree.setHeaderLabels(["Curves (no selection)"])
        return

    # Try to resolve nicer display names from the main selected_tree, else show key.
    name_by_key: Dict[str, str] = {}
    try:
        sel_tree = mw.selected_tree
        role_key = getattr(mw, "ROLE_KEY", Qt.ItemDataRole.UserRole + 1)
        root = sel_tree.invisibleRootItem()
        for i in range(root.childCount()):
            grp = root.child(i)
            for j in range(grp.childCount()):
                leaf = grp.child(j)
                kd = leaf.data(0, role_key)
                if isinstance(kd, tuple) and kd:
                    k = kd[0]
                else:
                    k = kd
                if isinstance(k, str) and k:
                    name_by_key[k] = leaf.text(0)
    except Exception as exc:
        log_noncritical_error("resolving curve display names for fit dialog", exc)

    for k in keys:
        it = QTreeWidgetItem([name_by_key.get(k, k)])
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
        it.setCheckState(0, Qt.CheckState.Checked)
        it.setData(0, Qt.ItemDataRole.UserRole, k)  # dialog-local role
        tree.addTopLevelItem(it)

    if tree.topLevelItemCount() > 0:
        tree.setCurrentItem(tree.topLevelItem(0))



def _build_payload_by_key(mw) -> Dict[str, Any]:
    """Build mapping key -> PlotPayload (or compatible payload) from main Selected-curves tree."""
    payload_by_key: Dict[str, Any] = {}
    tree = getattr(mw, "selected_tree", None)
    if tree is None:
        return payload_by_key

    role_key = getattr(mw, "ROLE_KEY", Qt.ItemDataRole.UserRole + 1)
    role_payload = getattr(mw, "ROLE_PAYLOAD", Qt.ItemDataRole.UserRole + 2)

    # Import PlotPayload lazily to avoid import cycles at module import time.
    try:
        from ...ui import PlotPayload  # type: ignore
    except Exception:
        PlotPayload = None  # type: ignore

    root = tree.invisibleRootItem()
    for i in range(root.childCount()):
        grp = root.child(i)
        for j in range(grp.childCount()):
            leaf = grp.child(j)
            kd = leaf.data(0, role_key)
            if isinstance(kd, tuple) and kd:
                k = kd[0]
            else:
                k = kd
            if not isinstance(k, str) or not k:
                continue
            pl = leaf.data(0, role_payload)
            if PlotPayload is not None:
                if isinstance(pl, PlotPayload):
                    payload_by_key[k] = pl
            else:
                # Fallback: accept any payload with x/y attributes
                if hasattr(pl, "x") and hasattr(pl, "y"):
                    payload_by_key[k] = pl
    return payload_by_key

class FitCoreLevelDialog(
    FitDialogCurveMixin,
    FitDialogBackgroundMixin,
    FitDialogComponentDisplayMixin,
    FitDialogPeakInteractionMixin,
    FitDialogDoubletMixin,
    FitDialogConstraintsMixin,
    FitDialogIOMixin,
    FitDialogStateMixin,
    FitDialogResultsMixin,
    FitDialogFitMixin,
    FitDialogRangeMixin,
    QDialog,
):
    """Core-level peak fitting dialog (initial layout scaffold)."""







    def __init__(self, mw, parent=None, *, supplied_payload=None, supplied_label: Optional[str] = None, initial_fit_state: Optional[Dict[str, Any]] = None, shared_fit_setup_ref: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self._logger = get_logger()
        self._mw = mw
        self._supplied_payload = supplied_payload
        self._supplied_label = supplied_label
        self._supplied_initial_fit_state = initial_fit_state
        self._shared_fit_setup_ref = shared_fit_setup_ref
        self._anchor_result_state = None
        self._anchor_result_setup = None
        self._single_payload_mode = supplied_payload is not None

        if self._single_payload_mode and supplied_label:
            self.setWindowTitle(f"Single curve fit of core-level PE spectra — {supplied_label}")
        else:
            self.setWindowTitle("Single curve fit of core-level PE spectra")
        # Keep the peak-fit editor non-modal so the main application window
        # (e.g. Help) remains usable while fitting.
        self.setModal(False)
        try:
            self.setWindowModality(Qt.WindowModality.NonModal)
        except Exception:
            pass

        # Allow maximize (and keep it as a dialog)
        try:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        except Exception:
            pass
        self.setSizeGripEnabled(True)

        main = QVBoxLayout(self)

        tab_single = QWidget(self)
        main.addWidget(tab_single, 1)

        lay_single = QVBoxLayout(tab_single)
        lay_single.setContentsMargins(8, 8, 8, 8)
        lay_single.setSpacing(6)

        # Use a splitter so the user can adjust the relative sizes (tree / plot / parameters)
        splitter = QSplitter(Qt.Orientation.Horizontal, tab_single)
        self._build_curve_selection_pane(tab_single, splitter)
        self._build_plot_pane(tab_single, splitter)
        self._build_parameters_pane(tab_single, splitter)
        self._configure_main_splitter(splitter, lay_single)
        self._build_dialog_buttons(main)
        self._initialize_curve_selection(mw, supplied_payload, supplied_label)

        # Initial sizing: same height but ~1.5x wider than Calibrate Energy dialog
        sh = self.sizeHint()
        self.resize(int(sh.width() * 1.5), int(sh.height() * 1.265))
        try:
            setattr(self._mw, "_single_fit_reference_size", self.size())
        except Exception:
            pass

    def _build_curve_selection_pane(self, tab_single: QWidget, splitter: QSplitter) -> None:
        """Build the curve-selection pane without changing selection behavior."""
        # Left: instructions + curve list
        left_w = QWidget(tab_single)
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        lbl_instr = QLabel(
            "Single-curve fit: select exactly one curve in the list below (checking another curve will unselect the previous one).",
            tab_single,
        )
        if self._single_payload_mode:
            lbl_instr.setText("Single-curve fit of the supplied anchor spectrum.")
        lbl_instr.setWordWrap(True)
        left_lay.addWidget(lbl_instr)

        self.tree_curves = QTreeWidget(tab_single)
        self.tree_curves.setHeaderLabels(["Curve"])
        self.tree_curves.setUniformRowHeights(True)
        self.tree_curves.setRootIsDecorated(False)
        self.tree_curves.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.tree_curves.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        try:
            self.tree_curves.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        except Exception:
            pass
        left_lay.addWidget(self.tree_curves, 1)

        if not self._single_payload_mode:
            splitter.addWidget(left_w)
        else:
            # In supplied/anchor-spectrum mode the curve-selection pane is not
            # part of the UI.  It is nevertheless constructed above because
            # some of the shared dialog logic expects ``tree_curves`` to exist.
            # A QWidget with ``tab_single`` as parent remains visible even when
            # it is not managed by a layout/splitter; on Windows this orphaned
            # pane could therefore sit at (0, 0) on top of the Matplotlib
            # toolbar, exposing a clipped tree/scrollbar that looked like a
            # stray slider.  Hide the unused pane explicitly.
            left_w.hide()

    def _build_plot_pane(self, tab_single: QWidget, splitter: QSplitter) -> None:
        """Build the embedded fit plot and its interaction toolbar."""
        # Middle: plot
        mid_w = QWidget(tab_single)
        mid_lay = QVBoxLayout(mid_w)
        mid_lay.setContentsMargins(0, 0, 0, 0)
        mid_lay.setSpacing(6)

        self.fig = Figure(figsize=(5, 4), dpi=100)
        gs = self.fig.add_gridspec(2, 1, height_ratios=[85, 15], hspace=0.06)
        try:
            self.fig.subplots_adjust(top=0.975, bottom=0.085)
        except Exception:
            pass
        self.ax = self.fig.add_subplot(gs[0])
        self.ax_res = self.fig.add_subplot(gs[1], sharex=self.ax)
        try:
            fit_plotting.style_fit_axes(self.ax, self.ax_res)
        except Exception:
            pass
        self.canvas = FigureCanvas(self.fig)
        # Peak-position guess markers in the single-fit view are draggable in
        # the horizontal direction.  Keep the interaction state on the dialog
        # and use canvas-level events so it remains independent of the actual
        # Matplotlib artist objects (which are recreated whenever a spin box
        # changes).
        self._drag_peak_index = None
        # Fit-range gestures are registered first so a click near a range line
        # is claimed before peak-marker dragging is considered.
        self.canvas.mpl_connect("button_press_event", self._on_fit_range_mouse_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_fit_range_mouse_motion)
        self.canvas.mpl_connect("button_release_event", self._on_fit_range_mouse_release)
        self.canvas.mpl_connect("button_press_event", self._on_peak_marker_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_peak_marker_motion)
        self.canvas.mpl_connect("button_release_event", self._on_peak_marker_release)
        # Parent the toolbar to the plot pane itself.  Parenting it to the outer
        # tab could leave a stray/overlapping child control at the far left of
        # the toolbar on some Qt/Matplotlib combinations (seen on Windows).
        self.nav = _FitNavigationToolbar(self.canvas, mid_w)
        self.nav.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        plot_tools = QWidget(mid_w)
        plot_tools_lay = QHBoxLayout(plot_tools)
        plot_tools_lay.setContentsMargins(0, 0, 0, 0)
        plot_tools_lay.setSpacing(6)
        plot_tools_lay.addWidget(self.nav, 1)
        self.cb_fit_legend = QCheckBox("Legend", plot_tools)
        self.cb_fit_legend.setChecked(True)
        self.cb_fit_legend.setToolTip("Show or hide the legend on the fitting plot.")
        self.cb_fit_legend.toggled.connect(lambda _checked=False: self._refresh_fit_legend())
        plot_tools_lay.addWidget(self.cb_fit_legend, 0)
        mid_lay.addWidget(plot_tools)
        mid_lay.addWidget(self.canvas, 1)

        splitter.addWidget(mid_w)

    def _build_parameters_pane(self, tab_single: QWidget, splitter: QSplitter) -> None:
        """Build the tabbed peak-parameter and fit-results pane."""
        # Right: tabbed parameter/results area
        right_w = QWidget(tab_single)
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        self.right_tabs = QTabWidget(tab_single)
        right_lay.addWidget(self.right_tabs, 1)
        self._build_peak_parameters_tab()
        self._build_fit_results_tab()
        splitter.addWidget(right_w)

    def _build_peak_parameters_tab(self) -> None:
        """Build peak, SO-doublet, fit-control, and background widgets."""
        # Peak parameters tab
        peak_tab = QWidget(self.right_tabs)
        peak_tab_lay = QVBoxLayout(peak_tab)
        peak_tab_lay.setContentsMargins(0, 0, 0, 0)
        peak_tab_lay.setSpacing(0)

        self.gb_peak = QGroupBox(peak_tab)
        lay_peak = QVBoxLayout(self.gb_peak)
        lay_peak.setContentsMargins(6, 6, 6, 6)
        lay_peak.setSpacing(6)

        # Top row: number of peaks + start fit placeholder button
        top_row = QWidget(self.gb_peak)
        top_lay = QHBoxLayout(top_row)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(6)
        top_lay.addWidget(QLabel("Number of peaks:", top_row))

        self.sb_num_peaks = QSpinBox(top_row)
        self.sb_num_peaks.setRange(1, 10)
        self.sb_num_peaks.setValue(1)
        self.sb_num_peaks.installEventFilter(self)
        top_lay.addWidget(self.sb_num_peaks)

        top_lay.addWidget(QLabel("Fit range:", top_row))
        self.lbl_fit_range_value = QLabel("Full", top_row)
        self.lbl_fit_range_value.setToolTip("Current energy interval used for fitting.")
        top_lay.addWidget(self.lbl_fit_range_value)

        self.btn_fit_range = QPushButton("Edit", top_row)
        self.btn_fit_range.setToolTip(
            "Set the fit range numerically or on the plot. The dashed boundaries can also be dragged directly."
        )
        self.btn_fit_range.clicked.connect(self._on_edit_fit_range)
        top_lay.addWidget(self.btn_fit_range)

        self.btn_start_fit = QPushButton("Start fit", top_row)
        self.btn_start_fit.setCheckable(True)
        self.btn_start_fit.setChecked(False)
        self.btn_start_fit.setEnabled(True)
        self.btn_start_fit.setMinimumHeight(30)
        self.btn_start_fit.setStyleSheet(
            "QPushButton {"
            "font-weight: bold;"
            "color: #5a4700;"
            "background-color: #fff4b3;"
            "border: 2px solid #b08a00;"
            "border-radius: 4px;"
            "padding: 4px 10px;"
            "}"
            "QPushButton:hover { background-color: #fff0a0; }"
            "QPushButton:pressed { background-color: #eadb8c; }"
            "QPushButton:checked { background-color: #e1cc64; border: 2px solid #7a5f00; }"
            "QPushButton:disabled { background-color: #f3e8b0; color: #716542; }"
        )
        top_lay.addWidget(self.btn_start_fit)
        self.btn_start_fit.clicked.connect(self._on_start_fit)

        self.btn_undo_fit = QPushButton("Undo fit", top_row)
        self.btn_undo_fit.setEnabled(False)
        self.btn_undo_fit.setToolTip("Restore the peak/background configuration from immediately before the last fit attempt.")
        self.btn_undo_fit.clicked.connect(self._on_undo_fit)
        top_lay.addWidget(self.btn_undo_fit)

        top_lay.addStretch(1)
        lay_peak.addWidget(top_row, 0)

        # Secondary model/display/I/O controls.  Keep this row compact: the
        # explicit Create action plus its tooltip are sufficient invitation; the
        # old explanatory sentence duplicated the dialog itself and consumed
        # valuable horizontal space.
        setup_row = QWidget(self.gb_peak)
        setup_lay = QHBoxLayout(setup_row)
        setup_lay.setContentsMargins(0, 0, 0, 0)
        setup_lay.setSpacing(6)

        self.btn_create_so_doublet = QPushButton("Create SO doublet...", setup_row)
        self.btn_create_so_doublet.setToolTip("Create a spin-orbit doublet from two existing standalone peaks.")
        self.btn_create_so_doublet.clicked.connect(self._on_create_so_doublet)
        setup_lay.addWidget(self.btn_create_so_doublet)

        self.chk_doublet_view = QCheckBox("Doublet view", setup_row)
        self.chk_doublet_view.setChecked(False)
        self.chk_doublet_view.setToolTip("Show each SO doublet as the sum of its major and minor components instead of showing the two peaks separately.")
        self.chk_doublet_view.toggled.connect(self._on_doublet_view_toggled)
        setup_lay.addWidget(self.chk_doublet_view)
        setup_lay.addStretch(1)

        # Keep fit I/O compact and action-oriented.  Configuration-only actions
        # live under Save/Load menus, while the curves-inclusive export is made
        # explicit in the Save menu.
        self.btn_save_fit = QToolButton(setup_row)
        self.btn_save_fit.setText("Save")
        self.btn_save_fit.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_save_fit.setToolTip("Save the current fit configuration, or export the configuration together with fitted curves.")
        self.menu_save_fit = QMenu(self.btn_save_fit)
        self.menu_save_fit.setToolTipsVisible(True)

        self.act_save_config_snapshot = QAction("Save config snapshot", self.menu_save_fit)
        self.act_save_config_snapshot.setToolTip("Save the current fit configuration temporarily in memory. Curves are not saved.")
        self.act_save_config_snapshot.triggered.connect(self._on_save_fit_setup)
        self.menu_save_fit.addAction(self.act_save_config_snapshot)

        self.act_save_config_file = QAction("Save config to file...", self.menu_save_fit)
        self.act_save_config_file.setToolTip("Save the current fit configuration to a reusable file. Curves are not saved.")
        self.act_save_config_file.triggered.connect(self._on_save_fit_setup_file)
        self.menu_save_fit.addAction(self.act_save_config_file)

        self.act_save_config_curves = QAction("Save config + curves...", self.menu_save_fit)
        self.act_save_config_curves.setToolTip("Export the fit configuration together with calculated component, sum, background and residual data.")
        self.act_save_config_curves.setEnabled(False)
        self.act_save_config_curves.triggered.connect(self._on_export_fit_results)
        self.menu_save_fit.addAction(self.act_save_config_curves)
        self.btn_save_fit.setMenu(self.menu_save_fit)

        self.btn_load_fit = QToolButton(setup_row)
        self.btn_load_fit.setText("Load")
        self.btn_load_fit.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.btn_load_fit.setToolTip("Restore a saved fit configuration. Curves are recalculated automatically.")
        self.menu_load_fit = QMenu(self.btn_load_fit)
        self.menu_load_fit.setToolTipsVisible(True)

        self.act_load_config_snapshot = QAction("Load config snapshot", self.menu_load_fit)
        self.act_load_config_snapshot.setToolTip("Restore the fit configuration previously saved in memory.")
        self.act_load_config_snapshot.setEnabled(False)
        self.act_load_config_snapshot.triggered.connect(self._on_apply_fit_setup)
        self.menu_load_fit.addAction(self.act_load_config_snapshot)

        self.act_load_config_file = QAction("Load config from file...", self.menu_load_fit)
        self.act_load_config_file.setToolTip("Load a saved fit configuration from file and recalculate the curves.")
        self.act_load_config_file.triggered.connect(self._on_load_fit_setup_file)
        self.menu_load_fit.addAction(self.act_load_config_file)
        self.btn_load_fit.setMenu(self.menu_load_fit)

        setup_lay.addWidget(self.btn_save_fit)
        setup_lay.addWidget(self.btn_load_fit)
        lay_peak.addWidget(setup_row, 0)

        # Dedicated third row for fit activity/result status.  Long optimizer
        # messages can then use the available width without competing with the
        # model/display controls above.
        status_row = QWidget(self.gb_peak)
        status_lay = QHBoxLayout(status_row)
        status_lay.setContentsMargins(0, 0, 0, 0)
        status_lay.setSpacing(6)
        status_lay.addStretch(1)
        self.lbl_fit_state = QLabel("○", status_row)
        try:
            self.lbl_fit_state.setStyleSheet("QLabel { color: #7a7a7a; font-size: 14pt; }")
            self.lbl_fit_state.setToolTip("Fitting stopped")
        except Exception:
            pass
        status_lay.addWidget(self.lbl_fit_state)

        self.lbl_fit_progress = QLabel("", status_row)
        self.lbl_fit_progress.setMinimumWidth(180)
        status_lay.addWidget(self.lbl_fit_progress)

        lay_peak.addWidget(status_row, 0)

        # Scrollable area with peak parameter widgets
        self._peak_scroll = QScrollArea(self.gb_peak)
        self._peak_scroll.setWidgetResizable(True)
        self._peak_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._peak_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._peak_scroll_host = QWidget(self._peak_scroll)
        self._peak_scroll_lay = QVBoxLayout(self._peak_scroll_host)
        self._peak_scroll_lay.setContentsMargins(0, 0, 0, 0)
        self._peak_scroll_lay.setSpacing(3)
        self._peak_scroll_lay.addStretch(1)

        self._peak_scroll.setWidget(self._peak_scroll_host)
        lay_peak.addWidget(self._peak_scroll, 1)

        # Internal storage for peak widgets
        self._peak_widgets = []  # list of per-peak widget dicts (preserves order)
        self._so_doublets = []    # pure doublet state dictionaries
        self._so_doublet_widgets = {}  # id -> compact relationship editor widgets
        self._current_xrange = None  # (xmin, xmax)
        self._current_yrange = None  # (ymin, ymax)
        self._constraint_change_in_progress = False
        self._constraint_refresh_in_progress = False
        self._fit_is_running = False
        self._fit_cancel_requested = False
        self._fit_spinner_frames = ["◴", "◷", "◶", "◵"]
        self._fit_spinner_index = 0
        self._fit_spinner_timer = QTimer(self)
        self._fit_spinner_timer.setInterval(180)
        self._fit_spinner_timer.timeout.connect(self._advance_fit_indicator)
        self._curve_states = {}
        if isinstance(getattr(self, "_shared_fit_setup_ref", None), dict):
            self._saved_fit_setup = self._shared_fit_setup_ref.get("setup")
        else:
            self._saved_fit_setup = None
        self._active_curve_key = None
        self._restoring_curve_state = False
        self._fit_range = None  # None means use the complete current spectrum
        self._fit_range_artists = []
        self._fit_range_dialog = None
        self._fit_range_select_mode = False
        self._fit_range_select_start = None
        self._fit_range_select_press_x = None
        self._fit_range_select_press_px = None
        self._fit_range_select_dragged = False
        self._fit_range_select_awaiting_second_click = False
        self._drag_fit_range_side = None
        self._drag_fit_range_press_x = None
        self._drag_fit_range_start = None

        self.sb_num_peaks.valueChanged.connect(self._rebuild_peak_widgets)
        self._rebuild_peak_widgets()
        try:
            self._update_saved_setup_status()
        except Exception:
            pass

        # Bottom control elements (reserve some space under peak parameters)
        ctrl_row = QWidget(self.gb_peak)
        ctrl_lay = QHBoxLayout(ctrl_row)
        ctrl_lay.setContentsMargins(0, 0, 0, 0)
        ctrl_lay.setSpacing(8)

        ctrl_lay.addWidget(QLabel("BG type:", ctrl_row))
        self.cb_bg_type = QComboBox(ctrl_row)
        self.cb_bg_type.addItems(["constant", "linear", "parabolic", "Shirley"])
        self.cb_bg_type.setCurrentText("Shirley")
        ctrl_lay.addWidget(self.cb_bg_type)

        # Background parameters (polynomial). Shown only for constant/linear/parabolic.
        self.lab_bg_b0 = QLabel("b0:", ctrl_row)
        self.sb_bg_b0 = QDoubleSpinBox(ctrl_row)
        self.lab_bg_b1 = QLabel("b1:", ctrl_row)
        self.sb_bg_b1 = QDoubleSpinBox(ctrl_row)
        self.lab_bg_b2 = QLabel("b2:", ctrl_row)
        self.sb_bg_b2 = QDoubleSpinBox(ctrl_row)

        for sb in (self.sb_bg_b0, self.sb_bg_b1, self.sb_bg_b2):
            sb.setDecimals(6)
            sb.setSingleStep(0.1)
            sb.setRange(-1e12, 1e12)
            sb.setKeyboardTracking(False)
            sb.setMinimumWidth(90)

        self.sb_bg_b0.setValue(0.0)
        self.sb_bg_b1.setValue(0.0)
        self.sb_bg_b2.setValue(0.0)

        # Track manual edits (prevents auto-overwrite on curve change)
        self.sb_bg_b0.valueChanged.connect(self._on_bg_coeff_changed)
        self.sb_bg_b1.valueChanged.connect(self._on_bg_coeff_changed)
        self.sb_bg_b2.valueChanged.connect(self._on_bg_coeff_changed)
        if hasattr(self, 'sb_bg_alpha'):
            self.sb_bg_alpha.valueChanged.connect(self._on_bg_coeff_changed)

        ctrl_lay.addSpacing(10)
        ctrl_lay.addWidget(self.lab_bg_b0); ctrl_lay.addWidget(self.sb_bg_b0)
        ctrl_lay.addWidget(self.lab_bg_b1); ctrl_lay.addWidget(self.sb_bg_b1)
        ctrl_lay.addWidget(self.lab_bg_b2); ctrl_lay.addWidget(self.sb_bg_b2)
        self.lab_bg_alpha = QLabel("α:", ctrl_row)
        self.sb_bg_alpha = QDoubleSpinBox(ctrl_row)
        self.sb_bg_alpha.setDecimals(3)
        self.sb_bg_alpha.setSingleStep(0.05)
        self.sb_bg_alpha.setRange(0.0, 1.0)
        self.sb_bg_alpha.setKeyboardTracking(False)
        self.sb_bg_alpha.setMinimumWidth(70)
        self.sb_bg_alpha.setValue(1.0)
        self.chk_bg_alpha_fixed = QCheckBox("Fixed", ctrl_row)
        self.chk_bg_alpha_fixed.setChecked(False)
        self.chk_bg_alpha_fixed.setToolTip("Keep Shirley α fixed during automated fitting.")
        ctrl_lay.addWidget(self.lab_bg_alpha); ctrl_lay.addWidget(self.sb_bg_alpha); ctrl_lay.addWidget(self.chk_bg_alpha_fixed)

        self._bg_coeffs_touched = False
        self.cb_bg_type.currentTextChanged.connect(self._on_bg_type_changed)
        self._last_bg_type = str(self.cb_bg_type.currentText())
        self._on_bg_type_changed(self.cb_bg_type.currentText())
        self.sb_bg_alpha.valueChanged.connect(self._on_bg_coeff_changed)
        self.sb_bg_alpha.editingFinished.connect(self._on_bg_coeff_changed)

        ctrl_lay.addStretch(1)
        lay_peak.addWidget(ctrl_row, 0)
        peak_tab_lay.addWidget(self.gb_peak, 1)
        self.right_tabs.addTab(peak_tab, "Peak parameters")

    def _build_fit_results_tab(self) -> None:
        """Build fit-quality and fitted-parameter result widgets."""
        # Fit results tab (placeholder tables, kept empty until a real fit is implemented)
        fitres_tab = QWidget(self.right_tabs)
        fitres_lay = QVBoxLayout(fitres_tab)
        fitres_lay.setContentsMargins(6, 6, 6, 6)
        fitres_lay.setSpacing(6)

        # Fit-quality summary
        _fq = fit_widgets.create_fit_quality_box(fitres_tab)
        fit_quality_box = _fq["group"]
        self.lab_fit_status = _fq["lab_fit_status"]
        self.lab_fit_rss = _fq["lab_fit_rss"]
        self.lab_fit_rms = _fq["lab_fit_rms"]
        self.lab_fit_redchi = _fq["lab_fit_redchi"]
        self.lbl_fit_status = _fq["lbl_fit_status"]
        self.lbl_fit_rss = _fq["lbl_fit_rss"]
        self.lbl_fit_rms = _fq["lbl_fit_rms"]
        self.lbl_fit_redchi = _fq["lbl_fit_redchi"]
        fitres_lay.addWidget(fit_quality_box, 0)

        fitres_lay.addWidget(QLabel("Peak fit parameters:"))
        self.tbl_fit_results = fit_widgets.create_results_table(
            fitres_tab, ["Energy", "Height", "Area", "LFWHM", "GFWHM", "Alpha"], pair_separator=True
        )
        fitres_lay.addWidget(self.tbl_fit_results, 1)

        fitres_lay.addWidget(QLabel("Background parameters:"))
        self.tbl_bg_results = fit_widgets.create_results_table(fitres_tab, None, pair_separator=False)
        fitres_lay.addWidget(self.tbl_bg_results, 0)

        self.right_tabs.addTab(fitres_tab, "Fit results")
        self._last_fit_bound_hits = set()
        self._last_fit_result = None
        self._last_fit_data = None
        self._last_fit_bg_type = None
        self._last_fit_status = ""
        self._pre_fit_snapshot = None
        self._update_fit_results_tables()
        self._clear_fit_quality_summary()

    def _configure_main_splitter(self, splitter: QSplitter, lay_single: QVBoxLayout) -> None:
        """Apply the established pane proportions and add the splitter."""
        # Stretch factors: keep curve list narrower in normal mode, and make
        # plot vs fit-parameters balanced. In supplied-anchor mode the left
        # curve-selection widget is omitted.
        if self._single_payload_mode:
            splitter.setStretchFactor(0, 5)
            splitter.setStretchFactor(1, 5)
            try:
                splitter.setSizes([700, 700])
            except Exception:
                pass
        else:
            splitter.setStretchFactor(0, 2)
            splitter.setStretchFactor(1, 5)
            splitter.setStretchFactor(2, 5)
            try:
                splitter.setSizes([260, 650, 650])
            except Exception:
                pass

        lay_single.addWidget(splitter, 1)

    def _build_dialog_buttons(self, main: QVBoxLayout) -> None:
        """Build the dialog-level OK/Cancel button box."""
        # Buttons
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        try:
            bb.button(QDialogButtonBox.StandardButton.Ok).setAutoDefault(False)
            bb.button(QDialogButtonBox.StandardButton.Ok).setDefault(False)
            bb.button(QDialogButtonBox.StandardButton.Cancel).setAutoDefault(False)
            bb.button(QDialogButtonBox.StandardButton.Cancel).setDefault(False)
        except Exception:
            pass
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        main.addWidget(bb)

    def _initialize_curve_selection(self, mw, supplied_payload, supplied_label: Optional[str]) -> None:
        """Populate the curve tree and initialize the first active curve state."""
        # Populate the curve list either from a supplied anchor payload or from
        # currently visible + checked curves in MW. In supplied-payload mode the
        # tree is kept hidden but still exists internally, so the existing
        # single-curve fitting code path can be reused unchanged.
        self._payload_by_key: dict = {}
        self._display_by_key: dict = {}
        if self._single_payload_mode:
            key = "__supplied_anchor__"
            self._payload_by_key[key] = supplied_payload
            self._display_by_key[key] = str(supplied_label or getattr(supplied_payload, "title", "Anchor spectrum"))
        elif hasattr(mw, "build_payload_by_key"):
            # If mw is a Host adapter in the future
            self._payload_by_key = mw.build_payload_by_key()
        else:
            # MainWindow: build from selected tree (visible items only)
            self._payload_by_key, self._display_by_key = self._build_payload_by_key_from_mainwindow(mw)

        for key, payload in self._payload_by_key.items():
            label = self._display_by_key.get(key, getattr(payload, 'title', key))
            it = QTreeWidgetItem(self.tree_curves, [label])
            it.setData(0, Qt.ItemDataRole.UserRole, key)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Unchecked)

        # Ensure full labels are visible (no eliding) and allow scrolling
        try:
            self.tree_curves.setTextElideMode(Qt.TextElideMode.ElideNone)
            self.tree_curves.header().setStretchLastSection(True)
            self.tree_curves.resizeColumnToContents(0)
        except Exception:
            pass

        self._ensure_single_checked()
        self._active_curve_key = self._get_checked_key()
        if self._single_payload_mode and self._supplied_initial_fit_state:
            # Explicit anchor state wins over automatic initialization.
            self._plot_checked_curve()
            try:
                self._restore_curve_state(self._supplied_initial_fit_state)
                key = self._get_checked_key()
                if key:
                    self._curve_states[key] = self._capture_curve_state()
            except Exception as exc:
                log_noncritical_error("restoring supplied anchor fit state", exc, logger=self._logger)
        else:
            # Fresh single-fit/anchor dialogs must go through the same default-state
            # builder used when switching to a previously unseen curve.  Merely
            # plotting the first curve leaves the constructor-created one-peak UI
            # in place and bypasses conservative multi-peak suggestions.
            self._initialize_current_curve_state()
            key = self._get_checked_key()
            if key:
                try:
                    self._curve_states[key] = self._capture_curve_state()
                except Exception:
                    pass
        self._install_no_enter_close_filters()

        # Respond to user selection changes
        self.tree_curves.itemChanged.connect(self._on_curve_item_changed)





    def _remember_fit_legend_position(self) -> None:
        """Remember a user-dragged fitting legend position before a redraw clears it."""
        try:
            legend = self.ax.get_legend()
            if legend is None:
                return
            loc = getattr(legend, "_loc", None)
            # Matplotlib converts a dragged legend from an integer/string loc to
            # a 2-tuple in the legend's bbox coordinate system.  Preserve only
            # that explicit user position; an untouched legend should continue
            # to use loc='best'.
            if isinstance(loc, (tuple, list)) and len(loc) == 2:
                self._fit_legend_loc = (float(loc[0]), float(loc[1]))
        except Exception:
            pass

    def _refresh_fit_legend(self) -> None:
        """Rebuild the fitting-plot legend without losing a dragged position."""
        try:
            handles, labels = self.ax.get_legend_handles_labels()
            pairs = [
                (h, str(label)) for h, label in zip(handles, labels)
                if str(label) and not str(label).startswith("_")
            ]
            old = self.ax.get_legend()
            if old is not None:
                self._remember_fit_legend_position()
                old.remove()
            if not pairs:
                self.canvas.draw_idle()
                return
            legend = self.ax.legend(
                [p[0] for p in pairs], [p[1] for p in pairs],
                loc=getattr(self, "_fit_legend_loc", "best"),
                fontsize=9, framealpha=0.85,
            )
            legend.set_draggable(True)
            legend.set_visible(bool(self.cb_fit_legend.isChecked()))
            self.canvas.draw_idle()
        except Exception:
            pass

    def accept(self) -> None:
        """Accept the dialog and, in supplied-anchor mode, expose latest fit state."""
        if getattr(self, "_single_payload_mode", False):
            try:
                key = self._get_checked_key()
                if key:
                    self._curve_states[key] = self._capture_curve_state()
                self._anchor_result_state = self._capture_curve_state()
                self._anchor_result_setup = self._capture_fit_setup_template()
            except Exception as exc:
                log_noncritical_error("capturing supplied anchor fit state", exc, logger=self._logger)
        super().accept()

    def anchor_fit_state(self) -> Optional[Dict[str, Any]]:
        """Return the latest full curve-fit state captured when OK was pressed."""
        return self._anchor_result_state

    def anchor_fit_setup(self) -> Optional[Dict[str, Any]]:
        """Return the latest reusable peak/BG setup captured when OK was pressed."""
        return self._anchor_result_setup






































































    _PARAM_LABELS = {"E": "Energy", "H": "Height", "L": "LFWHM", "G": "GFWHM", "A": "Alpha"}































def _collect_selected_curve_payloads(mw) -> List[Tuple[str, Any, str]]:
    """Collect currently selected/visible checked curve payloads from the main window."""
    payload_by_key: Dict[str, Any] = {}
    display_by_key: Dict[str, str] = {}
    if hasattr(mw, "build_payload_by_key"):
        payload_by_key = mw.build_payload_by_key()
    else:
        try:
            payload_by_key, display_by_key = FitCoreLevelDialog._build_payload_by_key_from_mainwindow(None, mw)  # type: ignore[misc]
        except Exception:
            payload_by_key, display_by_key = {}, {}
    items: List[Tuple[str, Any, str]] = []
    for key in _iter_visible_checked_curve_keys(mw):
        pl = payload_by_key.get(key)
        if pl is None:
            continue
        label = display_by_key.get(key, getattr(pl, "title", key))
        items.append((key, pl, label))
    return items


def _selected_curves_have_dissimilar_energy_ranges(items: List[Tuple[str, Any, str]]) -> bool:
    """Return True if selected curves appear to cover substantially different x ranges."""
    import numpy as np

    ranges = []
    for _key, pl, _label in items:
        try:
            x = np.asarray(getattr(pl, "x", None), dtype=float)
        except Exception:
            continue
        if x.size < 2:
            continue
        x = x[np.isfinite(x)]
        if x.size < 2:
            continue
        xmin = float(np.min(x))
        xmax = float(np.max(x))
        span = float(abs(xmax - xmin))
        if span <= 0:
            continue
        ranges.append((xmin, xmax, span))
    if len(ranges) < 2:
        return False

    mins = np.array([r[0] for r in ranges], dtype=float)
    maxs = np.array([r[1] for r in ranges], dtype=float)
    spans = np.array([r[2] for r in ranges], dtype=float)
    median_span = float(np.median(spans)) if spans.size else 0.0
    if median_span <= 0:
        return False

    common_overlap = float(np.min(maxs) - np.max(mins))
    common_frac = common_overlap / median_span
    left_spread = float(np.max(mins) - np.min(mins))
    right_spread = float(np.max(maxs) - np.min(maxs))
    edge_tol = max(2.0, 0.40 * median_span)

    return bool(common_frac < 0.70 or left_spread > edge_tol or right_spread > edge_tol)


def _warn_on_dissimilar_energy_ranges(parent, items: List[Tuple[str, Any, str]]) -> bool:
    """Return True if the user wants to proceed despite dissimilar energy ranges."""
    if not _selected_curves_have_dissimilar_energy_ranges(items):
        return True
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Different energy ranges")
    box.setText(
        "The selected curves do not have a reasonably similar energy range. "
        "Joint comparison or fitting may be unreliable. Do you want to proceed?"
    )
    proceed_btn = box.addButton("Proceed", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is proceed_btn


def _choose_fitting_mode(parent) -> str:
    """Ask whether many selected curves should be handled individually or as a sequence."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("Select fitting mode")
    box.setText(
        "More than 5 curves are selected. Do you want to fit them individually or prepare a sequence fit?"
    )
    btn_individual = box.addButton("Fit selected curves individually", QMessageBox.ButtonRole.AcceptRole)
    btn_sequence = box.addButton("Prepare sequence fit", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    clicked = box.clickedButton()
    if clicked is btn_individual:
        return "individual"
    if clicked is btn_sequence:
        return "sequence"
    return "cancel"


def open_fit_corelevel_dialog(mw) -> int:
    """Open the single-curve or batch fitting dialog based on the current selection."""
    items = _collect_selected_curve_payloads(mw)
    if not items:
        QMessageBox.warning(mw, "No curves selected", "Please check one or more curves in the selected-curves tree first.")
        return 0

    if len(items) > 1 and not _warn_on_dissimilar_energy_ranges(mw, items):
        return 0

    if len(items) > 5:
        mode = _choose_fitting_mode(mw)
        if mode == "cancel":
            return 0
        if mode == "sequence":
            try:
                marker = getattr(mw, "_mark_source_usage_from_payloads", None)
                if callable(marker):
                    marker(items, "peak fitting")
            except Exception:
                pass
            from .batch_dialog import open_batch_fit_dialog
            return open_batch_fit_dialog(mw, items)

    try:
        marker = getattr(mw, "_mark_source_usage_from_payloads", None)
        if callable(marker):
            marker(items, "peak fitting")
    except Exception:
        pass

    # Use an independent top-level window rather than a child/owned dialog.
    # A modeless QDialog that still has the main window as its parent remains
    # stacked above that parent on Windows, which prevents the main window from
    # coming to the foreground when clicked.  The dialog already keeps an
    # explicit reference to ``mw`` for application access, so no Qt parent is
    # needed here.
    dlg = FitCoreLevelDialog(mw, parent=None)

    # Restore any fit-editor state previously captured for this exact selected
    # curve set (for example from a reopened PANDA session).
    signature = "||".join(sorted(str(row[0]) for row in items))
    dlg._session_signature = signature
    try:
        registry = getattr(mw, "_fit_session_registry", {}) or {}
        saved_state = (registry.get("single", {}) or {}).get(signature)
        if isinstance(saved_state, dict):
            dlg._restore_session_fit_state(saved_state)
    except Exception as exc:
        log_noncritical_error("restoring fit-session state", exc)

    # Keep an application-owned reference so the independent fit window is not
    # garbage-collected after this function returns, and remove it again when
    # the window closes.
    dialogs = getattr(mw, "_peak_fit_dialogs", None)
    if dialogs is None:
        dialogs = []
        setattr(mw, "_peak_fit_dialogs", dialogs)
    dialogs.append(dlg)

    def _forget_dialog(*_args):
        # Persist the editor state in the main-window registry before the dialog
        # is destroyed.  Session saving therefore works even after the fit
        # window has been closed.
        try:
            registry = getattr(mw, "_fit_session_registry", None)
            if not isinstance(registry, dict):
                registry = {"single": {}, "batch": {}}
                setattr(mw, "_fit_session_registry", registry)
            registry.setdefault("single", {})[signature] = dlg._capture_session_fit_state()
        except Exception as exc:
            log_noncritical_error("capturing fit-session state", exc)
        try:
            dialogs.remove(dlg)
        except ValueError:
            pass
        try:
            dlg.deleteLater()
        except Exception:
            pass

    dlg.finished.connect(_forget_dialog)
    dlg.show()
    try:
        dlg.raise_()
        dlg.activateWindow()
    except Exception:
        pass
    return 1
