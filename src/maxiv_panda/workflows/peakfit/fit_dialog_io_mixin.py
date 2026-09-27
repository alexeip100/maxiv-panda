from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from PyQt6.QtWidgets import QFileDialog
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from . import fit_export, fit_io


class FitDialogIOMixin:
    def _update_saved_setup_status(self) -> None:
        action = getattr(self, "act_load_config_snapshot", None)
        if action is not None:
            action.setEnabled(bool(self._saved_fit_setup))
    def _on_save_fit_setup(self) -> None:
        self._saved_fit_setup = self._capture_fit_setup_template()
        if isinstance(getattr(self, "_shared_fit_setup_ref", None), dict):
            self._shared_fit_setup_ref["setup"] = self._saved_fit_setup
        self._update_saved_setup_status()
    def _on_apply_fit_setup(self) -> None:
        if isinstance(getattr(self, "_shared_fit_setup_ref", None), dict):
            shared_setup = self._shared_fit_setup_ref.get("setup")
            if shared_setup is not None:
                self._saved_fit_setup = shared_setup
        if not self._saved_fit_setup:
            self._show_warning("No saved setup", "No saved fit setup available.")
            return
        self._apply_fit_setup_template(self._saved_fit_setup)
        key = self._get_checked_key()
        if key:
            self._curve_states[key] = self._capture_curve_state()
    def _current_fit_io_metadata(self) -> Dict[str, Any]:
        """Return metadata that ties a saved setup to the current curve/anchor."""
        key = self._get_checked_key()
        payload = self._payload_by_key.get(key) if key else None
        display = self._display_by_key.get(key, "") if key else ""
        curve_label = display or str(getattr(payload, "title", "") or key or "curve")
        source_file = ""
        region = ""
        source_curve = ""
        source_key = ""

        # In anchor mode, the supplied payload may carry original source keys from the batch window.
        source_keys = getattr(payload, "source_keys", None)
        if isinstance(source_keys, (list, tuple)) and source_keys:
            source_key = str(source_keys[0])
        elif key and key != "__supplied_anchor__":
            source_key = str(key)

        if source_key:
            parts = source_key.split(":::")
            if len(parts) >= 1:
                source_file = parts[0]
            if len(parts) >= 2:
                region = parts[1]
            if len(parts) >= 3:
                source_curve = parts[2]

        anchor_label = ""
        anchor_range = ""
        if getattr(self, "_single_payload_mode", False):
            # For anchor spectra from the batch window, prefer compact metadata
            # attached to the payload over the long human-readable window title.
            anchor_label = str(getattr(payload, "anchor_label", "") or getattr(self, "_supplied_label", "") or curve_label or "anchor")
            anchor_range = str(getattr(payload, "anchor_range_text", "") or "")

        return {
            "curve_id": str(key or curve_label),
            "curve_label": str(source_curve or curve_label),
            "display_label": str(display or curve_label),
            "anchor_label": anchor_label,
            "anchor_range": anchor_range,
            "source_file": str(source_file),
            "region": str(region),
            "source_key": str(source_key),
            "payload_title": str(getattr(payload, "title", "") if payload is not None else ""),
            "energy_scale": str(getattr(payload, "energy_scale", "Unknown") if payload is not None else "Unknown"),
            "xlabel": str(getattr(payload, "xlabel", "") if payload is not None else ""),
            "ylabel": str(getattr(payload, "ylabel", "") if payload is not None else ""),
        }
    def _fit_io_default_dir(self) -> Path:
        """Choose a useful initial directory for fit setup file dialogs."""
        remembered = getattr(self, "_last_fit_io_dir", None) or getattr(self._mw, "_last_fit_io_dir", None)
        if remembered:
            try:
                p = Path(str(remembered))
                if p.exists():
                    return p
            except Exception:
                pass
        try:
            text = str(getattr(self._mw, "folder_label", None).text()).strip()
            p = Path(text)
            if text and p.exists() and p.is_dir():
                return p
        except Exception:
            pass
        try:
            return Path.home()
        except Exception:
            return Path(".")
    def _remember_fit_io_dir(self, path: str) -> None:
        try:
            p = Path(path).parent
            self._last_fit_io_dir = str(p)
            setattr(self._mw, "_last_fit_io_dir", str(p))
        except Exception:
            pass
    def _on_export_fit_results(self) -> None:
        fit_export.export_single_fit_results(self)
    def _on_save_fit_setup_file(self) -> None:
        setup = self._capture_fit_setup_template()
        metadata = self._current_fit_io_metadata()
        start_path = fit_io.suggest_fit_setup_path(self._fit_io_default_dir(), metadata)
        path, _flt = QFileDialog.getSaveFileName(
            self,
            "Save fit setup",
            str(start_path),
            "FlexPES fit setup (*.fit.json);;JSON files (*.json);;All files (*.*)",
        )
        if not path:
            return
        if not str(path).lower().endswith(".json"):
            path = f"{path}.fit.json"
        try:
            fit_io.save_fit_setup_json(path, setup, metadata=metadata)
            self._remember_fit_io_dir(path)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", f"Could not save fit setup file:\n\n{exc}")
    def _on_load_fit_setup_file(self) -> None:
        start_dir = self._fit_io_default_dir()
        path, _flt = QFileDialog.getOpenFileName(
            self,
            "Load fit setup",
            str(start_dir),
            "JSON files (*.json);;All files (*.*)",
        )
        if not path:
            return
        try:
            setup, metadata = fit_io.load_fit_setup_json(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load failed", f"Could not load fit setup file:\n\n{exc}")
            return
        try:
            self._apply_fit_setup_template(setup)
            self._saved_fit_setup = setup
            if isinstance(getattr(self, "_shared_fit_setup_ref", None), dict):
                self._shared_fit_setup_ref["setup"] = setup
            self._update_saved_setup_status()
            key = self._get_checked_key()
            if key:
                self._curve_states[key] = self._capture_curve_state()
            self._remember_fit_io_dir(path)
        except Exception as exc:
            QMessageBox.critical(self, "Apply failed", f"The file was read, but the setup could not be applied:\n\n{exc}")
