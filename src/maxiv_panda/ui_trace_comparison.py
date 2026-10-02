from __future__ import annotations

"""Lightweight, axis-agnostic comparison window for stored 1D traces."""

import csv
from pathlib import Path
from typing import Any

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog,
    QPushButton, QVBoxLayout,
)
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import ScalarFormatter

from .trace_comparison import ComparisonTrace


class TraceComparisonWindow(QDialog):
    """Non-modal plot window containing generic snapshot traces.

    Normal window closing only hides the window, preserving its traces.  The
    owner explicitly calls :meth:`terminate_session` when the application-level
    comparison session is meant to be discarded (main Clear all / Close all).
    """

    def __init__(self, parent=None):
        # Keep an ordinary independent top-level window rather than an owned
        # dialog.  On Windows, a QDialog with the main window as parent stays
        # above its owner and typically has no minimize button.  The main
        # window keeps the Python reference, so no Qt parent is required.
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowTitle("Trace comparison")
        self.setModal(False)
        self.resize(900, 620)
        self._traces: list[ComparisonTrace] = []
        self._next_trace_number = 1
        self._last_csv_dir: str | None = None
        self._export_basename = "trace_comparison.csv"

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        self.cb_legend = QCheckBox("Legend", self)
        self.cb_legend.setChecked(True)
        self.cb_legend.toggled.connect(self._redraw)
        controls.addWidget(self.cb_legend)

        self.cb_trace = QComboBox(self)
        self.cb_trace.setMinimumWidth(180)
        self.cb_trace.setToolTip("Select any stored trace to rename")
        controls.addWidget(self.cb_trace)

        self.btn_rename = QPushButton("Rename...", self)
        self.btn_rename.clicked.connect(self._rename_selected)
        controls.addWidget(self.btn_rename)

        self.btn_export = QPushButton("Export CSV", self)
        self.btn_export.clicked.connect(self._export_csv)
        controls.addWidget(self.btn_export)

        self.btn_clear = QPushButton("Clear all", self)
        self.btn_clear.clicked.connect(self._clear_from_button)
        controls.addWidget(self.btn_clear)
        controls.addStretch(1)
        root.addLayout(controls)

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        root.addWidget(self.toolbar)
        root.addWidget(self.canvas, 1)
        self.ax = self.figure.add_subplot(111)
        self._redraw()
        self._sync_controls()

    def set_export_basename(self, basename: str) -> None:
        """Set a producer-friendly default CSV name without changing generic logic."""
        name = str(basename or "trace_comparison.csv").strip()
        self._export_basename = name if name.lower().endswith(".csv") else f"{name}.csv"

    @property
    def trace_count(self) -> int:
        return len(self._traces)

    def add_trace(self, trace: ComparisonTrace | dict[str, Any]) -> str:
        """Add a numerical snapshot and return its assigned/default label."""
        if isinstance(trace, dict):
            trace = ComparisonTrace.from_mapping(trace)
        if not isinstance(trace, ComparisonTrace):
            raise TypeError("trace must be a ComparisonTrace")
        if self._traces and not trace.compatible_with(self._traces[0]):
            raise ValueError(
                "This trace has an incompatible X axis. "
                f"Current comparison uses '{self._traces[0].x_label}', "
                f"while the new trace uses '{trace.x_label}'."
            )

        if not trace.label.strip():
            trace.label = f"Trace {self._next_trace_number}"
        self._next_trace_number += 1
        self._traces.append(trace)
        self._sync_controls(select_last=True)
        self._redraw()
        self.show()
        self.raise_()
        self.activateWindow()
        return trace.label

    def clear_traces(self) -> None:
        self._traces.clear()
        self._next_trace_number = 1
        self._sync_controls()
        self._redraw()

    def capture_session_state(self) -> tuple[dict[str, Any], dict[str, tuple[np.ndarray, np.ndarray]]]:
        """Capture traces, visibility and window geometry for PANDA sessions."""
        rows: list[dict[str, Any]] = []
        arrays: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for idx, trace in enumerate(self._traces):
            member = f"trace/trace_{idx:05d}.npz"
            arrays[member] = (np.asarray(trace.x), np.asarray(trace.y))
            rows.append({
                "array_member": member, "x_label": trace.x_label, "y_label": trace.y_label,
                "x_quantity": trace.x_quantity, "x_unit": trace.x_unit, "invert_x": bool(trace.invert_x),
                "label": trace.label, "metadata": dict(trace.metadata or {}),
            })
        g = self.geometry()
        return {
            "traces": rows, "visible": bool(self.isVisible()),
            "geometry": [int(g.x()), int(g.y()), int(g.width()), int(g.height())],
            "legend": bool(self.cb_legend.isChecked()),
            "selected_trace": int(self.cb_trace.currentIndex()),
            "next_trace_number": int(self._next_trace_number),
            "export_basename": str(self._export_basename),
        }, arrays

    def restore_session_state(self, state: dict[str, Any], array_loader) -> list[str]:
        """Restore a trace-comparison session without forcing it visible."""
        problems: list[str] = []
        self._traces = []
        for row in list((state or {}).get("traces") or []):
            if not isinstance(row, dict):
                continue
            try:
                x, y = array_loader(str(row.get("array_member") or ""))
                self._traces.append(ComparisonTrace(
                    x=x, y=y, x_label=str(row.get("x_label") or "X"),
                    y_label=str(row.get("y_label") or "Intensity"), x_quantity=str(row.get("x_quantity") or ""),
                    x_unit=row.get("x_unit"), invert_x=bool(row.get("invert_x", False)),
                    label=str(row.get("label") or ""), metadata=dict(row.get("metadata") or {}),
                ))
            except Exception as exc:
                problems.append(f"Could not restore comparison trace {row.get('label') or ''}: {exc}")
        self._next_trace_number = max(int((state or {}).get("next_trace_number", len(self._traces) + 1)), len(self._traces) + 1)
        self._export_basename = str((state or {}).get("export_basename") or "trace_comparison.csv")
        self.cb_legend.setChecked(bool((state or {}).get("legend", True)))
        self._sync_controls()
        idx = int((state or {}).get("selected_trace", -1))
        if 0 <= idx < self.cb_trace.count(): self.cb_trace.setCurrentIndex(idx)
        geometry = (state or {}).get("geometry")
        if isinstance(geometry, (list, tuple)) and len(geometry) == 4:
            try: self.setGeometry(*(int(v) for v in geometry))
            except Exception: pass
        self._redraw()
        if bool((state or {}).get("visible", False)):
            self.show(); self.raise_(); self.activateWindow()
        else:
            self.hide()
        return problems

    def terminate_session(self) -> None:
        self.clear_traces()
        self.hide()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        event.ignore()
        self.hide()

    def _sync_controls(self, *, select_last: bool = False) -> None:
        current = self.cb_trace.currentIndex()
        self.cb_trace.blockSignals(True)
        self.cb_trace.clear()
        for idx, item in enumerate(self._traces):
            # Store the actual trace index as item data.  Rename therefore
            # follows the user's selected combo-box entry rather than relying
            # on whichever trace happened to be added most recently.
            self.cb_trace.addItem(item.label or "Trace", idx)
        if self._traces:
            if select_last:
                current = len(self._traces) - 1
            current = max(0, min(current, len(self._traces) - 1))
            self.cb_trace.setCurrentIndex(current)
        self.cb_trace.blockSignals(False)
        enabled = bool(self._traces)
        self.cb_trace.setEnabled(enabled)
        self.btn_rename.setEnabled(enabled)
        self.btn_export.setEnabled(enabled)
        self.btn_clear.setEnabled(enabled)

    def _redraw(self, *_args) -> None:
        self.ax.clear()
        for item in self._traces:
            self.ax.plot(item.x, item.y, linewidth=1.35, label=item.label or "Trace")
        if self._traces:
            self.ax.set_xlabel(self._traces[0].x_label)
            self.ax.set_ylabel(self._traces[0].y_label)
            if bool(getattr(self._traces[0], "invert_x", False)):
                self.ax.invert_xaxis()
        else:
            self.ax.set_xlabel("X")
            self.ax.set_ylabel("Intensity")
        self.ax.grid(True, linewidth=1.0, alpha=0.35)
        try:
            formatter = ScalarFormatter(useMathText=True)
            formatter.set_scientific(True)
            formatter.set_powerlimits((0, 0))
            self.ax.yaxis.set_major_formatter(formatter)
        except Exception:
            pass
        if self._traces and self.cb_legend.isChecked():
            legend = self.ax.legend()
            try:
                legend.set_draggable(True, use_blit=False)
            except Exception:
                pass
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _rename_selected(self) -> None:
        idx_data = self.cb_trace.currentData()
        try:
            idx = int(idx_data)
        except (TypeError, ValueError):
            idx = self.cb_trace.currentIndex()
        if idx < 0 or idx >= len(self._traces):
            return
        old = self._traces[idx].label or f"Trace {idx + 1}"
        text, ok = QInputDialog.getText(self, "Rename trace", "Legend name:", text=old)
        if not ok:
            return
        text = str(text).strip()
        if not text:
            return
        self._traces[idx].label = text
        self._sync_controls()
        self.cb_trace.setCurrentIndex(idx)
        self._redraw()

    def _clear_from_button(self) -> None:
        if not self._traces:
            return
        answer = QMessageBox.question(
            self, "Clear traces", "Remove all stored comparison traces?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.clear_traces()

    @staticmethod
    def _metadata_text(item: ComparisonTrace) -> str:
        parts: list[str] = []
        for key, value in item.metadata.items():
            if value in (None, ""):
                continue
            parts.append(f"{key}={value}")
        return "; ".join(parts)

    def _export_csv(self) -> None:
        if not self._traces:
            return
        initial_dir = self._last_csv_dir or str(Path.cwd())
        path, _ = QFileDialog.getSaveFileName(
            self, "Export trace comparison as CSV",
            str(Path(initial_dir) / self._export_basename),
            "CSV files (*.csv);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            self._last_csv_dir = str(Path(path).parent)
            max_len = max(len(item.x) for item in self._traces)
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                for item in self._traces:
                    writer.writerow([f"# {item.label or 'Trace'}", self._metadata_text(item)])
                header: list[str] = []
                for item in self._traces:
                    label = item.label or "Trace"
                    header.extend([f"{item.x_label} ({label})", label])
                writer.writerow(header)
                for row in range(max_len):
                    values: list[str] = []
                    for item in self._traces:
                        if row < len(item.x):
                            xv = item.x[row]; yv = item.y[row]
                            values.append(f"{float(xv):.12g}" if np.isfinite(xv) else "nan")
                            values.append(f"{float(yv):.12g}" if np.isfinite(yv) else "nan")
                        else:
                            values.extend(["", ""])
                    writer.writerow(values)
        except Exception as exc:
            QMessageBox.critical(self, "Export CSV", f"Could not export trace comparison CSV:\n{exc}")
