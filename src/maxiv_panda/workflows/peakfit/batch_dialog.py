from __future__ import annotations

from typing import Any, List, Tuple

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QTabWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from ...log_utils import get_logger
from ...plot_controller import PlotSelectionController
from ...selection_tree import SelectedTreeManager
from .batch_analyze_mixin import BatchAnalyzeMixin
from .batch_prepare_mixin import BatchPrepareMixin
from .batch_run_mixin import BatchRunMixin


class BatchFitDialog(BatchPrepareMixin, BatchRunMixin, BatchAnalyzeMixin, QDialog):
    """Batch-fitting dialog scaffold with initial sequence-preparation widgets."""

    ROLE_PAYLOAD = 0x0100
    ROLE_KEY = 0x0101
    ROLE_REGION = 0x0102
    ROLE_FILE = 0x0103
    ROLE_META = 0x0104

    def __init__(self, mw, selected_items: List[Tuple[str, Any, str]], parent=None):
        super().__init__(parent)
        self._mw = mw
        self._selected_items = list(selected_items)
        self._updating_tree = False
        self._last_selected_tree_press = None
        self._logger = get_logger()
        self._curve_color_map: dict[str, str] = {}
        self._next_color_index: int = 0
        self._selected_by_key: dict[str, QTreeWidgetItem] = {}
        self._selected_region_items: dict[tuple[str, str], QTreeWidgetItem] = {}
        self._region_map_buttons: dict[tuple[str, str], Any] = {}
        self._region_cmap: dict[tuple[str, str], str] = {}
        self._region_iteration_stack: dict[tuple[str, str], tuple[Any, Any, str]] = {}
        self._map_enabled_bases: set[tuple[str, str]] = set()
        self._cmap_by_base: dict[tuple[str, str], str] = {}
        self._waterfall_mono_color: str = "#1f77b4"
        self._original_entries: list[dict[str, Any]] = []
        self._original_checked_keys: set[str] = set()
        self._binned_checked_keys: set[str] = set()
        self._anchors: dict[str, dict[str, Any]] = {}
        self._batch_setup_created: bool = False
        self._batch_config: dict[str, Any] | None = None
        self._batch_config_valid: bool = False
        self._batch_initial_guesses: list[dict[str, Any]] = []
        self._batch_initial_guesses_valid: bool = False
        self._batch_passes: list[dict[str, Any]] = []
        self._batch_strategies: list[dict[str, Any]] = []
        self._preferred_next_strategy_id: str | None = None
        self._active_analyze_pass_id: str | None = None
        self._batch_trend_models: list[dict[str, Any]] = []
        self._batch_next_constraints: list[dict[str, Any]] = []
        self._active_trend_model: dict[str, Any] | None = None
        self._trend_analysis_trial_fit: dict[str, Any] | None = None
        self._trend_analysis_stored_fits: dict[str, dict[str, Any]] = {}
        self._populating_strategy_combo: bool = False
        self._populating_analyze_pass_combo: bool = False
        # Backward-compatible aliases pointing to the active/latest result pass.
        self._batch_fit_results: list[dict[str, Any]] = []
        self._batch_fit_results_by_key: dict[str, dict[str, Any]] = {}
        self._batch_fit_running: bool = False
        self._batch_fit_cancel_requested: bool = False
        self._batch_store_full_results_for_run: bool = False
        self._batch_fit_nav_index: int = -1
        self._populating_batch_table: bool = False
        self._populating_analyze_parameters: bool = False
        self._shared_anchor_fit_setup: dict[str, Any] = {"setup": None}
        self._anchor_model_note_shown: bool = False
        self._batch_model_mode: str = "peak-only"
        self._anchor_labels = ["Start", "Middle", "End"]
        self._anchor_colors: dict[str, str] = {
            "Start": "#1f77b4",
            "Middle": "#2ca02c",
            "End": "#d62728",
        }
        self._tree_mode: str = "original"
        self._defer_remember_visible_checks = False
        self._prepare_update_timer = QTimer(self)
        self._prepare_update_timer.setSingleShot(True)
        self._prepare_update_timer.timeout.connect(self._run_deferred_prepare_update)
        self.setWindowTitle("Batch fitting of core-level PE spectra")
        self.setModal(True)
        try:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowMinimizeButtonHint)
        except Exception:
            pass
        self.setSizeGripEnabled(True)

        self._selected_tree_manager = SelectedTreeManager(
            selected_tree=None,  # assigned after widget creation
            role_payload=self.ROLE_PAYLOAD,
            role_key=self.ROLE_KEY,
            role_region=self.ROLE_REGION,
            role_meta=self.ROLE_META,
            role_file=self.ROLE_FILE,
            region_items=self._selected_region_items,
            selected_by_key=self._selected_by_key,
            region_map_buttons=self._region_map_buttons,
            region_cmap=self._region_cmap,
            map_toggle_callback=self._on_region_map_toggled,
            choose_cmap_callback=self._choose_region_cmap,
        )
        self._plot_selection_controller = PlotSelectionController(self)

        main = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        main.addWidget(self.tabs, 1)

        tab_prepare = QWidget(self)
        self._build_prepare_tab(tab_prepare)
        self.tabs.addTab(tab_prepare, "Prepare sequence fit")

        self.tab_run = QWidget(self)
        self._build_run_tab(self.tab_run)
        self._run_tab_index = self.tabs.addTab(self.tab_run, "Run sequence fit")
        self.tabs.setTabEnabled(self._run_tab_index, False)

        self.tab_analyze = QWidget(self)
        self._build_analyze_tab(self.tab_analyze)
        self._analyze_tab_index = self.tabs.addTab(self.tab_analyze, "Analyze fit results")
        self.tabs.setTabEnabled(self._analyze_tab_index, False)
        self._reset_batch_pass_workflow(clear_results=True)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        try:
            bb.button(QDialogButtonBox.StandardButton.Close).setAutoDefault(False)
            bb.button(QDialogButtonBox.StandardButton.Close).setDefault(False)
        except Exception:
            pass
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        bb.clicked.connect(self.close)
        main.addWidget(bb)

        self._apply_single_fit_reference_size()

    def _apply_single_fit_reference_size(self) -> None:
        size = getattr(self._mw, "_single_fit_reference_size", None)
        if size is None:
            try:
                from .fit_dialog import FitCoreLevelDialog
                tmp = FitCoreLevelDialog(self._mw, parent=self._mw)
                size = tmp.size()
                setattr(self._mw, "_single_fit_reference_size", size)
                tmp.deleteLater()
            except Exception:
                size = None
        if size is not None:
            try:
                self.resize(size)
                return
            except Exception:
                pass
        sh = self.sizeHint()
        self.resize(int(sh.width() * 1.5), int(sh.height() * 1.265))


def open_batch_fit_dialog(mw, selected_items: List[Tuple[str, Any, str]]) -> int:
    dlg = BatchFitDialog(mw, selected_items=selected_items, parent=mw)
    return dlg.exec()
