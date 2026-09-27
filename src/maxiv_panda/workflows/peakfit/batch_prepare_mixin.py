from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QSizePolicy, QSlider, QSpinBox, QSplitter, QTableWidget,
    QTreeWidget, QVBoxLayout, QWidget,
)

from ...ui import PlotArea

from .batch_anchor_mixin import BatchAnchorMixin
from .batch_prepare_setup_mixin import BatchPrepareSetupMixin
from .batch_selection_mixin import BatchSelectionMixin
from .batch_waterfall_mixin import BatchWaterfallMixin

class BatchPrepareMixin(
    BatchPrepareSetupMixin,
    BatchWaterfallMixin,
    BatchSelectionMixin,
    BatchAnchorMixin,
):
    """Prepare-tab coordinator assembled from focused behavior mixins."""

    def _build_prepare_tab(self, parent: QWidget) -> None:
        outer = QVBoxLayout(parent)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        split = QSplitter(Qt.Orientation.Horizontal, parent)
        outer.addWidget(split, 1)

        left = QWidget(split)
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(6)

        self.selected_tree = QTreeWidget(left)
        self.selected_tree.setColumnCount(2)
        self.selected_tree.setHeaderLabels(["Selected curves", ""])
        self.selected_tree.setMinimumWidth(280)
        try:
            hdr = self.selected_tree.header()
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
            hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
            hdr.setStretchLastSection(False)
            try:
                hdr.setMinimumSectionSize(35)
            except Exception:
                pass
            self.selected_tree.setColumnWidth(1, 48)
            self.selected_tree.setColumnWidth(0, 260)
        except Exception:
            pass
        self._selected_tree_manager.selected_tree = self.selected_tree
        self.selected_tree.itemChanged.connect(self._on_selected_tree_item_changed)
        try:
            self.selected_tree.itemPressed.connect(self._on_selected_tree_item_pressed)
        except Exception:
            pass
        left_lay.addWidget(self.selected_tree, 1)

        # Bin size 1 is the unbinned state; a separate enable checkbox would
        # duplicate that state and consume scarce space in the Prepare tab.
        bin_box = QWidget(left)
        bin_lay = QHBoxLayout(bin_box)
        bin_lay.setContentsMargins(6, 4, 6, 4)
        bin_lay.setSpacing(5)
        bin_lay.addWidget(QLabel("Bin size", bin_box))
        self.sb_bin_size = QSpinBox(bin_box)
        self.sb_bin_size.setRange(1, max(1, len(self._selected_items)))
        self.sb_bin_size.setValue(1)
        self.sb_bin_size.setKeyboardTracking(False)
        self.sb_bin_size.setToolTip(
            "Average consecutive spectra in complete non-overlapping bins. "
            "Bin size 1 means no binning."
        )
        self.sb_bin_size.setMinimumWidth(52)
        self.sb_bin_size.setMaximumWidth(70)
        bin_lay.addWidget(self.sb_bin_size)

        self.lab_binning_info = QLabel("", bin_box)
        self.lab_binning_info.setWordWrap(False)
        self.lab_binning_info.setToolTip(
            "Number of spectra before and after binning. Incomplete trailing bins are discarded."
        )
        self.lab_binning_info.setVisible(False)
        bin_lay.addWidget(self.lab_binning_info, 1)
        left_lay.addWidget(bin_box, 0)

        plot_splitter = QSplitter(Qt.Orientation.Horizontal, split)
        try:
            plot_splitter.setChildrenCollapsible(False)
            plot_splitter.setHandleWidth(7)
        except Exception:
            pass

        plot_a_panel = QWidget(plot_splitter)
        plot_a_panel.setMinimumWidth(360)
        plot_a_lay = QVBoxLayout(plot_a_panel)
        plot_a_lay.setContentsMargins(0, 0, 0, 0)
        plot_a_lay.setSpacing(4)
        self.plot_sequence = PlotArea(plot_a_panel)
        self.plot_sequence.map_palette_callback = self._choose_active_map_cmap
        self._make_plot_area_expand(self.plot_sequence)
        plot_a_lay.addWidget(self.plot_sequence, 1)

        self.waterfall_controls_box = QWidget(plot_a_panel)
        self.waterfall_controls_box.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.waterfall_controls_box.setMaximumWidth(860)
        waterfall_row = QHBoxLayout(self.waterfall_controls_box)
        waterfall_row.setContentsMargins(8, 2, 8, 2)
        waterfall_row.setSpacing(8)

        self.chk_waterfall = QCheckBox("Waterfall", self.waterfall_controls_box)
        self.chk_waterfall.setChecked(False)
        self.chk_waterfall.setToolTip("Enable uniform vertical offsets for curve display")
        waterfall_row.addWidget(self.chk_waterfall, 0, Qt.AlignmentFlag.AlignLeft)

        waterfall_row.addWidget(QLabel("Offset", self.waterfall_controls_box), 0, Qt.AlignmentFlag.AlignLeft)
        self.slider_waterfall = QSlider(Qt.Orientation.Horizontal, self.waterfall_controls_box)
        self.slider_waterfall.setRange(0, 100)
        self.slider_waterfall.setValue(0)
        self.slider_waterfall.setEnabled(False)
        self.slider_waterfall.setMinimumWidth(300)
        self.slider_waterfall.setMaximumWidth(640)
        self.slider_waterfall.setToolTip("Waterfall offset: 0 = no offset, 100 = neighboring curves separated by one full Y range")
        waterfall_row.addWidget(self.slider_waterfall, 1)

        self.sb_waterfall_value = QSpinBox(self.waterfall_controls_box)
        self.sb_waterfall_value.setRange(0, 100)
        self.sb_waterfall_value.setValue(0)
        self.sb_waterfall_value.setEnabled(False)
        self.sb_waterfall_value.setToolTip("Waterfall offset: 0 = no offset, 100 = neighboring curves separated by one full Y range")
        self.sb_waterfall_value.setMinimumWidth(58)
        self.sb_waterfall_value.setMaximumWidth(70)
        waterfall_row.addWidget(self.sb_waterfall_value, 0, Qt.AlignmentFlag.AlignLeft)

        self.chk_waterfall_mono = QCheckBox("Fixed color:", self.waterfall_controls_box)
        self.chk_waterfall_mono.setChecked(False)
        self.chk_waterfall_mono.setEnabled(False)
        self.chk_waterfall_mono.setToolTip("Use one selected color for all curves in waterfall display")
        waterfall_row.addWidget(self.chk_waterfall_mono, 0, Qt.AlignmentFlag.AlignLeft)

        self.btn_waterfall_color = QPushButton("", self.waterfall_controls_box)
        self.btn_waterfall_color.setEnabled(False)
        self.btn_waterfall_color.setToolTip("Choose the fixed waterfall curve color")
        self.btn_waterfall_color.setFixedSize(24, 18)
        waterfall_row.addWidget(self.btn_waterfall_color, 0, Qt.AlignmentFlag.AlignLeft)
        self._update_waterfall_color_button()
        waterfall_wrap = QHBoxLayout()
        waterfall_wrap.setContentsMargins(0, 0, 0, 0)
        waterfall_wrap.addStretch(1)
        waterfall_wrap.addWidget(self.waterfall_controls_box)
        waterfall_wrap.addStretch(1)
        plot_a_lay.addLayout(waterfall_wrap)

        right = QWidget(plot_splitter)
        right.setMinimumWidth(360)
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(6)

        self.lab_anchor_instructions = QLabel(
            "Define representative anchor spectra from the currently checked effective sequence. "
            "Choose Start, Middle or End, select a spectrum range to average, then build the anchor. "
            "The resulting anchor spectrum is shown below and will later be fitted to define the batch-fit model.",
            right,
        )
        self.lab_anchor_instructions.setWordWrap(True)
        right_lay.addWidget(self.lab_anchor_instructions, 0)

        anchor_row = QHBoxLayout()
        anchor_row.setContentsMargins(0, 0, 0, 0)
        anchor_row.setSpacing(6)
        anchor_row.addWidget(QLabel("Anchor", right))
        self.cb_anchor_type = QComboBox(right)
        self.cb_anchor_type.addItems(self._anchor_labels)
        anchor_row.addWidget(self.cb_anchor_type, 0)
        anchor_row.addSpacing(6)
        anchor_row.addWidget(QLabel("From", right))
        self.sb_anchor_from = QSpinBox(right)
        self.sb_anchor_from.setRange(1, 1)
        self.sb_anchor_from.setValue(1)
        self.sb_anchor_from.setMinimumWidth(62)
        anchor_row.addWidget(self.sb_anchor_from, 0)
        anchor_row.addWidget(QLabel("To", right))
        self.sb_anchor_to = QSpinBox(right)
        self.sb_anchor_to.setRange(1, 1)
        self.sb_anchor_to.setValue(1)
        self.sb_anchor_to.setMinimumWidth(62)
        anchor_row.addWidget(self.sb_anchor_to, 0)
        self.btn_build_anchor = QPushButton("Build / update anchor", right)
        anchor_row.addWidget(self.btn_build_anchor, 0)
        self.btn_fit_anchor = QPushButton("Fit anchor...", right)
        self.btn_fit_anchor.setEnabled(False)
        self.btn_fit_anchor.setToolTip("Open the selected anchor in the single-curve fitting editor")
        anchor_row.addWidget(self.btn_fit_anchor, 0)
        anchor_row.addStretch(1)
        right_lay.addLayout(anchor_row)

        self.anchor_status_table = QTableWidget(0, 5, right)
        self.anchor_status_table.setHorizontalHeaderLabels(["Anchor", "Range", "Spectra", "Status", ""])
        self.anchor_status_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.anchor_status_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.anchor_status_table.setMaximumHeight(110)
        self.anchor_status_table.setMinimumHeight(92)
        try:
            ah = self.anchor_status_table.horizontalHeader()
            ah.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            ah.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            ah.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            ah.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            ah.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        except Exception:
            pass
        right_lay.addWidget(self.anchor_status_table, 0)

        proceed_row = QHBoxLayout()
        proceed_row.setContentsMargins(0, 0, 0, 0)
        proceed_row.addStretch(1)
        self.btn_proceed_batch_setup = QPushButton("Proceed to batch setup", right)
        self.btn_proceed_batch_setup.setEnabled(False)
        self.btn_proceed_batch_setup.setToolTip("Fit at least the Start anchor before creating the batch setup.")
        proceed_row.addWidget(self.btn_proceed_batch_setup)
        right_lay.addLayout(proceed_row)

        self.plot_anchor = PlotArea(right)
        self._make_plot_area_expand(self.plot_anchor)
        self.plot_anchor.clear("Anchor preview: build a Start, Middle or End anchor above")
        self._style_prepare_plot_area(self.plot_anchor)
        self._compact_plot_margins(self.plot_anchor)
        right_lay.addWidget(self.plot_anchor, 1)

        plot_splitter.setStretchFactor(0, 1)
        plot_splitter.setStretchFactor(1, 1)
        try:
            plot_splitter.setSizes([700, 700])
        except Exception:
            pass
        self.plot_splitter = plot_splitter

        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        try:
            split.setChildrenCollapsible(False)
            split.setSizes([320, 1400])
        except Exception:
            pass

        self._collect_original_entries_from_main_selected()
        self._rebuild_tree_for_current_binning()
        self.sb_bin_size.valueChanged.connect(self._on_binning_settings_changed)
        self.chk_waterfall.toggled.connect(self._on_waterfall_toggled)
        self.slider_waterfall.valueChanged.connect(self._on_waterfall_slider_changed)
        self.sb_waterfall_value.valueChanged.connect(self._on_waterfall_spin_changed)
        self.chk_waterfall_mono.toggled.connect(self._on_waterfall_mono_toggled)
        self.btn_waterfall_color.clicked.connect(self._choose_waterfall_mono_color)
        self.cb_anchor_type.currentTextChanged.connect(self._on_anchor_type_changed)
        self.btn_build_anchor.clicked.connect(self._build_current_anchor)
        self.btn_fit_anchor.clicked.connect(self._fit_current_anchor)
        self.btn_proceed_batch_setup.clicked.connect(self._proceed_to_batch_setup)
        self._refresh_anchor_controls()
        self._refresh_anchor_status_table()
        self._update_waterfall_controls_width()
        self._update_prepare_plot_from_selected()

