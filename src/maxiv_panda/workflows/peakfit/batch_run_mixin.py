from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHeaderView, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QSpinBox, QSplitter, QTableWidget, QVBoxLayout,
    QWidget,
)

from ...ui import PlotArea
from . import batch_config, batch_config_core, batch_passes
from . import batch_peak_only_config, batch_peak_only_runner
from . import batch_runner, batch_runner_core

class BatchRunMixin:
    """Run-tab, configuration, pass, and batch-execution behavior for BatchFitDialog."""

    def _build_run_tab(self, parent: QWidget) -> None:
        """Build the Run tab scaffold: controls/table on the left and monitor plot on the right."""
        lay = QVBoxLayout(parent)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        main_split = QSplitter(Qt.Orientation.Horizontal, parent)
        main_split.setChildrenCollapsible(False)
        main_split.setHandleWidth(8)
        try:
            main_split.setOpaqueResize(True)
        except Exception:
            pass
        lay.addWidget(main_split, 1)

        left = QWidget(main_split)
        left.setMinimumWidth(560)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        # Run-control strip belongs to the table side only.  This keeps the
        # monitor plot on the right free to use the full available height.
        ctrl = QWidget(left)
        # Keep the run controls compact.  A single long horizontal strip became
        # too wide once full-result storage was added, especially when the
        # left side of the splitter is narrowed.  Use two short rows instead:
        # actions/options on top, progress/status below.
        ctrl_lay = QVBoxLayout(ctrl)
        ctrl_lay.setContentsMargins(0, 0, 0, 0)
        ctrl_lay.setSpacing(3)

        ctrl_top = QHBoxLayout()
        ctrl_top.setContentsMargins(0, 0, 0, 0)
        ctrl_top.setSpacing(5)
        ctrl_bottom = QHBoxLayout()
        ctrl_bottom.setContentsMargins(0, 0, 0, 0)
        ctrl_bottom.setSpacing(5)

        self.btn_validate_batch_setup = QPushButton("Validate setup", ctrl)
        self.btn_validate_batch_setup.setEnabled(False)
        self.btn_validate_batch_setup.setToolTip("Optional pre-check: validate the editable batch setup table without starting the fit.")
        self.btn_validate_batch_setup.clicked.connect(lambda _checked=False: self._validate_and_build_batch_config(show_messages=True))
        ctrl_top.addWidget(self.btn_validate_batch_setup, 0)

        ctrl_top.addWidget(QLabel("Strategy:", ctrl), 0)
        self.cb_batch_strategy = QComboBox(ctrl)
        self.cb_batch_strategy.setMinimumWidth(180)
        self.cb_batch_strategy.setMaximumWidth(250)
        self.cb_batch_strategy.setToolTip("Select the pass strategy to execute. For now this starts with Pass 1: independent; later versions will add constrained pass recipes here.")
        self.cb_batch_strategy.currentIndexChanged.connect(self._on_batch_strategy_changed)
        ctrl_top.addWidget(self.cb_batch_strategy, 1)

        self.chk_batch_live_preview = QCheckBox("Live preview", ctrl)
        self.chk_batch_live_preview.setChecked(True)
        self.chk_batch_live_preview.setToolTip("Update the monitor plot after each fitted spectrum once batch fitting is implemented.")
        ctrl_top.addWidget(self.chk_batch_live_preview, 0)

        self.chk_batch_store_all_results = QCheckBox("Store all fit results", ctrl)
        self.chk_batch_store_all_results.setChecked(False)
        self.chk_batch_store_all_results.setToolTip(
            "Retain the fitted curve, background, residual and individual peak components for every spectrum. "
            "This enables post-run fit navigation and Export all fits; it uses more memory."
        )
        ctrl_top.addWidget(self.chk_batch_store_all_results, 0)

        self.btn_run_batch_fit = QPushButton("Run batch fit", ctrl)
        self.btn_run_batch_fit.setEnabled(False)
        self.btn_run_batch_fit.setToolTip("Run independent fits for all spectra from the generated initial guesses.")
        self.btn_run_batch_fit.clicked.connect(self._run_selected_batch_strategy)
        ctrl_top.addWidget(self.btn_run_batch_fit, 0)

        self.btn_stop_batch_fit = QPushButton("Stop", ctrl)
        self.btn_stop_batch_fit.setEnabled(False)
        self.btn_stop_batch_fit.setToolTip("Stop after the current spectrum finishes.")
        self.btn_stop_batch_fit.clicked.connect(self._request_stop_batch_fit)
        ctrl_top.addWidget(self.btn_stop_batch_fit, 0)

        self.progress_batch_fit = QProgressBar(ctrl)
        self.progress_batch_fit.setRange(0, 100)
        self.progress_batch_fit.setValue(0)
        self.progress_batch_fit.setTextVisible(True)
        self.progress_batch_fit.setMinimumWidth(100)
        ctrl_bottom.addWidget(self.progress_batch_fit, 1)

        self.lab_batch_run_status = QLabel("Batch setup not created.", ctrl)
        self.lab_batch_run_status.setMinimumWidth(120)
        ctrl_bottom.addWidget(self.lab_batch_run_status, 0)

        ctrl_lay.addLayout(ctrl_top)
        ctrl_lay.addLayout(ctrl_bottom)
        left_lay.addWidget(ctrl, 0)

        self.lab_batch_pass_status = QLabel("Pass status: no batch pass prepared yet.", left)
        self.lab_batch_pass_status.setWordWrap(True)
        self.lab_batch_pass_status.setStyleSheet(
            "QLabel { background: #eef7ee; color: #244b2a; border: 1px solid #a7c7a7; padding: 5px; }"
        )
        left_lay.addWidget(self.lab_batch_pass_status, 0)

        self.lab_run_instructions = QLabel(
            "Review and edit the proposed batch-fit setup before running the sequence fit. "
            "Each row defines how one peak or background parameter will be initialized and constrained across the selected sequence. "
            "Use the Start/Middle/End columns as anchor references, adjust Min/Max/Mode/Tie if needed, then press Run. The Validate setup button is only an optional pre-check.",
            left,
        )
        self.lab_run_instructions.setWordWrap(True)
        left_lay.addWidget(self.lab_run_instructions, 0)

        self.lab_batch_setup_summary = QLabel("Batch setup has not been created yet.", left)
        self.lab_batch_setup_summary.setWordWrap(True)
        self.lab_batch_setup_summary.setStyleSheet(
            "QLabel { background: #f4f7fb; color: #263f5a; border: 1px solid #b8c4d6; padding: 5px; }"
        )
        left_lay.addWidget(self.lab_batch_setup_summary, 0)

        self.lab_batch_warnings = QLabel("", left)
        self.lab_batch_warnings.setWordWrap(True)
        self.lab_batch_warnings.setStyleSheet(
            "QLabel { background: #fff8dc; color: #5e4900; border: 1px solid #d0b060; padding: 5px; }"
        )
        self.lab_batch_warnings.setVisible(False)
        left_lay.addWidget(self.lab_batch_warnings, 0)

        self.tbl_batch_parameters = QTableWidget(0, 13, left)
        self.tbl_batch_parameters.setHorizontalHeaderLabels([
            "Peak / BG", "Parameter", "Presence", "Start", "Middle", "End",
            "Initial", "Initial strategy", "Min", "Max", "Mode", "Tie / Link", "Notes"
        ])
        self.tbl_batch_parameters.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # Use one explicit editing policy for both batch-setup paths.  Do not
        # rely on platform/style-dependent QTableWidget defaults: editable
        # parameter cells must enter edit mode on a selected click, double
        # click, typing, or the standard edit key.  Individual read-only
        # cells (including derived SO-doublet members) are still protected by
        # their QTableWidgetItem flags.
        self.tbl_batch_parameters.setEditTriggers(
            QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.tbl_batch_parameters.setAlternatingRowColors(True)
        self.tbl_batch_parameters.itemChanged.connect(self._on_batch_table_edited)
        try:
            hdr = self.tbl_batch_parameters.horizontalHeader()
            # Make all batch-parameter columns user-resizable by dragging the
            # vertical header separators.  Fixed ResizeToContents/Stretch modes
            # prevent manual width adjustment, which is inconvenient for long
            # parameter notes and tie expressions.
            hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            hdr.setSectionsMovable(False)
            hdr.setStretchLastSection(False)
            default_widths = [86, 82, 72, 76, 76, 76, 76, 118, 72, 72, 76, 118, 190]
            for col, width in enumerate(default_widths):
                self.tbl_batch_parameters.setColumnWidth(col, int(width))
        except Exception:
            pass
        left_lay.addWidget(self.tbl_batch_parameters, 1)

        right = QWidget(main_split)
        right.setMinimumWidth(360)
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(4)
        self.plot_batch_monitor = PlotArea(right)
        self._make_plot_area_expand(self.plot_batch_monitor)
        self.plot_batch_monitor.clear("Batch fit monitor: run a sequence fit to see live results")
        self._style_prepare_plot_area(self.plot_batch_monitor)
        self._compact_plot_margins(self.plot_batch_monitor)
        right_lay.addWidget(self.plot_batch_monitor, 1)

        nav = QWidget(right)
        nav_lay = QHBoxLayout(nav)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(6)
        nav_lay.addStretch(1)
        nav_lay.addWidget(QLabel("Fit:", nav), 0)
        self.btn_batch_fit_prev = QPushButton("◀", nav)
        self.btn_batch_fit_prev.setFixedWidth(36)
        self.btn_batch_fit_prev.setEnabled(False)
        self.btn_batch_fit_prev.setToolTip("Show the previous stored fit in this pass.")
        self.btn_batch_fit_prev.clicked.connect(lambda _checked=False: self._step_batch_fit_navigation(-1))
        nav_lay.addWidget(self.btn_batch_fit_prev, 0)
        self.sb_batch_fit_nav = QSpinBox(nav)
        self.sb_batch_fit_nav.setRange(1, 1)
        self.sb_batch_fit_nav.setValue(1)
        self.sb_batch_fit_nav.setFixedWidth(72)
        self.sb_batch_fit_nav.setEnabled(False)
        self.sb_batch_fit_nav.setToolTip("Jump to a stored fit by its position in the fitted sequence.")
        self.sb_batch_fit_nav.valueChanged.connect(self._on_batch_fit_navigation_changed)
        nav_lay.addWidget(self.sb_batch_fit_nav, 0)
        self.lab_batch_fit_nav_total = QLabel("/ 0", nav)
        nav_lay.addWidget(self.lab_batch_fit_nav_total, 0)
        self.btn_batch_fit_next = QPushButton("▶", nav)
        self.btn_batch_fit_next.setFixedWidth(36)
        self.btn_batch_fit_next.setEnabled(False)
        self.btn_batch_fit_next.setToolTip("Show the next stored fit in this pass.")
        self.btn_batch_fit_next.clicked.connect(lambda _checked=False: self._step_batch_fit_navigation(1))
        nav_lay.addWidget(self.btn_batch_fit_next, 0)
        self.lab_batch_fit_nav_detail = QLabel("", nav)
        self.lab_batch_fit_nav_detail.setMinimumWidth(120)
        nav_lay.addWidget(self.lab_batch_fit_nav_detail, 1)
        right_lay.addWidget(nav, 0)

        main_split.addWidget(left)
        main_split.addWidget(right)
        try:
            main_split.setStretchFactor(0, 3)
            main_split.setStretchFactor(1, 2)
            main_split.setSizes([780, 520])
        except Exception:
            pass

    def _on_batch_table_edited(self, *args) -> None:
        """Mark the internal batch config as stale after the editable setup table changes."""
        if bool(getattr(self, "_populating_batch_table", False)):
            return
        self._clear_batch_config_and_guesses()
        try:
            if bool(getattr(self, "_batch_setup_created", False)):
                self.lab_batch_run_status.setText("Batch setup edited; press Run to auto-validate and fit.")
        except Exception:
            pass

    def _default_independent_strategy(self, *args, **kwargs):
        return batch_passes._default_independent_strategy(self, *args, **kwargs)

    def _reset_batch_pass_workflow(self, *args, **kwargs):
        return batch_passes._reset_batch_pass_workflow(self, *args, **kwargs)

    def _pass_by_id(self, *args, **kwargs):
        return batch_passes._pass_by_id(self, *args, **kwargs)

    def _strategy_by_id(self, *args, **kwargs):
        return batch_passes._strategy_by_id(self, *args, **kwargs)

    def _current_strategy(self, *args, **kwargs):
        return batch_passes._current_strategy(self, *args, **kwargs)

    def _refresh_strategy_combo(self, *args, **kwargs):
        return batch_passes._refresh_strategy_combo(self, *args, **kwargs)

    def _on_batch_strategy_changed(self, *args, **kwargs):
        return batch_passes._on_batch_strategy_changed(self, *args, **kwargs)

    def _refresh_pass_status_label(self, *args, **kwargs):
        return batch_passes._refresh_pass_status_label(self, *args, **kwargs)

    def _set_active_batch_results(self, *args, **kwargs):
        return batch_passes._set_active_batch_results(self, *args, **kwargs)

    def _current_binning_metadata_for_pass(self, *args, **kwargs):
        return batch_passes._current_binning_metadata_for_pass(self, *args, **kwargs)

    def _store_completed_batch_pass(self, *args, **kwargs):
        return batch_passes._store_completed_batch_pass(self, *args, **kwargs)

    def _selected_analyze_pass(self, *args, **kwargs):
        return batch_passes._selected_analyze_pass(self, *args, **kwargs)

    def _selected_analyze_results(self, *args, **kwargs):
        return batch_passes._selected_analyze_results(self, *args, **kwargs)

    def _on_analyze_result_pass_changed(self, *args, **kwargs):
        return batch_passes._on_analyze_result_pass_changed(self, *args, **kwargs)

    def _clear_batch_config_and_guesses(self) -> None:
        """Invalidate the validated batch config, generated guesses and runtime results."""
        self._batch_config = None
        self._batch_config_valid = False
        self._batch_initial_guesses = []
        self._batch_initial_guesses_valid = False
        self._clear_batch_fit_results()
        self._reset_batch_pass_workflow(clear_results=True)

    def _clear_batch_fit_results(self) -> None:
        """Clear in-memory batch-fit results without touching the setup table."""
        self._batch_fit_results = []
        self._batch_fit_results_by_key = {}
        self._active_trend_model = None
        self._batch_trend_models = []
        self._batch_next_constraints = []
        try:
            self._refresh_next_constraints_table()
        except Exception:
            pass
        try:
            self._refresh_analyze_results_tab()
        except Exception:
            pass

    def _batch_config_module(self):
        """Select the isolated config implementation for peak-only vs SO-doublet batches."""
        try:
            return batch_config if self._use_doublet_batch_path() else batch_peak_only_config
        except Exception:
            return batch_config if str(getattr(self, "_batch_model_mode", "peak-only")) == "doublet-aware" else batch_peak_only_config

    def _cell_text(self, *args, **kwargs):
        return batch_config_core._cell_text(self, *args, **kwargs)

    def _parse_optional_float(self, *args, **kwargs):
        return batch_config_core._parse_optional_float(self, *args, **kwargs)

    def _json_clean_value(self, *args, **kwargs):
        return batch_config_core._json_clean_value(self, *args, **kwargs)

    def _sequence_descriptor_for_batch_config(self, *args, **kwargs):
        return batch_config_core._sequence_descriptor_for_batch_config(self, *args, **kwargs)

    def _anchor_center_index(self, *args, **kwargs):
        return batch_config_core._anchor_center_index(self, *args, **kwargs)

    def _anchor_descriptor_for_batch_config(self, *args, **kwargs):
        module = self._batch_config_module()
        return module._anchor_descriptor_for_batch_config(self, *args, **kwargs)

    def _batch_row_metadata(self, *args, **kwargs):
        return batch_config._batch_row_metadata(self, *args, **kwargs)

    def _validate_batch_parameter_row(self, *args, **kwargs):
        module = self._batch_config_module()
        return module._validate_batch_parameter_row(self, *args, **kwargs)

    def _build_batch_config_from_table(self, *args, **kwargs):
        module = self._batch_config_module()
        return module._build_batch_config_from_table(self, *args, **kwargs)

    def _anchor_positions_for_initial_guesses(self, *args, **kwargs):
        module = self._batch_config_module()
        return module._anchor_positions_for_initial_guesses(self, *args, **kwargs)

    def _clip_guess_to_bounds(self, *args, **kwargs):
        return batch_config_core._clip_guess_to_bounds(self, *args, **kwargs)

    def _fallback_guess_value(self, *args, **kwargs):
        return batch_config_core._fallback_guess_value(self, *args, **kwargs)

    def _interpolated_guess_value(self, *args, **kwargs):
        module = self._batch_config_module()
        return module._interpolated_guess_value(self, *args, **kwargs)

    def _build_initial_guess_sequence(self, *args, **kwargs):
        module = self._batch_config_module()
        return module._build_initial_guess_sequence(self, *args, **kwargs)

    def _natural_label_sort_key(self, *args, **kwargs):
        return batch_config_core._natural_label_sort_key(self, *args, **kwargs)

    def _validate_and_build_batch_config(self, *args, **kwargs):
        return batch_config_core._validate_and_build_batch_config(self, *args, **kwargs)

    def _request_stop_batch_fit(self, *args, **kwargs):
        return batch_runner_core._request_stop_batch_fit(self, *args, **kwargs)

    def _payload_for_batch_spectrum(self, *args, **kwargs):
        return batch_runner_core._payload_for_batch_spectrum(self, *args, **kwargs)

    def _collect_fit_data_from_payload(self, *args, **kwargs):
        return batch_runner_core._collect_fit_data_from_payload(self, *args, **kwargs)

    def _batch_human_readable_param_name(self, *args, **kwargs):
        return batch_runner_core._batch_human_readable_param_name(self, *args, **kwargs)

    def _resolve_batch_tie_meta(self, *args, **kwargs):
        return batch_runner_core._resolve_batch_tie_meta(self, *args, **kwargs)

    def _peak_specs_from_batch_fit_state(self, *args, **kwargs):
        return batch_runner_core._peak_specs_from_batch_fit_state(self, *args, **kwargs)

    def _bg_values_from_batch_fit_state(self, *args, **kwargs):
        return batch_runner_core._bg_values_from_batch_fit_state(self, *args, **kwargs)

    def _build_batch_model_from_values(self, *args, **kwargs):
        return batch_runner_core._build_batch_model_from_values(self, *args, **kwargs)

    def _fit_one_batch_spectrum(self, *args, **kwargs):
        guess = args[0] if args else kwargs.get("guess")
        try:
            has_doublets = bool((((guess or {}).get("fit_state") or {}).get("so_doublets") or []))
        except Exception:
            has_doublets = False
        module = batch_runner if has_doublets else batch_peak_only_runner
        return module._fit_one_batch_spectrum(self, *args, **kwargs)

    def _update_batch_monitor_plot(self, *args, **kwargs):
        return batch_runner_core._update_batch_monitor_plot(self, *args, **kwargs)

    def _selected_run_pass(self, *args, **kwargs):
        return batch_runner_core._selected_run_pass(self, *args, **kwargs)

    def _refresh_batch_fit_navigation_controls(self, *args, **kwargs):
        return batch_runner_core._refresh_batch_fit_navigation_controls(self, *args, **kwargs)

    def _on_batch_fit_navigation_changed(self, *args, **kwargs):
        return batch_runner_core._on_batch_fit_navigation_changed(self, *args, **kwargs)

    def _step_batch_fit_navigation(self, *args, **kwargs):
        return batch_runner_core._step_batch_fit_navigation(self, *args, **kwargs)

    def _confirm_run_strategy(self, *args, **kwargs):
        return batch_runner_core._confirm_run_strategy(self, *args, **kwargs)

    def _run_selected_batch_strategy(self, *args, **kwargs):
        return batch_runner_core._run_selected_batch_strategy(self, *args, **kwargs)

    def _run_independent_batch_fit(self, *args, **kwargs):
        return batch_runner_core._run_independent_batch_fit(self, *args, **kwargs)

    def _constraint_value_map(self, *args, **kwargs):
        return batch_runner_core._constraint_value_map(self, *args, **kwargs)

    def _apply_constraints_to_fit_state(self, *args, **kwargs):
        return batch_runner_core._apply_constraints_to_fit_state(self, *args, **kwargs)

    def _build_constrained_guesses_from_strategy(self, *args, **kwargs):
        return batch_runner_core._build_constrained_guesses_from_strategy(self, *args, **kwargs)

    def _run_constrained_batch_fit(self, *args, **kwargs):
        return batch_runner_core._run_constrained_batch_fit(self, *args, **kwargs)

    def _run_batch_fit_from_guesses(self, *args, **kwargs):
        return batch_runner_core._run_batch_fit_from_guesses(self, *args, **kwargs)
