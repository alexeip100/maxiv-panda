from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QPushButton, QSplitter, QTableWidget, QTextEdit,
    QTreeWidget, QVBoxLayout, QWidget,
)

from ...ui import PlotArea
from . import batch_analysis, batch_analysis_constraints, batch_analysis_export, batch_analysis_plot, batch_analysis_trends, batch_trend_models


class BatchAnalyzeMixin:
    """Analyze-tab construction and result-analysis workflow delegates."""

    def _build_analyze_tab(self, parent: QWidget) -> None:
        """Build result-analysis tab for trend plots, constraints, trend fitting, and export."""
        lay = QVBoxLayout(parent)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        outer = QSplitter(Qt.Orientation.Horizontal, parent)
        outer.setChildrenCollapsible(False)
        outer.setHandleWidth(8)
        lay.addWidget(outer, 1)

        main = self._build_analyze_main_panel(outer)
        trend_panel = self._build_analyze_trend_panel(outer)

        outer.addWidget(main)
        outer.addWidget(trend_panel)
        try:
            outer.setStretchFactor(0, 4)
            outer.setStretchFactor(1, 1)
            outer.setSizes([1000, 260])
        except Exception:
            pass
        self._on_trend_fit_model_changed()

    def _build_analyze_main_panel(self, parent: QWidget) -> QWidget:
        main = QWidget(parent)
        main_lay = QVBoxLayout(main)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(6)
        main_lay.addWidget(self._build_analyze_top_bar(main), 0)

        split = QSplitter(Qt.Orientation.Horizontal, main)
        split.setChildrenCollapsible(False)
        split.setHandleWidth(8)
        main_lay.addWidget(split, 1)

        left = self._build_analyze_parameter_panel(split)
        self.plot_analyze_trend = PlotArea(split)
        self._make_plot_area_expand(self.plot_analyze_trend)
        self.plot_analyze_trend.clear("Run a batch fit, then select parameter trends to plot")
        self._style_prepare_plot_area(self.plot_analyze_trend)
        split.addWidget(left)
        split.addWidget(self.plot_analyze_trend)
        try:
            split.setStretchFactor(0, 0)
            split.setStretchFactor(1, 1)
            split.setSizes([300, 900])
        except Exception:
            pass
        return main

    def _build_analyze_top_bar(self, parent: QWidget) -> QWidget:
        top = QWidget(parent)
        top_lay = QHBoxLayout(top)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(8)

        top_lay.addWidget(QLabel("Result pass:", top), 0)
        self.cb_analyze_result_pass = QComboBox(top)
        self.cb_analyze_result_pass.setMinimumWidth(210)
        self.cb_analyze_result_pass.setToolTip("Select which completed batch pass is used for trend plotting.")
        self.cb_analyze_result_pass.currentIndexChanged.connect(self._on_analyze_result_pass_changed)
        top_lay.addWidget(self.cb_analyze_result_pass, 0)

        self.lab_analyze_status = QLabel("No batch-fit results in memory yet.", top)
        self.lab_analyze_status.setWordWrap(True)
        top_lay.addWidget(self.lab_analyze_status, 1)

        top_lay.addWidget(QLabel("Y parameter:", top), 0)
        self.cb_analyze_parameter_type = QComboBox(top)
        self.cb_analyze_parameter_type.setMinimumWidth(170)
        self.cb_analyze_parameter_type.currentIndexChanged.connect(self._on_analyze_parameter_type_changed)
        top_lay.addWidget(self.cb_analyze_parameter_type, 0)
        return top

    def _build_analyze_parameter_panel(self, parent: QWidget) -> QWidget:
        left = QWidget(parent)
        left.setMinimumWidth(230)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(4)
        lbl = QLabel(
            "Select one or several parameters of the chosen type. "
            "The X axis is the spectrum number in the fitted sequence.",
            left,
        )
        lbl.setWordWrap(True)
        left_lay.addWidget(lbl, 0)

        self.tree_analyze_parameters = QTreeWidget(left)
        self.tree_analyze_parameters.setColumnCount(1)
        self.tree_analyze_parameters.setHeaderLabels(["Parameters to plot"])
        self.tree_analyze_parameters.itemChanged.connect(self._on_analyze_parameter_item_changed)
        left_lay.addWidget(self.tree_analyze_parameters, 1)
        left_lay.addWidget(self._build_next_pass_controls(left), 0)
        return left

    def _build_next_pass_controls(self, parent: QWidget) -> QWidget:
        smooth_box = QWidget(parent)
        smooth_lay = QGridLayout(smooth_box)
        smooth_lay.setContentsMargins(6, 6, 6, 6)
        smooth_lay.setHorizontalSpacing(6)
        smooth_lay.setVerticalSpacing(4)
        smooth_title = QLabel("Trend smoothing / next pass", smooth_box)
        try:
            smooth_title.setStyleSheet("font-weight: bold;")
        except Exception:
            pass
        smooth_lay.addWidget(smooth_title, 0, 0, 1, 3)
        smooth_lay.addWidget(QLabel("Target:", smooth_box), 1, 0)
        self.cb_smooth_target = QComboBox(smooth_box)
        self.cb_smooth_target.setMinimumWidth(160)
        self.cb_smooth_target.setToolTip("Select one plotted independent parameter to smooth and use as a fixed constraint in the next pass. Derived SO-doublet minor members remain plottable but are omitted here.")
        smooth_lay.addWidget(self.cb_smooth_target, 1, 1, 1, 2)
        smooth_lay.addWidget(QLabel("Polynomial order:", smooth_box), 2, 0)
        self.cb_smooth_poly_order = QComboBox(smooth_box)
        for order in (0, 1, 2, 3):
            self.cb_smooth_poly_order.addItem(str(order), order)
        self.cb_smooth_poly_order.setCurrentIndex(0)
        smooth_lay.addWidget(self.cb_smooth_poly_order, 2, 1)
        self.chk_smooth_success_only = QCheckBox("Use only successful/warning fits", smooth_box)
        self.chk_smooth_success_only.setChecked(True)
        smooth_lay.addWidget(self.chk_smooth_success_only, 3, 0, 1, 3)
        self.chk_smooth_clip_bounds = QCheckBox("Clip desired values to table bounds", smooth_box)
        self.chk_smooth_clip_bounds.setChecked(True)
        smooth_lay.addWidget(self.chk_smooth_clip_bounds, 4, 0, 1, 3)
        self.btn_fit_smooth_trend = QPushButton("Fit smooth trend", smooth_box)
        self.btn_fit_smooth_trend.clicked.connect(self._fit_selected_smooth_trend)
        smooth_lay.addWidget(self.btn_fit_smooth_trend, 5, 0, 1, 2)
        self.btn_add_next_constraint = QPushButton("Add/update constraint", smooth_box)
        self.btn_add_next_constraint.clicked.connect(self._add_update_next_pass_constraint)
        smooth_lay.addWidget(self.btn_add_next_constraint, 5, 2)
        self.tbl_next_constraints = QTableWidget(0, 5, smooth_box)
        self.tbl_next_constraints.setHorizontalHeaderLabels(["Use", "Parameter", "Source", "Model", "RMS"])
        self.tbl_next_constraints.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        try:
            self.tbl_next_constraints.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            self.tbl_next_constraints.horizontalHeader().setStretchLastSection(True)
        except Exception:
            pass
        smooth_lay.addWidget(self.tbl_next_constraints, 6, 0, 1, 3)
        self.btn_prepare_next_pass = QPushButton("Prepare next pass", smooth_box)
        self.btn_prepare_next_pass.clicked.connect(self._prepare_next_constrained_pass)
        smooth_lay.addWidget(self.btn_prepare_next_pass, 7, 0, 1, 3)
        self.lab_smooth_status = QLabel("Fit a smooth trend, add it as a constraint, then prepare the next pass.", smooth_box)
        self.lab_smooth_status.setWordWrap(True)
        smooth_lay.addWidget(self.lab_smooth_status, 8, 0, 1, 3)
        return smooth_box

    def _build_analyze_trend_panel(self, parent: QWidget) -> QWidget:
        trend_panel = QWidget(parent)
        trend_panel.setMinimumWidth(250)
        trend_lay = QVBoxLayout(trend_panel)
        trend_lay.setContentsMargins(8, 4, 4, 4)
        trend_lay.setSpacing(6)
        trend_title = QLabel("Trend analysis and export", trend_panel)
        try:
            trend_title.setStyleSheet("font-weight: bold; font-size: 11pt;")
        except Exception:
            pass
        trend_lay.addWidget(trend_title, 0)
        trend_note = QLabel(
            "Analytical fits are for plotting/export only and do not affect next-pass constraints.",
            trend_panel,
        )
        trend_note.setWordWrap(True)
        trend_lay.addWidget(trend_note, 0)

        trend_lay.addWidget(QLabel("Trend curve:", trend_panel), 0)
        self.cb_trend_fit_target = QComboBox(trend_panel)
        self.cb_trend_fit_target.setToolTip("Select one of the currently shown trend curves for analytical fitting.")
        self.cb_trend_fit_target.currentIndexChanged.connect(self._on_trend_fit_target_changed)
        trend_lay.addWidget(self.cb_trend_fit_target, 0)

        trend_lay.addWidget(QLabel("Model:", trend_panel), 0)
        self.cb_trend_fit_model = QComboBox(trend_panel)
        for code, label in batch_trend_models.available_models():
            self.cb_trend_fit_model.addItem(label, code)
        self.cb_trend_fit_model.currentIndexChanged.connect(self._on_trend_fit_model_changed)
        trend_lay.addWidget(self.cb_trend_fit_model, 0)

        self.lab_trend_fit_formula = QLabel("", trend_panel)
        self.lab_trend_fit_formula.setWordWrap(True)
        self.lab_trend_fit_formula.setToolTip(
            "Analytical model used for the selected trend fit. x₀ is fixed to the first finite spectrum number used in the trend."
        )
        try:
            self.lab_trend_fit_formula.setStyleSheet(
                ""
                "background: palette(alternate-base); color: palette(text); border: 1px solid palette(mid); "
                "border-radius: 4px; padding: 4px;"
            )
        except Exception:
            pass
        trend_lay.addWidget(self.lab_trend_fit_formula, 0)

        order_row = QWidget(trend_panel)
        order_lay = QHBoxLayout(order_row)
        order_lay.setContentsMargins(0, 0, 0, 0)
        order_lay.addWidget(QLabel("Polynomial order:", order_row), 0)
        self.cb_trend_fit_poly_order = QComboBox(order_row)
        for order in range(0, 6):
            self.cb_trend_fit_poly_order.addItem(str(order), order)
        self.cb_trend_fit_poly_order.setCurrentIndex(1)
        self.cb_trend_fit_poly_order.currentIndexChanged.connect(self._on_trend_fit_model_changed)
        order_lay.addWidget(self.cb_trend_fit_poly_order, 1)
        trend_lay.addWidget(order_row, 0)
        self._trend_fit_order_row = order_row

        self.chk_trend_fit_success_only = QCheckBox("Use only successful/warning fits", trend_panel)
        self.chk_trend_fit_success_only.setChecked(True)
        trend_lay.addWidget(self.chk_trend_fit_success_only, 0)

        self.btn_fit_analysis_trend = QPushButton("Fit selected trend", trend_panel)
        self.btn_fit_analysis_trend.clicked.connect(self._fit_selected_analysis_trend)
        trend_lay.addWidget(self.btn_fit_analysis_trend, 0)
        self.btn_accept_analysis_trend = QPushButton("Accept/store fit for export", trend_panel)
        self.btn_accept_analysis_trend.clicked.connect(self._accept_trend_analysis_fit)
        trend_lay.addWidget(self.btn_accept_analysis_trend, 0)
        self.btn_clear_selected_analysis_trend = QPushButton("Clear selected stored fit", trend_panel)
        self.btn_clear_selected_analysis_trend.clicked.connect(self._clear_selected_trend_analysis_fit)
        trend_lay.addWidget(self.btn_clear_selected_analysis_trend, 0)
        self.btn_clear_all_analysis_trends = QPushButton("Clear all stored fits", trend_panel)
        self.btn_clear_all_analysis_trends.clicked.connect(self._clear_all_trend_analysis_fits)
        trend_lay.addWidget(self.btn_clear_all_analysis_trends, 0)

        self.lab_trend_fit_quality = QLabel("Fit quality: nRMSE = n/a", trend_panel)
        self.lab_trend_fit_quality.setWordWrap(True)
        trend_lay.addWidget(self.lab_trend_fit_quality, 0)
        self.txt_trend_fit_summary = QTextEdit(trend_panel)
        self.txt_trend_fit_summary.setReadOnly(True)
        self.txt_trend_fit_summary.setMinimumHeight(170)
        self.txt_trend_fit_summary.setPlaceholderText("Fit summaries will appear here.")
        trend_lay.addWidget(self.txt_trend_fit_summary, 1)

        self.btn_export_analyze_trends = QPushButton("Export CSV", trend_panel)
        self.btn_export_analyze_trends.setToolTip("Export the shown raw trends and accepted analytical trend fits as CSV.")
        self.btn_export_analyze_trends.clicked.connect(self._export_analyze_trends_csv)
        trend_lay.addWidget(self.btn_export_analyze_trends, 0)

        self.btn_export_all_batch_fits = QPushButton("Export all fits...", trend_panel)
        self.btn_export_all_batch_fits.setEnabled(False)
        self.btn_export_all_batch_fits.setToolTip(
            "Export all stored full fit curves from the selected result pass as one ZIP archive "
            "containing one CSV per spectrum plus batch_manifest.csv."
        )
        self.btn_export_all_batch_fits.clicked.connect(self._export_all_batch_fits_zip)
        trend_lay.addWidget(self.btn_export_all_batch_fits, 0)
        return trend_panel

    def _available_analyze_parameter_types(self, *args, **kwargs):
        return batch_analysis._available_analyze_parameter_types(self, *args, **kwargs)

    def _refresh_analyze_results_tab(self, *args, **kwargs):
        return batch_analysis._refresh_analyze_results_tab(self, *args, **kwargs)

    def _on_analyze_parameter_type_changed(self, *args, **kwargs):
        return batch_analysis_plot._on_analyze_parameter_type_changed(self, *args, **kwargs)

    def _on_analyze_parameter_item_changed(self, *args, **kwargs):
        return batch_analysis_plot._on_analyze_parameter_item_changed(self, *args, **kwargs)

    def _populate_analyze_parameter_tree(self, *args, **kwargs):
        return batch_analysis_plot._populate_analyze_parameter_tree(self, *args, **kwargs)

    def _selected_analyze_series(self, *args, **kwargs):
        return batch_analysis_plot._selected_analyze_series(self, *args, **kwargs)

    def _value_for_analyze_series(self, *args, **kwargs):
        return batch_analysis_plot._value_for_analyze_series(self, *args, **kwargs)

    def _update_analyze_trend_plot(self, *args, **kwargs):
        return batch_analysis_plot._update_analyze_trend_plot(self, *args, **kwargs)

    def _export_analyze_trends_csv(self, *args, **kwargs):
        return batch_analysis_export._export_analyze_trends_csv(self, *args, **kwargs)

    def _export_all_batch_fits_zip(self, *args, **kwargs):
        return batch_analysis_export._export_all_batch_fits_zip(self, *args, **kwargs)

    def _derived_so_minor_peak_indices(self, *args, **kwargs):
        return batch_analysis_constraints._derived_so_minor_peak_indices(self, *args, **kwargs)

    def _is_derived_so_minor_target(self, *args, **kwargs):
        return batch_analysis_constraints._is_derived_so_minor_target(self, *args, **kwargs)

    def _refresh_smoothing_target_combo(self, *args, **kwargs):
        return batch_analysis_constraints._refresh_smoothing_target_combo(self, *args, **kwargs)

    def _current_smoothing_target(self, *args, **kwargs):
        return batch_analysis_constraints._current_smoothing_target(self, *args, **kwargs)

    def _target_sort_key(self, *args, **kwargs):
        return batch_analysis_constraints._target_sort_key(self, *args, **kwargs)

    def _target_short_label(self, *args, **kwargs):
        return batch_analysis_constraints._target_short_label(self, *args, **kwargs)

    def _collect_trend_points_for_target(self, *args, **kwargs):
        return batch_analysis_constraints._collect_trend_points_for_target(self, *args, **kwargs)

    def _table_bounds_for_target(self, *args, **kwargs):
        return batch_analysis_constraints._table_bounds_for_target(self, *args, **kwargs)

    def _fit_selected_smooth_trend(self, *args, **kwargs):
        return batch_analysis_constraints._fit_selected_smooth_trend(self, *args, **kwargs)

    def _add_update_next_pass_constraint(self, *args, **kwargs):
        return batch_analysis_constraints._add_update_next_pass_constraint(self, *args, **kwargs)

    def _refresh_next_constraints_table(self, *args, **kwargs):
        return batch_analysis_constraints._refresh_next_constraints_table(self, *args, **kwargs)

    def _enabled_next_constraints_from_table(self, *args, **kwargs):
        return batch_analysis_constraints._enabled_next_constraints_from_table(self, *args, **kwargs)

    def _constraint_compact_list(self, *args, **kwargs):
        return batch_analysis_constraints._constraint_compact_list(self, *args, **kwargs)

    def _next_strategy_pass_number(self, *args, **kwargs):
        return batch_analysis_constraints._next_strategy_pass_number(self, *args, **kwargs)

    def _prepare_next_constrained_pass(self, *args, **kwargs):
        return batch_analysis_constraints._prepare_next_constrained_pass(self, *args, **kwargs)


    def _refresh_trend_fit_target_combo(self, *args, **kwargs):
        return batch_analysis_trends._refresh_trend_fit_target_combo(self, *args, **kwargs)

    def _on_trend_fit_target_changed(self, *args, **kwargs):
        return batch_analysis_trends._on_trend_fit_target_changed(self, *args, **kwargs)

    def _on_trend_fit_model_changed(self, *args, **kwargs):
        return batch_analysis_trends._on_trend_fit_model_changed(self, *args, **kwargs)

    def _fit_selected_analysis_trend(self, *args, **kwargs):
        return batch_analysis_trends._fit_selected_analysis_trend(self, *args, **kwargs)

    def _accept_trend_analysis_fit(self, *args, **kwargs):
        return batch_analysis_trends._accept_trend_analysis_fit(self, *args, **kwargs)

    def _clear_selected_trend_analysis_fit(self, *args, **kwargs):
        return batch_analysis_trends._clear_selected_trend_analysis_fit(self, *args, **kwargs)

    def _clear_all_trend_analysis_fits(self, *args, **kwargs):
        return batch_analysis_trends._clear_all_trend_analysis_fits(self, *args, **kwargs)

    def _update_trend_analysis_summary(self, *args, **kwargs):
        return batch_analysis_trends._update_trend_analysis_summary(self, *args, **kwargs)
