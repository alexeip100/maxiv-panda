from __future__ import annotations

from dataclasses import replace

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QPushButton, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from .log_utils import log_noncritical_error
from .signal_identification import SignalIdentificationController
from .ui_style import current_ui_metrics, register_layout_role


class RegionPreviewComboBox(QComboBox):
    """QComboBox that reports whether a popup close committed a new item."""

    popupOpened = pyqtSignal(int)
    popupClosed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup_open_index = -1
        self._popup_activated = False
        self.activated.connect(self._mark_popup_activated)

    def _mark_popup_activated(self, _index: int) -> None:
        self._popup_activated = True

    def showPopup(self) -> None:
        self._popup_open_index = int(self.currentIndex())
        self._popup_activated = False
        self.popupOpened.emit(self._popup_open_index)
        super().showPopup()

    def hidePopup(self) -> None:
        committed = bool(self._popup_activated)
        super().hidePopup()
        if not committed and self._popup_open_index >= 0 and self.currentIndex() != self._popup_open_index:
            self.blockSignals(True)
            try:
                self.setCurrentIndex(self._popup_open_index)
            finally:
                self.blockSignals(False)
        self.popupClosed.emit(committed)


class UiRawDataMixin:
    """Raw Data tab construction and raw-only selection controls.

    This mixin expects the shared plot/tree splitter and selection state to be
    created by ``MainWindow`` before :meth:`_build_raw_data_tab` is called.
    """

    def _build_raw_data_tab(self, tabs) -> None:
        """Create the Raw Data tab around the shared plot/tree view."""
        raw_tab = QWidget(tabs)
        self.raw_data_tab = raw_tab
        metrics = current_ui_metrics()
        raw_layout = QVBoxLayout(raw_tab)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        raw_layout.setSpacing(0)

        # Raw top controls
        self.raw_controls_above_plot = QWidget(raw_tab)
        raw_top = QHBoxLayout(self.raw_controls_above_plot)
        register_layout_role(raw_top, "strip")
        raw_top.setContentsMargins(
            metrics.strip_horizontal_margin, metrics.strip_vertical_margin,
            metrics.strip_horizontal_margin, metrics.strip_vertical_margin,
        )
        raw_top.setSpacing(metrics.strip_spacing)

        # Group loading controls (trace + average): All in region + region selector.
        self.cb_all_in_region = QCheckBox("All in region:", self.raw_controls_above_plot)
        self.cb_all_in_region.setChecked(False)
        self.cb_all_in_region.stateChanged.connect(self._on_all_in_region_toggled)
        raw_top.addWidget(self.cb_all_in_region)

        self.combo_all_region = RegionPreviewComboBox(self.raw_controls_above_plot)
        self.combo_all_region.setMinimumWidth(180)
        self.combo_all_region.setEnabled(False)
        self.combo_all_region.currentIndexChanged.connect(self._on_all_in_region_changed)
        self.combo_all_region.activated.connect(self._on_all_region_activated)
        self.combo_all_region.highlighted.connect(self._on_all_region_preview_highlighted)
        self.combo_all_region.popupOpened.connect(self._on_all_region_preview_opened)
        self.combo_all_region.popupClosed.connect(self._on_all_region_preview_closed)
        self._all_region_preview_active = False
        self._all_region_preview_popup_open = False
        raw_top.addWidget(self.combo_all_region)
        raw_top.addStretch(1)

        raw_layout.addWidget(self.raw_controls_above_plot, 0)

        # Holder where the shared splitter is inserted when this tab is active.
        self.raw_view_holder = QWidget(raw_tab)
        self.raw_view_holder_layout = QVBoxLayout(self.raw_view_holder)
        self.raw_view_holder_layout.setContentsMargins(0, 0, 0, 0)
        self.raw_view_holder_layout.setSpacing(0)
        self.raw_view_holder_layout.addWidget(self.data_view_splitter)
        raw_layout.addWidget(self.raw_view_holder, 1)

        # Raw bottom controls
        self.raw_controls_under_plot = QWidget(raw_tab)
        raw_bottom = QHBoxLayout(self.raw_controls_under_plot)
        register_layout_role(raw_bottom, "strip")
        raw_bottom.setContentsMargins(
            metrics.strip_horizontal_margin, metrics.strip_vertical_margin,
            metrics.strip_horizontal_margin, metrics.strip_vertical_margin,
        )
        raw_bottom.setSpacing(metrics.strip_spacing)
        self._flip_user_set = False
        self._auto_setting_flip = False
        self.cb_flip_be = QCheckBox("Flip X axis", self.raw_controls_under_plot)
        # Default is Binding-style; we may auto-adjust based on loaded data.
        self.cb_flip_be.setChecked(True)

        def _on_flip_changed(_state: int) -> None:
            if not self._auto_setting_flip:
                self._flip_user_set = True
            self._update_plot_from_selected()

        self.cb_flip_be.stateChanged.connect(_on_flip_changed)
        raw_bottom.addWidget(self.cb_flip_be)

        self.cb_identify_signals = QCheckBox("Identify signals", self.raw_controls_under_plot)
        self.cb_identify_signals.setToolTip(
            "Detect peaks and show conservative photoelectron/Auger assignments for selected expected elements. "
            "Available only when exactly one spectrum is active."
        )
        self.cb_identify_signals.setEnabled(False)
        raw_bottom.addWidget(self.cb_identify_signals)

        self.btn_signal_settings = QPushButton("Signals…", self.raw_controls_under_plot)
        self.btn_signal_settings.setToolTip(
            "Select expected elements, adjust identification settings, and review candidates"
        )
        self.btn_signal_settings.setEnabled(False)
        raw_bottom.addWidget(self.btn_signal_settings)

        self.cb_show_auger = QCheckBox("Show Auger", self.raw_controls_under_plot)
        self.cb_show_auger.setChecked(True)
        self.cb_show_auger.setEnabled(False)
        self.cb_show_auger.setToolTip(
            "Show or hide already identified Auger-family annotations without rerunning signal identification."
        )
        raw_bottom.addWidget(self.cb_show_auger)

        # Initialize signal identification during startup so the first use is
        # immediate rather than paying a one-off import/construction delay.
        self._signal_identification = SignalIdentificationController(self)
        self.cb_identify_signals.toggled.connect(self._signal_identification.toggle)
        self.btn_signal_settings.clicked.connect(self._signal_identification.open_dialog)
        self.cb_show_auger.toggled.connect(self._signal_identification.set_show_auger)

        raw_bottom.addStretch(1)
        raw_layout.addWidget(self.raw_controls_under_plot, 0)

        tabs.addTab(raw_tab, "Raw Data")


    def _ensure_signal_identification(self):
        return self._signal_identification

    def _refresh_signal_identification_availability(self) -> None:
        """Update signal controls without importing the heavy identification stack."""
        controller = getattr(self, "_plot_selection_controller", None)
        enabled = False
        if controller is not None:
            try:
                selection = controller.collect_selection()
                enabled = len(selection.payloads) == 1 and not selection.images
            except Exception:
                enabled = False
        self.cb_identify_signals.setEnabled(enabled)
        self.btn_signal_settings.setEnabled(enabled)
        if not enabled:
            self.cb_show_auger.setEnabled(False)
            if self.cb_identify_signals.isChecked():
                self.cb_identify_signals.blockSignals(True)
                self.cb_identify_signals.setChecked(False)
                self.cb_identify_signals.blockSignals(False)
        else:
            self.cb_show_auger.setEnabled(bool(self.cb_identify_signals.isChecked()))

    def _on_identify_signals_toggled(self, checked: bool) -> None:
        controller = self._ensure_signal_identification()
        controller.toggle(bool(checked))

    def _open_signal_settings(self) -> None:
        self._ensure_signal_identification().open_dialog()

    def _on_show_auger_toggled(self, checked: bool) -> None:
        controller = getattr(self, "_signal_identification", None)
        if controller is not None:
            controller.set_show_auger(bool(checked))

    def _refresh_all_region_combo(self) -> None:
        """Update the 'All in region' combo box based on loaded files."""
        try:
            ordered = self._loaded_tree_controller.collect_region_names()
        except Exception as exc:
            log_noncritical_error("collecting region names", exc, logger=self._logger)
            ordered = []

        self.combo_all_region.blockSignals(True)
        try:
            current = self.combo_all_region.currentText()
            self.combo_all_region.clear()
            self.combo_all_region.addItems(ordered)
            self.combo_all_region.setEnabled(len(ordered) > 0)
            if current and current in ordered:
                self.combo_all_region.setCurrentText(current)
        finally:
            self.combo_all_region.blockSignals(False)


    def _on_all_in_region_changed(self, _idx: int) -> None:
        """If the feature is active, re-apply selection for the newly chosen region."""
        try:
            if self._all_region_preview_popup_open:
                return
            if self.cb_all_in_region.isChecked():
                self._apply_all_in_region_selection()
        except Exception as exc:
            log_noncritical_error("re-applying all-in-region selection", exc, logger=self._logger)

    def _on_all_region_activated(self, _idx: int) -> None:
        """Commit a region chosen from the open popup, including the current item."""
        try:
            if self.cb_all_in_region.isChecked():
                self._apply_all_in_region_selection()
        except Exception as exc:
            log_noncritical_error("committing all-in-region selection", exc, logger=self._logger)

    def _on_all_region_preview_opened(self, _committed_index: int) -> None:
        self._all_region_preview_active = False
        self._all_region_preview_popup_open = True

    def _on_all_region_preview_highlighted(self, index: int) -> None:
        """Preview a highlighted region without changing the real selection state."""
        try:
            if not self._all_region_preview_popup_open:
                return
            if not self.cb_all_in_region.isChecked():
                return
            if index < 0 or index >= self.combo_all_region.count():
                return
            region = self.combo_all_region.itemText(index).strip()
            if not region:
                return
            self._preview_all_in_region(region)
            self._all_region_preview_active = True
        except Exception as exc:
            log_noncritical_error("previewing all-in-region selection", exc, logger=self._logger)

    def _on_all_region_preview_closed(self, committed: bool) -> None:
        """Restore the committed plot when popup browsing ends without a selection."""
        try:
            self._all_region_preview_popup_open = False
            if not self._all_region_preview_active:
                return
            self._all_region_preview_active = False
            if not committed:
                self._update_plot_from_selected()
        except Exception as exc:
            log_noncritical_error("restoring all-in-region preview", exc, logger=self._logger)

    def _preview_all_in_region(self, region: str) -> None:
        """Plot Average/Trace curves for *region* without changing tree check states."""
        payloads = []
        items_in_order = []
        metas = []
        for leaf in self._iter_curve_leaves():
            try:
                leaf_region = leaf.data(0, self.ROLE_REGION)
                meta = leaf.data(0, self.ROLE_META)
                if not (isinstance(leaf_region, str) and leaf_region == region):
                    continue
                kind = str(meta.get("kind", "")).lower() if isinstance(meta, dict) else ""
                label = str(leaf.text(0) or "").strip().lower()
                if kind not in {"average", "trace"} and label not in {"average", "trace"}:
                    continue
                payload = leaf.data(0, self.ROLE_PAYLOAD)
                if payload is None:
                    continue
                key_data = leaf.data(0, self.ROLE_KEY)
                key = key_data[0] if isinstance(key_data, tuple) and key_data else ""
                payloads.append(payload)
                items_in_order.append((leaf, str(key or "")))
                if isinstance(meta, dict):
                    metas.append(meta)
            except Exception as exc:
                log_noncritical_error("collecting region preview curves", exc, logger=self._logger)

        if not payloads:
            return

        title = f"{region} (Average)" if any(str(m.get("kind", "")).lower() == "average" for m in metas) else region
        try:
            payloads[0] = replace(payloads[0], title=title)
        except Exception:
            pass

        try:
            mode = self._current_intensity_mode()
            scaled, missing = self._apply_intensity_mode_to_payloads(payloads, items_in_order, mode)
            if not missing:
                payloads = scaled
        except Exception as exc:
            log_noncritical_error("applying preview intensity mode", exc, logger=self._logger)

        self.plot_area.plot_many(
            payloads,
            flip_binding_energy=bool(self.cb_flip_be.isChecked()),
        )


    def _on_all_in_region_toggled(self, _state: int) -> None:
        try:
            if self.cb_all_in_region.isChecked():
                self._apply_all_in_region_selection()
            else:
                # ``All in region`` is a replacement/group-selection mode: when
                # it is enabled, ``apply_all_in_region_selection`` first clears
                # every non-target leaf.  Turning the mode off should therefore
                # clear the group selection as well rather than leaving those
                # spectra checked and plotted after the checkbox is unchecked.
                leaves = self._iter_curve_leaves()
                self._show_selection_loading()
                try:
                    self._loaded_tree_controller.clear_curve_selection(leaves=leaves)
                    self._rebuild_selected_from_loaded()
                finally:
                    self._hide_selection_loading()
        except Exception as exc:
            log_noncritical_error("toggling all-in-region selection", exc, logger=self._logger)


    def _iter_curve_leaves(self) -> list[QTreeWidgetItem]:
        try:
            return self._loaded_tree_controller.iter_curve_leaves()
        except Exception as exc:
            log_noncritical_error("collecting curve leaves", exc, logger=self._logger)
            return []


    def _apply_all_in_region_selection(self) -> None:
        """Select all *average* and *trace* curves for the chosen region across all loaded files."""
        region = self._selected_target_region()
        if not region:
            return

        leaves = self._iter_curve_leaves()
        self._show_selection_loading()
        try:
            self._loaded_tree_controller.apply_all_in_region_selection(region=region, leaves=leaves)
            self._rebuild_selected_from_loaded()
        finally:
            self._hide_selection_loading()

