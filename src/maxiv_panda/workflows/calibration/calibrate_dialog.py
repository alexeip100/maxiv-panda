"""Energy calibration workflow: Calibrate Energy dialog.

This module hosts the (currently monolithic) dialog implementation extracted from
`maxiv_panda.ui` as a first refactoring step. The implementation still operates
on the MainWindow instance passed in as `mw` and therefore preserves behavior.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

# Pure fitting helpers (already extracted in v0.4.73)
from .fitters import _fit_fermi_edge, _fit_core_level, _smooth, _voigt_profile
from ...energy_utils import normalize_energy_xlabel


def _guess_reference_type_from_name(ref_display: str) -> str:
    """Guess reference type from a curve/display name.

    Rules kept intentionally simple and deterministic:
    - names containing Fermi-edge markers -> "Fermi edge"
    - any other non-empty name -> "Core level"
    - missing/blank names -> "Unknown"
    """
    s = (ref_display or "").strip()
    if not s:
        return "Unknown"
    s_lower = s.lower()
    if "fermi" in s_lower or "f.e." in s_lower:
        return "Fermi edge"
    # Token-based checks avoid accidental matches inside unrelated words.
    tokens = []
    token = []
    for ch in s:
        if ch.isalnum():
            token.append(ch)
        elif token:
            tokens.append("".join(token))
            token = []
    if token:
        tokens.append("".join(token))
    tokens_upper = {tok.upper() for tok in tokens if tok}
    if "FE" in tokens_upper or "EF" in tokens_upper:
        return "Fermi edge"
    return "Core level"


def open_calibrate_energy_dialog(mw_or_host) -> None:
    """Open the Calibrate Energy dialog.

    Accepts either a MainWindow instance or a CalibrationHost (during refactor).
    """
    # Accept either MainWindow or CalibrationHost (for gradual refactor).
    from ...common import CalibrationHost
    from .calibrate_logic import CalibrationLogic
    if hasattr(mw_or_host, 'mw'):
        host = mw_or_host
        mw = mw_or_host.mw
    else:
        mw = mw_or_host
        host = CalibrationHost(mw_or_host)

    # Import locally to avoid module import cycles at application startup.
    # PlotPayload is the container type used throughout the main UI.
    from ...ui import PlotPayload

    # Collect currently selected (checked) curves in the selected tree, in the
    # exact visual order shown to the user.  Iterating _selected_by_key instead
    # preserves historical insertion/click order and can scramble an otherwise
    # numerically sorted selection after processing.
    raw_keys: list[str] = []
    raw_labels: list[str] = []
    try:
        tree = mw.selected_tree
        role_key = getattr(mw, "ROLE_KEY", Qt.ItemDataRole.UserRole + 1)
        root = tree.invisibleRootItem()
        for i in range(root.childCount()):
            group = root.child(i)
            if group is None or group.isHidden():
                continue
            for j in range(group.childCount()):
                it = group.child(j)
                if it is None or it.isHidden() or it.checkState(0) != Qt.CheckState.Checked:
                    continue
                key = it.data(0, role_key)
                if isinstance(key, tuple) and key:
                    key = key[0]
                if not isinstance(key, str) or not key:
                    continue
                raw_keys.append(key)
                raw_labels.append(it.text(0))
    except Exception:
        pass

    if not raw_keys:
        QMessageBox.information(mw, "Calibrate energy", "Select at least one curve first.")
        return

    # Normalization is a Processed-data view transform.  Mark the selected
    # calibration inputs explicitly so the dialog mirrors what is on screen.
    try:
        _pc = getattr(mw, "_processed_controller", None)
        if _pc is not None and _pc.workflow_normalization_active():
            raw_labels = [lbl if "(Norm)" in lbl else f"{lbl} (Norm)" for lbl in raw_labels]
    except Exception:
        pass

    # Collect all candidate curves from the loaded-files tree.
    candidates: list[tuple[str, str]] = []  # (key, display)
    try:
        for leaf in mw._iter_curve_leaves():
            key_display = leaf.data(0, mw.ROLE_KEY)
            if isinstance(key_display, tuple) and len(key_display) == 2:
                k, disp = key_display
                if isinstance(k, str) and isinstance(disp, str):
                    candidates.append((k, disp))
    except Exception:
        pass

    # Fallback: ensure at least the raw curves are present as candidates.
    if not candidates:
        candidates = list(zip(raw_keys, raw_labels))

    # Deduplicate candidates by key, keep first display.
    seen: set[str] = set()
    cand_keys: list[str] = []
    cand_disp: list[str] = []
    for k, d in candidates:
        if k in seen:
            continue
        seen.add(k)
        cand_keys.append(k)
        cand_disp.append(d)

    dlg = QDialog(mw)
    dlg.setWindowTitle("Calibrate energy")
    dlg.setModal(True)
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)


    def _style_help_label(lbl: QLabel, text: str) -> None:
        """Apply a consistent, readable help-text style across tabs."""
        lbl.setWordWrap(True)
        lbl.setText(text)
        try:
            f = lbl.font()
            f.setPointSize(f.pointSize() + 1)
            f.setBold(True)
            f.setItalic(True)
            lbl.setFont(f)
            lbl.setTextFormat(Qt.TextFormat.RichText)
            t = lbl.text().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            t = t.replace("\n", "<br/>")
            lbl.setText(f"<div style='line-height:145%'>{t}</div>")
            lbl.setContentsMargins(6, 10, 6, 6)
        except Exception:
            pass


    tabs = QTabWidget(dlg)
    layout.addWidget(tabs, 1)

    # --- Tab: Energy references (mapping)
    tab_map = QWidget(tabs)
    tab_map_layout = QVBoxLayout(tab_map)
    tab_map_layout.setContentsMargins(0, 0, 0, 0)
    tab_map_layout.setSpacing(8)

    help_lbl = QLabel(tab_map)
    _style_help_label(
        help_lbl,
        "Start here: map each curve to a reference (a single reference may be reused).\n"
        "Set reference type if needed (Unknown / Fermi edge / Core level), then click Next.",
    )
    tab_map_layout.addWidget(help_lbl, 0)

    table = QTableWidget(tab_map)
    table.setColumnCount(3)
    table.setHorizontalHeaderLabels(["Curve to calibrate", "Reference curve", "Reference type"])
    table.setRowCount(len(raw_keys))
    table.verticalHeader().setVisible(False)
    try:
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    except Exception:
        pass
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    # Ensure the mapping list remains scrollable for large numbers of curves.
    try:
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    except Exception:
        pass

    # Store mapping in a dict on the dialog instance for later stages.
    mapping: dict[str, str] = {}
    ref_types: dict[str, str] = {}
    ref_type_manual: set[str] = set()  # raw_key where user explicitly set Reference type

    def _guess_default_ref_type(ref_display: str) -> str:
        return _guess_reference_type_from_name(ref_display)

    _setting_type_programmatically = False


    def _combo_find_index_by_key(combo: QComboBox, key: str) -> int:
        for ii in range(combo.count()):
            if combo.itemData(ii) == key:
                return ii
        return 0

    def _on_ref_changed(row: int) -> None:
        nonlocal _setting_type_programmatically
        try:
            cb: QComboBox = table.cellWidget(row, 1)  # type: ignore
            rk = raw_keys[row]
            mapping[rk] = str(cb.currentData())
            # If the user hasn't explicitly chosen the reference type, try to guess it from the reference title.
            if rk not in ref_type_manual:
                refk = mapping.get(rk, "")
                disp = ""
                try:
                    if isinstance(refk, str) and refk in cand_keys:
                        disp = cand_disp[cand_keys.index(refk)]
                except Exception:
                    disp = ""
                guessed = _guess_default_ref_type(disp)
                cb_type: QComboBox = table.cellWidget(row, 2)  # type: ignore
                _setting_type_programmatically = True
                try:
                    cb_type.setCurrentText(guessed)
                    ref_types[rk] = guessed
                finally:
                    _setting_type_programmatically = False
        except Exception:
            pass

    def _on_type_changed(row: int) -> None:
        nonlocal _setting_type_programmatically
        try:
            cb: QComboBox = table.cellWidget(row, 2)  # type: ignore
            rk = raw_keys[row]
            ref_types[rk] = str(cb.currentText())
            if not _setting_type_programmatically:
                ref_type_manual.add(rk)
        except Exception:
            pass

    for r, (rk, rl) in enumerate(zip(raw_keys, raw_labels)):
        item = QTableWidgetItem(rl)
        table.setItem(r, 0, item)

        cb_ref = QComboBox(table)
        for k, d in zip(cand_keys, cand_disp):
            cb_ref.addItem(d, userData=k)
        # Default: self-reference (useful for testing), else first.
        cb_ref.setCurrentIndex(_combo_find_index_by_key(cb_ref, rk))
        mapping[rk] = str(cb_ref.currentData())
        cb_ref.currentIndexChanged.connect(lambda _ix, row=r: _on_ref_changed(row))
        table.setCellWidget(r, 1, cb_ref)

        cb_type = QComboBox(table)
        cb_type.addItems(["Unknown", "Fermi edge", "Core level"])

        # Default reference type: try to guess from the reference title.
        refk0 = mapping.get(rk, "")
        disp0 = ""
        try:
            if isinstance(refk0, str) and refk0 in cand_keys:
                disp0 = cand_disp[cand_keys.index(refk0)]
        except Exception:
            disp0 = ""
        guessed0 = _guess_default_ref_type(disp0)

        _setting_type_programmatically = True
        try:
            cb_type.setCurrentText(guessed0)
            ref_types[rk] = guessed0
        finally:
            _setting_type_programmatically = False

        cb_type.currentIndexChanged.connect(lambda _ix, row=r: _on_type_changed(row))
        table.setCellWidget(r, 2, cb_type)

    tab_map_layout.addWidget(table, 1)
    tabs.addTab(tab_map, "Energy references")

    # Build a lookup from curve key -> PlotPayload for fitting.
    payload_by_key = host.build_payload_by_key()
    # If Processed-data normalization is active, calibration must operate on
    # exactly the curves the user is looking at.  Replace only the currently
    # selected/visible inputs with virtual normalized payloads; unrelated loaded
    # reference candidates remain untouched.
    try:
        controller = getattr(mw, "_processed_controller", None)
        if controller is not None and controller.workflow_normalization_active():
            for _rk in raw_keys:
                _pl = payload_by_key.get(_rk)
                if _pl is not None:
                    payload_by_key[_rk] = controller.normalize_payload_for_workflow(_pl, getattr(mw, "_selected_by_key", {}).get(_rk))
    except Exception:
        pass
    logic = CalibrationLogic(host)

    def _auto_reference_type(ref_key: str, ref_display: str) -> str:
        return _guess_reference_type_from_name(ref_display)

    # Store fit results in dicts on the dialog for later tabs.
    fit_results: dict[str, dict[str, Any]] = {}

    # --- Tab: Fit references
    tab_fit = QWidget(tabs)
    fit_layout = QVBoxLayout(tab_fit)
    fit_layout.setContentsMargins(0, 0, 0, 0)
    fit_layout.setSpacing(8)

    fit_help = QLabel(tab_fit)
    _style_help_label(
        fit_help,
        "Next: fit reference curves to extract marker energies (EF for Fermi edge, max of fit for core levels).\n"
        "Adjust Expected E and fit range if needed, then click Fit references.",
    )
    fit_layout.addWidget(fit_help, 0)

    fit_btn_row = QWidget(tab_fit)
    fit_btn_lay = QHBoxLayout(fit_btn_row)
    fit_btn_lay.setContentsMargins(0, 0, 0, 0)
    fit_btn_lay.setSpacing(8)
    btn_fit_all = QPushButton("Fit references", fit_btn_row)
    btn_fit_all.setToolTip("Fit all mapped references and show all fitted references together")
    fit_btn_lay.addWidget(btn_fit_all)

    # Optional expected EF (helps stabilize FE fits and provides quality control)
    cb_use_expected = QCheckBox("Expected E", fit_btn_row)
    cb_use_expected.setToolTip("Optional: use an expected energy (EF for Fermi edge, peak energy for core-level)")
    sb_expected_ef = QDoubleSpinBox(fit_btn_row)
    sb_expected_ef.setDecimals(3)
    # NOTE: range is adjusted dynamically depending on reference type (FE vs core-level).
    sb_expected_ef.setRange(-10.0, 10.0)
    sb_expected_ef.setSingleStep(0.1)
    sb_expected_ef.setValue(0.0)
    sb_expected_ef.setEnabled(False)
    cb_use_expected.toggled.connect(sb_expected_ef.setEnabled)
    fit_btn_lay.addWidget(cb_use_expected)
    fit_btn_lay.addWidget(sb_expected_ef)

    # Fit range controls (general):
    # We use a *relative* fit window around the "Expected marker" value:
    #   x_min = expected + dE_from,  x_max = expected + dE_to
    # This works for both Fermi edge and core-level fits and makes the UI consistent.
    cb_use_window = QCheckBox("Fit in range around E:", fit_btn_row)
    cb_use_window.setToolTip(
        "Fit only within [expected + dE_from, expected + dE_to].\n"
        "Tip: keep Expected marker at EF (FE) or peak position (core-level), then adjust the relative window."
    )

    sb_de_from = QDoubleSpinBox(fit_btn_row)
    sb_de_from.setDecimals(3)
    sb_de_from.setRange(-1e6, 1e6)
    sb_de_from.setSingleStep(0.1)
    sb_de_from.setToolTip("Relative lower bound (eV) around Expected E")

    sb_de_to = QDoubleSpinBox(fit_btn_row)
    sb_de_to.setDecimals(3)
    sb_de_to.setRange(-1e6, 1e6)
    sb_de_to.setSingleStep(0.1)
    sb_de_to.setToolTip("Relative upper bound (eV) around Expected E")

    # Initial default assumes the common Fermi-edge case.  The window is
    # intentionally asymmetric on the high-BE side to reduce the chance that
    # nearby valence-band structure biases an otherwise plausible-looking EF fit.
    # Core-level references are switched to the conventional ±1 eV default below.
    sb_de_from.setValue(-1.0)
    sb_de_to.setValue(+0.4)

    lbl_abs_window = QLabel("", fit_btn_row)
    lbl_abs_window.setToolTip("Absolute fit window computed from Expected marker and dE_from/to")

    def _update_abs_window_label() -> None:
        try:
            e0 = float(sb_expected_ef.value())
            d0 = float(sb_de_from.value())
            d1 = float(sb_de_to.value())
            x0 = e0 + d0
            x1 = e0 + d1
            if x0 > x1:
                x0, x1 = x1, x0
            lbl_abs_window.setText(f"abs: [{x0:.3f}, {x1:.3f}]")
        except Exception:
            lbl_abs_window.setText("")

    def _set_window_enabled(on: bool) -> None:
        sb_de_from.setEnabled(on)
        sb_de_to.setEnabled(on)
        lbl_abs_window.setEnabled(on)
        _update_abs_window_label()

    cb_use_window.toggled.connect(_set_window_enabled)
    cb_use_window.setChecked(True)
    _set_window_enabled(True)

    sb_expected_ef.valueChanged.connect(lambda _v: _update_abs_window_label())
    sb_de_from.valueChanged.connect(lambda _v: _update_abs_window_label())
    sb_de_to.valueChanged.connect(lambda _v: _update_abs_window_label())

    fit_btn_lay.addWidget(cb_use_window)
    fit_btn_lay.addWidget(QLabel("from", fit_btn_row))
    fit_btn_lay.addWidget(sb_de_from)
    fit_btn_lay.addWidget(QLabel("to", fit_btn_row))
    fit_btn_lay.addWidget(sb_de_to)
    fit_btn_lay.addWidget(lbl_abs_window)

    # Core-level peak model controls (single peak vs doublet).  This row is
    # shown only when a core-level reference is selected; for Fermi-edge-only
    # calibration it collapses completely so the table/plot use the space.
    fit_ctrl_row2 = QWidget(tab_fit)
    fit_ctrl_lay2 = QHBoxLayout(fit_ctrl_row2)
    fit_ctrl_lay2.setContentsMargins(0, 0, 0, 0)
    fit_ctrl_lay2.setSpacing(8)
    try:
        fit_ctrl_lay2.setAlignment(Qt.AlignmentFlag.AlignLeft)
    except Exception:
        pass

    # No permanently visible progress widget here.  The old idle progress bar
    # produced a dead-looking control row below Fit references.  Fitting is
    # synchronous and the Fit references button is disabled while it runs.
    busy_fit = None

    lbl_core_model = QLabel("Model:", fit_ctrl_row2)
    cmb_core_model = QComboBox(fit_ctrl_row2)
    cmb_core_model.addItems(["Single peak", "Doublet (2 peaks)"])
    cmb_core_model.setFixedWidth(160)
    cmb_core_model.setToolTip("Core-level model: fit a single peak or a 2-peak doublet. (Fermi edge ignores this)")
    fit_ctrl_lay2.addWidget(lbl_core_model)
    fit_ctrl_lay2.addWidget(cmb_core_model)

    # Doublet-specific controls (kept compact)
    lbl_split = QLabel("ΔE:", fit_ctrl_row2)
    cb_auto_split = QCheckBox("auto", fit_ctrl_row2)
    sb_split = QDoubleSpinBox(fit_ctrl_row2)
    sb_split.setDecimals(4)
    sb_split.setRange(0.0, 200.0)
    sb_split.setSingleStep(0.1)
    sb_split.setValue(1.0)
    sb_split.setFixedWidth(80)
    cb_auto_split.setChecked(True)
    lbl_split.setToolTip("Energy splitting between the two peaks (μ2 = μ1 + ΔE).")
    cb_auto_split.setToolTip("Estimate ΔE automatically from the data.")
    sb_split.setToolTip("Manual ΔE (eV). Used when auto is off.")
    fit_ctrl_lay2.addSpacing(8)
    fit_ctrl_lay2.addWidget(lbl_split)
    fit_ctrl_lay2.addWidget(cb_auto_split)
    fit_ctrl_lay2.addWidget(sb_split)

    lbl_ratio = QLabel("I2/I1:", fit_ctrl_row2)
    cb_auto_ratio = QCheckBox("auto", fit_ctrl_row2)
    sb_ratio = QDoubleSpinBox(fit_ctrl_row2)
    sb_ratio.setDecimals(4)
    sb_ratio.setRange(0.0, 10.0)
    sb_ratio.setSingleStep(0.05)
    sb_ratio.setValue(0.5)
    sb_ratio.setFixedWidth(80)
    cb_auto_ratio.setChecked(True)
    lbl_ratio.setToolTip("Intensity ratio of the 2nd peak to the main peak.")
    cb_auto_ratio.setToolTip("Estimate the intensity ratio automatically from the data.")
    sb_ratio.setToolTip("Manual intensity ratio. Used when auto is off.")
    fit_ctrl_lay2.addSpacing(8)
    fit_ctrl_lay2.addWidget(lbl_ratio)
    fit_ctrl_lay2.addWidget(cb_auto_ratio)
    fit_ctrl_lay2.addWidget(sb_ratio)

    cb_tie_widths = QCheckBox("Tie widths", fit_ctrl_row2)
    cb_tie_widths.setChecked(True)
    cb_tie_widths.setToolTip("Use the same width parameters for both peaks (recommended for stability).")
    fit_ctrl_lay2.addSpacing(8)
    fit_ctrl_lay2.addWidget(cb_tie_widths)

    fit_ctrl_lay2.addStretch(1)

    def _on_core_model_changed(_idx: int = 0) -> None:
        # Show/hide doublet-specific controls depending on model selection.
        try:
            is_doublet = str(cmb_core_model.currentText()).lower().startswith("double")
        except Exception:
            is_doublet = False
        for w in (lbl_split, cb_auto_split, sb_split, lbl_ratio, cb_auto_ratio, sb_ratio, cb_tie_widths):
            try:
                w.setVisible(bool(is_doublet))
            except Exception:
                pass
        # Enable/disable manual fields depending on auto checkboxes
        try:
            sb_split.setEnabled(bool(is_doublet) and (not cb_auto_split.isChecked()))
        except Exception:
            pass
        try:
            sb_ratio.setEnabled(bool(is_doublet) and (not cb_auto_ratio.isChecked()))
        except Exception:
            pass

    def _set_core_model_controls_visible(is_core: bool) -> None:
        # Show the entire second row only for core-level references.  When the
        # selected reference is a Fermi edge, reclaim this vertical space for
        # the reference table/plot.
        try:
            fit_ctrl_row2.setVisible(bool(is_core))
        except Exception:
            pass
        # Show these only for core-level references; hide for Fermi edge.
        for w in (lbl_core_model, cmb_core_model, lbl_split, cb_auto_split, sb_split, lbl_ratio, cb_auto_ratio, sb_ratio, cb_tie_widths):
            try:
                w.setVisible(bool(is_core))
            except Exception:
                pass

        if not is_core:
            try:
                cmb_core_model.setCurrentText("Single peak")
            except Exception:
                pass
        _on_core_model_changed(0)

    # wire signals
    try:
        cmb_core_model.currentIndexChanged.connect(_on_core_model_changed)
        cb_auto_split.toggled.connect(lambda _v: _on_core_model_changed(0))
        cb_auto_ratio.toggled.connect(lambda _v: _on_core_model_changed(0))
    except Exception:
        pass

    # default hidden until a core-level row is selected
    _set_core_model_controls_visible(False)

    fit_btn_lay.addStretch(1)

    fit_layout.addWidget(fit_btn_row, 0)
    fit_layout.addWidget(fit_ctrl_row2, 0)

    fit_table = QTableWidget(tab_fit)
    fit_table.setColumnCount(4)
    fit_table.setHorizontalHeaderLabels(["Reference curve", "Type", "Status", "Measured marker(s)"])
    fit_table.verticalHeader().setVisible(False)
    fit_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    fit_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    # Ensure the fit references list remains scrollable for large numbers of curves.
    try:
        fit_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        fit_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    except Exception:
        pass
    try:
        fit_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        fit_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        fit_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        fit_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    except Exception:
        pass
    # Put table + plot into a vertical splitter (draggable horizontal handle)
    fit_split = QSplitter(Qt.Orientation.Vertical, tab_fit)
    fit_split.addWidget(fit_table)

    # Diagnostic plot: show reference + fit overlay (legend enabled here)
    fit_plot = QWidget(tab_fit)
    fit_plot_lay = QVBoxLayout(fit_plot)
    fit_plot_lay.setContentsMargins(0, 0, 0, 0)
    fit_plot_lay.setSpacing(4)
    try:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as _Nav
        _fig = Figure(figsize=(5, 3), dpi=100)
        _ax = _fig.add_subplot(111)
        _canvas = FigureCanvas(_fig)
        _toolbar = _Nav(_canvas, fit_plot)
        fit_plot_lay.addWidget(_toolbar)
        fit_plot_lay.addWidget(_canvas, 1)
    except Exception:
        _fig = None
        _ax = None
        _canvas = None

    fit_split.addWidget(fit_plot)
    try:
        fit_split.setStretchFactor(0, 1)
        fit_split.setStretchFactor(1, 3)
        # Give plot more space by default
        fit_split.setSizes([150, 750])
    except Exception:
        pass

    fit_layout.addWidget(fit_split, 1)
    tabs.addTab(tab_fit, "Fit references")

    # Local import to avoid loading fit dependencies at app start.
    # We are already inside maxiv_panda.workflows.calibration, so import relatively.
    from .fitters import _voigt_profile, _smooth, _fit_fermi_edge, _fit_core_level
    def _update_fit_table() -> None:
                # Unique references used by mapping.
                ref_keys = []
                for rk in raw_keys:
                    refk = mapping.get(rk)
                    if isinstance(refk, str) and refk:
                        ref_keys.append(refk)
                uniq = []
                seen_r = set()
                for r in ref_keys:
                    if r in seen_r:
                        continue
                    seen_r.add(r)
                    uniq.append(r)

                fit_table.setRowCount(len(uniq))
                for row, refk in enumerate(uniq):
                    disp = refk
                    try:
                        # find display from cand lists
                        if refk in cand_keys:
                            disp = cand_disp[cand_keys.index(refk)]
                    except Exception:
                        pass

                    # Decide type: if any raw mapped to this ref has explicit type, use that.
                    t = "Unknown"
                    for i, rk in enumerate(raw_keys):
                        if mapping.get(rk) == refk:
                            t = ref_types.get(rk, "Unknown")
                            if t != "Unknown":
                                break
                    if t == "Unknown":
                        t = _auto_reference_type(refk, disp)

                    it0 = QTableWidgetItem(disp)
                    it1 = QTableWidgetItem(t)
                    it2 = QTableWidgetItem("Not fit")
                    it3 = QTableWidgetItem("")
                    fit_table.setItem(row, 0, it0)
                    fit_table.setItem(row, 1, it1)
                    fit_table.setItem(row, 2, it2)
                    fit_table.setItem(row, 3, it3)
                    # Store key
                    it0.setData(Qt.ItemDataRole.UserRole, refk)

                    # If already fit, show results.
                    if refk in fit_results:
                        fr = fit_results[refk]
                        q = fr.get("quality") or {}
                        status = str(q.get("status") or "OK")
                        it2.setText(status)
                        r2 = q.get("r2")
                        if fr.get("kind") == "fermi_edge":
                            w = (fr.get("params") or {}).get("w")
                            it3.setText(
                                f"EF = {fr.get('E_meas'):.4f}; w={w:.3f}  R2={r2:.4f}" if r2 is not None and w is not None else f"EF = {fr.get('E_meas'):.4f}"
                            )
                        else:
                            it3.setText(f"Peak = {fr.get('E_meas'):.4f}" + (f"  R2={r2:.4f}" if r2 is not None else ""))
    def _fit_one_reference(refk: str, typ: str) -> tuple[bool, str, dict[str, Any] | None]:
        pl = payload_by_key.get(refk)
        if pl is None:
            return False, "No data", None
        try:
            if typ == "Fermi edge":
                exp = float(sb_expected_ef.value()) if cb_use_expected.isChecked() else None
                if cb_use_window.isChecked():
                    e0 = float(sb_expected_ef.value())
                    d0 = float(sb_de_from.value())
                    d1 = float(sb_de_to.value())
                    x_min = e0 + d0
                    x_max = e0 + d1
                else:
                    x_min = None
                    x_max = None
                fr = _fit_fermi_edge(
                    pl.x,
                    pl.y,
                    expected_ef=exp,
                    energy_scale=getattr(pl, "energy_scale", "Unknown"),
                    x_min=x_min,
                    x_max=x_max,
                )
            else:
                exp_pk = float(sb_expected_ef.value()) if cb_use_expected.isChecked() else None
                if cb_use_window.isChecked():
                    e0 = float(sb_expected_ef.value())
                    d0 = float(sb_de_from.value())
                    d1 = float(sb_de_to.value())
                    x_min = e0 + d0
                    x_max = e0 + d1
                else:
                    x_min = None
                    x_max = None
                # Core-level peak model settings (single vs doublet)
                try:
                    _mdl_txt = str(cmb_core_model.currentText()).strip()
                    _mdl = "doublet" if _mdl_txt.lower().startswith("double") else "single"
                except Exception:
                    _mdl = "single"

                _delta = None
                _ratio = None
                try:
                    if _mdl == "doublet" and (not cb_auto_split.isChecked()):
                        _delta = float(sb_split.value())
                except Exception:
                    _delta = None
                try:
                    if _mdl == "doublet" and (not cb_auto_ratio.isChecked()):
                        _ratio = float(sb_ratio.value())
                except Exception:
                    _ratio = None
                try:
                    _tie = bool(cb_tie_widths.isChecked())
                except Exception:
                    _tie = True

                fr = _fit_core_level(
                    pl.x,
                    pl.y,
                    expected_peak=exp_pk,
                    x_min=x_min,
                    x_max=x_max,
                    model=_mdl,
                    delta_e=_delta,
                    ratio=_ratio,
                    tie_widths=_tie,
                )
            fit_results[refk] = fr
            q = fr.get("quality", {})
            status = q.get("status", "OK")
            return True, status, fr
        except Exception as e:
            return False, str(e), None
    def _fit_all() -> None:
        # Fit all rows shown in table.
        logic.fit_all_references(
            _ax, _canvas,
            fit_table,
            fit_results,
            payload_by_key,
            _fit_one_reference,
            busy_fit,
            btn_fit_all,
            None,
        )
        # A completed multi-reference fit is most useful as an overview.
        # Always show all references and their fits; the former separate
        # "Plot all" button was therefore redundant.
        logic.plot_all_references(_ax, _canvas, fit_table, fit_results, payload_by_key)

    btn_fit_all.clicked.connect(_fit_all)

    def _plot_selected_reference() -> None:
        """Plot the currently selected reference curve and its fit, if available."""
        if _ax is None or _canvas is None:
            return
        try:
            row = fit_table.currentRow()
            if row < 0:
                return
            it0 = fit_table.item(row, 0)
            if it0 is None:
                return
            refk = it0.data(Qt.ItemDataRole.UserRole)
            if not isinstance(refk, str):
                return
            # Use the shared calibration plotting helper.  The old local plotting
            # code accidentally referenced variables from another workflow
            # (fit_list/self), which could abort before draw_idle().
            logic.plot_reference(_ax, _canvas, refk, fit_results, payload_by_key, title=it0.text())
        except Exception:
            pass

    fit_table.currentCellChanged.connect(lambda *_a: _plot_selected_reference())

    def _expected_peak_from_payload(refk: str | None) -> float | None:
        try:
            if not isinstance(refk, str):
                return None
            pl = payload_by_key.get(refk)
            if pl is None:
                return None
            import numpy as _np
            xx = _np.asarray(pl.x, dtype=float)
            yy = _np.asarray(pl.y, dtype=float)
            if xx.size == 0 or yy.size == 0:
                return None
            n = min(xx.size, yy.size)
            xx = xx[:n]
            yy = yy[:n]
            good = _np.isfinite(xx) & _np.isfinite(yy)
            if not _np.any(good):
                return None
            xx = xx[good]
            yy = yy[good]
            if xx.size == 0 or yy.size == 0:
                return None
            return float(xx[int(_np.nanargmax(yy))])
        except Exception:
            return None

    def _first_core_level_reference_key() -> str | None:
        try:
            for _r in range(fit_table.rowCount()):
                _it0 = fit_table.item(_r, 0)
                _it1 = fit_table.item(_r, 1)
                if _it0 is None:
                    continue
                _rk = _it0.data(Qt.ItemDataRole.UserRole)
                _typ = (_it1.text().strip() if _it1 is not None else "")
                if _typ == "Core level" and isinstance(_rk, str) and _rk:
                    return _rk
            return None
        except Exception:
            return None

    def _update_expected_label_for_ref(refk: str | None) -> None:
        try:
            # Prefer actual fit result kind if available; fall back to mapping/type heuristics.
            kind = None
            if isinstance(refk, str):
                fr = fit_results.get(refk)
                if isinstance(fr, dict):
                    kind = fr.get("kind")
            if kind is None and isinstance(refk, str):
                for _r in range(fit_table.rowCount()):
                    _it0 = fit_table.item(_r, 0)
                    if _it0 is None:
                        continue
                    _rk = _it0.data(Qt.ItemDataRole.UserRole)
                    if _rk == refk:
                        _it1 = fit_table.item(_r, 1)
                        if _it1 is not None and _it1.text().strip() == "Fermi edge":
                            kind = "fermi_edge"
                        else:
                            kind = "core_level"
                        break
            if kind == "fermi_edge":
                cb_use_expected.setText("Expected EF")
                cb_use_expected.setToolTip("Optional: use an expected energy (EF for Fermi edge, peak energy for core-level)")
                # For EF, keep a tight and meaningful range around 0.  Use an
                # asymmetric default fit window so valence-band structure just
                # above EF is less likely to bias the Fermi-edge fit.
                sb_expected_ef.setRange(-10.0, 10.0)
                sb_expected_ef.setSingleStep(0.1)
                sb_expected_ef.setValue(0.0)
                sb_de_from.setValue(-1.0)
                sb_de_to.setValue(+0.4)
            else:
                cb_use_expected.setText("Expected E")
                cb_use_expected.setToolTip("Optional: use an expected peak energy for stability/quality checks")
                # Core-level references retain the conventional symmetric default.
                sb_de_from.setValue(-1.0)
                sb_de_to.setValue(+1.0)
                # For core-level peaks, the expected position can be anywhere within the spectrum range.
                pl = payload_by_key.get(refk) if isinstance(refk, str) else None
                if pl is not None:
                    import numpy as _np
                    try:
                        xx = _np.asarray(pl.x, dtype=float)
                        xmin = float(_np.nanmin(xx))
                        xmax = float(_np.nanmax(xx))
                        if _np.isfinite(xmin) and _np.isfinite(xmax) and xmax > xmin:
                            pad = 0.02 * (xmax - xmin)
                            sb_expected_ef.setRange(xmin - pad, xmax + pad)
                            sb_expected_ef.setSingleStep(max(0.1, 0.005 * (xmax - xmin)))
                    except Exception:
                        sb_expected_ef.setRange(-1e6, 1e6)
                        sb_expected_ef.setSingleStep(1.0)
                else:
                    sb_expected_ef.setRange(-1e6, 1e6)
                    sb_expected_ef.setSingleStep(1.0)
                # Single shared field: default to the maximum of the first core-level
                # reference shown in the list.
                _core_refk = _first_core_level_reference_key()
                _exp_pk = _expected_peak_from_payload(_core_refk)
                if _exp_pk is not None:
                    sb_expected_ef.setValue(float(_exp_pk))

            # Show/hide core-level model controls depending on the selected reference type.
            try:
                is_core = True
                if kind == "fermi_edge":
                    is_core = False
                else:
                    # fall back to the "Type" column in the fit table if available
                    if isinstance(refk, str):
                        for _r in range(fit_table.rowCount()):
                            _it0 = fit_table.item(_r, 0)
                            if _it0 is None:
                                continue
                            _rk = _it0.data(Qt.ItemDataRole.UserRole)
                            if _rk == refk:
                                _it1 = fit_table.item(_r, 1)
                                if _it1 is not None and _it1.text().strip() == "Fermi edge":
                                    is_core = False
                                break
                _set_core_model_controls_visible(is_core)
            except Exception:
                pass
        except Exception:
            pass

    def _on_fit_row_changed() -> None:
        try:
            row = fit_table.currentRow()
            if row < 0:
                _update_expected_label_for_ref(None)
                return
            it0 = fit_table.item(row, 0)
            if it0 is None:
                _update_expected_label_for_ref(None)
                return
            refk = it0.data(Qt.ItemDataRole.UserRole)
            _update_expected_label_for_ref(refk if isinstance(refk, str) else None)
        except Exception:
            pass

    fit_table.currentCellChanged.connect(lambda *_a: _on_fit_row_changed())


    def _on_tab_changed(ix: int) -> None:
        try:
            tab_name = tabs.tabText(ix)
            if tab_name == "Fit references":
                _update_fit_table()
                # Make the tab immediately useful after pressing Next: select the
                # first reference and draw the references without requiring a model
                # combobox change or a manual row click.
                try:
                    if fit_table.rowCount() > 0 and fit_table.currentRow() < 0:
                        fit_table.selectRow(0)
                except Exception:
                    pass
                try:
                    _on_fit_row_changed()
                except Exception:
                    pass
                try:
                    logic.plot_all_references(_ax, _canvas, fit_table, fit_results, payload_by_key)
                except Exception:
                    pass
            elif tab_name == "Targets & shifts":
                _build_targets_table()
        except Exception:
            pass

    tabs.currentChanged.connect(_on_tab_changed)

    # --- Tab: Targets & shifts
    tab_targets = QWidget(tabs)
    targets_layout = QVBoxLayout(tab_targets)
    targets_layout.setContentsMargins(0, 0, 0, 0)
    targets_layout.setSpacing(8)

    targets_help = QLabel(tab_targets)
    _style_help_label(
        targets_help,
        "Finally: review Measured E, enter Target E (default 0 eV for Fermi edge), and Confirm targets.\n"
        "Press Apply to create calibrated copies of the selected curves.",
    )
    targets_layout.addWidget(targets_help, 0)

    targets_table = QTableWidget(tab_targets)
    targets_table.setColumnCount(6)
    targets_table.setHorizontalHeaderLabels(
        [
            "Curve to calibrate",
            "Reference curve",
            "Ref type",
            "Measured E",
            "Target E",
            "Shift",
        ]
    )
    targets_table.verticalHeader().setVisible(False)
    targets_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    targets_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    try:
        targets_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        targets_table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    except Exception:
        pass
    try:
        targets_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        targets_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        targets_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        targets_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        targets_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        targets_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    except Exception:
        pass
    targets_layout.addWidget(targets_table, 1)

    # Store targets/shifts for later tabs.
    targets_by_raw: dict[str, float] = {}
    shifts_by_raw: dict[str, float] = {}
    targets_confirmed = {"value": False}

    targets_btn_row = QWidget(tab_targets)
    targets_btn_lay = QHBoxLayout(targets_btn_row)
    targets_btn_lay.setContentsMargins(0, 0, 0, 0)
    targets_btn_lay.setSpacing(8)

    lbl_confirm = QLabel("Targets not confirmed", targets_btn_row)
    targets_btn_lay.addWidget(lbl_confirm)
    targets_btn_lay.addStretch(1)
    btn_confirm_targets = QPushButton("Confirm targets", targets_btn_row)
    btn_confirm_targets.setToolTip("Validate and lock target values")
    targets_btn_lay.addWidget(btn_confirm_targets)
    btn_unlock_targets = QPushButton("Unlock", targets_btn_row)
    btn_unlock_targets.setToolTip("Allow editing target values again")
    btn_unlock_targets.setEnabled(False)
    targets_btn_lay.addWidget(btn_unlock_targets)

    btn_apply = QPushButton("Apply", targets_btn_row)
    btn_apply.setToolTip("Apply energy shifts to the currently selected curves and close this dialog")
    btn_apply.setEnabled(False)
    targets_btn_lay.addWidget(btn_apply)
    targets_layout.addWidget(targets_btn_row, 0)

    def _format_num(v: Any) -> str:
        try:
            if v is None:
                return ""
            fv = float(v)
            if not np.isfinite(fv):
                return ""
            return f"{fv:.4f}"
        except Exception:
            return ""

    def _resolve_fit_ref_key(ref_key: str) -> str | None:
        """Resolve ref key robustly (exact, stripped, case-insensitive) for fit_results lookup."""
        if not isinstance(ref_key, str) or not ref_key:
            return None
        if ref_key in fit_results:
            return ref_key
        rk = ref_key.strip()
        if rk in fit_results:
            return rk
        # Case-insensitive match
        rkl = rk.casefold()
        for k in fit_results.keys():
            try:
                if isinstance(k, str) and k.strip().casefold() == rkl:
                    return k
            except Exception:
                continue
        return None

    def _measured_energy_for_ref(ref_key: str) -> float | None:
        resolved = _resolve_fit_ref_key(ref_key)
        if resolved is None:
            return None
        fr = fit_results.get(resolved)
        if not isinstance(fr, dict):
            return None
        try:
            ev = fr.get("E_meas")
            if ev is None:
                return None
            evf = float(ev)
            if np.isfinite(evf):
                kind = fr.get("kind")
                marker = fr.get("marker")
                return evf
            return None
        except Exception as exc:
            return None
    def _ref_type_for_raw(raw_key: str) -> str:
        # Use user mapping type, falling back to auto heuristic.
        t = (ref_types.get(raw_key) or "Unknown").strip()
        if t == "Unknown":
            refk = mapping.get(raw_key, "")
            disp = ""
            try:
                disp = cand_disp[cand_keys.index(refk)] if refk in cand_keys else ""
            except Exception:
                disp = ""
            return _auto_reference_type(refk, disp)
        return t

    def _update_shift_row(row: int) -> None:
        """Recompute shift cell for a given row."""
        try:
            raw_key = raw_keys[row]
            ref_key = mapping.get(raw_key, "")
            meas = _measured_energy_for_ref(ref_key)
            sb: QDoubleSpinBox = targets_table.cellWidget(row, 4)  # type: ignore
            target = float(sb.value())
            if meas is None:
                shift_txt = ""
            else:
                shift = target - float(meas)
                shift_txt = f"{shift:.4f}"
                shifts_by_raw[raw_key] = shift
                targets_by_raw[raw_key] = target
            targets_table.item(row, 5).setText(shift_txt)
        except Exception:
            pass

    def _build_targets_table() -> None:
        targets_confirmed["value"] = False
        lbl_confirm.setText("Targets not confirmed")
        btn_unlock_targets.setEnabled(False)
        try:
            btn_confirm_targets.setEnabled(True)
        except Exception:
            pass
        targets_table.setRowCount(len(raw_keys))
        shifts_by_raw.clear()
        targets_by_raw.clear()

        for r, (rk, rl) in enumerate(zip(raw_keys, raw_labels)):
            refk = mapping.get(rk, "")
            # Reference display
            ref_disp = ""
            try:
                if refk in cand_keys:
                    ref_disp = cand_disp[cand_keys.index(refk)]
                else:
                    ref_disp = refk
            except Exception:
                ref_disp = refk

            # Ref type
            rtype = _ref_type_for_raw(rk)
            meas = _measured_energy_for_ref(refk)

            targets_table.setItem(r, 0, QTableWidgetItem(rl))
            targets_table.setItem(r, 1, QTableWidgetItem(ref_disp))
            targets_table.setItem(r, 2, QTableWidgetItem(rtype))
            targets_table.setItem(r, 3, QTableWidgetItem(_format_num(meas)))

            sb_target = QDoubleSpinBox(targets_table)
            sb_target.setDecimals(4)
            sb_target.setRange(-1e6, 1e6)
            sb_target.setSingleStep(0.1)
            # Defaults: EF target is 0.0; otherwise default to measured (=> shift 0) if available.
            if rtype == "Fermi edge":
                sb_target.setValue(0.0)
            elif meas is not None:
                sb_target.setValue(float(meas))
            else:
                sb_target.setValue(0.0)
            sb_target.valueChanged.connect(lambda _v, row=r: _update_shift_row(row))
            targets_table.setCellWidget(r, 4, sb_target)

            targets_table.setItem(r, 5, QTableWidgetItem(""))
            _update_shift_row(r)

    def _confirm_targets() -> None:
        # Validate: measured must exist for each row, and target is present.
        bad_rows: list[int] = []
        for r in range(targets_table.rowCount()):
            rk = raw_keys[r]
            refk = mapping.get(rk, "")
            meas = _measured_energy_for_ref(refk)
            if meas is None:
                bad_rows.append(r)
        if bad_rows:
            QMessageBox.warning(
                dlg,
                "Confirm targets",
                "Some rows have no measured reference energy yet.\n"
                "Go to 'Fit references' and fit the reference curves first.",
            )
            return
        # Lock target fields
        for r in range(targets_table.rowCount()):
            try:
                sb: QDoubleSpinBox = targets_table.cellWidget(r, 4)  # type: ignore
                sb.setEnabled(False)
            except Exception:
                pass
        targets_confirmed["value"] = True
        lbl_confirm.setText("Targets confirmed")
        btn_confirm_targets.setEnabled(False)
        btn_unlock_targets.setEnabled(True)
        try:
            btn_apply.setEnabled(True)
        except Exception:
            pass

    def _unlock_targets() -> None:
        for r in range(targets_table.rowCount()):
            try:
                sb: QDoubleSpinBox = targets_table.cellWidget(r, 4)  # type: ignore
                sb.setEnabled(True)
            except Exception:
                pass
        targets_confirmed["value"] = False
        lbl_confirm.setText("Targets not confirmed")
        btn_confirm_targets.setEnabled(True)
        btn_unlock_targets.setEnabled(False)
        try:
            btn_apply.setEnabled(False)
        except Exception:
            pass

    def _apply_calibration_and_close() -> None:
        applied = logic.apply_calibration(
            dlg=dlg,
            raw_keys=list(raw_keys),
            shifts_by_raw=shifts_by_raw,
            targets_by_raw=targets_by_raw,
            mapping=mapping,
            measured_energy_for_ref=_measured_energy_for_ref,
            ref_type_for_raw=_ref_type_for_raw,
            targets_confirmed=targets_confirmed,
            btn_e_cal_toggle=getattr(mw, 'btn_e_cal_toggle', None),
            update_selected_tree_visibility=getattr(mw, '_update_selected_tree_visibility', None),
            update_plot_from_selected=getattr(mw, '_update_plot_from_selected', None),
            payload_by_key=payload_by_key,
        )
        if applied > 0:
            dlg.accept()

    btn_confirm_targets.clicked.connect(_confirm_targets)
    btn_unlock_targets.clicked.connect(_unlock_targets)
    btn_apply.clicked.connect(_apply_calibration_and_close)

    targets_layout.addWidget(targets_btn_row, 0)
    tabs.addTab(tab_targets, "Targets & shifts")

    # When entering the Fit references tab, auto-enable "Expected EF" if any curve is mapped as a Fermi-edge reference.
    expected_user_set: bool = False

    def _mark_expected_user_set() -> None:
        nonlocal expected_user_set
        expected_user_set = True

    try:
        cb_use_expected.clicked.connect(_mark_expected_user_set)
    except Exception:
        pass

    def _has_any_fermi_reference() -> bool:
        try:
            for rk in raw_keys:
                refk = mapping.get(rk, "")
                disp = ""
                if isinstance(refk, str) and refk in cand_keys:
                    disp = cand_disp[cand_keys.index(refk)]
                t = ref_types.get(rk, "Unknown")
                if t == "Fermi edge":
                    return True
                if t == "Unknown":
                    guessed = _guess_default_ref_type(disp)
                    if guessed == "Fermi edge":
                        return True
            return False
        except Exception:
            return False

    def _on_calib_tab_changed(_idx: int) -> None:
        # Fit references tab index is 1.
        if _idx != 1:
            return
        try:
            if expected_user_set:
                return
            want = _has_any_fermi_reference()
            cb_use_expected.blockSignals(True)
            try:
                cb_use_expected.setChecked(bool(want))
                sb_expected_ef.setEnabled(bool(want))
            finally:
                cb_use_expected.blockSignals(False)
            # Update label based on current selection.
            _on_fit_row_changed()
        except Exception:
            pass

    tabs.currentChanged.connect(_on_calib_tab_changed)

    # Buttons (Close + Next for guidance on the first tabs)
    btn_row = QWidget(dlg)
    btn_layout = QHBoxLayout(btn_row)
    btn_layout.setContentsMargins(0, 0, 0, 0)
    btn_layout.setSpacing(8)
    btn_layout.addStretch(1)

    btn_next = QPushButton("Next", btn_row)

    def _go_next_tab() -> None:
        try:
            idx = tabs.currentIndex()
            if idx < tabs.count() - 1:
                tabs.setCurrentIndex(idx + 1)
        except Exception:
            pass

    btn_next.clicked.connect(_go_next_tab)
    btn_layout.addWidget(btn_next)

    btn_close = QPushButton("Cancel", btn_row)
    btn_close.clicked.connect(dlg.reject)
    btn_layout.addWidget(btn_close)
    layout.addWidget(btn_row, 0)

    def _update_next_button_visibility(_idx: int) -> None:
        try:
            btn_next.setVisible(_idx in (0, 1))
        except Exception:
            pass

    tabs.currentChanged.connect(_update_next_button_visibility)
    _update_next_button_visibility(tabs.currentIndex())

    try:
        # Start ~15% taller than the natural size to improve readability (without changing width policy).
        sh = dlg.sizeHint()
        dlg.resize(sh.width(), int(sh.height() * 1.265))
    except Exception:
        pass


    dlg.exec()

    # --------------------------
    # Group loading: averages by region
    # --------------------------
