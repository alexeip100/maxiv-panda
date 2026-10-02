from __future__ import annotations

from PyQt6.QtCore import Qt, QLocale
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QPushButton, QRadioButton, QSpinBox,
    QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget,
)
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from .processed_controller import ProcessedController
from .ui_map_controls_mixin import UiMapControlsMixin
from .ui_style import current_ui_metrics, register_layout_role


class UiProcessedDataMixin(UiMapControlsMixin):
    """Processed Data tab construction and processed-view controls."""

    def _build_processed_data_tab(self, tabs) -> None:
        processed_tab = QWidget(tabs)
        metrics = current_ui_metrics()
        processed_layout = QVBoxLayout(processed_tab)
        processed_layout.setContentsMargins(0, 0, 0, 0)
        processed_layout.setSpacing(0)

        # The Processed tab uses the same amount of vertical space for its
        # controls in both 1D and map modes.  The dedicated map page keeps
        # 2D-specific controls from disturbing the established 1D layout.
        self.processed_controls_stack = QStackedWidget(processed_tab)
        self.processed_controls_above_plot = QWidget(self.processed_controls_stack)
        proc_top = QHBoxLayout(self.processed_controls_above_plot)
        register_layout_role(proc_top, "strip")
        proc_top.setContentsMargins(
            metrics.strip_horizontal_margin, metrics.strip_vertical_margin,
            metrics.strip_horizontal_margin, metrics.strip_vertical_margin,
        )
        proc_top.setSpacing(metrics.strip_spacing)

        group_style = """
            QGroupBox {
                border: 1px solid #C9CDD3;
                border-radius: 5px;
                margin-top: 7px;
                padding-top: 2px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 8px;
                padding: 0 3px;
                color: #4B5563;
                font-weight: 600;
            }
        """

        self.grp_calibration = QGroupBox("Energy calibration", self.processed_controls_above_plot)
        self.grp_calibration.setStyleSheet(group_style)
        calibration_layout = QHBoxLayout(self.grp_calibration)
        register_layout_role(calibration_layout, "group")
        calibration_layout.setContentsMargins(
            metrics.group_margin_h, metrics.group_margin_top,
            metrics.group_margin_h, metrics.group_margin_bottom,
        )
        calibration_layout.setSpacing(metrics.group_spacing)

        from .workflows.calibration import build_calibrate_control
        self.w_calibrate_control, self.btn_calibrate_be, self.btn_e_cal_toggle = build_calibrate_control(
            self.grp_calibration,
            self._open_calibrate_be_dialog,
            self._on_e_cal_toggle,
        )
        calibration_layout.addWidget(self.w_calibrate_control)
        proc_top.addWidget(self.grp_calibration)

        from .workflows.normalization import build_normalization_control
        (
            self.w_norm_control,
            self.cb_norm_to1_proc,
            self.sb_norm_e_proc,
            self.sb_norm_span_proc,
            self.lbl_norm_span_ev_proc,
        ) = build_normalization_control(self.processed_controls_above_plot)
        proc_top.addWidget(self.w_norm_control)

        self.grp_fitting = QGroupBox("Fitting", self.processed_controls_above_plot)
        self.grp_fitting.setStyleSheet(group_style)
        fitting_layout = QHBoxLayout(self.grp_fitting)
        register_layout_role(fitting_layout, "group")
        fitting_layout.setContentsMargins(
            metrics.group_margin_h, metrics.group_margin_top,
            metrics.group_margin_h, metrics.group_margin_bottom,
        )
        fitting_layout.setSpacing(metrics.group_spacing)

        from .workflows.peakfit import open_fit_corelevel_dialog
        self.btn_fit_selected = QPushButton("Fit selected", self.grp_fitting)
        self.btn_fit_selected.setToolTip("Fit selected core-level spectra (opens fitting dialog)")
        self.btn_fit_selected.clicked.connect(lambda _=False: open_fit_corelevel_dialog(self))
        fitting_layout.addWidget(self.btn_fit_selected)
        proc_top.addWidget(self.grp_fitting)

        self.grp_plotting = QGroupBox("Plotting", self.processed_controls_above_plot)
        self.grp_plotting.setStyleSheet(group_style)
        plotting_layout = QHBoxLayout(self.grp_plotting)
        register_layout_role(plotting_layout, "group")
        plotting_layout.setContentsMargins(
            metrics.group_margin_h, metrics.group_margin_top,
            metrics.group_margin_h, metrics.group_margin_bottom,
        )
        plotting_layout.setSpacing(metrics.group_spacing)
        self.btn_pass_to_plotting = QPushButton("Pass to plotting", self.grp_plotting)
        self.btn_pass_to_plotting.setToolTip(
            "Copy the currently selected Processed Data curves to the Plotted Data tab."
        )
        self.btn_pass_to_plotting.clicked.connect(self._pass_selected_to_plotting)
        plotting_layout.addWidget(self.btn_pass_to_plotting)
        proc_top.addWidget(self.grp_plotting)
        proc_top.addStretch(1)

        self.processed_controls_map_placeholder = QWidget(self.processed_controls_stack)
        map_controls_layout = QHBoxLayout(self.processed_controls_map_placeholder)
        register_layout_role(map_controls_layout, "strip")
        map_controls_layout.setContentsMargins(
            metrics.strip_horizontal_margin, metrics.strip_vertical_margin,
            metrics.strip_horizontal_margin, metrics.strip_vertical_margin,
        )
        map_controls_layout.setSpacing(metrics.layout_spacing)

        # Map analysis mode.  The compact combo box is the visible control;
        # hidden radio buttons retain the long-established internal state API
        # used by the plotting/map mixins.
        map_controls_layout.addWidget(QLabel("View:", self.processed_controls_map_placeholder))
        self.cb_map_view = QComboBox(self.processed_controls_map_placeholder)
        self.cb_map_view.addItem("Simple", "simple")
        self.cb_map_view.addItem("Lines", "lines")
        self.cb_map_view.addItem("ROI", "roi")
        self.cb_map_view.setMinimumWidth(78)
        self.cb_map_view.setMaximumWidth(92)
        self.cb_map_view.setToolTip(
            "Choose the 2D map inspection view: Simple, Lines, or ROI."
        )
        map_controls_layout.addWidget(self.cb_map_view)

        # Map palette is changed directly from the map: right-click the 2D image.

        # Lines-only binning.  These controls intentionally mirror the batch-fit
        # workflow: complete consecutive groups are averaged and any incomplete
        # trailing group is discarded.  Keep them compact because the map strip
        # shares one row with normalization and trace controls.
        self._map_lines_binning_controls = QWidget(self.processed_controls_map_placeholder)
        map_bin_layout = QHBoxLayout(self._map_lines_binning_controls)
        map_bin_layout.setContentsMargins(8, 0, 0, 0)
        map_bin_layout.setSpacing(4)
        map_bin_layout.addWidget(QLabel("Bin size", self._map_lines_binning_controls))
        self.sb_map_bin_size = QSpinBox(self._map_lines_binning_controls)
        self.sb_map_bin_size.setRange(1, 10000)
        self.sb_map_bin_size.setValue(1)
        self.sb_map_bin_size.setKeyboardTracking(False)
        self.sb_map_bin_size.setMinimumWidth(52)
        self.sb_map_bin_size.setMaximumWidth(66)
        map_bin_layout.addWidget(self.sb_map_bin_size)
        self.lab_map_binning_info = QLabel("", self._map_lines_binning_controls)
        self.lab_map_binning_info.setToolTip(
            "Number of selected map rows before and after binning. Incomplete trailing bins are discarded."
        )
        self.lab_map_binning_info.setVisible(False)
        # Never let the optional status text establish the minimum width of the
        # whole top control strip (notably important on macOS).
        self.lab_map_binning_info.setMinimumWidth(0)
        # Ignore the text-dependent horizontal size hint.  This keeps the
        # established full status wording while preventing a newly-visible
        # binning label from forcing the main window wider on macOS.
        self.lab_map_binning_info.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        map_bin_layout.addWidget(self.lab_map_binning_info)

        # Lines cross-section thickness is the odd number of samples averaged
        # symmetrically about the draggable cursor.  1 preserves the historical
        # single-row/single-column behavior.
        map_bin_layout.addSpacing(6)
        map_bin_layout.addWidget(QLabel("H thickness", self._map_lines_binning_controls))
        self.sb_map_h_thickness = QSpinBox(self._map_lines_binning_controls)
        self.sb_map_h_thickness.setRange(1, 25)
        self.sb_map_h_thickness.setSingleStep(2)
        self.sb_map_h_thickness.setValue(1)
        self.sb_map_h_thickness.setKeyboardTracking(False)
        self.sb_map_h_thickness.setFixedWidth(48)
        self.sb_map_h_thickness.setToolTip(
            "Odd number of map rows averaged symmetrically for the horizontal profile (1, 3, 5, …, 25)."
        )
        map_bin_layout.addWidget(self.sb_map_h_thickness)
        map_bin_layout.addWidget(QLabel("V thickness", self._map_lines_binning_controls))
        self.sb_map_v_thickness = QSpinBox(self._map_lines_binning_controls)
        self.sb_map_v_thickness.setRange(1, 25)
        self.sb_map_v_thickness.setSingleStep(2)
        self.sb_map_v_thickness.setValue(1)
        self.sb_map_v_thickness.setKeyboardTracking(False)
        self.sb_map_v_thickness.setFixedWidth(48)
        self.sb_map_v_thickness.setToolTip(
            "Odd number of map columns averaged symmetrically for the vertical profile (1, 3, 5, …, 25)."
        )
        map_bin_layout.addWidget(self.sb_map_v_thickness)

        self._map_lines_binning_controls.setVisible(False)
        map_controls_layout.addWidget(self._map_lines_binning_controls)

        self.rb_map_none = QRadioButton("Simple", self.processed_controls_map_placeholder)
        self.rb_map_lines = QRadioButton("Lines", self.processed_controls_map_placeholder)
        self.rb_map_roi = QRadioButton("ROI", self.processed_controls_map_placeholder)
        self.rb_map_none.setChecked(True)
        self._map_view_group = QButtonGroup(self.processed_controls_map_placeholder)
        self._map_view_group.setExclusive(True)
        self._map_view_group.addButton(self.rb_map_none)
        self._map_view_group.addButton(self.rb_map_lines)
        self._map_view_group.addButton(self.rb_map_roi)
        for button in (self.rb_map_none, self.rb_map_lines, self.rb_map_roi):
            button.setVisible(False)

        # Map normalization is independent of the inspection view (Simple / Lines / ROI).
        # Keep only method selection on the crowded main row; method parameters live
        # in a small non-modal settings dialog.
        map_controls_layout.addSpacing(10)
        map_controls_layout.addWidget(QLabel("Normalize:", self.processed_controls_map_placeholder))
        self.cb_map_normalization = QComboBox(self.processed_controls_map_placeholder)
        self.cb_map_normalization.addItem("None", "none")
        self.cb_map_normalization.addItem("At BE", "at_be")
        self.cb_map_normalization.addItem("Area", "area")
        self.cb_map_normalization.setMinimumWidth(92)
        self.cb_map_normalization.setMaximumWidth(112)
        self.cb_map_normalization.setToolTip(
            "Normalize each row of the 2D map independently. This affects the map, Lines/ROI traces, ResPES cuts, and stored comparison traces."
        )
        map_controls_layout.addWidget(self.cb_map_normalization)

        self._map_norm_mode = "none"
        self._map_norm_context_key = None
        self._map_norm_be = None
        self._map_norm_width_ev = None
        self._map_norm_area_low = None
        self._map_norm_area_high = None
        self._map_norm_show_region = True
        self._map_norm_active_interval = None
        self._map_norm_dialog = None
        self.cb_map_normalization.currentIndexChanged.connect(self._on_map_normalization_changed)
        # Re-selecting the active normalization entry is the compact way to
        # reopen its settings dialog now that the redundant cog button has
        # been removed from the crowded MAP control row.
        self.cb_map_normalization.activated.connect(self._on_map_normalization_activated)

        self.btn_respes_analysis = QToolButton(self.processed_controls_map_placeholder)
        self.btn_respes_analysis.setText("ResPES analysis")
        self.btn_respes_analysis.setCheckable(True)
        self.btn_respes_analysis.setVisible(False)
        self.btn_respes_analysis.setToolTip(
            "Show constant-BE / constant-KE cuts for maps whose second dimension is photon energy."
        )
        self.btn_respes_analysis.toggled.connect(self._on_respes_analysis_toggled)
        map_controls_layout.addSpacing(8)
        map_controls_layout.addWidget(self.btn_respes_analysis)

        self._respes_cut_type = "constant_be"
        self._respes_cut_position = None
        self._respes_cut_width = None
        self._respes_dataset_key = None
        self._respes_energy_axis = "be"
        self._respes_work_function = 4.5

        # Lines/ROI traces are snapshotted into the generic comparison window.
        # Export is intentionally centralized there rather than duplicated here.
        self._map_trace_add_controls = QWidget(self.processed_controls_map_placeholder)
        trace_add_layout = QHBoxLayout(self._map_trace_add_controls)
        trace_add_layout.setContentsMargins(6, 0, 0, 0)
        trace_add_layout.setSpacing(4)
        self.btn_map_add_h_trace = QPushButton("Plot H-trace", self._map_trace_add_controls)
        self.btn_map_add_v_trace = QPushButton("Plot V-trace", self._map_trace_add_controls)
        self.btn_map_add_h_trace.setToolTip("Plot the current horizontal trace in Trace comparison")
        self.btn_map_add_v_trace.setToolTip("Plot the current vertical trace in Trace comparison")
        self.btn_map_add_h_trace.clicked.connect(
            lambda _=False: self._add_map_trace_to_comparison("horizontal")
        )
        self.btn_map_add_v_trace.clicked.connect(
            lambda _=False: self._add_map_trace_to_comparison("vertical")
        )
        trace_add_layout.addWidget(self.btn_map_add_h_trace)
        trace_add_layout.addWidget(self.btn_map_add_v_trace)
        self._map_trace_add_controls.setVisible(False)
        map_controls_layout.addWidget(self._map_trace_add_controls)

        self._map_roi_controls = QWidget(self.processed_controls_map_placeholder)
        roi_layout = QHBoxLayout(self._map_roi_controls)
        roi_layout.setContentsMargins(8, 0, 0, 0)
        roi_layout.setSpacing(5)
        c_locale = QLocale.c()

        def _roi_spin(decimals=3):
            sb = QDoubleSpinBox(self._map_roi_controls)
            sb.setLocale(c_locale)
            sb.setDecimals(decimals)
            sb.setRange(-1.0e12, 1.0e12)
            sb.setKeyboardTracking(False)
            sb.setMinimumWidth(68)
            sb.setMaximumWidth(86)
            return sb

        roi_layout.addWidget(QLabel("X ctr", self._map_roi_controls))
        self.sb_map_roi_x_center = _roi_spin(3)
        roi_layout.addWidget(self.sb_map_roi_x_center)
        roi_layout.addWidget(QLabel("W", self._map_roi_controls))
        self.sb_map_roi_x_width = _roi_spin(3)
        roi_layout.addWidget(self.sb_map_roi_x_width)
        roi_layout.addSpacing(7)
        roi_layout.addWidget(QLabel("Y ctr", self._map_roi_controls))
        self.sb_map_roi_y_center = _roi_spin(3)
        roi_layout.addWidget(self.sb_map_roi_y_center)
        roi_layout.addWidget(QLabel("W", self._map_roi_controls))
        self.sb_map_roi_y_width = _roi_spin(3)
        roi_layout.addWidget(self.sb_map_roi_y_width)
        self._map_roi_controls.setVisible(False)
        map_controls_layout.addWidget(self._map_roi_controls)
        map_controls_layout.addStretch(1)

        self._build_respes_side_panel()

        self._map_roi_spec = None
        self.rb_map_none.toggled.connect(self._on_map_analysis_mode_changed)
        self.rb_map_lines.toggled.connect(self._on_map_analysis_mode_changed)
        self.rb_map_roi.toggled.connect(self._on_map_analysis_mode_changed)
        self.cb_map_view.currentIndexChanged.connect(self._on_map_view_combo_changed)
        self.sb_map_bin_size.valueChanged.connect(self._on_map_lines_binning_changed)
        self.sb_map_h_thickness.valueChanged.connect(
            lambda _v: self._on_map_lines_thickness_value_changed("horizontal")
        )
        self.sb_map_v_thickness.valueChanged.connect(
            lambda _v: self._on_map_lines_thickness_value_changed("vertical")
        )
        self.sb_map_h_thickness.editingFinished.connect(
            lambda: self._normalize_map_lines_thickness_spin(self.sb_map_h_thickness, "horizontal")
        )
        self.sb_map_v_thickness.editingFinished.connect(
            lambda: self._normalize_map_lines_thickness_spin(self.sb_map_v_thickness, "vertical")
        )
        self._processed_map_was_active = False
        for sb in (
            self.sb_map_roi_x_center, self.sb_map_roi_x_width,
            self.sb_map_roi_y_center, self.sb_map_roi_y_width,
        ):
            sb.editingFinished.connect(self._on_map_roi_numeric_changed)

        # Keep the map-mode controls exactly as tall as the normal control
        # page, so activating Map does not make the plot jump vertically.
        controls_height = self.processed_controls_above_plot.sizeHint().height()
        if controls_height > 0:
            self.processed_controls_map_placeholder.setMinimumHeight(controls_height)
            self.processed_controls_map_placeholder.setMaximumHeight(controls_height)

        self.processed_controls_stack.addWidget(self.processed_controls_above_plot)
        self.processed_controls_stack.addWidget(self.processed_controls_map_placeholder)
        self.processed_controls_stack.setCurrentWidget(self.processed_controls_above_plot)
        processed_layout.addWidget(self.processed_controls_stack, 0)

        self.processed_view_holder = QWidget(processed_tab)
        self.processed_view_holder_layout = QVBoxLayout(self.processed_view_holder)
        self.processed_view_holder_layout.setContentsMargins(0, 0, 0, 0)
        self.processed_view_holder_layout.setSpacing(0)
        processed_layout.addWidget(self.processed_view_holder, 1)

        self.processed_controls_under_plot = QWidget(processed_tab)
        proc_bottom = QHBoxLayout(self.processed_controls_under_plot)
        proc_bottom.setContentsMargins(
            metrics.strip_horizontal_margin, max(4, metrics.strip_vertical_margin - 4),
            metrics.strip_horizontal_margin, max(4, metrics.strip_vertical_margin - 4),
        )
        proc_bottom.setSpacing(metrics.strip_spacing)
        proc_bottom.addStretch(1)
        processed_layout.addWidget(self.processed_controls_under_plot, 0)

        tabs.addTab(processed_tab, "Processed Data")

        self._norm_to1_enabled: bool = False
        self._norm_to1_energy: float | None = None
        self._norm_span_percent: float = 1.0
        self._norm_to1_auto_default: float | None = None
        self._norm_to1_user_override: bool = False
        self._norm_to1_sig_when_enabled: tuple[str, ...] | None = None

        self._processed_controller = ProcessedController(self)

        # QCheckBox.toggled emits a real bool in both Qt5 and Qt6.  Using it
        # avoids comparing the integer emitted by stateChanged with a Qt6
        # CheckState enum, which would silently leave normalization disabled.
        def _on_norm_energy_changed(value: float) -> None:
            self._processed_controller.on_norm_energy_changed(float(value))

        def _on_norm_span_changed(value: float) -> None:
            self._processed_controller.on_norm_span_changed(float(value))

        self.cb_norm_to1_proc.toggled.connect(self._processed_controller.on_norm_toggled)
        self.sb_norm_e_proc.valueChanged.connect(_on_norm_energy_changed)
        self.sb_norm_span_proc.valueChanged.connect(_on_norm_span_changed)

        default_energy = self._processed_controller.guess_norm_default_energy()
        if default_energy is not None:
            self._norm_to1_energy = float(default_energy)
            try:
                self.sb_norm_e_proc.blockSignals(True)
                self.sb_norm_e_proc.setValue(float(default_energy))
            finally:
                self.sb_norm_e_proc.blockSignals(False)
            self._norm_to1_auto_default = float(default_energy)
            self._norm_to1_user_override = False

        tabs.currentChanged.connect(self._on_tab_changed)





















    def _choose_active_map_cmap(self) -> None:
        """Open the palette chooser for the currently active Processed Data map."""
        for key, button in getattr(self, "_region_map_buttons", {}).items():
            try:
                if button is not None and button.isChecked():
                    file_name, region_name = key
                    self._choose_region_cmap(file_name, region_name)
                    return
            except Exception:
                continue

    def _on_map_view_combo_changed(self, _index: int = -1) -> None:
        """Drive the established hidden radio-button map state from the compact View combo."""
        combo = getattr(self, "cb_map_view", None)
        if combo is None:
            return
        mode = str(combo.currentData() or "simple")
        button = {
            "simple": getattr(self, "rb_map_none", None),
            "lines": getattr(self, "rb_map_lines", None),
            "roi": getattr(self, "rb_map_roi", None),
        }.get(mode)
        if button is not None and not button.isChecked():
            button.setChecked(True)

    def _sync_processed_controls_for_map_mode(self) -> None:
        """Show the dedicated 2D-controls page whenever any region map is active.

        The selected-curves tree already owns the Map toggle and enforces when
        that toggle can be used.  This method only mirrors that established
        state into the Processed Data control area.
        """
        stack = getattr(self, "processed_controls_stack", None)
        normal_page = getattr(self, "processed_controls_above_plot", None)
        map_page = getattr(self, "processed_controls_map_placeholder", None)
        if stack is None or normal_page is None or map_page is None:
            return

        map_active = False
        for button in getattr(self, "_region_map_buttons", {}).values():
            try:
                if button is not None and button.isChecked():
                    map_active = True
                    break
            except Exception:
                continue

        # Every fresh entry into Processed Data Map starts in the neutral
        # full-map view.  Lines and ROI are analysis overlays selected
        # explicitly by the user, not sticky defaults from a previous map.
        was_active = bool(getattr(self, "_processed_map_was_active", False))
        restoring_session_view = bool(getattr(self, "_session_restoring_map_view", False))
        if map_active and not was_active and not restoring_session_view:
            try:
                self.plot_area.reset_map_palette_hint_visit()
            except Exception:
                pass
            none_button = getattr(self, "rb_map_none", None)
            if none_button is not None:
                try:
                    none_button.blockSignals(True)
                    none_button.setChecked(True)
                finally:
                    none_button.blockSignals(False)
            combo = getattr(self, "cb_map_view", None)
            if combo is not None:
                try:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(max(0, combo.findData("simple")))
                finally:
                    combo.blockSignals(False)
            # The hidden radio buttons were changed with signals blocked, so
            # explicitly synchronize representation-specific widgets as well.
            # Otherwise Lines/ROI controls from the previous map can remain
            # visible even though the combo now says Simple.
            sync_visibility = getattr(self, "_sync_map_analysis_control_visibility", None)
            if callable(sync_visibility):
                sync_visibility()

        self._processed_map_was_active = map_active
        stack.setCurrentWidget(map_page if map_active else normal_page)
        if map_active:
            try:
                self._update_respes_availability()
            except Exception:
                pass
        else:
            panel = getattr(self, "respes_side_panel", None)
            if panel is not None:
                panel.setVisible(False)

    def _pass_selected_to_plotting(self) -> None:
        """Copy the currently selected Processed Data curves to Plotted Data."""
        try:
            selection = self._plot_selection_controller.collect_selection()
            payloads = list(selection.payloads)
            items_in_order = list(selection.items_in_order)

            # Use source-aware names in Plotted Data.  Region/curve labels can be
            # identical across files, so include the source file tag (for example
            # XPS_0008 -> 0008) before making the snapshots.
            from .workflows.plotting.model import source_aware_curve_title
            named_payloads = []
            for payload, item_info in zip(payloads, items_in_order):
                item, key = item_info
                file_name = ""
                try:
                    parent = item.parent()
                    if parent is not None:
                        file_name = str(parent.data(0, self.ROLE_FILE) or "")
                except Exception:
                    file_name = ""
                if not file_name or file_name == "__GROUP__":
                    try:
                        file_name = str(key).split(":::", 1)[0]
                    except Exception:
                        file_name = ""
                base_title = str(getattr(payload, "title", "") or item.text(0) or "Curve")
                title = source_aware_curve_title(base_title, file_name)
                named_payloads.append(type(payload)(
                    title=title,
                    x=payload.x,
                    y=payload.y,
                    xlabel=payload.xlabel,
                    ylabel=payload.ylabel,
                    energy_scale=getattr(payload, "energy_scale", "Unknown"),
                    metadata=dict(getattr(payload, "metadata", {}) or {}),
                ))
            payloads = named_payloads

            # Plotted Data receives exactly the numerical representation shown
            # in Processed Data.  Unlike MAP, ordinary child spectra therefore
            # inherit CPS when it is selected upstream.
            if str(getattr(self, "_processed_intensity_mode", "counts")).lower() == "cps":
                payloads_scaled, missing_cps = self._apply_intensity_mode_to_payloads(
                    payloads, items_in_order, "cps"
                )
                if missing_cps:
                    from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox
                    QMessageBox.warning(
                        self,
                        "CPS unavailable",
                        "Counts per second cannot be passed because 'Time per Spectrum Channel' "
                        f"is missing or invalid for: {', '.join(missing_cps[:5])}" +
                        (" ..." if len(missing_cps) > 5 else ""),
                        QMessageBox.StandardButton.Ok,
                    )
                    return
                payloads = payloads_scaled

            controller = getattr(self, "_processed_controller", None)
            if controller is not None:
                result, _applied = controller.apply_normalization_if_enabled(
                    payloads, items_in_order
                )
                if result is None:
                    return
                payloads = result

            if not payloads:
                from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox
                QMessageBox.information(
                    self,
                    "Nothing to pass",
                    "Select at least one curve in Processed Data.",
                    QMessageBox.StandardButton.Ok,
                )
                return

            plotted_panel = self._ensure_plotted_data_panel()
            plotted_panel.add_curves(payloads)
            self.tabs.setCurrentWidget(self._plotted_data_host)
        except Exception as exc:
            from .log_utils import log_noncritical_error
            log_noncritical_error("passing curves to Plotted Data", exc)

    def _is_processed_tab_active(self) -> bool:
        try:
            return self.data_view_splitter.parentWidget() == self.processed_view_holder
        except Exception:
            return False

    def _has_any_processed_curves(self) -> bool:
        """Return True if any selected-curve item is marked as processed."""
        controller = getattr(self, '_processed_controller', None)
        if controller is None:
            return False
        return controller.has_any_processed_curves()

    def _on_e_cal_toggle(self, checked: bool) -> None:

        """Toggle visibility between raw and E-calibrated curves.

        Do not gate the data-state change on the current Qt parent of the shared
        plot/tree splitter.  That parent can be transiently different during
        session restore/reparenting; the power button should still switch the
        canonical raw/E-cal representation whenever calibrated curves exist.
        """
        try:
            if not self._has_any_processed_curves():
                # Nothing to toggle yet.
                return

            # Update the welded control's visual "latched" state (unified border).
            try:
                self.w_calibrate_control.setProperty("ecal_on", bool(checked))
                for _w in (self.w_calibrate_control, self.btn_calibrate_be, self.btn_e_cal_toggle):
                    _w.style().unpolish(_w)
                    _w.style().polish(_w)
                    _w.update()
            except Exception:
                pass

            self._update_selected_tree_visibility(show_processed=bool(checked))
            self._update_plot_from_selected()
        except Exception:
            pass

    def _on_tab_changed(self, index: int) -> None:
        """Move the shared plot+selected-tree view between tabs.

        The plot and selected-curve tree must be the same objects in both tabs.
        Qt widgets can only belong to one layout at a time, so we re-parent the
        shared splitter when the user switches tab.
        """
        try:
            # The Raw and Processed tabs share one plot/tree splitter.  Standalone
            # tabs such as Plotted Data and Cross sections own their own widgets.
            if index == 0:
                target_layout = self.raw_view_holder_layout
            elif index == 1:
                target_layout = self.processed_view_holder_layout
            else:
                return

            try:
                self.plot_area.reset_map_palette_hint_visit()
            except Exception:
                pass

            # Remove from current parent layout if needed.
            try:
                cur_parent = self.data_view_splitter.parentWidget()
                if cur_parent is not None:
                    cur_layout = cur_parent.layout()
                    if cur_layout is not None:
                        cur_layout.removeWidget(self.data_view_splitter)
            except Exception:
                pass

            # Reparent and insert.
            self.data_view_splitter.setParent(target_layout.parentWidget())
            target_layout.addWidget(self.data_view_splitter)
            self.data_view_splitter.show()
            try:
                # Decide what to show in the shared Selected-curves tree.
                # Raw tab always shows raw curves.
                # Processed tab:
                #   - before any processing -> mirror Raw (show raw)
                #   - after processing exists -> controlled by the E-cal toggle (Off=raw, On=processed)
                has_processed = self._has_any_processed_curves()
                if index == 0:
                    show_processed = False
                else:
                    if not has_processed:
                        show_processed = False
                    else:
                        try:
                            show_processed = bool(self.btn_e_cal_toggle.isChecked())
                        except Exception:
                            show_processed = True
                self._update_selected_tree_visibility(show_processed=bool(show_processed))
                if index == 1:
                    self._sync_processed_controls_for_map_mode()
                # ResPES is a Processed-Data-only workflow.  In particular,
                # hide its side panel immediately when switching to Raw Data;
                # the shared plot widget otherwise leaves that sibling widget
                # visible until another Processed-map availability refresh.
                try:
                    self._update_respes_availability()
                except Exception:
                    pass
                # Redraw plot so it matches what is visible in the Selected-curves tree.
                self._update_plot_from_selected()
            except Exception:
                pass
        except Exception:
            # Never allow tab switching to crash the GUI.
            pass

    def _update_selected_tree_visibility(self, show_processed: bool) -> None:
        """Show either processed or raw curves in the Selected-curves tree."""
        controller = getattr(self, '_processed_controller', None)
        if controller is None:
            return
        controller.update_selected_tree_visibility(show_processed=bool(show_processed))
