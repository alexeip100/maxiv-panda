from __future__ import annotations

from typing import Callable, Mapping, Sequence

import numpy as np

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem


def capture_table_state(table) -> dict:
    data = {"rows": table.rowCount(), "cols": table.columnCount(), "cells": []}
    for r in range(table.rowCount()):
        row = []
        for c in range(table.columnCount()):
            it = table.item(r, c)
            if it is None:
                row.append(None)
                continue
            fg = it.foreground().color()
            bg = it.background().color()
            row.append({
                "text": it.text(),
                "fg_rgba": (int(fg.red()), int(fg.green()), int(fg.blue()), int(fg.alpha())),
                "bg_rgba": (int(bg.red()), int(bg.green()), int(bg.blue()), int(bg.alpha())),
                "bold": bool(it.font().bold()),
            })
        data["cells"].append(row)
    return data


def restore_table_state(table, state: Mapping[str, object] | None) -> None:
    if not state:
        return
    try:
        base_bg = table.palette().base().color()
    except Exception:
        base_bg = QColor("white")
    rows = min(table.rowCount(), int(state.get("rows", 0)))
    cols = min(table.columnCount(), int(state.get("cols", 0)))
    cells = state.get("cells", [])
    for r in range(rows):
        row = cells[r] if r < len(cells) else []
        for c in range(cols):
            cell = row[c] if c < len(row) else None
            if cell is None:
                continue
            item = QTableWidgetItem(str(cell.get("text", "")))
            try:
                fg_rgba = cell.get("fg_rgba")
                if isinstance(fg_rgba, (tuple, list)) and len(fg_rgba) == 4:
                    item.setForeground(QColor(*[int(v) for v in fg_rgba]))
                bg_rgba = cell.get("bg_rgba")
                if isinstance(bg_rgba, (tuple, list)) and len(bg_rgba) == 4:
                    rgba = [int(v) for v in bg_rgba]
                    if int(rgba[3]) > 0:
                        item.setBackground(QColor(*rgba))
                    else:
                        item.setBackground(base_bg)
                else:
                    item.setBackground(base_bg)
                font = item.font()
                font.setBold(bool(cell.get("bold", False)))
                item.setFont(font)
            except Exception:
                try:
                    item.setBackground(base_bg)
                except Exception:
                    pass
            table.setItem(r, c, item)


def make_constraint_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    font = item.font()
    font.setBold(True)
    item.setFont(font)
    low = str(text or "").lower()
    if low == "free":
        item.setForeground(QColor("#1b8f2f"))
    elif low == "fixed":
        item.setForeground(QColor("#c62828"))
    elif low.startswith("tied to"):
        item.setForeground(QColor("#d97706"))
    return item


def make_result_item(text: str, param_name: str, bound_hits: set[str] | None = None) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    hits = bound_hits or set()
    if param_name in hits:
        item.setBackground(QColor("#ffd9d9"))
        item.setForeground(QColor("#6b2020"))
        item.setToolTip("Parameter reached a fit bound.")
    return item


def bg_constraint_display_map(bg_type: str, shirley_alpha_fixed: bool) -> dict:
    if bg_type == "Shirley":
        return {"bg_alpha": "Fixed" if shirley_alpha_fixed else "Free"}
    return {"b0": "Free", "b1": "Free", "b2": "Free"}


def clear_fit_quality_summary(lbl_status: QLabel, lbl_rss: QLabel, lbl_rms: QLabel, lbl_redchi: QLabel) -> None:
    for lbl in (lbl_status, lbl_rss, lbl_rms, lbl_redchi):
        try:
            lbl.setText("—")
        except Exception:
            pass


def update_fit_quality_summary(
    lbl_status: QLabel,
    lbl_rss: QLabel,
    lbl_rms: QLabel,
    lbl_redchi: QLabel,
    status: str,
    metrics: Mapping[str, float] | None,
) -> None:
    try:
        lbl_status.setText(status or "—")
    except Exception:
        pass
    if not metrics:
        for lbl in (lbl_rss, lbl_rms, lbl_redchi):
            try:
                lbl.setText("—")
            except Exception:
                pass
        return
    import math
    def fmt(v: float) -> str:
        return f"{v:.6g}" if isinstance(v, (int, float)) and math.isfinite(v) else "—"
    try:
        lbl_rss.setText(fmt(metrics.get("rss", float("nan"))))
        lbl_rms.setText(fmt(metrics.get("rms", float("nan"))))
        lbl_redchi.setText(fmt(metrics.get("redchi_poisson", float("nan"))))
    except Exception:
        pass


def populate_fit_results_tables(
    tbl_fit_results: QTableWidget,
    tbl_bg_results: QTableWidget,
    peak_widgets: Sequence[dict],
    result_values: Mapping[str, float],
    bg_type: str,
    bound_hits: set[str],
    constraint_display_text_fn: Callable[[str, dict], str],
    shirley_alpha_fixed: bool,
    peak_areas: Sequence[float] | None = None,
) -> None:
    n_peaks = len(peak_widgets)
    tbl_fit_results.clearContents()
    tbl_fit_results.setRowCount(n_peaks * 2)
    headers = []
    for i in range(n_peaks):
        headers.extend([f"Peak {i+1}", ""])
    tbl_fit_results.setVerticalHeaderLabels(headers)
    peak_cols = [("E", "Energy"), ("H", "Height"), ("Area", "Area"), ("L", "LFWHM"), ("G", "GFWHM"), ("A", "Alpha")]
    for r, w in enumerate(peak_widgets):
        value_row = 2 * r
        constr_row = value_row + 1
        for c, (suffix, _label) in enumerate(peak_cols):
            if suffix == "Area":
                area = None
                if peak_areas is not None and r < len(peak_areas):
                    area = peak_areas[r]
                try:
                    txt = f"{float(area):.6g}" if area is not None and np.isfinite(float(area)) else ""
                except Exception:
                    txt = ""
                tbl_fit_results.setItem(value_row, c, make_result_item(txt, "", set()))
                tbl_fit_results.setItem(constr_row, c, make_constraint_item("Derived"))
                continue
            key = f"p{r+1}_{suffix}"
            txt = f"{float(result_values[key]):.6g}" if key in result_values else ""
            tbl_fit_results.setItem(value_row, c, make_result_item(txt, key, bound_hits))
            tbl_fit_results.setItem(constr_row, c, make_constraint_item(constraint_display_text_fn(suffix, w)))
        try:
            tbl_fit_results.setRowHeight(value_row, 26)
            tbl_fit_results.setRowHeight(constr_row, 26)
        except Exception:
            pass

    bg_cols = {
        "constant": ["b0"],
        "linear": ["b0", "b1"],
        "parabolic": ["b0", "b1", "b2"],
    }.get(bg_type, ["bg_alpha"] if bg_type == "Shirley" else ["b0"])
    tbl_bg_results.clear()
    tbl_bg_results.setRowCount(2)
    tbl_bg_results.setColumnCount(len(bg_cols))
    tbl_bg_results.setVerticalHeaderLabels(["Background", ""])
    header_map = {"bg_alpha": "α"}
    tbl_bg_results.setHorizontalHeaderLabels([header_map.get(name, name) for name in bg_cols])
    constraint_map = bg_constraint_display_map(bg_type, shirley_alpha_fixed)
    for c, name in enumerate(bg_cols):
        txt = f"{float(result_values[name]):.6g}" if name in result_values else ""
        tbl_bg_results.setItem(0, c, make_result_item(txt, name, bound_hits))
        tbl_bg_results.setItem(1, c, make_constraint_item(constraint_map.get(name, "Free")))
    try:
        tbl_bg_results.setRowHeight(0, 26)
        tbl_bg_results.setRowHeight(1, 26)
    except Exception:
        pass
