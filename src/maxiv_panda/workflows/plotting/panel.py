from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QSlider, QSpinBox, QDoubleSpinBox, QSplitter, QVBoxLayout, QWidget, QMenu, QColorDialog,
)
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.ticker import AutoMinorLocator

from ...energy_utils import default_flip_for_energy_scale, normalize_energy_xlabel
from .curve_item import CurveItemWidget
from .annotation_dialog import AnnotationEditDialog
from .legend_style_dialog import LegendStyleDialog
from .tex_reference_dialog import LegendNameDialog
from .export import export_visible_curves_csv, import_curves_csv
from .model import PlottedCurve
from .settings import AnnotationSettings, LegendSettings


class PlottedDataPanel(QWidget):
    """Compose and style independent curve snapshots for final plotting."""

    _DEFAULT_COLORS = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    ]
    _DEFAULT_WATERFALL_COLOR = "#1f77b4"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._curves: list[PlottedCurve] = []
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.ax = self.figure.add_subplot(111)
        self.annotation_settings = AnnotationSettings()
        self.legend_settings = LegendSettings()
        self._annotation_artist = None
        self._legend_artist = None
        self._default_directory = Path.home()
        self._waterfall_mono_color = self._DEFAULT_WATERFALL_COLOR
        self.canvas.mpl_connect("button_release_event", self._on_button_release)
        self.canvas.mpl_connect("pick_event", self._on_pick)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(QLabel("Legend:"))
        self.cmb_legend = QComboBox(self)
        self.cmb_legend.addItem("None", "None")
        self.cmb_legend.addItem("Curve name", "Curve name")
        self.cmb_legend.addItem("Custom (TeX)", "Custom")
        self.cmb_legend.setCurrentText("Curve name")
        self.cmb_legend.setToolTip(
            "Custom (TeX) supports Matplotlib TeX-style notation, e.g. "
            r"S 2p$_{3/2}$ or Fe$^{3+}$."
        )
        top.addWidget(self.cmb_legend)
        self.chk_reverse_x = QCheckBox("Reverse X", self)
        self.chk_reverse_x.setToolTip("Reverse the horizontal axis direction")
        top.addWidget(self.chk_reverse_x)
        self.btn_annotation = QPushButton("Annotation...", self)
        self.btn_annotation.setToolTip("Add or edit a draggable plot annotation")
        top.addWidget(self.btn_annotation)
        self.btn_legend_style = QPushButton("Legend style...", self)
        top.addWidget(self.btn_legend_style)
        top.addStretch(1)
        self.btn_check_all = QPushButton("Check all", self)
        self.btn_check_all.setToolTip("Show all plotted curves")
        top.addWidget(self.btn_check_all)
        self.btn_uncheck_all = QPushButton("Uncheck all", self)
        self.btn_uncheck_all.setToolTip("Hide all plotted curves")
        top.addWidget(self.btn_uncheck_all)
        root.addLayout(top)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        plot_side = QWidget(self.splitter)
        plot_lay = QVBoxLayout(plot_side)
        plot_lay.setContentsMargins(0, 0, 0, 0)
        plot_lay.setSpacing(4)
        plot_lay.addWidget(self.toolbar, 0)
        plot_lay.addWidget(self.canvas, 1)

        list_side = QWidget(self.splitter)
        list_lay = QVBoxLayout(list_side)
        list_lay.setContentsMargins(4, 0, 0, 0)
        list_lay.setSpacing(4)
        list_lay.addWidget(QLabel("Plotted curves"), 0)
        self.curve_list = QListWidget(list_side)
        self.curve_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.curve_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.curve_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.curve_list.setAlternatingRowColors(True)
        list_lay.addWidget(self.curve_list, 1)
        self.splitter.addWidget(plot_side)
        self.splitter.addWidget(list_side)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([1050, 390])
        root.addWidget(self.splitter, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(7)
        self.chk_waterfall = QCheckBox("Waterfall", self)
        bottom.addWidget(self.chk_waterfall)
        bottom.addWidget(QLabel("Offset"))
        self.slider_waterfall = QSlider(Qt.Orientation.Horizontal, self)
        # Keep a fixed fine internal slider resolution and map it onto an
        # adaptive percentage range that depends on the number of visible curves.
        self.slider_waterfall.setRange(0, 1000)
        self.slider_waterfall.setValue(200)
        # Keep the slider handle responsive for very large curve sets: while the
        # user drags, update only the numeric value; redraw once the handle is
        # released.  Programmatic/keyboard changes still redraw normally.
        self.slider_waterfall.setTracking(False)
        self.slider_waterfall.setEnabled(False)
        self.slider_waterfall.setMinimumWidth(180)
        bottom.addWidget(self.slider_waterfall, 1)
        self.spin_waterfall = QDoubleSpinBox(self)
        self.spin_waterfall.setRange(0.0, 100.0)
        self.spin_waterfall.setDecimals(2)
        self.spin_waterfall.setSingleStep(0.1)
        self.spin_waterfall.setValue(20.0)
        self.spin_waterfall.setSuffix(" %")
        self.spin_waterfall.setEnabled(False)
        self.spin_waterfall.setMaximumWidth(86)
        bottom.addWidget(self.spin_waterfall)
        self._waterfall_max_percent = 100.0
        bottom.addWidget(QLabel("Filling"))
        self.slider_waterfall_fill = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_waterfall_fill.setRange(0, 100)
        self.slider_waterfall_fill.setValue(0)
        self.slider_waterfall_fill.setEnabled(False)
        self.slider_waterfall_fill.setMinimumWidth(100)
        self.slider_waterfall_fill.setMaximumWidth(180)
        self.slider_waterfall_fill.setToolTip(
            "Opaque background filling beneath each waterfall curve: 0 = lines only, 100 = fully opaque"
        )
        bottom.addWidget(self.slider_waterfall_fill)
        self.lbl_waterfall_fill = QLabel("0 %", self)
        self.lbl_waterfall_fill.setMinimumWidth(34)
        self.lbl_waterfall_fill.setToolTip(self.slider_waterfall_fill.toolTip())
        bottom.addWidget(self.lbl_waterfall_fill)
        self.chk_waterfall_mono = QCheckBox("Fixed color:", self)
        self.chk_waterfall_mono.setChecked(False)
        self.chk_waterfall_mono.setEnabled(False)
        self.chk_waterfall_mono.setToolTip("Use one selected color for all curves in waterfall display")
        bottom.addWidget(self.chk_waterfall_mono)
        self.btn_waterfall_color = QPushButton("", self)
        self.btn_waterfall_color.setFixedSize(24, 18)
        self.btn_waterfall_color.setEnabled(False)
        self.btn_waterfall_color.setToolTip("Choose the fixed waterfall curve color")
        bottom.addWidget(self.btn_waterfall_color)
        self._update_waterfall_color_button()
        bottom.addSpacing(10)
        self.chk_fixed_width = QCheckBox("Fixed width:", self)
        self.chk_fixed_width.setChecked(False)
        self.chk_fixed_width.setToolTip("Use one line width for all plotted curves without changing their individual saved widths")
        bottom.addWidget(self.chk_fixed_width)
        self.spin_fixed_width = QDoubleSpinBox(self)
        self.spin_fixed_width.setRange(0.5, 8.0)
        self.spin_fixed_width.setSingleStep(0.2)
        self.spin_fixed_width.setDecimals(1)
        self.spin_fixed_width.setValue(2.0)
        self.spin_fixed_width.setSuffix(" pt")
        self.spin_fixed_width.setMaximumWidth(76)
        self.spin_fixed_width.setEnabled(False)
        self.spin_fixed_width.setToolTip("Common display line width used while Fixed width is enabled")
        bottom.addWidget(self.spin_fixed_width)
        bottom.addSpacing(12)
        bottom.addWidget(QLabel("Grid:"))
        self.cmb_grid = QComboBox(self)
        self.cmb_grid.addItems(["None", "Coarse", "Fine", "Finest"])
        self.cmb_grid.setCurrentText("Finest")
        bottom.addWidget(self.cmb_grid)
        bottom.addStretch(1)
        self.btn_csv = QPushButton("Export / Import", self)
        self.btn_csv.setToolTip("Export plotted curves or import curves from CSV")
        self.csv_menu = QMenu(self.btn_csv)
        self.action_export_csv = self.csv_menu.addAction("Export CSV")
        self.action_import_csv = self.csv_menu.addAction("Import CSV")
        self.btn_csv.setMenu(self.csv_menu)
        bottom.addWidget(self.btn_csv)
        self.btn_clear = QPushButton("Clear plotted", self)
        bottom.addWidget(self.btn_clear)
        root.addLayout(bottom)

        self.cmb_legend.currentIndexChanged.connect(self._on_legend_mode_changed)
        self.btn_annotation.clicked.connect(self.edit_annotation)
        self.btn_legend_style.clicked.connect(self.edit_legend_style)
        self.btn_check_all.clicked.connect(self._check_all_curves)
        self.btn_uncheck_all.clicked.connect(self._uncheck_all_curves)
        self.chk_reverse_x.toggled.connect(self.redraw)
        self.chk_waterfall.toggled.connect(self._on_waterfall_toggled)
        self.slider_waterfall.sliderMoved.connect(self._slider_preview_changed)
        self.slider_waterfall.valueChanged.connect(self._slider_changed)
        self.spin_waterfall.valueChanged.connect(self._spin_changed)
        self.slider_waterfall_fill.valueChanged.connect(self._on_waterfall_fill_changed)
        self.chk_waterfall_mono.toggled.connect(self._on_waterfall_mono_toggled)
        self.btn_waterfall_color.clicked.connect(self._choose_waterfall_mono_color)
        self.chk_fixed_width.toggled.connect(self._on_fixed_width_toggled)
        self.spin_fixed_width.valueChanged.connect(self.redraw)
        self.cmb_grid.currentIndexChanged.connect(self.redraw)
        self.action_import_csv.triggered.connect(self.import_csv)
        self.action_export_csv.triggered.connect(self.export_csv)
        self.btn_clear.clicked.connect(self.confirm_clear)
        self.curve_list.model().rowsMoved.connect(self._on_rows_moved)

        self.clear()

    @property
    def curves(self) -> tuple[PlottedCurve, ...]:
        return tuple(self._curves)

    def capture_session_state(self) -> tuple[dict[str, Any], dict[str, tuple[np.ndarray, np.ndarray]]]:
        """Return JSON-safe plotting state plus NPZ-ready numerical snapshots."""
        curves: list[dict[str, Any]] = []
        arrays: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        for idx, curve in enumerate(self._curves):
            member = f"plotted/curve_{idx:05d}.npz"
            arrays[member] = (np.asarray(curve.x), np.asarray(curve.y))
            curves.append({
                "array_member": member, "title": curve.title, "xlabel": curve.xlabel,
                "ylabel": curve.ylabel, "energy_scale": curve.energy_scale,
                "visible": bool(curve.visible), "color": curve.color,
                "linestyle": curve.linestyle, "linewidth": float(curve.linewidth),
                "custom_name": curve.custom_name, "metadata": dict(curve.metadata or {}),
            })
        ann = self.annotation_settings
        leg = self.legend_settings
        state = {
            "curves": curves,
            "legend_mode": self._legend_mode(),
            "reverse_x": bool(self.chk_reverse_x.isChecked()),
            "waterfall": bool(self.chk_waterfall.isChecked()),
            "waterfall_percent": float(self.spin_waterfall.value()),
            "waterfall_fill": int(self.slider_waterfall_fill.value()),
            "waterfall_mono": bool(self.chk_waterfall_mono.isChecked()),
            "waterfall_color": str(self._waterfall_mono_color),
            "fixed_width": bool(self.chk_fixed_width.isChecked()),
            "fixed_width_value": float(self.spin_fixed_width.value()),
            "grid": str(self.cmb_grid.currentText()),
            "splitter_sizes": [int(v) for v in self.splitter.sizes()],
            "annotation": {"text": ann.text, "visible": bool(ann.visible), "x": float(ann.x), "y": float(ann.y), "style": dict(ann.style or {})},
            "legend_settings": {"location": leg.location, "anchor": list(leg.anchor) if leg.anchor is not None else None, "style": dict(leg.style or {})},
        }
        return state, arrays

    def restore_session_state(self, state: dict[str, Any], array_loader) -> list[str]:
        """Restore a plotted composition captured by :meth:`capture_session_state`."""
        problems: list[str] = []
        restored: list[PlottedCurve] = []
        for row in list((state or {}).get("curves") or []):
            if not isinstance(row, dict):
                continue
            try:
                x, y = array_loader(str(row.get("array_member") or ""))
                restored.append(PlottedCurve(
                    title=str(row.get("title") or "Curve"), x=np.asarray(x), y=np.asarray(y),
                    xlabel=str(row.get("xlabel") or "Energy"), ylabel=str(row.get("ylabel") or "Intensity"),
                    energy_scale=str(row.get("energy_scale") or "Unknown"), visible=bool(row.get("visible", True)),
                    color=row.get("color"), linestyle=str(row.get("linestyle") or "-"),
                    linewidth=float(row.get("linewidth", 2.0)), custom_name=str(row.get("custom_name") or ""),
                    metadata=dict(row.get("metadata") or {}),
                ))
            except Exception as exc:
                problems.append(f"Could not restore plotted curve {row.get('title') or ''}: {exc}")
        self._curves = restored
        try:
            mode = str((state or {}).get("legend_mode") or "Curve name")
            idx = self.cmb_legend.findData(mode)
            if idx < 0: idx = self.cmb_legend.findText(mode)
            if idx >= 0: self.cmb_legend.setCurrentIndex(idx)
            self.chk_reverse_x.setChecked(bool((state or {}).get("reverse_x", False)))
            self.spin_waterfall.setValue(float((state or {}).get("waterfall_percent", 20.0)))
            self.slider_waterfall_fill.setValue(int((state or {}).get("waterfall_fill", 0)))
            self._waterfall_mono_color = str((state or {}).get("waterfall_color") or self._DEFAULT_WATERFALL_COLOR)
            self.chk_waterfall_mono.setChecked(bool((state or {}).get("waterfall_mono", False)))
            self.spin_fixed_width.setValue(float((state or {}).get("fixed_width_value", 2.0)))
            self.chk_fixed_width.setChecked(bool((state or {}).get("fixed_width", False)))
            grid = str((state or {}).get("grid") or "Finest")
            if self.cmb_grid.findText(grid) >= 0: self.cmb_grid.setCurrentText(grid)
            self.chk_waterfall.setChecked(bool((state or {}).get("waterfall", False)))
            sizes = (state or {}).get("splitter_sizes")
            if isinstance(sizes, list) and len(sizes) == 2: self.splitter.setSizes([int(v) for v in sizes])
            ann = dict((state or {}).get("annotation") or {})
            self.annotation_settings = AnnotationSettings(
                text=str(ann.get("text") or ""), visible=bool(ann.get("visible", False)),
                x=float(ann.get("x", 0.04)), y=float(ann.get("y", 0.96)), style=dict(ann.get("style") or AnnotationSettings().style),
            )
            leg = dict((state or {}).get("legend_settings") or {})
            anchor = leg.get("anchor")
            self.legend_settings = LegendSettings(
                location=str(leg.get("location") or "best"),
                anchor=(float(anchor[0]), float(anchor[1])) if isinstance(anchor, (list, tuple)) and len(anchor) == 2 else None,
                style=dict(leg.get("style") or LegendSettings().style),
            )
        except Exception as exc:
            problems.append(f"Could not restore Plotted Data display settings: {exc}")
        self._rebuild_list(); self.redraw()
        return problems

    def remove_curves_by_metadata(self, key: str, value: Any) -> int:
        """Remove plotted snapshots whose metadata ``key`` equals ``value``.

        This is the public provenance-aware removal contract used by source
        snapshot management.  It avoids coupling file-management code to the
        panel's private list/rebuild implementation.
        """
        before = len(self._curves)
        self._curves = [
            curve for curve in self._curves
            if (getattr(curve, "metadata", {}) or {}).get(key) != value
        ]
        removed = before - len(self._curves)
        if removed:
            self._rebuild_list()
            self.redraw()
        return removed

    def confirm_clear(self) -> None:
        """Ask before clearing the complete plotted composition."""
        if not self._curves:
            return
        answer = QMessageBox.question(
            self,
            "Clear plotted curves",
            "Do you want to clear all plotted curves?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Ok:
            self.clear()

    def clear(self) -> None:
        # Clearing the plotted composition also exits waterfall mode.
        self.chk_waterfall.blockSignals(True)
        self.chk_waterfall.setChecked(False)
        self.chk_waterfall.blockSignals(False)
        self.slider_waterfall.setEnabled(False)
        self.spin_waterfall.setEnabled(False)
        self.slider_waterfall_fill.setEnabled(False)
        self.chk_waterfall_mono.setEnabled(False)
        self.btn_waterfall_color.setEnabled(False)
        self._curves = []
        self.curve_list.clear()
        # Annotation belongs to the plotted composition.  Clear its persistent
        # settings too, otherwise the old annotation reappears when new curves
        # are passed to plotting after a clear.
        self.annotation_settings = AnnotationSettings()
        self._annotation_artist = None
        self.redraw()

    def set_curves(self, curves: Iterable[Any]) -> None:
        """Replace plotted contents with independent snapshots of ``curves``."""
        self._curves = []
        self.add_curves(curves)

    def add_curves(self, curves: Iterable[Any]) -> None:
        """Append independent snapshots without clearing curves already plotted."""
        start = len(self._curves)
        snapshots: list[PlottedCurve] = []
        used_names = {curve.title for curve in self._curves}
        for idx, payload in enumerate(curves):
            preferred_color = getattr(payload, "color", None)
            snapshot = PlottedCurve.from_payload(
                payload,
                color=(preferred_color if preferred_color else self._DEFAULT_COLORS[(start + idx) % len(self._DEFAULT_COLORS)]),
            )
            if snapshot is not None:
                base = snapshot.title or "Curve"
                unique = base
                suffix = 2
                while unique in used_names:
                    unique = f"{base} ({suffix})"
                    suffix += 1
                snapshot.title = unique
                used_names.add(unique)
                snapshots.append(snapshot)
        was_empty = not self._curves
        self._curves.extend(snapshots)
        self._rebuild_list()
        if was_empty and snapshots:
            flip = default_flip_for_energy_scale(snapshots[0].energy_scale)
            self.chk_reverse_x.blockSignals(True)
            self.chk_reverse_x.setChecked(bool(flip))
            self.chk_reverse_x.blockSignals(False)
        self.redraw()

    def _rebuild_list(self) -> None:
        self.curve_list.clear()
        for curve in self._curves:
            item = QListWidgetItem(self.curve_list)
            widget = CurveItemWidget(
                curve, self.curve_list, legend_mode=self._legend_mode()
            )
            widget.changed.connect(self.redraw)
            widget.remove_requested.connect(self._remove_widget)
            widget.drag_requested.connect(self._start_drag_for_widget)
            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.ItemDataRole.UserRole, curve)
            self.curve_list.setItemWidget(item, widget)

    def _set_all_curve_visibility(self, visible: bool) -> None:
        """Set all plotted-curve visibility states and redraw only once."""
        visible = bool(visible)
        for curve in self._curves:
            curve.visible = visible
        for row in range(self.curve_list.count()):
            item = self.curve_list.item(row)
            widget = self.curve_list.itemWidget(item)
            if isinstance(widget, CurveItemWidget):
                widget.chk_visible.blockSignals(True)
                widget.chk_visible.setChecked(visible)
                widget.chk_visible.blockSignals(False)
        self.redraw()

    def _check_all_curves(self) -> None:
        self._set_all_curve_visibility(True)

    def _uncheck_all_curves(self) -> None:
        self._set_all_curve_visibility(False)

    def _on_fixed_width_toggled(self, checked: bool) -> None:
        self.spin_fixed_width.setEnabled(bool(checked))
        self.redraw()

    def _effective_curve_width(self, curve: PlottedCurve) -> float:
        if self.chk_fixed_width.isChecked():
            return float(self.spin_fixed_width.value())
        return float(curve.linewidth)


    def _legend_mode(self) -> str:
        data = self.cmb_legend.currentData()
        return str(data if data is not None else self.cmb_legend.currentText())

    def _on_legend_mode_changed(self, *_args) -> None:
        """Change legend labels without changing the static curve list."""
        mode = self._legend_mode()
        for row in range(self.curve_list.count()):
            item = self.curve_list.item(row)
            widget = self.curve_list.itemWidget(item)
            if isinstance(widget, CurveItemWidget):
                widget.set_legend_mode(mode)
        self.redraw()

    def _export_name_for_curve(self, curve: PlottedCurve) -> str:
        if self._legend_mode() == "Custom":
            return curve.custom_name.strip() or "<select curve name>"
        return (curve.title or "Curve").strip() or "Curve"

    def set_default_directory(self, directory: str | Path | None) -> None:
        """Set the initial directory used by Plotted Data CSV dialogs."""
        if directory is None:
            return
        path = Path(directory).expanduser()
        if path.is_file():
            path = path.parent
        if path.exists() and path.is_dir():
            self._default_directory = path

    def _start_drag_for_widget(self, widget: CurveItemWidget) -> None:
        for row in range(self.curve_list.count()):
            item = self.curve_list.item(row)
            if self.curve_list.itemWidget(item) is widget:
                self.curve_list.setCurrentRow(row)
                self.curve_list.startDrag(Qt.DropAction.MoveAction)
                return

    def _remove_widget(self, widget: CurveItemWidget) -> None:
        answer = QMessageBox.question(
            self,
            "Remove curve",
            "Do you want to remove this curve?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Ok:
            return
        for row in range(self.curve_list.count()):
            item = self.curve_list.item(row)
            if self.curve_list.itemWidget(item) is widget:
                self.curve_list.takeItem(row)
                break
        self._curves = [c for c in self._curves if c is not widget.curve]
        self.redraw()

    def _on_rows_moved(self, *_args) -> None:
        ordered: list[PlottedCurve] = []
        for row in range(self.curve_list.count()):
            curve = self.curve_list.item(row).data(Qt.ItemDataRole.UserRole)
            if isinstance(curve, PlottedCurve):
                ordered.append(curve)
        if len(ordered) == len(self._curves):
            self._curves = ordered
        self.redraw()



    def edit_annotation(self) -> None:
        dialog = AnnotationEditDialog(self.annotation_settings.text, self.annotation_settings.style, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        text, style = dialog.get_text_and_style()
        self.annotation_settings.text = str(text)
        self.annotation_settings.style = dict(style)
        self.annotation_settings.visible = bool(str(text).strip())
        self.redraw()

    def edit_legend_style(self) -> None:
        dialog = LegendStyleDialog(self.legend_settings.style, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.legend_settings.style = dict(dialog.get_style())
        self.redraw()

    def _remember_interactive_positions(self, _event) -> None:
        artist = self._annotation_artist
        if artist is not None:
            try:
                x, y = artist.get_position()
                self.annotation_settings.x = float(x)
                self.annotation_settings.y = float(y)
            except Exception:
                pass

        legend = self._legend_artist
        if legend is not None:
            try:
                renderer = self.canvas.get_renderer()
                bbox = legend.get_window_extent(renderer=renderer).transformed(self.ax.transAxes.inverted())
                self.legend_settings.anchor = (float(bbox.x0), float(bbox.y1))
            except Exception:
                pass

    def _on_button_release(self, event) -> None:
        """Finish dragging, remember positions, then handle custom-name clicks.

        Renaming on button press conflicts with Matplotlib's draggable legend: the
        modal Qt dialog can open before Matplotlib receives the release event,
        leaving the legend attached to the pointer.  Handling the click here
        guarantees that the drag gesture has ended first.
        """
        self._remember_interactive_positions(event)
        if getattr(event, "button", None) != 1:
            return
        if self._legend_mode() != "Custom":
            return
        legend = self._legend_artist
        if legend is None or getattr(event, "x", None) is None or getattr(event, "y", None) is None:
            return
        texts = list(legend.get_texts() or [])
        clicked_index = None
        for idx, text in enumerate(texts):
            try:
                contains, _details = text.contains(event)
            except Exception:
                contains = False
            if contains:
                clicked_index = idx
                break
        if clicked_index is None:
            return
        self._rename_custom_legend_entry(clicked_index)

    def _rename_custom_legend_entry(self, index: int) -> None:
        """Rename one visible curve using the current legend ordering."""
        visible = [curve for curve in self._curves if curve.visible]
        if not (0 <= index < len(visible)):
            return
        curve = visible[index]
        old_text = curve.custom_name or "<select curve name>"

        # Fully detach the draggable helper before opening a modal dialog.  This
        # also clears any blitted drag copy that could otherwise remain visible.
        legend = self._legend_artist
        if legend is not None:
            try:
                legend.set_draggable(False)
            except Exception:
                pass
        try:
            self.canvas.draw()
        except Exception:
            pass

        dialog = LegendNameDialog(old_text if old_text != "<select curve name>" else "", self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_text = dialog.text().strip()
            if new_text and new_text != "<select curve name>":
                curve.custom_name = new_text
                self._rebuild_list()

        # Rebuild on both OK and Cancel.  This guarantees one clean legend and
        # reinstalls a fresh draggable helper after the modal dialog closes.
        self.redraw()

    def _on_pick(self, event) -> None:
        artist = getattr(event, "artist", None)
        mouse = getattr(event, "mouseevent", None)
        button = getattr(mouse, "button", None)
        if artist is self._annotation_artist and button == 3:
            self.edit_annotation()
            return
        legend = self._legend_artist
        if legend is None:
            return
        texts = list(legend.get_texts() or [])
        frame = legend.get_frame()
        if button == 3 and (artist in texts or artist is frame):
            self.edit_legend_style()
            return

    def _csv_dialog(self, *, save: bool) -> str:
        title = "Export CSV" if save else "Import CSV"
        initial = self._default_directory / ("plotted_data.csv" if save else "")
        dialog = QFileDialog(self, title, str(initial))
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave if save else QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile if save else QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter("CSV Files (*.csv)")
        if save:
            dialog.setDefaultSuffix("csv")
        dialog.resize(900, 600)
        dialog.setMinimumSize(700, 500)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return ""
        selected = dialog.selectedFiles()
        return selected[0] if selected else ""

    def import_csv(self) -> None:
        path = self._csv_dialog(save=False)
        if not path:
            return
        try:
            curves = import_curves_csv(path)
        except Exception as exc:
            QMessageBox.critical(self, "Import CSV", f"Could not import curves:\n{exc}")
            return
        self.set_default_directory(Path(path).parent)
        self.add_curves(curves)
        QMessageBox.information(self, "Import CSV", f"Imported {len(curves)} curve(s).")

    def export_csv(self) -> None:
        visible = [curve for curve in self._curves if curve.visible]
        if not visible:
            QMessageBox.information(self, "Export CSV", "No visible plotted curves to export.")
            return
        if self._legend_mode() == "Custom" and any(
            not curve.custom_name.strip() for curve in visible
        ):
            answer = QMessageBox.question(
                self,
                "Export CSV",
                "Some curves have generic names. Proceed?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                return
        path = self._csv_dialog(save=True)
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            names = [self._export_name_for_curve(curve) for curve in visible]
            count = export_visible_curves_csv(path, self._curves, names=names)
        except Exception as exc:
            QMessageBox.critical(self, "Export CSV", f"Could not export curves:\n{exc}")
            return
        self.set_default_directory(Path(path).parent)
        QMessageBox.information(self, "Export CSV", f"Exported {count} curve(s).")

    def _on_waterfall_toggled(self, enabled: bool) -> None:
        self.slider_waterfall.setEnabled(enabled)
        self.spin_waterfall.setEnabled(enabled)
        self.slider_waterfall_fill.setEnabled(enabled)
        self.chk_waterfall_mono.setEnabled(enabled)
        self._update_waterfall_color_button()
        self.redraw()

    def _on_waterfall_fill_changed(self, value: int) -> None:
        self.lbl_waterfall_fill.setText(f"{int(value)} %")
        self.redraw()

    def _on_waterfall_mono_toggled(self, _checked: bool) -> None:
        self._update_waterfall_color_button()
        self.redraw()

    def _update_waterfall_color_button(self) -> None:
        active = bool(self.chk_waterfall.isChecked() and self.chk_waterfall_mono.isChecked())
        self.btn_waterfall_color.setEnabled(active)
        self.btn_waterfall_color.setStyleSheet(
            "QPushButton {"
            f" background-color: {self._waterfall_mono_color};"
            " border: 1px solid #555; border-radius: 2px; padding: 0px;"
            "}"
        )

    def _choose_waterfall_mono_color(self) -> None:
        color = QColorDialog.getColor(QColor(self._waterfall_mono_color), self, "Choose waterfall curve color")
        if not color.isValid():
            return
        self._waterfall_mono_color = color.name()
        self._update_waterfall_color_button()
        self.redraw()

    def _waterfall_monochrome_enabled(self) -> bool:
        return bool(self.chk_waterfall.isChecked() and self.chk_waterfall_mono.isChecked())

    @staticmethod
    def _adaptive_waterfall_max_percent(curve_count: int) -> float:
        """Useful per-curve offset range for the current number of visible curves."""
        count = max(0, int(curve_count))
        if count <= 30:
            return 100.0
        return max(5.0, min(100.0, 3000.0 / float(count)))

    def _update_waterfall_offset_scale(self) -> None:
        visible_count = sum(1 for curve in self._curves if curve.visible)
        new_max = self._adaptive_waterfall_max_percent(visible_count)
        self._waterfall_max_percent = float(new_max)

        current = min(float(self.spin_waterfall.value()), self._waterfall_max_percent)
        self.spin_waterfall.blockSignals(True)
        self.spin_waterfall.setMaximum(self._waterfall_max_percent)
        self.spin_waterfall.setValue(current)
        self.spin_waterfall.blockSignals(False)

        slider_value = int(round(1000.0 * current / self._waterfall_max_percent)) if self._waterfall_max_percent > 0 else 0
        self.slider_waterfall.blockSignals(True)
        self.slider_waterfall.setValue(max(0, min(1000, slider_value)))
        self.slider_waterfall.blockSignals(False)

        tip = (
            f"Waterfall offset per curve. Current slider range: 0–{self._waterfall_max_percent:g}% "
            f"for {visible_count} visible curve{'s' if visible_count != 1 else ''}."
        )
        self.slider_waterfall.setToolTip(tip)
        self.spin_waterfall.setToolTip(tip + " Type an exact value if needed.")

    def _slider_preview_changed(self, value: int) -> None:
        """Update the displayed percentage during a drag without replotting."""
        percent = self._waterfall_max_percent * float(value) / 1000.0
        self.spin_waterfall.blockSignals(True)
        self.spin_waterfall.setValue(percent)
        self.spin_waterfall.blockSignals(False)

    def _slider_changed(self, value: int) -> None:
        self._slider_preview_changed(value)
        self.redraw()

    def _spin_changed(self, value: float) -> None:
        percent = max(0.0, min(float(value), self._waterfall_max_percent))
        slider_value = int(round(1000.0 * percent / self._waterfall_max_percent)) if self._waterfall_max_percent > 0 else 0
        self.slider_waterfall.blockSignals(True)
        self.slider_waterfall.setValue(max(0, min(1000, slider_value)))
        self.slider_waterfall.blockSignals(False)
        self.redraw()

    def _visible_curves_with_offsets(self) -> list[tuple[PlottedCurve, np.ndarray, float]]:
        """Return visible curves, displayed Y arrays, and each curve's waterfall baseline.

        The baseline is the minimum finite intensity of the source curve plus its
        waterfall offset.  Using the per-curve minimum keeps filled-waterfall
        occlusion local to the spectrum rather than filling down to a global zero.
        """
        visible = [curve for curve in self._curves if curve.visible]
        if not visible:
            return []
        fraction = float(self.spin_waterfall.value()) / 100.0 if self.chk_waterfall.isChecked() else 0.0
        minima = [float(np.nanmin(c.y)) for c in visible if c.y.size and np.isfinite(c.y).any()]
        maxima = [float(np.nanmax(c.y)) for c in visible if c.y.size and np.isfinite(c.y).any()]
        if not minima or not maxima:
            return [(curve, curve.y, 0.0) for curve in visible]
        full_range = max(maxima) - min(minima)
        step = fraction * full_range if np.isfinite(full_range) and full_range > 0 else 0.0
        rows: list[tuple[PlottedCurve, np.ndarray, float]] = []
        for idx, curve in enumerate(visible):
            offset = idx * step
            y_display = curve.y + offset
            finite = curve.y[np.isfinite(curve.y)] if curve.y.size else np.asarray([])
            baseline = float(np.nanmin(finite)) + offset if finite.size else offset
            rows.append((curve, y_display, baseline))
        return rows

    def _apply_grid(self) -> None:
        mode = self.cmb_grid.currentText()
        if mode == "None":
            self.ax.grid(False, which="both")
            return
        self.ax.grid(True, which="major", linewidth=1.05, alpha=0.60)
        if mode in {"Fine", "Finest"}:
            subdivisions = 2 if mode == "Fine" else 5
            self.ax.xaxis.set_minor_locator(AutoMinorLocator(subdivisions))
            self.ax.yaxis.set_minor_locator(AutoMinorLocator(subdivisions))
            self.ax.grid(True, which="minor", linestyle="--", linewidth=0.72, alpha=0.38)

    def _apply_plot_margins(self) -> None:
        """Use stable margins instead of tight_layout for the interactive plotting panel."""
        try:
            self.figure.subplots_adjust(left=0.085, right=0.985, bottom=0.105, top=0.965)
        except Exception:
            pass

    def redraw(self, *_args) -> None:
        self._update_waterfall_offset_scale()
        self.figure.clear()
        self._legend_artist = None
        self.ax = self.figure.add_subplot(111)
        if not self._curves:
            self.ax.set_xlabel("Energy")
            self.ax.set_ylabel("Intensity")
            self.ax.text(0.5, 0.5, "Pass curves from Processed Data", transform=self.ax.transAxes,
                         ha="center", va="center")
            self._apply_grid()
            self._apply_plot_margins()
            self.canvas.draw_idle()
            return

        first = self._curves[0]
        default_xlabel = normalize_energy_xlabel(first.xlabel, first.energy_scale)
        default_ylabel = first.ylabel
        self.ax.set_xlabel(default_xlabel)
        self.ax.set_ylabel(default_ylabel)
        legend_mode = self._legend_mode()
        waterfall_rows = self._visible_curves_with_offsets()
        fill_alpha = (
            self.slider_waterfall_fill.value() / 100.0
            if self.chk_waterfall.isChecked()
            else 0.0
        )
        # Filled waterfall is a pseudo-depth view: draw the highest-offset spectra
        # first, then progressively lower spectra so foreground ridges can occlude
        # those behind them.  At Filling=0 the result is the ordinary line waterfall.
        rows_to_draw = list(reversed(waterfall_rows)) if fill_alpha > 0 else waterfall_rows
        fill_color = self.ax.get_facecolor()
        for draw_idx, (curve, y_display, baseline) in enumerate(rows_to_draw):
            label = None
            if legend_mode == "Curve name":
                label = curve.title or None
            elif legend_mode == "Custom":
                label = curve.custom_name or "<select curve name>"
            plot_color = self._waterfall_mono_color if self._waterfall_monochrome_enabled() else curve.color
            if fill_alpha > 0 and curve.x.size and y_display.size:
                self.ax.fill_between(
                    curve.x,
                    baseline,
                    y_display,
                    facecolor=fill_color,
                    alpha=fill_alpha,
                    linewidth=0.0,
                    zorder=2 * draw_idx,
                )
            effective_width = self._effective_curve_width(curve)
            kwargs = dict(
                color=plot_color, linewidth=effective_width, label=label,
                zorder=(2 * draw_idx + 1) if fill_alpha > 0 else 2,
            )
            if curve.linestyle == "None":
                kwargs.update(linestyle="None", marker="o", markersize=max(2.0, effective_width * 2.0))
            else:
                kwargs.update(linestyle=curve.linestyle)
            self.ax.plot(curve.x, y_display, **kwargs)

        if legend_mode != "None" and self.ax.lines:
            handles, labels = self.ax.get_legend_handles_labels()
            # Filled waterfall is drawn back-to-front for occlusion, but the
            # legend should continue to follow the user's plotted-curve order.
            if fill_alpha > 0:
                handles = list(reversed(handles))
                labels = list(reversed(labels))
            if labels:
                st = self.legend_settings.style
                legend_kwargs = dict(
                    fontsize=int(st.get("fontsize", 10)),
                    frameon=True,
                    framealpha=float(st.get("alpha", 1.0)),
                    borderpad=float(st.get("borderpad", 0.4)),
                )
                if self.legend_settings.anchor is not None:
                    legend_kwargs.update(
                        loc="upper left",
                        bbox_to_anchor=self.legend_settings.anchor,
                        bbox_transform=self.ax.transAxes,
                    )
                else:
                    legend_kwargs["loc"] = self.legend_settings.location
                self._legend_artist = self.ax.legend(**legend_kwargs)
                self._legend_artist.set_draggable(True, use_blit=False)
                try:
                    self._legend_artist.get_frame().set_picker(True)
                    for text in self._legend_artist.get_texts():
                        text.set_picker(5)
                        text.set_fontweight("bold" if bool(st.get("bold", False)) else "normal")
                        text.set_fontstyle("italic" if bool(st.get("italic", False)) else "normal")
                        text.set_underline(bool(st.get("underline", False)))
                except Exception:
                    pass
        self._apply_grid()
        if self.chk_reverse_x.isChecked() and not self.ax.xaxis_inverted():
            self.ax.invert_xaxis()
        elif not self.chk_reverse_x.isChecked() and self.ax.xaxis_inverted():
            self.ax.invert_xaxis()
        self._annotation_artist = None
        ann = self.annotation_settings
        if ann.visible and ann.text.strip():
            st = ann.style
            bbox = None
            if bool(st.get("bg_enabled", True)):
                bbox = {
                    "facecolor": st.get("bg_color", "#FFFFFF"),
                    "edgecolor": st.get("border_color", "#000000") if bool(st.get("border_enabled", True)) else "none",
                    "linewidth": float(st.get("border_width", 0.8)),
                    "boxstyle": f"round,pad={float(st.get('pad', 0.30))}",
                }
            self._annotation_artist = self.ax.annotate(
                ann.text, xy=(ann.x, ann.y), xycoords="axes fraction", ha="left", va="top",
                fontsize=int(st.get("fontsize", 12)),
                fontweight="bold" if bool(st.get("bold", False)) else "normal",
                fontstyle="italic" if bool(st.get("italic", False)) else "normal",
                color=st.get("font_color", "#000000"), bbox=bbox, annotation_clip=False, zorder=10000,
            )
            try: self._annotation_artist.set_underline(bool(st.get("underline", False)))
            except Exception: pass
            self._annotation_artist.set_picker(True)
            self._annotation_artist.draggable(use_blit=True)
        self._apply_plot_margins()
        self.canvas.draw_idle()
