from __future__ import annotations

from typing import Any
from pathlib import Path

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor, QBrush, QFont, QKeySequence, QTextDocument, QShortcut
from PyQt6.QtWidgets import (
    QFileDialog,
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpinBox, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from .version import __date__, __version__
from .loaders import filter_for_kind, open_files_dialog, parse_file
from .icon import application_icon
from .utils.help_text import get_usage_html
from .widgets.help_browser import HelpBrowser
from .widgets.appearance_settings_dialog import SettingsDialog
from .ui_style import (
    SETTINGS_APPLICATION, SETTINGS_ORGANIZATION,
    current_ui_configuration, apply_ui_configuration_live,
    apply_dialog_metrics, apply_control_metrics,
)


class UiActionsMixin:
    """File, help, and top-level application actions for ``MainWindow``."""

    _SESSION_DIRECTORY_SETTINGS_KEY = "files/last_session_directory"

    def _remembered_session_directory(self) -> Path:
        """Return the last session folder, including across application restarts."""
        current = getattr(self, "_session_directory", None)
        if current:
            return Path(current)
        try:
            value = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION).value(
                self._SESSION_DIRECTORY_SETTINGS_KEY, ""
            )
            if value:
                candidate = Path(str(value))
                if candidate.exists() and candidate.is_dir():
                    self._session_directory = candidate
                    return candidate
        except Exception:
            pass
        return Path(getattr(self, "_current_data_directory", Path.cwd()))

    def _set_session_directory(self, directory: str | Path) -> None:
        """Remember the session folder for this run and future PANDA launches."""
        directory = Path(directory)
        self._session_directory = directory
        try:
            settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
            settings.setValue(self._SESSION_DIRECTORY_SETTINGS_KEY, str(directory))
            settings.sync()
        except Exception:
            pass

    def _update_load_menu_state(self) -> None:
        """Enable/disable Load submenu entries based on loaded file kind."""
        try:
            if getattr(self, '_loaded_kind', None) == 'TXT':
                self.act_txt.setEnabled(True)
                self.act_ibw.setEnabled(False)
                self.act_xy.setEnabled(False)
                self.tree.setHeaderLabels(['TXT file structure'])
            elif getattr(self, '_loaded_kind', None) == 'IBW':
                self.act_txt.setEnabled(False)
                self.act_ibw.setEnabled(True)
                self.act_xy.setEnabled(False)
                self.tree.setHeaderLabels(['IBW file structure'])
            elif getattr(self, '_loaded_kind', None) == 'XY':
                self.act_txt.setEnabled(False)
                self.act_ibw.setEnabled(False)
                self.act_xy.setEnabled(True)
                self.tree.setHeaderLabels(['SPECS Prodigy XY file structure'])
            else:
                self.act_txt.setEnabled(True)
                self.act_ibw.setEnabled(True)
                self.act_xy.setEnabled(True)
                self.tree.setHeaderLabels(['File structure'])
        except Exception:
            pass


    def _set_loaded_kind(self, kind: str | None) -> None:
        self._loaded_kind = kind
        self._update_load_menu_state()


    def _reset_signal_identification(self) -> None:
        """Restore signal identification to its new-session state."""
        controller = getattr(self, "_signal_identification", None)
        if controller is not None:
            controller.reset_to_defaults()



    def _return_to_raw_data(self) -> None:
        """Return the main workspace to Raw Data after a top-level reset."""
        try:
            self.tabs.setCurrentWidget(self.raw_data_tab)
        except Exception:
            pass

    def close_all(self) -> None:
        """Close all loaded files (clear tree and plot)."""

        self._reset_signal_identification()
        # A top-level workspace reset also clears fitting-session state.
        for dlg in list(getattr(self, "_peak_fit_dialogs", []) or []):
            try:
                dlg.close()
            except Exception:
                pass
        for dlg in list(getattr(self, "_batch_fit_dialogs", []) or []):
            try:
                dlg.close()
            except Exception:
                pass
        self._fit_session_registry = {"single": {}, "batch": {}}
        reset_map_norm = getattr(self, "_reset_map_normalization_context", None)
        if callable(reset_map_norm):
            reset_map_norm(close_dialog=True)
        self._files_root.takeChildren()
        self._files_root.setExpanded(True)
        self._set_loaded_kind(None)
        self.folder_label.setText("No folder selected")
        self._selected_tree_manager.clear()
        terminate_comparison = getattr(self, "_terminate_trace_comparison_session", None)
        if callable(terminate_comparison):
            terminate_comparison()
        reset_respes = getattr(self, "_reset_respes_context", None)
        if callable(reset_respes):
            reset_respes()
        sync_processed = getattr(self, "_sync_processed_controls_for_map_mode", None)
        if callable(sync_processed):
            sync_processed()
        self._curve_color_map.clear()
        self._next_color_index = 0
        self.plot_area.clear("Load a TXT or IBW file to begin")

        # Reset group-loading controls.
        try:
            self.cb_all_in_region.blockSignals(True)
            self.combo_all_region.blockSignals(True)
            self.cb_all_in_region.setChecked(False)
            self.combo_all_region.clear()
            self.combo_all_region.setEnabled(False)
        finally:
            try:
                self.cb_all_in_region.blockSignals(False)
                self.combo_all_region.blockSignals(False)
            except Exception:
                pass

        self._return_to_raw_data()


    def clear_all(self) -> None:
        """Clear all selected curves without unloading files.

        - Unchecks all checkboxes in the left (loaded files) tree.
        - Clears the selected-curves tree.
        - Clears the plot.
        - Disables signal identification and restores its default settings.
        """

        self._reset_signal_identification()
        for dlg in list(getattr(self, "_peak_fit_dialogs", []) or []):
            try:
                dlg.close()
            except Exception:
                pass
        for dlg in list(getattr(self, "_batch_fit_dialogs", []) or []):
            try:
                dlg.close()
            except Exception:
                pass
        self._fit_session_registry = {"single": {}, "batch": {}}
        reset_map_norm = getattr(self, "_reset_map_normalization_context", None)
        if callable(reset_map_norm):
            reset_map_norm(close_dialog=True)

        # Uncheck everything in the loaded-files tree without triggering updates on every item.
        try:
            self.tree.blockSignals(True)
            # Walk the tree recursively starting from the root.
            def _walk(item: QTreeWidgetItem) -> None:
                for i in range(item.childCount()):
                    ch = item.child(i)
                    # Only touch checkable items.
                    try:
                        if ch.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                            ch.setCheckState(0, Qt.CheckState.Unchecked)
                    except Exception:
                        pass
                    _walk(ch)

            _walk(self._files_root)
        finally:
            try:
                self.tree.blockSignals(False)
            except Exception:
                pass

        # Clear selection state and plot.
        self._selected_tree_manager.clear()
        terminate_comparison = getattr(self, "_terminate_trace_comparison_session", None)
        if callable(terminate_comparison):
            terminate_comparison()
        reset_respes = getattr(self, "_reset_respes_context", None)
        if callable(reset_respes):
            reset_respes()
        sync_processed = getattr(self, "_sync_processed_controls_for_map_mode", None)
        if callable(sync_processed):
            sync_processed()
        # Do NOT clear self._curve_color_map so colors remain stable when re-selecting.
        self.plot_area.clear("No curves selected")

        # Reset group-loading controls.
        try:
            self.cb_all_in_region.blockSignals(True)
            self.combo_all_region.blockSignals(True)
            self.cb_all_in_region.setChecked(False)
        finally:
            try:
                self.cb_all_in_region.blockSignals(False)
                self.combo_all_region.blockSignals(False)
            except Exception:
                pass

        # Files remain loaded after Clear all, so rebuild the available region
        # names instead of leaving the selector in the disabled state that can
        # be inherited from a just-restored session.
        refresh_regions = getattr(self, "_refresh_all_region_combo", None)
        if callable(refresh_regions):
            refresh_regions()

        self._return_to_raw_data()



    def _session_sources(self):
        """Return source descriptors for the minimal .panda session manifest."""
        from .session_io import SessionSource

        sources = []
        kind = str(getattr(self, "_loaded_kind", "") or "")
        for item in self._iter_loaded_file_items() or ():
            snapshot = self._snapshot_from_file_item(item)
            if snapshot is None:
                continue
            sources.append(
                SessionSource(
                    kind=kind,
                    snapshot_id=snapshot.snapshot_id,
                    canonical_path=snapshot.canonical_path,
                    physical_path=snapshot.physical_path,
                    file_name=snapshot.file_name,
                    source_label=snapshot.source_label,
                    loaded_at=snapshot.loaded_at,
                    file_mtime_ns=snapshot.file_mtime_ns,
                    file_size=snapshot.file_size,
                )
            )
        return sources

    def _session_processed_state(self):
        """Return build-3 Processed Data session descriptors and arrays."""
        from .session_io import SessionProcessedCurve, SessionSelection

        selected_raw = []
        processed = []
        arrays = {}
        for key, item in list(getattr(self, "_selected_by_key", {}).items()):
            try:
                meta = item.data(0, self.ROLE_META)
                meta = dict(meta) if isinstance(meta, dict) else {}
                checked = item.checkState(0) == Qt.CheckState.Checked
                if not bool(meta.get("processed", False)):
                    selected_raw.append(SessionSelection(key=str(key), checked=checked))
                    continue
                payload = item.data(0, self.ROLE_PAYLOAD)
                if payload is None:
                    continue
                parent = item.parent()
                parent_file = ""
                if parent is not None:
                    try:
                        region_key = self._selected_tree_manager._region_key_for_parent(parent)
                    except Exception:
                        region_key = None
                    if isinstance(region_key, tuple) and region_key:
                        parent_file = str(region_key[0])
                    else:
                        parent_file = str(parent.data(0, self.ROLE_FILE) or "")
                source_file = str(item.data(0, self.ROLE_FILE) or "")
                region = str(item.data(0, self.ROLE_REGION) or "")
                member = f"processed/{str(key).replace('/', '_').replace('\\', '_')}.npz"
                processed.append(SessionProcessedCurve(
                    key=str(key), display=str(item.text(0)), parent_file=parent_file,
                    source_file=source_file, region_name=region, array_member=member,
                    title=str(getattr(payload, "title", item.text(0))),
                    xlabel=str(getattr(payload, "xlabel", "x")), ylabel=str(getattr(payload, "ylabel", "Intensity")),
                    energy_scale=str(getattr(payload, "energy_scale", "Unknown")),
                    metadata=dict(getattr(payload, "metadata", {}) or {}), item_meta=meta, checked=checked,
                ))
                arrays[member] = (getattr(payload, "x", []), getattr(payload, "y", []))
            except Exception:
                continue

        map_states = []
        for (file_name, region_name), btn in list(getattr(self, "_region_map_buttons", {}).items()):
            try:
                map_states.append({"file": file_name, "region": region_name, "checked": bool(btn.isChecked())})
            except Exception:
                pass
        view = {
            "intensity_mode": str(getattr(self, "_processed_intensity_mode", "counts")),
            "ecal_enabled": bool(getattr(getattr(self, "btn_e_cal_toggle", None), "isChecked", lambda: False)()),
            "norm_enabled": bool(getattr(self, "_norm_to1_enabled", False)),
            "norm_energy": getattr(self, "_norm_to1_energy", None),
            "norm_span_percent": float(getattr(self, "_norm_span_percent", 1.0)),
            "norm_user_override": bool(getattr(self, "_norm_to1_user_override", False)),
            "region_cmap": [{"file": k[0], "region": k[1], "cmap": v} for k, v in getattr(self, "_region_cmap", {}).items()],
            "map_states": map_states,
            "all_in_region_enabled": bool(getattr(getattr(self, "cb_all_in_region", None), "isChecked", lambda: False)()),
            "all_in_region_target": str(getattr(self, "_selected_target_region", lambda: "")() or ""),
            "map_view_mode": (
                "lines" if bool(getattr(getattr(self, "rb_map_lines", None), "isChecked", lambda: False)()) else
                "roi" if bool(getattr(getattr(self, "rb_map_roi", None), "isChecked", lambda: False)()) else
                "simple"
            ),
            "map_bin_size": int(getattr(getattr(self, "sb_map_bin_size", None), "value", lambda: 1)()),
            "map_h_thickness": int(getattr(getattr(self, "sb_map_h_thickness", None), "value", lambda: 1)()),
            "map_v_thickness": int(getattr(getattr(self, "sb_map_v_thickness", None), "value", lambda: 1)()),
            "map_roi_spec": dict(getattr(self, "_map_roi_spec", None) or {}),
            "map_right_y_mode": str(getattr(self, "_map_right_y_mode", "iteration") or "iteration"),
            # Map normalization is independent of the 1D Processed-data
            # normalization above.  Preserve the actual 2D workspace state,
            # including the orange normalization band shown in map views.
            "map_norm_mode": str(getattr(self, "_map_norm_mode", None) or getattr(getattr(self, "cb_map_normalization", None), "currentData", lambda: "none")() or "none"),
            "map_norm_context_key": getattr(self, "_map_norm_context_key", None),
            "map_norm_be": getattr(self, "_map_norm_be", None),
            "map_norm_width_ev": getattr(self, "_map_norm_width_ev", None),
            "map_norm_area_low": getattr(self, "_map_norm_area_low", None),
            "map_norm_area_high": getattr(self, "_map_norm_area_high", None),
            "map_norm_active_interval": list(getattr(self, "_map_norm_active_interval", None) or []),
            "map_norm_show_region": bool(getattr(self, "_map_norm_show_region", True)),
            "map_lines_positions": [
                {"title": str(k[0]), "xlabel": str(k[1]), "x": float(v.get("x", 0.0)), "y": float(v.get("y", 0.0))}
                for k, v in dict(getattr(self, "_map_lines_position_memory", {}) or {}).items()
                if isinstance(k, tuple) and len(k) == 2 and isinstance(v, dict)
            ],
        }
        return selected_raw, processed, arrays, view

    def _session_fitting_state(self) -> dict[str, Any]:
        """Capture fitting state, including still-open single-fit editors."""
        registry = getattr(self, "_fit_session_registry", None)
        if not isinstance(registry, dict):
            registry = {"single": {}, "batch": {}}
            self._fit_session_registry = registry
        # Synchronize live fitting windows immediately before writing the session
        # so edits made since the dialogs were opened are not missed.
        single = registry.setdefault("single", {})
        for dlg in list(getattr(self, "_peak_fit_dialogs", []) or []):
            try:
                state = dlg._capture_session_fit_state()
                keys = state.get("curve_keys") or []
                signature = "||".join(sorted(str(k) for k in keys))
                if signature:
                    single[signature] = state
            except Exception:
                continue
        batch = registry.setdefault("batch", {})
        for dlg in list(getattr(self, "_batch_fit_dialogs", []) or []):
            try:
                state = dlg._capture_session_batch_state()
                keys = state.get("curve_keys") or []
                signature = "||".join(sorted(str(k) for k in keys))
                if signature:
                    batch[signature] = state
            except Exception:
                continue
        return registry

    def _session_signal_identification_state(self) -> dict[str, Any]:
        """Capture signal-identification controls and reusable settings.

        Plot artists/assignments are intentionally not serialized: they are
        deterministic products of the selected spectrum and settings and are
        rebuilt on session restore.
        """
        controller = getattr(self, "_signal_identification", None)
        settings = getattr(controller, "settings", None) if controller is not None else None
        if settings is None:
            return {}
        current_key = ""
        try:
            current = controller.current_single_curve()
            if current is not None:
                current_key = str(current[2] or "")
        except Exception:
            pass
        return {
            "checked": bool(getattr(getattr(self, "cb_identify_signals", None), "isChecked", lambda: False)()),
            "show_auger": bool(getattr(getattr(self, "cb_show_auger", None), "isChecked", lambda: True)()),
            "spectrum_key": current_key,
            "settings": {
                "photon_energy": settings.photon_energy,
                "tolerance_eV": float(settings.tolerance_eV),
                "prominence_fraction": float(settings.prominence_fraction),
                "include_auger": bool(settings.include_auger),
                "include_second_order": bool(settings.include_second_order),
                "small_charging_possible": bool(settings.small_charging_possible),
                "elements": sorted(str(v) for v in (settings.elements or set())),
                "sample_mode": str(settings.sample_mode),
                "valence_band_cutoff_eV": float(settings.valence_band_cutoff_eV),
            },
        }

    def _restore_signal_identification_state(self, manifest) -> list[str]:
        """Restore signal-identification settings and regenerate annotations."""
        state = dict(getattr(manifest, "signal_identification_state", {}) or {})
        if not state:
            return []
        controller = getattr(self, "_signal_identification", None)
        if controller is None:
            return ["Signal-identification state is present but cannot be restored by this PANDA build."]
        try:
            from .signal_identification.dialogs import IdentificationSettings
            raw = dict(state.get("settings") or {})
            defaults = IdentificationSettings()
            photon = raw.get("photon_energy", defaults.photon_energy)
            controller.settings = IdentificationSettings(
                photon_energy=None if photon is None else float(photon),
                tolerance_eV=float(raw.get("tolerance_eV", defaults.tolerance_eV)),
                prominence_fraction=float(raw.get("prominence_fraction", defaults.prominence_fraction)),
                include_auger=bool(raw.get("include_auger", defaults.include_auger)),
                include_second_order=bool(raw.get("include_second_order", defaults.include_second_order)),
                small_charging_possible=bool(raw.get("small_charging_possible", defaults.small_charging_possible)),
                elements=set(str(v) for v in (raw.get("elements") or [])),
                sample_mode=str(raw.get("sample_mode", defaults.sample_mode)),
                valence_band_cutoff_eV=float(raw.get("valence_band_cutoff_eV", defaults.valence_band_cutoff_eV)),
            )
            # Preserve a manually edited photon energy when the restored active
            # spectrum is the same one that owned it when the session was saved.
            controller._photon_spectrum_key = str(state.get("spectrum_key") or "") or None

            show_auger = getattr(self, "cb_show_auger", None)
            if show_auger is not None:
                show_auger.blockSignals(True)
                try:
                    show_auger.setChecked(bool(state.get("show_auger", True)))
                finally:
                    show_auger.blockSignals(False)

            controller.refresh_availability()
            identify = getattr(self, "cb_identify_signals", None)
            wanted = bool(state.get("checked", False))
            can_identify = controller.current_single_curve() is not None
            if identify is not None:
                identify.blockSignals(True)
                try:
                    identify.setChecked(bool(wanted and can_identify))
                finally:
                    identify.blockSignals(False)
            if wanted and can_identify:
                controller.identify(show_messages=False)
            else:
                controller.clear()
            if show_auger is not None:
                show_auger.setEnabled(bool(wanted and can_identify))
            try:
                self._update_plot_from_selected()
            except Exception:
                pass
            return []
        except Exception as exc:
            return [f"Could not restore signal identification: {exc}"]

    def _session_plotted_state(self) -> tuple[dict[str, Any], dict[str, tuple[Any, Any]]]:
        """Capture Plotted Data as independent numerical snapshots."""
        panel = getattr(self, "plotted_data_panel", None)
        if panel is None or not hasattr(panel, "capture_session_state"):
            return {}, {}
        try:
            return panel.capture_session_state()
        except Exception:
            return {}, {}

    def _session_workspace_state(self) -> tuple[dict[str, Any], dict[str, tuple[Any, Any]]]:
        """Capture active panel and modeless analysis-window state."""
        state: dict[str, Any] = {}
        arrays: dict[str, tuple[Any, Any]] = {}
        try:
            idx = int(self.tabs.currentIndex())
            state["active_tab_index"] = idx
            state["active_tab_text"] = str(self.tabs.tabText(idx))
        except Exception:
            pass
        try:
            g = self.geometry()
            state["main_geometry"] = [int(g.x()), int(g.y()), int(g.width()), int(g.height())]
            state["main_maximized"] = bool(self.isMaximized())
        except Exception:
            pass
        try:
            state["data_splitter_sizes"] = [int(v) for v in self.data_view_splitter.sizes()]
        except Exception:
            pass

        fit_windows = []
        for dlg in list(getattr(self, "_peak_fit_dialogs", []) or []):
            try:
                signature = str(getattr(dlg, "_session_signature", "") or "")
                if not signature:
                    fit_state = dlg._capture_session_fit_state()
                    signature = "||".join(sorted(str(k) for k in (fit_state.get("curve_keys") or [])))
                if not signature:
                    continue
                g = dlg.geometry()
                fit_windows.append({
                    "signature": signature,
                    "visible": bool(dlg.isVisible()),
                    "geometry": [int(g.x()), int(g.y()), int(g.width()), int(g.height())],
                    "maximized": bool(dlg.isMaximized()),
                })
            except Exception:
                continue
        state["fit_windows"] = fit_windows

        batch_windows = []
        for dlg in list(getattr(self, "_batch_fit_dialogs", []) or []):
            try:
                signature = str(getattr(dlg, "_session_signature", "") or "")
                if not signature:
                    batch_state = dlg._capture_session_batch_state()
                    signature = "||".join(sorted(str(k) for k in (batch_state.get("curve_keys") or [])))
                if not signature:
                    continue
                g = dlg.geometry()
                batch_windows.append({
                    "signature": signature,
                    "visible": bool(dlg.isVisible()),
                    "geometry": [int(g.x()), int(g.y()), int(g.width()), int(g.height())],
                    "maximized": bool(dlg.isMaximized()),
                })
            except Exception:
                continue
        state["batch_windows"] = batch_windows

        trace = getattr(self, "_trace_comparison_window", None)
        if trace is not None and hasattr(trace, "capture_session_state"):
            try:
                trace_state, trace_arrays = trace.capture_session_state()
                state["trace_window"] = trace_state
                arrays.update(trace_arrays)
            except Exception:
                pass
        return state, arrays

    def _restore_plotted_workspace(self, path: Path, manifest) -> list[str]:
        """Restore Plotted Data after Raw/Processed workspace reconstruction."""
        state = dict(getattr(manifest, "plotted_state", {}) or {})
        if not state:
            return []
        panel = getattr(self, "plotted_data_panel", None)
        if panel is None or not hasattr(panel, "restore_session_state"):
            return ["Plotted Data state is present but this PANDA build cannot restore it."]
        from .session_io import load_array_pair
        return panel.restore_session_state(state, lambda member: load_array_pair(path, member))

    def _iter_selected_curve_items(self):
        tree = getattr(self, "selected_tree", None)
        if tree is None:
            return
        root = tree.invisibleRootItem()
        for i in range(root.childCount()):
            parent = root.child(i)
            for j in range(parent.childCount()):
                leaf = parent.child(j)
                if leaf is not None:
                    yield leaf

    def _restore_open_fit_window(self, entry: dict[str, Any]) -> None:
        """Reopen one modeless fit editor without changing persistent selection."""
        signature = str(entry.get("signature") or "")
        keys = {k for k in signature.split("||") if k}
        if not keys:
            return
        saved_checks: dict[str, Qt.CheckState] = {}
        tree = getattr(self, "selected_tree", None)
        if tree is None:
            return
        tree.blockSignals(True)
        try:
            for leaf in self._iter_selected_curve_items() or ():
                kd = leaf.data(0, self.ROLE_KEY)
                key = kd[0] if isinstance(kd, tuple) and kd else kd
                if not isinstance(key, str) or not key:
                    continue
                saved_checks[key] = leaf.checkState(0)
                leaf.setCheckState(0, Qt.CheckState.Checked if key in keys else Qt.CheckState.Unchecked)
        finally:
            tree.blockSignals(False)
        try:
            # Fit selected is a Processed Data workflow.  Make the saved raw/E-cal
            # representation visible while constructing the dialog, then the caller
            # restores the saved main tab after all auxiliary windows exist.
            try:
                self.tabs.setCurrentIndex(1)
            except Exception:
                pass
            try:
                enabled = bool(getattr(getattr(self, "btn_e_cal_toggle", None), "isChecked", lambda: False)())
                self._update_selected_tree_visibility(show_processed=enabled)
            except Exception:
                pass
            from .workflows.peakfit.fit_dialog import open_fit_corelevel_dialog
            before = len(list(getattr(self, "_peak_fit_dialogs", []) or []))
            open_fit_corelevel_dialog(self)
            dialogs = list(getattr(self, "_peak_fit_dialogs", []) or [])
            if len(dialogs) > before:
                dlg = dialogs[-1]
                geometry = entry.get("geometry")
                if isinstance(geometry, (list, tuple)) and len(geometry) == 4:
                    try: dlg.setGeometry(*(int(v) for v in geometry))
                    except Exception: pass
                if bool(entry.get("maximized", False)):
                    try: dlg.showMaximized()
                    except Exception: pass
        finally:
            tree.blockSignals(True)
            try:
                for leaf in self._iter_selected_curve_items() or ():
                    kd = leaf.data(0, self.ROLE_KEY)
                    key = kd[0] if isinstance(kd, tuple) and kd else kd
                    if isinstance(key, str) and key in saved_checks:
                        leaf.setCheckState(0, saved_checks[key])
            finally:
                tree.blockSignals(False)

    def _restore_open_batch_window(self, entry: dict[str, Any]) -> None:
        """Reopen one modeless batch workspace without changing main selection."""
        signature = str(entry.get("signature") or "")
        saved_batch = {}
        try:
            registry = getattr(self, "_fit_session_registry", {}) or {}
            saved_batch = (registry.get("batch", {}) or {}).get(signature) or {}
        except Exception:
            saved_batch = {}
        # The sorted signature is an identity key only.  Batch fitting is a
        # sequence workflow, so reconstruct curves in their saved sequence order.
        keys = [str(k) for k in (saved_batch.get("curve_keys") or []) if str(k)]
        if not keys:
            keys = [k for k in signature.split("||") if k]
        if not keys:
            return
        # Rebuild payloads from the restored main Selected-curves tree.
        # MainWindow does not itself guarantee a build_payload_by_key() helper;
        # use the same collector as the fitting workflow so session reopening
        # works with ordinary restored raw curves as well as test hosts.
        try:
            from .workflows.peakfit.fit_dialog import _build_payload_by_key
            payload_by_key = _build_payload_by_key(self)
        except Exception:
            payload_by_key = {}
        items = []
        for key in keys:
            payload = payload_by_key.get(key)
            if payload is None:
                continue
            items.append((key, payload, str(getattr(payload, "title", key))))
        if len(items) != len(keys):
            missing = [key for key in keys if key not in payload_by_key]
            raise ValueError("missing restored curve(s): " + ", ".join(missing[:4]))

        from .workflows.peakfit.batch_dialog import open_batch_fit_dialog
        before = len(list(getattr(self, "_batch_fit_dialogs", []) or []))
        open_batch_fit_dialog(self, items)
        dialogs = list(getattr(self, "_batch_fit_dialogs", []) or [])
        if len(dialogs) <= before:
            return
        dlg = dialogs[-1]
        geometry = entry.get("geometry")
        if isinstance(geometry, (list, tuple)) and len(geometry) == 4:
            try:
                dlg.setGeometry(*(int(v) for v in geometry))
            except Exception:
                pass
        if bool(entry.get("maximized", False)):
            try:
                dlg.showMaximized()
            except Exception:
                pass

    def _restore_workspace_state(self, path: Path, manifest) -> list[str]:
        """Restore main-panel choice and auxiliary windows after data/models exist."""
        state = dict(getattr(manifest, "workspace_state", {}) or {})
        if not state:
            return []
        problems: list[str] = []
        try:
            sizes = state.get("data_splitter_sizes")
            if isinstance(sizes, (list, tuple)) and len(sizes) == 2:
                self.data_view_splitter.setSizes([int(v) for v in sizes])
        except Exception as exc:
            problems.append(f"Could not restore main workspace splitter: {exc}")
        try:
            g = state.get("main_geometry")
            if isinstance(g, (list, tuple)) and len(g) == 4:
                self.setGeometry(*(int(v) for v in g))
            if bool(state.get("main_maximized", False)):
                self.showMaximized()
        except Exception:
            pass

        trace_state = state.get("trace_window")
        if isinstance(trace_state, dict):
            try:
                from .session_io import load_array_pair
                window = self._trace_comparison_window_instance()
                problems.extend(window.restore_session_state(trace_state, lambda member: load_array_pair(path, member)))
            except Exception as exc:
                problems.append(f"Could not restore Trace window: {exc}")

        for entry in list(state.get("fit_windows") or []):
            if not isinstance(entry, dict) or not bool(entry.get("visible", True)):
                continue
            try:
                self._restore_open_fit_window(entry)
            except Exception as exc:
                problems.append(f"Could not reopen fit window: {exc}")

        for entry in list(state.get("batch_windows") or []):
            if not isinstance(entry, dict) or not bool(entry.get("visible", True)):
                continue
            try:
                self._restore_open_batch_window(entry)
            except Exception as exc:
                problems.append(f"Could not reopen batch fitting window: {exc}")

        # Restore the main panel last, after helper windows have been rebuilt.
        try:
            wanted_text = str(state.get("active_tab_text") or "")
            target = -1
            if wanted_text:
                for idx in range(self.tabs.count()):
                    if str(self.tabs.tabText(idx)) == wanted_text:
                        target = idx; break
            if target < 0:
                target = int(state.get("active_tab_index", 0))
            target = max(0, min(self.tabs.count() - 1, target))
            self.tabs.setCurrentIndex(target)
        except Exception as exc:
            problems.append(f"Could not restore active main panel: {exc}")
        return problems

    def _save_session(self) -> None:
        """Save source references and build-3 Processed Data workspace."""
        from .session_io import make_manifest, save_session_file

        start_dir = str(self._remembered_session_directory())
        path, _ = QFileDialog.getSaveFileName(self, "Save PANDA session", str(Path(start_dir) / "session.panda"),
                                               "PANDA session (*.panda);;All files (*.*)")
        if not path:
            return
        target = Path(path)
        if target.suffix.lower() != ".panda":
            target = target.with_suffix(".panda")
        try:
            raw, processed, arrays, view = self._session_processed_state()
            plotted_state, plotted_arrays = self._session_plotted_state()
            workspace_state, workspace_arrays = self._session_workspace_state()
            arrays.update(plotted_arrays); arrays.update(workspace_arrays)
            manifest = make_manifest(panda_version=__version__, sources=self._session_sources(),
                                     selected_raw=raw, processed_curves=processed, processed_view=view,
                                     fitting_state=self._session_fitting_state(), plotted_state=plotted_state,
                                     workspace_state=workspace_state,
                                     signal_identification_state=self._session_signal_identification_state())
            save_session_file(target, manifest, processed_arrays=arrays)
        except Exception as exc:
            QMessageBox.critical(self, "Save session failed", f"Could not save session:\n\n{exc}")
            return
        self._set_session_directory(target.parent)

    def _source_snapshot_from_session(self, source):
        from .source_snapshots import SourceSnapshot
        return SourceSnapshot(snapshot_id=source.snapshot_id, canonical_path=source.canonical_path,
                              physical_path=source.physical_path, file_name=source.file_name,
                              source_label=source.source_label, loaded_at=source.loaded_at,
                              file_mtime_ns=source.file_mtime_ns, file_size=source.file_size)

    def _restore_session_sources(self, manifest) -> tuple[int, list[str]]:
        restored = 0
        problems = []
        kinds = {str(src.kind) for src in manifest.sources if str(src.kind)}
        if len(kinds) > 1:
            return 0, ["This session contains mixed source formats, which this PANDA build cannot restore."]
        for source in manifest.sources:
            kind = str(source.kind or "")
            if kind not in {"TXT", "IBW", "XY"}:
                problems.append(f"{source.file_name or source.physical_path}: unsupported source kind {kind!r}")
                continue
            path = Path(source.physical_path)
            if not path.exists():
                problems.append(f"{path}: file not found")
                continue
            try:
                parsed = parse_file(path, kind=kind)
                self._add_txt_to_tree(parsed, snapshot=self._source_snapshot_from_session(source))
                restored += 1
            except Exception as exc:
                problems.append(f"{path}: {exc}")
        if restored:
            kind = next(iter(kinds), None)
            if kind:
                self._set_loaded_kind(kind)
            folders = sorted({Path(src.physical_path).parent for src in manifest.sources if Path(src.physical_path).exists()})
            if len(folders) == 1:
                self.folder_label.setText(str(folders[0])); self._current_data_directory = folders[0]
            elif folders:
                self.folder_label.setText("Multiple folders"); self._current_data_directory = folders[-1]
            panel = getattr(self, "plotted_data_panel", None)
            if panel is not None and getattr(self, "_current_data_directory", None) is not None:
                panel.set_default_directory(self._current_data_directory)
            self._refresh_all_region_combo()
        return restored, problems

    def _iter_loaded_leaves(self):
        def walk(item):
            for i in range(item.childCount()):
                child = item.child(i)
                if child is None:
                    continue
                kd = child.data(0, self.ROLE_KEY)
                if isinstance(kd, tuple):
                    yield child
                yield from walk(child)
        root = self.tree.invisibleRootItem()
        yield from walk(root)

    def _restore_processed_workspace(self, path: Path, manifest) -> list[str]:
        from .session_io import load_processed_arrays
        problems = []
        wanted = {entry.key: entry for entry in manifest.selected_raw}

        # Restore raw selections at their canonical source: the Loaded-files tree.
        # The Selected-curves tree is normally derived from these check states, so
        # restoring only Selected items leaves the two trees inconsistent and a
        # later UI refresh/rebuild can erase the apparent session selection.
        tree = getattr(self, "tree", None)
        if tree is not None:
            tree.blockSignals(True)
        try:
            for loaded in self._iter_loaded_leaves():
                kd = loaded.data(0, self.ROLE_KEY)
                if not isinstance(kd, tuple) or not kd:
                    continue
                entry = wanted.get(str(kd[0]))
                try:
                    # Presence in ``selected_raw`` means membership in the
                    # Selected-curves workspace.  ``entry.checked`` is a separate
                    # property: whether that already-selected curve was visible in
                    # the plot.  Do not conflate the two when restoring the
                    # left-hand Loaded-files tree.
                    loaded.setCheckState(
                        0,
                        Qt.CheckState.Checked if entry is not None else Qt.CheckState.Unchecked,
                    )
                except Exception as exc:
                    if entry is not None:
                        problems.append(f"Could not restore selected curve {entry.key}: {exc}")
        finally:
            if tree is not None:
                tree.blockSignals(False)

        # Restore grouping mode before rebuilding the Selected workspace.  This
        # keeps session round-trips faithful for "All in region" selections.
        # Older build-3 sessions may not contain these fields; they remain
        # compatible and are repaired below by attaching processed children to
        # the actual restored raw-source parent.
        view = dict(manifest.processed_view or {})
        try:
            grouped = bool(view.get("all_in_region_enabled", False))
            target = str(view.get("all_in_region_target") or "")
            cb = getattr(self, "cb_all_in_region", None)
            combo = getattr(self, "combo_all_region", None)
            if combo is not None and target:
                idx = combo.findText(target)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            if cb is not None:
                cb.blockSignals(True)
                cb.setChecked(grouped)
                cb.blockSignals(False)
            if combo is not None:
                combo.setEnabled(grouped)
        except Exception:
            pass

        # Rebuild through the normal selection path so internal lookup tables,
        # region parents and map controls have exactly the same shape as after a
        # user makes these selections manually.
        try:
            self._rebuild_selected_from_loaded()
            # Loading each source can queue the normal deferred Selected-tree
            # rebuild.  This explicit session rebuild supersedes those callbacks;
            # invalidate them before restoring persistent processed children so a
            # later event-loop turn cannot wipe the restored E-cal workspace.
            self._selected_rebuild_pending = False
            self._selected_rebuild_generation = int(getattr(self, "_selected_rebuild_generation", 0)) + 1
            try:
                self._hide_selection_loading()
            except Exception:
                pass
        except Exception as exc:
            problems.append(f"Could not rebuild restored Processed Data selection: {exc}")

        # Reapply per-curve plot visibility after the membership rebuild.  This
        # is deliberately separate from Loaded-tree membership so an unchecked
        # curve remains inside the same All-in-region group after a round trip.
        selected_tree = getattr(self, "selected_tree", None)
        if selected_tree is not None:
            selected_tree.blockSignals(True)
        try:
            for entry in manifest.selected_raw:
                item = getattr(self, "_selected_by_key", {}).get(entry.key)
                if item is None:
                    problems.append(f"Could not restore selected curve {entry.key}")
                    continue
                item.setCheckState(
                    0, Qt.CheckState.Checked if entry.checked else Qt.CheckState.Unchecked
                )
        finally:
            if selected_tree is not None:
                selected_tree.blockSignals(False)

        # A persistent processed (E-calibrated) curve is derived from a raw
        # source spectrum.  Guarantee that every saved source_key is present in
        # the Selected workspace, even for sessions produced by an earlier
        # build that did not capture the raw membership correctly.  This keeps
        # energy calibration reversible after reopening the session.
        required_source_keys = set()
        for proc_entry in manifest.processed_curves:
            meta = dict(proc_entry.item_meta or {})
            source_key = meta.get("source_key")
            if isinstance(source_key, str) and source_key:
                required_source_keys.add(source_key)
        missing_source_keys = required_source_keys.difference(getattr(self, "_selected_by_key", {}).keys())
        if missing_source_keys:
            for loaded in self._iter_loaded_leaves():
                kd = loaded.data(0, self.ROLE_KEY)
                if not isinstance(kd, tuple) or not kd:
                    continue
                raw_key = str(kd[0])
                if raw_key not in missing_source_keys:
                    continue
                try:
                    self._selected_tree_manager.add_from_loaded_item(
                        loaded_item=loaded, all_in_region_enabled=False, target_region=""
                    )
                    missing_source_keys.discard(raw_key)
                except Exception as exc:
                    problems.append(f"Could not restore raw source {raw_key} for calibrated curve: {exc}")
                if not missing_source_keys:
                    break
        for raw_key in sorted(missing_source_keys):
            problems.append(f"Could not find raw source {raw_key} for calibrated curve")

        try:
            arrays = load_processed_arrays(path, manifest)
        except Exception as exc:
            arrays = {}; problems.append(str(exc))
        from .ui import PlotPayload
        max_curve = int(getattr(self, "_next_curve_id", 1))
        for entry in manifest.processed_curves:
            try:
                x, y = arrays[entry.key]
                payload = PlotPayload(title=entry.title, x=x, y=y, xlabel=entry.xlabel, ylabel=entry.ylabel,
                                      energy_scale=entry.energy_scale, metadata=dict(entry.metadata or {}))
                item_meta = dict(entry.item_meta or {})

                # A calibrated curve must be a sibling of its raw source, just
                # as it is when calibration is created interactively.  Do not
                # trust historical serialized parent_file values here: early
                # build-3 sessions encoded the special __GROUP__ parent as an
                # empty string.  Resolve the canonical parent from source_key
                # whenever possible so those sessions are repaired on load.
                parent_file = entry.parent_file or entry.source_file
                source_key = item_meta.get("source_key")
                if isinstance(source_key, str) and source_key:
                    raw_item = getattr(self, "_selected_by_key", {}).get(source_key)
                    if raw_item is not None:
                        raw_parent = raw_item.parent()
                        try:
                            region_key = self._selected_tree_manager._region_key_for_parent(raw_parent)
                        except Exception:
                            region_key = None
                        if isinstance(region_key, tuple) and region_key:
                            parent_file = str(region_key[0])

                item = self._selected_tree_manager.add_selected_leaf(
                    parent_file=parent_file, region_name=entry.region_name,
                    display=entry.display, key=entry.key, payload=payload, meta=item_meta,
                    source_file=entry.source_file,
                )
                item.setCheckState(0, Qt.CheckState.Checked if entry.checked else Qt.CheckState.Unchecked)
                if entry.key.startswith("curve_"):
                    try: max_curve = max(max_curve, int(entry.key.split("_")[-1]) + 1)
                    except Exception: pass
            except Exception as exc:
                problems.append(f"Could not restore processed curve {entry.display or entry.key}: {exc}")
        self._next_curve_id = max_curve

        self._processed_intensity_mode = str(view.get("intensity_mode") or getattr(self, "_processed_intensity_mode", "counts"))
        self._norm_to1_enabled = bool(view.get("norm_enabled", False))
        self._norm_to1_energy = view.get("norm_energy")
        self._norm_span_percent = float(view.get("norm_span_percent", getattr(self, "_norm_span_percent", 1.0)))
        # Older build-3 sessions did not store this flag.  Their normalization
        # energy was normally an automatically selected edge value, so default
        # to automatic rather than accidentally converting it into a manual
        # override during widget restoration.
        self._norm_to1_user_override = bool(view.get("norm_user_override", False))
        self._norm_to1_auto_default = (
            None if self._norm_to1_user_override or self._norm_to1_energy is None
            else float(self._norm_to1_energy)
        )
        for row in view.get("region_cmap", []):
            if isinstance(row, dict):
                self._region_cmap[(str(row.get("file") or ""), str(row.get("region") or ""))] = str(row.get("cmap") or "terrain")
        # Restore the saved 2D analysis view before activating map buttons.
        # Ordinary fresh map entry intentionally defaults to Simple, but a
        # session is a workspace restore and must preserve Lines/ROI state.
        saved_map_mode = str(view.get("map_view_mode") or "simple").lower()
        if saved_map_mode not in {"simple", "lines", "roi"}:
            saved_map_mode = "simple"
        self._session_restoring_map_view = True
        self._session_saved_map_view_mode = saved_map_mode
        try:
            self._map_roi_spec = dict(view.get("map_roi_spec") or {}) or None
            self._map_right_y_mode = str(view.get("map_right_y_mode") or "iteration")
            memory = {}
            for row in view.get("map_lines_positions", []):
                if isinstance(row, dict):
                    memory[(str(row.get("title") or ""), str(row.get("xlabel") or ""))] = {
                        "x": float(row.get("x", 0.0)), "y": float(row.get("y", 0.0))
                    }
            if memory:
                self._map_lines_position_memory = memory
            for name, value in (("sb_map_bin_size", view.get("map_bin_size", 1)),
                                ("sb_map_h_thickness", view.get("map_h_thickness", 1)),
                                ("sb_map_v_thickness", view.get("map_v_thickness", 1))):
                widget = getattr(self, name, None)
                if widget is not None:
                    widget.blockSignals(True); widget.setValue(int(value)); widget.blockSignals(False)

            # Restore 2D map normalization without invoking the ordinary
            # combobox handler.  That handler intentionally reseeds defaults
            # for a fresh map and opens the settings dialog, neither of which
            # is appropriate during a quiet session restore.
            map_norm_mode = str(view.get("map_norm_mode") or "none")
            if map_norm_mode not in {"none", "at_be", "area"}:
                map_norm_mode = "none"
            self._map_norm_mode = map_norm_mode
            saved_context = view.get("map_norm_context_key")
            if isinstance(saved_context, list):
                saved_context = tuple(tuple(v) if isinstance(v, (list, tuple)) else v for v in saved_context)
            self._map_norm_context_key = saved_context
            self._map_norm_be = view.get("map_norm_be")
            self._map_norm_width_ev = view.get("map_norm_width_ev")
            self._map_norm_area_low = view.get("map_norm_area_low")
            self._map_norm_area_high = view.get("map_norm_area_high")
            interval = view.get("map_norm_active_interval")
            self._map_norm_active_interval = tuple(interval) if isinstance(interval, (list, tuple)) and len(interval) == 2 else None
            self._map_norm_show_region = bool(view.get("map_norm_show_region", True))
            norm_combo = getattr(self, "cb_map_normalization", None)
            if norm_combo is not None:
                idx = norm_combo.findData(map_norm_mode)
                norm_combo.blockSignals(True); norm_combo.setCurrentIndex(max(0, idx)); norm_combo.blockSignals(False)
        except Exception:
            pass
        for row in view.get("map_states", []):
            if not isinstance(row, dict) or not row.get("checked"):
                continue
            btn = self._region_map_buttons.get((str(row.get("file") or ""), str(row.get("region") or "")))
            if btn is not None:
                try: btn.setChecked(True)
                except Exception: pass
        try:
            button = {
                "simple": getattr(self, "rb_map_none", None),
                "lines": getattr(self, "rb_map_lines", None),
                "roi": getattr(self, "rb_map_roi", None),
            }.get(saved_map_mode)
            if button is not None:
                button.blockSignals(True); button.setChecked(True); button.blockSignals(False)
            combo = getattr(self, "cb_map_view", None)
            if combo is not None:
                idx = combo.findData(saved_map_mode)
                combo.blockSignals(True); combo.setCurrentIndex(max(0, idx)); combo.blockSignals(False)
            sync_visibility = getattr(self, "_sync_map_analysis_control_visibility", None)
            if callable(sync_visibility):
                sync_visibility()
        except Exception:
            pass
        finally:
            self._session_restoring_map_view = False
        try:
            cb = getattr(self, "cb_norm_to1_proc", None)
            if cb is not None:
                cb.blockSignals(True)
                cb.setChecked(self._norm_to1_enabled)
                cb.blockSignals(False)
            sb = getattr(self, "sb_norm_e_proc", None)
            if sb is not None and self._norm_to1_energy is not None:
                # QDoubleSpinBox may round the displayed value.  Do not let its
                # valueChanged signal replace the exact saved energy or mark an
                # automatic edge value as a user override during restore.
                sb.blockSignals(True)
                sb.setValue(float(self._norm_to1_energy))
                sb.blockSignals(False)
            span = getattr(self, "sb_norm_span_proc", None)
            if span is not None:
                span.blockSignals(True)
                span.setValue(float(self._norm_span_percent))
                span.blockSignals(False)
        except Exception:
            pass

        # Restore the E-calibration view state explicitly.  Build 3 originally
        # forced processed curves visible without synchronising the welded power
        # toggle, leaving the control and tree visibility out of step.
        has_processed = self._has_any_processed_curves()
        ecal_enabled = bool(view.get("ecal_enabled", has_processed)) if has_processed else False
        try:
            btn = getattr(self, "btn_e_cal_toggle", None)
            if btn is not None:
                btn.blockSignals(True)
                btn.setChecked(ecal_enabled)
                btn.blockSignals(False)
            welded = getattr(self, "w_calibrate_control", None)
            if welded is not None:
                welded.setProperty("ecal_on", ecal_enabled)
                for widget in (welded, getattr(self, "btn_calibrate_be", None), btn):
                    if widget is None:
                        continue
                    widget.style().unpolish(widget); widget.style().polish(widget); widget.update()
        except Exception:
            pass
        try:
            # Opening a session normally leaves the user on Raw Data.  The
            # shared tree/plot must therefore show raw curves there even when
            # the saved Processed view had E-calibration enabled.  The saved
            # toggle state is retained and takes effect when Processed Data is
            # entered.
            try:
                on_processed_tab = bool(self.tabs.currentIndex() == 1)
            except Exception:
                on_processed_tab = False
            self._update_selected_tree_visibility(
                show_processed=bool(ecal_enabled and on_processed_tab)
            )
            self._update_plot_from_selected()
        except Exception:
            pass
        return problems

    def _open_session(self) -> None:
        """Open a .panda session and restore Raw + Processed Data state."""
        from .session_io import load_session_file
        start_dir = str(self._remembered_session_directory())
        path, _ = QFileDialog.getOpenFileName(self, "Open PANDA session", start_dir,
                                               "PANDA session (*.panda);;All files (*.*)")
        if not path:
            return
        session_path = Path(path)
        try:
            manifest = load_session_file(session_path)
        except Exception as exc:
            QMessageBox.critical(self, "Open session failed", f"Could not open session:\n\n{exc}")
            return
        self._set_session_directory(session_path.parent)
        # Treat session loading as one atomic workspace transaction.  Raw source
        # insertion and checkbox cascades can normally queue deferred rebuilds;
        # those must never run midway through or immediately after restoration
        # and wipe persistent E-calibrated children.
        self._session_restore_in_progress = True
        self._selected_rebuild_pending = False
        self._selected_rebuild_generation = int(getattr(self, "_selected_rebuild_generation", 0)) + 1
        try:
            self.close_all()
            restored, problems = self._restore_session_sources(manifest)
            problems.extend(self._restore_processed_workspace(session_path, manifest))
            fitting = getattr(manifest, "fitting_state", {}) or {}
            self._fit_session_registry = {
                "single": dict(fitting.get("single") or {}),
                "batch": dict(fitting.get("batch") or {}),
            }
            problems.extend(self._restore_plotted_workspace(session_path, manifest))
            problems.extend(self._restore_signal_identification_state(manifest))
            problems.extend(self._restore_workspace_state(session_path, manifest))
        finally:
            # Invalidate every timer captured before/during the restore before
            # ordinary Loaded-tree rebuild scheduling is allowed again.
            self._selected_rebuild_pending = False
            self._selected_rebuild_generation = int(getattr(self, "_selected_rebuild_generation", 0)) + 1
            self._session_restore_in_progress = False
            try:
                self._hide_selection_loading()
            except Exception:
                pass
        if problems:
            detail = "\n".join(f"• {row}" for row in problems[:12])
            if len(problems) > 12: detail += f"\n• ... and {len(problems) - 12} more"
            QMessageBox.warning(self, "Session opened with warnings",
                                f"Restored {restored} source file(s).\n\nSome session items could not be restored:\n{detail}")

    def _load_file(self, kind: str) -> None:
        filt = filter_for_kind(kind)
        paths = self._open_files_dialog(kind=kind, filter_string=filt)
        if not paths:
            return
        self._load_paths(paths=paths, kind=kind)


    def _load_paths(self, paths: list[Any], kind: str) -> None:
        # Prevent mixing TXT and IBW in one session.
        if self._loaded_kind is not None and self._loaded_kind != kind:
            QMessageBox.information(
                self,
                'Load not allowed',
                "Only one file type at a time is supported.\n\n"
                f"You currently have {self._loaded_kind} files loaded. Please use 'Close all' first.",
            )
            return

        success_count = 0
        folders = sorted({p.parent for p in paths})
        if len(folders) == 1:
            self.folder_label.setText(str(folders[0]))
            self._current_data_directory = folders[0]
        else:
            self.folder_label.setText("Multiple folders")
            # Use the directory of the most recently supplied file for later
            # import/export dialogs while still showing the multi-folder label.
            self._current_data_directory = paths[-1].parent
        plotted_panel = getattr(self, "plotted_data_panel", None)
        if plotted_panel is not None:
            plotted_panel.set_default_directory(self._current_data_directory)

        for path in paths:
            existing = self._loaded_file_item_for_path(path)
            policy = None
            if existing is not None:
                policy = self._ask_duplicate_load_policy(existing)
                if policy == "cancel":
                    continue
            try:
                parsed = parse_file(path, kind=kind)
            except Exception as exc:
                QMessageBox.critical(self, "Load failed", f"Could not parse {path.name}\n\n{exc}")
                continue

            if existing is None:
                snapshot = self._new_source_snapshot(path, updated_copy=False)
                self._add_txt_to_tree(parsed, snapshot=snapshot)
            elif policy == "copy":
                snapshot = self._new_source_snapshot(path, updated_copy=True)
                self._add_txt_to_tree(parsed, snapshot=snapshot)
            else:
                snapshot = self._new_source_snapshot(path, updated_copy=False)
                self._replace_loaded_snapshot(
                    item=existing,
                    parsed=parsed,
                    snapshot=snapshot,
                    remove_dependencies=(policy == "remove_replace"),
                )
            success_count += 1

        if success_count > 0:
            self._refresh_all_region_combo()

        if success_count > 0 and self._loaded_kind is None:
            self._set_loaded_kind(kind)


    def _load_dropped_files(self, raw_paths: list[str]) -> None:
        from pathlib import Path

        paths = [Path(p) for p in raw_paths if p]
        if not paths:
            return

        exts = {p.suffix.lower() for p in paths}
        supported = {'.txt', '.ibw', '.xy'}
        exts = {e for e in exts if e in supported}
        if not exts:
            return
        if len(exts) > 1:
            QMessageBox.information(
                self,
                'Load not allowed',
                "Please drop either TXT files or IBW files in one action, not both together.",
            )
            return

        ext = next(iter(exts))
        kind = 'TXT' if ext == '.txt' else ('IBW' if ext == '.ibw' else 'XY')
        self._load_paths(paths=paths, kind=kind)


    def _open_files_dialog(self, kind: str, filter_string: str) -> list[Any]:
        return open_files_dialog(self, kind=kind, filter_string=filter_string)


    def _open_calibrate_be_dialog(self) -> None:
        from .workflows.calibration import open_calibrate_energy_dialog

        # If an energy calibration already exists, reopening calibration is a
        # destructive redo: old E-cal children must not coexist with a second
        # generation.  Ask explicitly before removing them.
        ecal_items = []
        try:
            for key, item in list(getattr(self, "_selected_by_key", {}).items()):
                meta = item.data(0, self.ROLE_META)
                is_ecal = (
                    isinstance(meta, dict)
                    and bool(meta.get("processed", False))
                    and ("energy_shift" in meta or "reference_key" in meta)
                )
                if is_ecal:
                    ecal_items.append((key, item))
        except Exception:
            ecal_items = []

        if ecal_items:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Redo energy calibration")
            box.setText("Energy calibration has already been performed.")
            box.setInformativeText(
                "Redoing it will delete the existing E-calibrated curves and start a new calibration from the defaults."
            )
            btn_redo = box.addButton("Redo", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(btn_cancel)
            box.exec()
            if box.clickedButton() is not btn_redo:
                return

            # Remove all existing E-cal children from the selected-curves tree
            # and registry before opening a fresh calibration dialog.
            for key, item in ecal_items:
                try:
                    parent = item.parent()
                    if parent is not None:
                        idx = parent.indexOfChild(item)
                        if idx >= 0:
                            parent.takeChild(idx)
                except Exception:
                    pass
                try:
                    self._selected_by_key.pop(key, None)
                except Exception:
                    pass

            try:
                self.btn_e_cal_toggle.setChecked(False)
            except Exception:
                pass
            try:
                self._update_selected_tree_visibility(show_processed=False)
                self._update_plot_from_selected()
            except Exception:
                pass

        open_calibrate_energy_dialog(self)


    def show_usage_info(self, md_filename: str = "usage_controls.md", window_title: str = "Usage — PANDA"):
        """Show the modeless Help browser with TOC, search, and font-size controls."""
        # Help is deliberately modeless: users should be able to keep it open
        # while working normally in the main window.  Keep at most one Help
        # window alive so repeated Help-menu actions do not accumulate dialogs.
        existing = getattr(self, "_help_dialog", None)
        if existing is not None:
            try:
                if getattr(self, "_help_md_filename", None) == md_filename and existing.isVisible():
                    existing.raise_()
                    existing.activateWindow()
                    return
                existing.close()
            except Exception:
                pass

        try:
            usage_html = get_usage_html(md_filename, 17)
        except Exception:
            usage_html = "<p><b>Help text could not be loaded.</b></p>"

        # Use a parentless top-level window rather than a dialog owned by the
        # main window.  On Windows, an owned dialog is kept above its owner and
        # normally lacks a standard taskbar/minimize relationship.  Help should
        # behave as an independent application window while remaining modeless.
        dlg = QDialog(None, Qt.WindowType.Window)
        dlg.setModal(False)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._help_dialog = dlg
        self._help_md_filename = md_filename

        def _forget_help_dialog(*_args):
            if getattr(self, "_help_dialog", None) is dlg:
                self._help_dialog = None
                self._help_md_filename = None

        dlg.destroyed.connect(_forget_help_dialog)

        help_name = "What is what?" if md_filename == "usage_controls.md" else "How to?"
        pane_subtitle = (
            "GUI elements and analysis methods"
            if md_filename == "usage_controls.md"
            else "Practical workflows and troubleshooting"
        )
        dlg.setWindowTitle(f"Help — {help_name}")
        dlg.resize(1240, 800)
        dlg.setMinimumSize(980, 680)
        dlg.setSizeGripEnabled(True)

        try:
            dlg.setWindowFlags(
                dlg.windowFlags()
                | Qt.WindowType.WindowMinimizeButtonHint
                | Qt.WindowType.WindowMaximizeButtonHint
                | Qt.WindowType.WindowCloseButtonHint
            )
        except Exception:
            pass

        layout = QVBoxLayout(dlg)
        apply_dialog_metrics(layout, compact=True)

        header = QWidget(dlg)
        header.setObjectName("helpHeader")
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header.setMaximumHeight(44)
        header.setStyleSheet(
            "QWidget#helpHeader { background: palette(alternate-base); border: 1px solid palette(mid); }"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 8, 5)
        header_layout.setSpacing(8)

        pane_title = QLabel(pane_subtitle)
        pane_title.setObjectName("helpPaneTitle")
        pane_title.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        pane_title.setStyleSheet(
            "QLabel#helpPaneTitle { font-weight: 700; font-style: italic; "
            "color: palette(link); padding: 0; }"
        )
        header_layout.addWidget(pane_title)
        header_layout.addStretch(1)

        header_layout.addWidget(QLabel("Font size:"))
        font_spin = QSpinBox()
        font_spin.setRange(8, 28)
        font_spin.setSingleStep(1)
        font_spin.setValue(17)
        font_spin.setToolTip("Set the base Help text size. Headings and navigation scale with it.")
        header_layout.addWidget(font_spin)

        header_layout.addSpacing(10)
        header_layout.addWidget(QLabel("Find:"))
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("Search help...")
        try:
            search_edit.setClearButtonEnabled(True)
        except Exception:
            pass
        search_edit.setToolTip("Press Enter for next, Shift+Enter for previous.")
        search_edit.setMinimumWidth(220)
        header_layout.addWidget(search_edit)

        prev_btn = QPushButton("Prev")
        prev_btn.setToolTip("Find the previous match.")
        header_layout.addWidget(prev_btn)
        next_btn = QPushButton("Next")
        next_btn.setToolTip("Find the next match.")
        header_layout.addWidget(next_btn)
        layout.addWidget(header, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, dlg)

        toc_panel = QWidget()
        toc_layout = QVBoxLayout(toc_panel)
        toc_layout.setContentsMargins(0, 0, 0, 0)
        toc_layout.setSpacing(5)
        toc_title = QLabel("Table of Contents")
        toc_title.setObjectName("tocTitle")
        toc_title.setStyleSheet(
            "QLabel#tocTitle { font-weight: 700; color: palette(link); "
            "background: palette(button); border: 1px solid palette(mid); padding: 5px 7px; }"
        )
        toc_layout.addWidget(toc_title)

        toc = QTreeWidget()
        toc.setHeaderHidden(True)
        toc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toc.setMinimumWidth(255)
        toc_layout.addWidget(toc, 1)

        def _set_toc_style(px: int):
            """Apply proportional navigation typography from the base Help size."""
            try:
                base = int(px)
            except Exception:
                base = 17
            sizes = {
                1: min(20, max(12, round(base * 0.84))),
                2: min(18, max(11, round(base * 0.76))),
                3: min(16, max(10, round(base * 0.68))),
            }
            toc_title_font = QFont(toc_title.font())
            toc_title_font.setPointSize(sizes[1])
            toc_title_font.setBold(True)
            toc_title.setFont(toc_title_font)
            pane_title_font = QFont(pane_title.font())
            pane_title_font.setPointSize(sizes[1])
            pane_title_font.setBold(True)
            pane_title_font.setItalic(True)
            pane_title.setFont(pane_title_font)
            try:
                toc.setStyleSheet(
                    "QTreeWidget { border: 1px solid palette(mid); padding: 3px; }"
                    "QTreeWidget::item { padding: 3px 4px; }"
                    "QTreeWidget::item:selected {"
                    " background: palette(highlight); color: palette(highlighted-text);"
                    " border-left: 4px solid palette(link);"
                    " }"
                    "QTreeWidget::branch { margin-right: 2px; }"
                )
                root = toc.invisibleRootItem()
                stack = [root.child(i) for i in range(root.childCount())]
                while stack:
                    item = stack.pop()
                    level = int(item.data(0, Qt.ItemDataRole.UserRole + 1) or 3)
                    font = QFont(toc.font())
                    font.setPointSize(sizes.get(level, sizes[3]))
                    font.setBold(level == 1)
                    font.setWeight(QFont.Weight.DemiBold if level == 2 else (QFont.Weight.Bold if level == 1 else QFont.Weight.Normal))
                    item.setFont(0, font)
                    if level == 1:
                        item.setSizeHint(0, item.sizeHint(0).expandedTo(item.sizeHint(0)))
                    stack.extend(item.child(i) for i in range(item.childCount()))
            except Exception:
                pass

        _set_toc_style(font_spin.value())

        browser = HelpBrowser()
        browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        browser.setStyleSheet("font-size: 17px;")
        # Keep Help search matches highly visible, independent of the application
        # selection palette/theme. QTextBrowser.find() selects the current match.
        try:
            help_palette = browser.palette()
            help_palette.setColor(help_palette.ColorRole.Highlight, QColor(255, 235, 59))
            help_palette.setColor(help_palette.ColorRole.HighlightedText, QColor(0, 0, 0))
            browser.setPalette(help_palette)
        except Exception:
            pass
        browser.setMinimumWidth(380)
        browser.setHtml(usage_html)

        def _do_help_search(backward: bool = False):
            text = (search_edit.text() or "").strip()
            if not text:
                return
            flags = (
                QTextDocument.FindFlag.FindBackward
                if backward
                else QTextDocument.FindFlag(0)
            )
            try:
                found = browser.find(text, flags)
            except Exception:
                found = False
            if not found:
                try:
                    cursor = browser.textCursor()
                    cursor.movePosition(cursor.End if backward else cursor.Start)
                    browser.setTextCursor(cursor)
                    found = browser.find(text, flags)
                except Exception:
                    found = False
            if not found:
                try:
                    QMessageBox.information(dlg, "Search", f'No matches for "{text}".')
                except Exception:
                    pass

        try:
            next_btn.clicked.connect(lambda: _do_help_search(False))
            prev_btn.clicked.connect(lambda: _do_help_search(True))
            search_edit.returnPressed.connect(lambda: _do_help_search(False))
        except Exception:
            pass

        try:
            sc_find = QShortcut(QKeySequence.StandardKey.Find, dlg)
            sc_find.activated.connect(lambda: (search_edit.setFocus(), search_edit.selectAll()))
            sc_next = QShortcut(QKeySequence("F3"), dlg)
            sc_next.activated.connect(lambda: _do_help_search(False))
            sc_prev = QShortcut(QKeySequence("Shift+F3"), dlg)
            sc_prev.activated.connect(lambda: _do_help_search(True))
            sc_prev_enter = QShortcut(QKeySequence("Shift+Return"), dlg)
            sc_prev_enter.activated.connect(lambda: _do_help_search(True))
        except Exception:
            pass

        try:
            toc.clear()
            current_h1 = None
            current_h2 = None
            for level, title, anchor in getattr(browser, "_help_anchors", []) or []:
                item = QTreeWidgetItem([title])
                item.setData(0, Qt.ItemDataRole.UserRole, anchor)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, level)
                if level == 1:
                    toc.addTopLevelItem(item)
                    current_h1 = item
                    current_h2 = None
                elif level == 2:
                    if current_h1 is None:
                        toc.addTopLevelItem(item)
                    else:
                        current_h1.addChild(item)
                    current_h2 = item
                else:
                    parent = current_h2 or current_h1
                    if parent is None:
                        toc.addTopLevelItem(item)
                    else:
                        parent.addChild(item)
            # Keep the major application map visible while avoiding a fully
            # expanded, visually flat contents list.
            toc.collapseAll()
            if toc.topLevelItemCount():
                toc.topLevelItem(0).setExpanded(True)
            _set_toc_style(font_spin.value())

            _expansion_guard = {"active": False}

            def _keep_one_major_branch(item):
                if _expansion_guard["active"] or item.parent() is not None:
                    return
                _expansion_guard["active"] = True
                try:
                    for idx in range(toc.topLevelItemCount()):
                        other = toc.topLevelItem(idx)
                        if other is not item:
                            other.setExpanded(False)
                finally:
                    _expansion_guard["active"] = False

            toc.itemExpanded.connect(_keep_one_major_branch)

            def _jump_to_section(item, _col=0):
                anchor = item.data(0, Qt.ItemDataRole.UserRole)
                if anchor:
                    browser.scrollToAnchor(str(anchor))
            toc.itemClicked.connect(_jump_to_section)
        except Exception:
            pass

        splitter.addWidget(toc_panel)
        splitter.addWidget(browser)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setSizes([390, 830])
        layout.addWidget(splitter, 1)

        def _apply_help_font(px: int):
            try:
                px = int(px)
            except Exception:
                px = 14
            try:
                browser.setStyleSheet(f"font-size: {px}px;")
                browser.setHtml(get_usage_html(md_filename, px))
            except Exception:
                pass
            try:
                _set_toc_style(px)
            except Exception:
                pass

        font_spin.valueChanged.connect(_apply_help_font)
        apply_control_metrics(dlg)
        dlg.show()
        try:
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            pass


    def _show_not_implemented_dialog(self, title: str):
        QMessageBox.information(self, title, "Not implemented yet")


    def show_settings(self):
        """Open the lightweight application settings dialog."""
        dlg = SettingsDialog(current_ui_configuration(), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        apply_ui_configuration_live(dlg.configuration())


    def _get_about_version(self) -> str:
        return __version__


    def show_about_info(self):
        info_text = (
            "PANDA: Photoemission Analysis, Normalization and Data Assessment\n\n"
            f"Software Version: {self._get_about_version()}\n"
            f"Date: {__date__}\n\n"
            "Created by: Alexei Preobrajenski (MAX IV Laboratory)\n"
            "License: MIT\n\n"
            "PANDA is a Python software package with an interactive graphical interface for "
            "loading, visualization, processing, analysis, and fitting of photoelectron "
            "spectroscopy (PES/XPS) data. It was developed at the FlexPES beamline at "
            "MAX IV Laboratory."
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("About PANDA")
        msg.setText(info_text)
        logo = application_icon().pixmap(96, 96)
        if not logo.isNull():
            msg.setIconPixmap(logo)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

