from __future__ import annotations

from typing import Callable, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout,
    QGroupBox, QHeaderView, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy,
    QStyledItemDelegate, QStyleOptionViewItem, QTableWidget, QTableWidgetItem, QWidget
)
from PyQt6.QtGui import QPainter, QPen

from .fit_plotting import default_peak_color


class PairSeparatorDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        super().paint(painter, option, index)
        row = index.row()
        if row % 2 == 1:
            pen = QPen(option.palette.mid().color())
            pen.setWidth(1)
            painter.save()
            painter.setPen(pen)
            painter.drawLine(option.rect.bottomLeft(), option.rect.bottomRight())
            painter.restore()


def create_results_table(parent: QWidget, headers: Optional[list[str]], pair_separator: bool = False) -> QTableWidget:
    tbl = QTableWidget(parent)
    tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    tbl.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    tbl.setShowGrid(False)
    if pair_separator:
        tbl.setItemDelegate(PairSeparatorDelegate(tbl))
    try:
        vh = tbl.verticalHeader()
        vh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vh.setDefaultSectionSize(26)
    except Exception:
        pass
    if headers is not None:
        tbl.setColumnCount(len(headers))
        tbl.setHorizontalHeaderLabels(headers)
    try:
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    except Exception:
        pass
    try:
        tbl.setStyleSheet(
            "QTableWidget { background: palette(base); color: palette(text); "
            "alternate-background-color: palette(alternate-base); gridline-color: palette(mid); }"
            "QHeaderView::section { background: palette(button); color: palette(button-text); }"
        )
    except Exception:
        pass
    return tbl


def create_fit_quality_box(parent: QWidget) -> dict:
    lbl_fit_status = QLabel("Status: —", parent)
    lbl_fit_rss = QLabel("RSS: —", parent)
    lbl_fit_rms = QLabel("RMS: —", parent)
    lbl_fit_redchi = QLabel("Reduced χ²: —", parent)

    lbl_fit_rss.setToolTip(
        "RSS = Residual Sum of Squares = Σ(data - fit)^2 over all fitted points.\n"
        "Smaller values indicate a closer fit for the same spectrum."
    )
    lbl_fit_rms.setToolTip(
        "RMS = root-mean-square residual = sqrt(mean((data - fit)^2)).\n"
        "It has the same units as the y-axis signal."
    )
    lbl_fit_redchi.setToolTip(
        "Reduced χ² = Σ(((data - fit)/σ)^2) / (N - p), assuming Poisson statistics with σ = sqrt(max(data, 1)).\n"
        "Here N is the number of fitted points and p is the number of free parameters."
    )
    lbl_fit_status.setToolTip("Overall fit status reported by the current fitting workflow.")

    fit_quality_box = QGroupBox("Fit quality", parent)
    fit_quality_lay = QFormLayout(fit_quality_box)
    fit_quality_lay.setContentsMargins(6, 6, 6, 6)
    lab_fit_status = QLabel("Status:", fit_quality_box)
    lab_fit_rss = QLabel("RSS:", fit_quality_box)
    lab_fit_rms = QLabel("RMS:", fit_quality_box)
    lab_fit_redchi = QLabel("Reduced χ²:", fit_quality_box)
    lab_fit_status.setToolTip(lbl_fit_status.toolTip())
    lab_fit_rss.setToolTip(lbl_fit_rss.toolTip())
    lab_fit_rms.setToolTip(lbl_fit_rms.toolTip())
    lab_fit_redchi.setToolTip(lbl_fit_redchi.toolTip())
    fit_quality_lay.addRow(lab_fit_status, lbl_fit_status)
    fit_quality_lay.addRow(lab_fit_rss, lbl_fit_rss)
    fit_quality_lay.addRow(lab_fit_rms, lbl_fit_rms)
    fit_quality_lay.addRow(lab_fit_redchi, lbl_fit_redchi)
    return {
        "group": fit_quality_box,
        "lab_fit_status": lab_fit_status,
        "lab_fit_rss": lab_fit_rss,
        "lab_fit_rms": lab_fit_rms,
        "lab_fit_redchi": lab_fit_redchi,
        "lbl_fit_status": lbl_fit_status,
        "lbl_fit_rss": lbl_fit_rss,
        "lbl_fit_rms": lbl_fit_rms,
        "lbl_fit_redchi": lbl_fit_redchi,
    }


def make_plain_table_item(text: str = "") -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    return item


def sync_results_tables_structure(tbl_fit_results: QTableWidget, tbl_bg_results: QTableWidget, n_peaks: int, bg_type: str) -> None:
    n_peaks = max(0, int(n_peaks))
    tbl_fit_results.clearContents()
    tbl_fit_results.setRowCount(n_peaks * 2)
    headers = []
    for i in range(n_peaks):
        headers.extend([f"Peak {i+1}", ""])
    tbl_fit_results.setVerticalHeaderLabels(headers)
    for r in range(n_peaks):
        value_row = 2 * r
        constr_row = value_row + 1
        for c in range(tbl_fit_results.columnCount()):
            tbl_fit_results.setItem(value_row, c, make_plain_table_item(""))
            tbl_fit_results.setItem(constr_row, c, make_plain_table_item(""))
    bg_cols = {
        'constant': ['b0'],
        'linear': ['b0', 'b1'],
        'parabolic': ['b0', 'b1', 'b2'],
        'Shirley': ['α'],
    }.get(bg_type, ['value'])
    tbl_bg_results.clear()
    tbl_bg_results.setRowCount(2)
    tbl_bg_results.setColumnCount(len(bg_cols))
    tbl_bg_results.setVerticalHeaderLabels(['Background', ''])
    tbl_bg_results.setHorizontalHeaderLabels(bg_cols)
    for r in range(2):
        for c in range(len(bg_cols)):
            tbl_bg_results.setItem(r, c, make_plain_table_item(""))
    for r in range(tbl_fit_results.rowCount()):
        tbl_fit_results.setRowHeight(r, 26)
    for r in range(tbl_bg_results.rowCount()):
        tbl_bg_results.setRowHeight(r, 26)


def _mk_lim_sb(owner: QWidget, v: float, hard_min: float, hard_max: float, decimals: int) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setDecimals(decimals)
    sb.setRange(hard_min, hard_max)
    sb.setValue(v)
    sb.setKeyboardTracking(False)
    sb.setAccelerated(True)
    sb.setMaximumWidth(90)
    sb.installEventFilter(owner)
    try:
        sb.lineEdit().installEventFilter(owner)
    except Exception:
        pass
    return sb


def _mk_val_sb(owner: QWidget, decimals: int, step: float, hard_min: float, hard_max: float, default: float) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setDecimals(decimals)
    sb.setSingleStep(step)
    sb.setRange(hard_min, hard_max)
    sb.setValue(default)
    sb.setKeyboardTracking(False)
    sb.setAccelerated(True)
    sb.installEventFilter(owner)
    try:
        sb.lineEdit().installEventFilter(owner)
    except Exception:
        pass
    return sb


def _add_param_row(grid: QGridLayout, row: int, label: str, sb_val: QDoubleSpinBox, sb_min: QDoubleSpinBox, sb_max: QDoubleSpinBox, cb_mode: QComboBox):
    lab = QLabel(label)
    lab.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    grid.addWidget(lab, row, 0)
    grid.addWidget(sb_val, row, 1)
    grid.addWidget(sb_min, row, 2)
    grid.addWidget(sb_max, row, 3)
    grid.addWidget(cb_mode, row, 4)
    return lab


def _wire_limits(sbmin: QDoubleSpinBox, sbval: QDoubleSpinBox, sbmax: QDoubleSpinBox) -> None:
    def _apply():
        vmin = float(sbmin.value())
        vmax = float(sbmax.value())
        hbmin = sbmin.property("hard_min")
        hbmax = sbmax.property("hard_max")
        hbmin = float(hbmin) if hbmin is not None else float(sbmin.minimum())
        hbmax = float(hbmax) if hbmax is not None else float(sbmax.maximum())
        if vmin < hbmin:
            vmin = hbmin
        if vmax > hbmax:
            vmax = hbmax
        if vmin > vmax:
            vmin, vmax = hbmin, hbmax
        sbmin.blockSignals(True)
        sbmax.blockSignals(True)
        sbmin.setValue(vmin)
        sbmax.setValue(vmax)
        sbmin.blockSignals(False)
        sbmax.blockSignals(False)
        sbval.setRange(vmin, vmax)
        if sbval.value() < vmin:
            sbval.setValue(vmin)
        if sbval.value() > vmax:
            sbval.setValue(vmax)
    sbmin.valueChanged.connect(lambda _=0: _apply())
    sbmax.valueChanged.connect(lambda _=0: _apply())
    _apply()


def create_peak_group(peak_index: int, n_target: int, owner: QWidget, *,
                      on_delete: Callable[[int], None],
                      on_pick_color: Callable[[int], None],
                      set_constraint_items: Callable[[QComboBox, str, int, str], None],
                      on_refresh_peak_markers: Callable[[], None],
                      on_refresh_all_tied: Callable[[], None],
                      on_refresh_live: Callable[[], None],
                      on_constraint_mode_changed: Callable[[str, int], None]) -> dict:
    i = peak_index
    gb = QGroupBox("")
    gb.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    grid = QGridLayout(gb)
    grid.setContentsMargins(5, 4, 5, 4)
    grid.setHorizontalSpacing(5)
    grid.setVerticalSpacing(2)
    grid.setColumnStretch(0, 0)
    grid.setColumnStretch(1, 0)
    grid.setColumnStretch(2, 1)
    grid.setColumnStretch(3, 0)
    grid.setColumnStretch(4, 0)

    title_lab = QLabel(f"Peak {i}")
    try:
        title_lab.setStyleSheet("QLabel { font-weight: bold; }")
    except Exception:
        pass
    btn_color = QPushButton("")
    btn_color.setFixedSize(16, 16)
    btn_color.setToolTip(f"Choose color for Peak {i}")
    btn_color.setProperty("peak_index", i)
    color = default_peak_color(i)
    btn_color.setStyleSheet(f"QPushButton {{ background-color: {color}; border: 1px solid #555; }}")
    btn_color.clicked.connect(lambda _=False, btn=btn_color: on_pick_color(int(btn.property("peak_index"))))

    btn_delete_peak = QPushButton("Delete")
    btn_delete_peak.setProperty("peak_index", i)
    btn_delete_peak.setEnabled(n_target > 1)
    btn_delete_peak.clicked.connect(lambda _=False, btn=btn_delete_peak: on_delete(int(btn.property("peak_index"))))
    header = QWidget(gb)
    header_lay = QHBoxLayout(header)
    header_lay.setContentsMargins(0, 0, 0, 0)
    header_lay.setSpacing(4)
    label_lab = QLabel("Label:", header)
    label_edit = QLineEdit(f"P{i}", header)
    label_edit.setToolTip(
        "Optional peak identity label. Used later to match chemically equivalent peaks "
        "between anchor fits and batch fits. Ordinary single-curve fitting can ignore it."
    )
    label_edit.setMaxLength(48)
    label_edit.setProperty("peak_label_edit", True)
    label_edit.installEventFilter(owner)
    label_edit.setMinimumWidth(55)
    label_edit.setMaximumWidth(95)
    label_edit.setPlaceholderText(f"P{i}")

    header_lay.addWidget(title_lab)
    header_lay.addWidget(btn_color)
    header_lay.addSpacing(8)
    header_lay.addWidget(label_lab)
    header_lay.addWidget(label_edit)
    header_lay.addStretch(1)
    header_lay.addWidget(btn_delete_peak)
    grid.addWidget(header, 0, 0, 1, 5)

    hdr_val = QLabel("value")
    hdr_min = QLabel("min")
    hdr_max = QLabel("max")
    hdr_min.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hdr_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hdr_max.setAlignment(Qt.AlignmentFlag.AlignCenter)
    grid.addWidget(QLabel(""), 1, 0)
    grid.addWidget(hdr_val, 1, 1)
    grid.addWidget(hdr_min, 1, 2)
    grid.addWidget(hdr_max, 1, 3)
    grid.addWidget(QLabel(""), 1, 4)

    e_hard_min, e_hard_max = -1e9, 1e9
    h_hard_min, h_hard_max = 0.0, 1e12
    l_hard_min, l_hard_max = 0.05, 1.0
    g_hard_min, g_hard_max = 0.05, 2.0
    a_hard_min, a_hard_max = 0.0, 0.2

    sb_E_min = _mk_lim_sb(owner, 0.0, e_hard_min, e_hard_max, decimals=3)
    sb_E = _mk_val_sb(owner, 3, 0.05, e_hard_min, e_hard_max, 0.0)
    sb_E_max = _mk_lim_sb(owner, 0.0, e_hard_min, e_hard_max, decimals=3)
    sb_E_min.setProperty("hard_min", e_hard_min); sb_E_max.setProperty("hard_max", e_hard_max)

    sb_H_min = _mk_lim_sb(owner, 0.0, 0.0, 1.0, decimals=3)
    sb_H = _mk_val_sb(owner, 3, 0.1, 0.0, 1.0, 0.0)
    sb_H_max = _mk_lim_sb(owner, 1.0, 0.0, 1.0, decimals=3)

    # Energy and Height directly drive the interactive model preview.  Track
    # keyboard edits continuously so component/sum/residual curves respond while
    # the user types, not only after focus leaves the spin box.
    sb_E.setKeyboardTracking(True)
    sb_H.setKeyboardTracking(True)
    sb_H_min.setProperty("hard_min", 0.0); sb_H_max.setProperty("hard_max", 1.0)

    sb_L_min = _mk_lim_sb(owner, l_hard_min, l_hard_min, l_hard_max, decimals=3)
    sb_L = _mk_val_sb(owner, 3, 0.05, l_hard_min, l_hard_max, 0.2)
    sb_L_max = _mk_lim_sb(owner, l_hard_max, l_hard_min, l_hard_max, decimals=3)
    sb_L_min.setProperty("hard_min", l_hard_min); sb_L_max.setProperty("hard_max", l_hard_max)

    sb_G_min = _mk_lim_sb(owner, g_hard_min, g_hard_min, g_hard_max, decimals=3)
    sb_G = _mk_val_sb(owner, 3, 0.05, g_hard_min, g_hard_max, 0.3)
    sb_G_max = _mk_lim_sb(owner, g_hard_max, g_hard_min, g_hard_max, decimals=3)
    sb_G_min.setProperty("hard_min", g_hard_min); sb_G_max.setProperty("hard_max", g_hard_max)

    sb_A_min = _mk_lim_sb(owner, a_hard_min, a_hard_min, a_hard_max, decimals=3)
    sb_A = _mk_val_sb(owner, 3, 0.01, a_hard_min, a_hard_max, 0.0)
    sb_A_max = _mk_lim_sb(owner, a_hard_max, a_hard_min, a_hard_max, decimals=3)
    sb_A_min.setProperty("hard_min", a_hard_min); sb_A_max.setProperty("hard_max", a_hard_max)

    cb_E = QComboBox(); cb_H = QComboBox(); cb_L = QComboBox(); cb_G = QComboBox(); cb_A = QComboBox()
    for cb in (cb_E, cb_H, cb_L, cb_G, cb_A):
        cb.setMinimumContentsLength(12)
        cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

    _wire_limits(sb_E_min, sb_E, sb_E_max)
    _wire_limits(sb_H_min, sb_H, sb_H_max)
    _wire_limits(sb_L_min, sb_L, sb_L_max)
    _wire_limits(sb_G_min, sb_G, sb_G_max)
    _wire_limits(sb_A_min, sb_A, sb_A_max)

    lab_E = _add_param_row(grid, 2, f"Energy_{i}", sb_E, sb_E_min, sb_E_max, cb_E)
    lab_H = _add_param_row(grid, 3, f"Height_{i}", sb_H, sb_H_min, sb_H_max, cb_H)
    lab_L = _add_param_row(grid, 4, f"LFWHM_{i}", sb_L, sb_L_min, sb_L_max, cb_L)
    lab_G = _add_param_row(grid, 5, f"GFWHM_{i}", sb_G, sb_G_min, sb_G_max, cb_G)
    lab_A = _add_param_row(grid, 6, f"Alpha_{i}", sb_A, sb_A_min, sb_A_max, cb_A)

    set_constraint_items(cb_E, "E", i, preserve_text="Free")
    set_constraint_items(cb_H, "H", i, preserve_text="Free")
    set_constraint_items(cb_L, "L", i, preserve_text="Free")
    set_constraint_items(cb_G, "G", i, preserve_text="Free")
    set_constraint_items(cb_A, "A", i, preserve_text="Free")

    lab_L.setToolTip("Lorentzian FWHM; mainly the lifetime-broadening contribution to the line shape.")
    lab_G.setToolTip("Gaussian FWHM; mainly instrumental and inhomogeneous broadening contributions.")
    lab_A.setToolTip("Peak asymmetry parameter.")
    constraint_tip = "Free fits this parameter; Fixed holds it constant; Tied links it to the corresponding parameter of another peak."
    for _cb in (cb_E, cb_H, cb_L, cb_G, cb_A):
        _cb.setToolTip(constraint_tip)

    sb_E.valueChanged.connect(lambda _=0: on_refresh_peak_markers())
    sb_H.valueChanged.connect(lambda _=0: on_refresh_peak_markers())
    for _sb in (sb_E, sb_H, sb_L, sb_G, sb_A, sb_E_min, sb_E_max, sb_H_min, sb_H_max, sb_L_min, sb_L_max, sb_G_min, sb_G_max, sb_A_min, sb_A_max):
        _sb.valueChanged.connect(lambda _=0: on_refresh_all_tied())
        _sb.valueChanged.connect(lambda _=0: on_refresh_live())
    cb_E.currentTextChanged.connect(lambda _=None, idx=i: on_constraint_mode_changed("E", idx))
    cb_H.currentTextChanged.connect(lambda _=None, idx=i: on_constraint_mode_changed("H", idx))
    cb_L.currentTextChanged.connect(lambda _=None, idx=i: on_constraint_mode_changed("L", idx))
    cb_G.currentTextChanged.connect(lambda _=None, idx=i: on_constraint_mode_changed("G", idx))
    cb_A.currentTextChanged.connect(lambda _=None, idx=i: on_constraint_mode_changed("A", idx))
    # Peak labels are also the fitting-plot legend labels; refresh the live
    # calculated curves so renaming a peak is reflected immediately.
    label_edit.textChanged.connect(lambda _text="": on_refresh_live())

    return {
        "group": gb,
        "title_label": title_lab,
        "label_edit": label_edit,
        "color_btn": btn_color,
        "color": color,
        "delete_btn": btn_delete_peak,
        "E_label": lab_E, "H_label": lab_H, "L_label": lab_L, "G_label": lab_G, "A_label": lab_A,
        "E_min": sb_E_min, "E": sb_E, "E_max": sb_E_max, "E_mode": cb_E, "E_tie": None,
        "H_min": sb_H_min, "H": sb_H, "H_max": sb_H_max, "H_mode": cb_H, "H_tie": None,
        "L_min": sb_L_min, "L": sb_L, "L_max": sb_L_max, "L_mode": cb_L, "L_tie": None,
        "G_min": sb_G_min, "G": sb_G, "G_max": sb_G_max, "G_mode": cb_G, "G_tie": None,
        "A_min": sb_A_min, "A": sb_A, "A_max": sb_A_max, "A_mode": cb_A, "A_tie": None,
    }



def create_so_doublet_group(state: dict, owner: QWidget, *, on_changed: Callable[[], None], on_ungroup: Callable[[int], None], on_clone: Callable[[int], None], tie_options=None) -> dict:
    """Create the compact relationship editor for one spin-orbit doublet.

    The two constituent peaks remain ordinary peak editors underneath; this
    panel owns only the physical relations between them.
    """
    from .so_doublets import normalize_state, statistical_ratio
    s = normalize_state(state, ordinal=int(state.get("id", 1) or 1))
    gb = QGroupBox("")
    gb.setProperty("so_doublet_group", True)
    grid = QGridLayout(gb)
    grid.setContentsMargins(5, 4, 5, 4)
    grid.setHorizontalSpacing(5)
    grid.setVerticalSpacing(2)

    title = QLabel(f"SO doublet {s['id']}", gb)
    title.setStyleSheet("QLabel { font-weight: bold; }")
    label_lab = QLabel("Label:", gb)
    label_edit = QLineEdit(s["label"], gb)
    label_edit.setMaximumWidth(110)
    label_edit.setToolTip(
        "This label identifies the same SO-doublet component across batch anchors. "
        "Keep the same label if the component shifts or changes intensity; use a new label only for a different component."
    )
    orbital_lab = QLabel("Type:", gb)
    orbital = QComboBox(gb)
    orbital.addItems(["p", "d", "f", "Custom"])
    orbital.setCurrentText(s["orbital"])
    orbital.setToolTip("Orbital type supplies the statistical intensity-ratio starting value only; all values remain editable.")
    btn_clone = QPushButton("Clone", gb)
    btn_clone.setToolTip("Clone this doublet")
    btn_clone.clicked.connect(lambda _=False, did=s["id"]: on_clone(int(did)))
    btn_ungroup = QPushButton("Ungroup", gb)
    btn_ungroup.setToolTip("Convert this doublet back to two independent peaks.")
    btn_ungroup.clicked.connect(lambda _=False, did=s["id"]: on_ungroup(int(did)))

    component_tip = f"Major component: P{int(s['major'])}; minor component: P{int(s['minor'])}."
    title.setToolTip(component_tip)

    header = QWidget(gb)
    hl = QHBoxLayout(header)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(4)
    hl.addWidget(title); hl.addSpacing(4); hl.addWidget(label_lab); hl.addWidget(label_edit)
    hl.addSpacing(4); hl.addWidget(orbital_lab); hl.addWidget(orbital); hl.addStretch(1); hl.addWidget(btn_clone); hl.addWidget(btn_ungroup)
    grid.addWidget(header, 0, 0, 1, 5)

    for col, txt in enumerate(("", "value", "min", "max", "mode")):
        lab = QLabel(txt, gb)
        if col:
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(lab, 1, col)

    tie_options = list(tie_options or [])

    def _make_doublet_mode_combo(param_key: str):
        cb = QComboBox(gb)
        cb.addItem("Fixed", ("Fixed", None))
        cb.addItem("Free", ("Free", None))
        for opt in tie_options:
            try:
                target_id = int(opt.get("id"))
            except Exception:
                continue
            if target_id == int(s["id"]):
                continue
            label = str(opt.get("label") or f"SO doublet {target_id}")
            cb.addItem(f"Tied to {label}", ("Tied", target_id))
        desired_mode = str(s.get(f"{param_key}_mode", "Fixed"))
        desired_target = s.get(f"{param_key}_tie_target")
        found = False
        for i in range(cb.count()):
            data = cb.itemData(i)
            if isinstance(data, tuple) and data[0] == desired_mode and (desired_mode != "Tied" or data[1] == desired_target):
                cb.setCurrentIndex(i); found = True; break
        if not found:
            cb.setCurrentIndex(0)
        return cb

    split = _mk_val_sb(owner, 3, 0.05, 0.0, 1e4, s["split"])
    split_min = _mk_lim_sb(owner, s["split_min"], 0.0, 1e4, 3)
    split_max = _mk_lim_sb(owner, s["split_max"], 0.0, 1e4, 3)
    split_mode = _make_doublet_mode_combo("split")
    _wire_limits(split_min, split, split_max)
    split_label = _add_param_row(grid, 2, "Splitting", split, split_min, split_max, split_mode)
    split_label.setToolTip("Spin-orbit energy separation between the major and minor components.")
    split_mode.setToolTip("Fixed keeps the splitting constant; Free fits it within min/max; Tied uses the splitting of the selected SO doublet.")

    ratio = _mk_val_sb(owner, 3, 0.05, 0.05, 20.0, s["ratio"])
    ratio_min = _mk_lim_sb(owner, s["ratio_min"], 0.05, 20.0, 3)
    ratio_max = _mk_lim_sb(owner, s["ratio_max"], 0.05, 20.0, 3)
    ratio_mode = _make_doublet_mode_combo("ratio")
    _wire_limits(ratio_min, ratio, ratio_max)
    ratio_label = _add_param_row(grid, 3, "Major/minor ratio", ratio, ratio_min, ratio_max, ratio_mode)
    ratio_label.setToolTip("Major/minor peak-height ratio. Statistical ratios are starting estimates and may be fitted or tied to another SO doublet.")
    ratio_mode.setToolTip("Fixed keeps the ratio constant; Free fits it within min/max; Tied uses the ratio of the selected SO doublet.")

    def _update_doublet_mode_ui(combo, value_widget, min_widget, max_widget):
        data = combo.currentData()
        mode = data[0] if isinstance(data, tuple) else str(combo.currentText())
        tied = mode == "Tied"
        value_widget.setEnabled(not tied)
        min_widget.setEnabled(mode == "Free")
        max_widget.setEnabled(mode == "Free")

    rel_row = QWidget(gb)
    rl = QHBoxLayout(rel_row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(5)
    relations = {}
    relation_tips = {
        "L": "Lorentzian FWHM. Same constrains major and minor components to the same value; Independent fits them separately.",
        "G": "Gaussian FWHM. Same constrains major and minor components to the same value; Independent fits them separately.",
        "A": "Peak asymmetry parameter. Same constrains major and minor components to the same value; Independent fits them separately.",
    }
    for pkey, text in (("L", "L FWHM"), ("G", "G FWHM"), ("A", "Alpha")):
        rel_lab = QLabel(text + ":", rel_row)
        rel_lab.setToolTip(relation_tips[pkey])
        rl.addWidget(rel_lab)
        cb = QComboBox(rel_row); cb.addItems(["Same", "Independent"]); cb.setCurrentText(s[f"{pkey}_relation"])
        cb.setToolTip(relation_tips[pkey])
        rl.addWidget(cb); relations[pkey] = cb
    rl.addStretch(1)
    grid.addWidget(rel_row, 4, 0, 1, 5)

    def _orbital_changed(text: str):
        # Only replace an untouched/statistical-looking ratio.  Never overwrite
        # a ratio the user has already changed materially.
        old = float(ratio.value())
        known = [2.0, 1.5, 4.0/3.0]
        if any(abs(old-k) < 1e-6 for k in known):
            new = statistical_ratio(text)
            ratio.setValue(new)
            ratio_min.setValue(max(0.1, new*0.75))
            ratio_max.setValue(max(new*1.25, new+0.2))
        on_changed()
    orbital.currentTextChanged.connect(_orbital_changed)
    label_edit.textChanged.connect(lambda _=None: on_changed())
    for w in (split, split_min, split_max, ratio, ratio_min, ratio_max):
        w.valueChanged.connect(lambda _=0: on_changed())
    def _split_mode_changed(_=None):
        _update_doublet_mode_ui(split_mode, split, split_min, split_max)
        on_changed()
    def _ratio_mode_changed(_=None):
        _update_doublet_mode_ui(ratio_mode, ratio, ratio_min, ratio_max)
        on_changed()
    split_mode.currentTextChanged.connect(_split_mode_changed)
    ratio_mode.currentTextChanged.connect(_ratio_mode_changed)
    _update_doublet_mode_ui(split_mode, split, split_min, split_max)
    _update_doublet_mode_ui(ratio_mode, ratio, ratio_min, ratio_max)
    for cb in relations.values():
        cb.currentTextChanged.connect(lambda _=None: on_changed())

    return {
        "group": gb, "title_label": title, "label_edit": label_edit, "orbital": orbital,
        "split": split, "split_min": split_min, "split_max": split_max, "split_mode": split_mode,
        "ratio": ratio, "ratio_min": ratio_min, "ratio_max": ratio_max, "ratio_mode": ratio_mode,
        "L_relation": relations["L"], "G_relation": relations["G"], "A_relation": relations["A"],
        "clone_btn": btn_clone, "ungroup_btn": btn_ungroup,
    }
