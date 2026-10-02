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
        # Batch fitting is modeless so the main PANDA window remains available
        # for session saving while a sequence-fit workflow is in progress.
        self.setModal(False)
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


    def _capture_batch_parameter_table_state(self) -> list[dict[str, Any]]:
        """Capture the live batch-parameter table, including unapplied edits."""
        table = getattr(self, "tbl_batch_parameters", None)
        if table is None:
            return []
        rows: list[dict[str, Any]] = []
        for row in range(table.rowCount()):
            first = table.item(row, 0)
            parameter = table.item(row, 1)
            metadata = first.data(Qt.ItemDataRole.UserRole) if first is not None else None
            values: dict[str, str] = {}
            for col, name in ((6, "initial"), (8, "min"), (9, "max"), (11, "tie")):
                item = table.item(row, col)
                if item is not None:
                    values[name] = str(item.text())
            mode = ""
            widget = table.cellWidget(row, 10)
            if widget is not None and hasattr(widget, "currentText"):
                try:
                    mode = str(widget.currentText())
                except Exception:
                    pass
            rows.append({
                "component": str(first.text()) if first is not None else "",
                "parameter": str(parameter.text()) if parameter is not None else "",
                "metadata": dict(metadata) if isinstance(metadata, dict) else {},
                "values": values,
                "mode": mode,
            })
        return rows

    def _restore_batch_parameter_table_state(self, rows: list[dict[str, Any]]) -> None:
        """Reapply live table edits after the normal anchor-driven table rebuild."""
        table = getattr(self, "tbl_batch_parameters", None)
        if table is None or not rows:
            return

        def identity(row: int) -> tuple[str, str, str, str]:
            first = table.item(row, 0)
            parameter = table.item(row, 1)
            metadata = first.data(Qt.ItemDataRole.UserRole) if first is not None else None
            md = metadata if isinstance(metadata, dict) else {}
            return (
                str(md.get("kind") or ""),
                str(md.get("doublet_id") or md.get("doublet_label") or ""),
                str(first.text()) if first is not None else "",
                str(parameter.text()) if parameter is not None else "",
            )

        saved_by_identity: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for saved in rows:
            if not isinstance(saved, dict):
                continue
            md = saved.get("metadata") if isinstance(saved.get("metadata"), dict) else {}
            key = (
                str(md.get("kind") or ""),
                str(md.get("doublet_id") or md.get("doublet_label") or ""),
                str(saved.get("component") or ""),
                str(saved.get("parameter") or ""),
            )
            saved_by_identity[key] = saved

        self._populating_batch_table = True
        try:
            table.blockSignals(True)
            for row in range(table.rowCount()):
                saved = saved_by_identity.get(identity(row))
                if not saved:
                    continue
                values = saved.get("values") if isinstance(saved.get("values"), dict) else {}
                for col, name in ((6, "initial"), (8, "min"), (9, "max"), (11, "tie")):
                    item = table.item(row, col)
                    if item is not None and name in values:
                        item.setText(str(values.get(name) or ""))
                mode = str(saved.get("mode") or "")
                widget = table.cellWidget(row, 10)
                if mode and widget is not None and hasattr(widget, "setCurrentText"):
                    try:
                        widget.blockSignals(True)
                        widget.setCurrentText(mode)
                        widget.blockSignals(False)
                    except Exception:
                        pass
        finally:
            table.blockSignals(False)
            self._populating_batch_table = False


    def _capture_session_batch_state(self) -> dict[str, Any]:
        """Capture JSON-safe sequence-fit state for PANDA sessions."""
        anchors = {}
        for label, anchor in dict(getattr(self, "_anchors", {}) or {}).items():
            if not isinstance(anchor, dict):
                continue
            anchors[str(label)] = {
                "label": str(anchor.get("label") or label),
                "start_index": anchor.get("start_index"),
                "end_index": anchor.get("end_index"),
                "range_text": str(anchor.get("range_text") or ""),
                "n_spectra": anchor.get("n_spectra"),
                "source_keys": list(anchor.get("source_keys") or []),
                "fit_state": anchor.get("fit_state"),
                "fit_setup": anchor.get("fit_setup"),
                "fit_status": str(anchor.get("fit_status") or ""),
            }
        prepare_state = {
            "bin_size": int(getattr(self, "sb_bin_size", None).value()) if getattr(self, "sb_bin_size", None) is not None else 1,
            "tree_mode": str(getattr(self, "_tree_mode", "original") or "original"),
            "original_checked_keys": sorted(str(k) for k in (getattr(self, "_original_checked_keys", set()) or set())),
            "binned_checked_keys": sorted(str(k) for k in (getattr(self, "_binned_checked_keys", set()) or set())),
        }
        return {
            "curve_keys": [str(row[0]) for row in self._selected_items],
            "prepare_state": prepare_state,
            "anchors": anchors,
            "batch_setup_created": bool(self._batch_setup_created),
            "batch_config": self._batch_config,
            "batch_config_valid": bool(self._batch_config_valid),
            "batch_initial_guesses": self._batch_initial_guesses,
            "batch_initial_guesses_valid": bool(self._batch_initial_guesses_valid),
            "batch_passes": self._batch_passes,
            "batch_strategies": self._batch_strategies,
            "preferred_next_strategy_id": self._preferred_next_strategy_id,
            "active_analyze_pass_id": self._active_analyze_pass_id,
            "batch_trend_models": self._batch_trend_models,
            "batch_next_constraints": self._batch_next_constraints,
            "shared_anchor_fit_setup": self._shared_anchor_fit_setup,
            "batch_model_mode": self._batch_model_mode,
            "batch_parameter_table": self._capture_batch_parameter_table_state(),
            "live_preview": bool(getattr(self, "chk_batch_live_preview", None).isChecked()) if getattr(self, "chk_batch_live_preview", None) is not None else True,
            "store_all_fit_results": bool(getattr(self, "chk_batch_store_all_results", None).isChecked()) if getattr(self, "chk_batch_store_all_results", None) is not None else False,
            "active_tab": int(self.tabs.currentIndex()),
        }

    def _restore_session_batch_state(self, state: dict[str, Any]) -> None:
        """Restore a previously captured batch workspace onto current curves."""
        if not isinstance(state, dict):
            return
        import re
        import numpy as np
        from ...ui import PlotPayload

        # Restore Prepare-tab sequence state before rebuilding anchors.  Binned
        # spectra are synthetic dialog-local payloads, so they must be recreated
        # from the restored original curves before anchor source_keys can resolve.
        prepare = state.get("prepare_state") if isinstance(state.get("prepare_state"), dict) else {}
        original_keys = [str(k) for k in (prepare.get("original_checked_keys") or state.get("curve_keys") or []) if str(k)]
        if original_keys:
            available_original = {str(e.get("key", "")) for e in getattr(self, "_original_entries", [])}
            restored_original = {k for k in original_keys if k in available_original}
            if restored_original:
                self._original_checked_keys = restored_original

        bin_size = 1
        try:
            bin_size = max(1, int(prepare.get("bin_size", 1)))
        except Exception:
            bin_size = 1
        if bin_size <= 1:
            # Backward compatibility for build-8 sessions: infer the bin size
            # from the saved effective sequence (e.g. bin:...:12:001).
            config = state.get("batch_config") if isinstance(state.get("batch_config"), dict) else {}
            for row in list(config.get("sequence") or []):
                key = str(row.get("key") or "") if isinstance(row, dict) else ""
                m = re.match(r"^bin:.*:(\d+):\d+$", key)
                if m:
                    try:
                        bin_size = max(1, int(m.group(1)))
                    except Exception:
                        bin_size = 1
                    break
        try:
            if getattr(self, "sb_bin_size", None) is not None:
                self.sb_bin_size.blockSignals(True)
                self.sb_bin_size.setValue(bin_size)
                self.sb_bin_size.blockSignals(False)
            self._binned_checked_keys = {str(k) for k in (prepare.get("binned_checked_keys") or []) if str(k)}
            self._rebuild_tree_for_current_binning()
        except Exception:
            pass

        # Use the effective Prepare tree here, not _selected_items: after binning
        # the anchor/source keys refer to synthetic bin:* payloads.
        payload_by_key = {}
        try:
            for i in range(self.selected_tree.topLevelItemCount()):
                item = self.selected_tree.topLevelItem(i)
                key = item.data(0, self.ROLE_KEY) if item is not None else None
                payload = item.data(0, self.ROLE_PAYLOAD) if item is not None else None
                if isinstance(key, str) and key and payload is not None:
                    payload_by_key[key] = payload
        except Exception:
            payload_by_key = {str(k): p for k, p, _display in self._selected_items}
        anchors = {}
        for label, saved in dict(state.get("anchors") or {}).items():
            if not isinstance(saved, dict):
                continue
            source_keys = [str(k) for k in saved.get("source_keys") or [] if str(k) in payload_by_key]
            payloads = [payload_by_key[k] for k in source_keys]
            if not payloads:
                continue
            try:
                n = min(min(len(np.asarray(p.x)), len(np.asarray(p.y))) for p in payloads)
                x = np.nanmean(np.vstack([np.asarray(p.x, dtype=float)[:n] for p in payloads]), axis=0)
                y = np.nanmean(np.vstack([np.asarray(p.y, dtype=float)[:n] for p in payloads]), axis=0)
                first = payloads[0]
                anchor_payload = PlotPayload(
                    title=f"{label} anchor ({len(payloads)} spectra)", x=x, y=y,
                    xlabel=getattr(first, "xlabel", "x"), ylabel=getattr(first, "ylabel", "Intensity"),
                    energy_scale=getattr(first, "energy_scale", "Unknown"),
                )
                anchor_payload.source_keys = source_keys
                anchor_payload.anchor_label = str(label)
                anchor_payload.anchor_range_text = str(saved.get("range_text") or "")
            except Exception:
                continue
            restored = dict(saved)
            restored["payload"] = anchor_payload
            restored["source_keys"] = source_keys
            anchors[str(label)] = restored
        self._anchors = anchors
        self._batch_setup_created = bool(state.get("batch_setup_created", False))
        self._batch_config = state.get("batch_config")
        self._batch_config_valid = bool(state.get("batch_config_valid", False))
        self._batch_initial_guesses = list(state.get("batch_initial_guesses") or [])
        self._batch_initial_guesses_valid = bool(state.get("batch_initial_guesses_valid", False))
        self._batch_passes = list(state.get("batch_passes") or [])
        self._batch_strategies = list(state.get("batch_strategies") or []) or [self._default_independent_strategy()]
        self._preferred_next_strategy_id = state.get("preferred_next_strategy_id")
        self._active_analyze_pass_id = state.get("active_analyze_pass_id")
        self._batch_trend_models = list(state.get("batch_trend_models") or [])
        self._batch_next_constraints = list(state.get("batch_next_constraints") or [])
        shared = state.get("shared_anchor_fit_setup")
        if isinstance(shared, dict):
            self._shared_anchor_fit_setup = shared
        self._batch_model_mode = str(state.get("batch_model_mode") or self._batch_model_mode)
        try:
            self._refresh_anchor_status_table(); self._update_anchor_preview_plot(); self._update_proceed_button_state()
            self.tabs.setTabEnabled(self._run_tab_index, bool(self._batch_setup_created))
            if self._batch_setup_created:
                self._refresh_run_tab_anchor_summary(); self._populate_batch_parameter_table(); self._restore_batch_parameter_table_state(list(state.get("batch_parameter_table") or [])); self._refresh_batch_run_controls()
            if getattr(self, "chk_batch_live_preview", None) is not None:
                self.chk_batch_live_preview.setChecked(bool(state.get("live_preview", True)))
            if getattr(self, "chk_batch_store_all_results", None) is not None:
                self.chk_batch_store_all_results.setChecked(bool(state.get("store_all_fit_results", False)))
            if self._batch_passes:
                chosen = self._pass_by_id(self._active_analyze_pass_id) or self._batch_passes[-1]
                self._set_active_batch_results(list(chosen.get("results") or []), str(chosen.get("id") or ""))
            self._refresh_strategy_combo(); self._refresh_pass_status_label(); self._refresh_analyze_results_tab()
            idx = int(state.get("active_tab", 0)); idx = max(0, min(self.tabs.count()-1, idx))
            if self.tabs.isTabEnabled(idx): self.tabs.setCurrentIndex(idx)
        except Exception:
            pass

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
    """Open a modeless batch-fit workspace and keep it owned by the application."""
    dlg = BatchFitDialog(mw, selected_items=selected_items, parent=None)
    signature = "||".join(sorted(str(row[0]) for row in selected_items))
    dlg._session_signature = signature
    try:
        registry = getattr(mw, "_fit_session_registry", {}) or {}
        saved = (registry.get("batch", {}) or {}).get(signature)
        if isinstance(saved, dict):
            dlg._restore_session_batch_state(saved)
    except Exception:
        pass

    dialogs = getattr(mw, "_batch_fit_dialogs", None)
    if dialogs is None:
        dialogs = []
        setattr(mw, "_batch_fit_dialogs", dialogs)
    dialogs.append(dlg)

    def _forget_dialog(*_args):
        try:
            registry = getattr(mw, "_fit_session_registry", None)
            if not isinstance(registry, dict):
                registry = {"single": {}, "batch": {}}
                setattr(mw, "_fit_session_registry", registry)
            registry.setdefault("batch", {})[signature] = dlg._capture_session_batch_state()
        except Exception:
            pass
        try:
            dialogs.remove(dlg)
        except ValueError:
            pass
        try:
            dlg.deleteLater()
        except Exception:
            pass

    dlg.finished.connect(_forget_dialog)
    dlg.show()
    try:
        dlg.raise_()
        dlg.activateWindow()
    except Exception:
        pass
    return 1
