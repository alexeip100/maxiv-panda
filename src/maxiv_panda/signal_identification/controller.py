from __future__ import annotations

from typing import Any

import numpy as np
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from .annotation_plotting import draw_signal_annotations
from .auger_detection import _broad_auger_assignments
from .element_consistency import apply_element_consistency
from .dialogs import IdentificationSettings, SignalIdentificationDialog
from .guided_detection import (
    _companion_assisted_peaks,
    _expected_core_windows,
    _refine_assignments_to_local_features,
)
from .matcher import PeakAssignment, match_peaks
from .peak_detection import detect_peaks, detect_reference_guided_peaks
from .spectrum_context import extract_photon_energy


class SignalIdentificationController:
    def __init__(self, window: Any):
        self.window = window
        self.settings = IdentificationSettings()
        self.assignments: list[PeakAssignment] = []
        self._active_key: str | None = None
        self._active_payload: Any = None
        self._active_meta: dict[str, Any] | None = None
        # Track which spectrum supplied the photon-energy value. A value read
        # from one spectrum must never leak into identification of another.
        self._photon_spectrum_key: str | None = None

    def _sync_photon_energy_for_spectrum(self, meta: dict[str, Any], key: str) -> float | None:
        """Refresh photon energy when the active spectrum changes.

        A manually edited value remains valid while the same spectrum stays
        active. Selecting a different spectrum replaces it with that spectrum's
        metadata value, or clears it when the new spectrum has no photon-energy
        metadata. This prevents a stale hν from being reused accidentally.
        """
        key = str(key or "")
        if key != self._photon_spectrum_key:
            self.settings.photon_energy = extract_photon_energy(meta)
            self._photon_spectrum_key = key
        return self.settings.photon_energy

    def current_single_curve(self):
        controller = getattr(self.window, "_plot_selection_controller", None)
        if controller is None:
            return None
        selection = controller.collect_selection()
        if len(selection.payloads) != 1 or selection.images:
            return None
        item, key = selection.items_in_order[0] if selection.items_in_order else (None, "")
        meta = item.data(0, self.window.ROLE_META) if item is not None else None
        return selection.payloads[0], (meta if isinstance(meta, dict) else {}), str(key or "")

    def refresh_availability(self) -> None:
        current = self.current_single_curve()
        enabled = current is not None
        if current is not None:
            _payload, meta, key = current
            self._sync_photon_energy_for_spectrum(meta, key)
        self.window.cb_identify_signals.setEnabled(enabled)
        self.window.btn_signal_settings.setEnabled(enabled)
        show_auger = getattr(self.window, "cb_show_auger", None)
        if show_auger is not None:
            show_auger.setEnabled(enabled and self.window.cb_identify_signals.isChecked())
        if not enabled and self.window.cb_identify_signals.isChecked():
            self.window.cb_identify_signals.blockSignals(True)
            self.window.cb_identify_signals.setChecked(False)
            self.window.cb_identify_signals.blockSignals(False)
            self.clear()

    def toggle(self, checked: bool) -> None:
        show_auger = getattr(self.window, "cb_show_auger", None)
        if show_auger is not None:
            show_auger.setEnabled(bool(checked) and self.current_single_curve() is not None)
        if not checked:
            self.clear()
            self.window._update_plot_from_selected()
            return
        if self.current_single_curve() is None:
            return
        if not self.settings.elements:
            self.window.cb_identify_signals.blockSignals(True)
            self.window.cb_identify_signals.setChecked(False)
            self.window.cb_identify_signals.blockSignals(False)
            QMessageBox.information(
                self.window,
                "Identify signals",
                "Select at least one expected element before identification.",
            )
            self.open_dialog()
            return
        self.identify(show_messages=True)
        self.window._update_plot_from_selected()


    def set_show_auger(self, _checked: bool) -> None:
        """Redraw annotations after changing Auger visibility.

        The toggle is intentionally display-only: assignments are preserved and
        identification is not rerun, so Auger annotations can be restored
        immediately by checking the box again.
        """
        if not self.window.cb_identify_signals.isChecked():
            return
        self.window._update_plot_from_selected()

    def identify(self, *, show_messages: bool = False) -> None:
        current = self.current_single_curve()
        if current is None:
            self.clear()
            return
        payload, meta, key = current
        photon = self._sync_photon_energy_for_spectrum(meta, key)
        self._active_payload, self._active_meta, self._active_key = payload, meta, key
        detected_all = detect_peaks(
            payload.x,
            payload.y,
            prominence_fraction=self.settings.prominence_fraction,
            # Charging-assisted matching may need to resolve a weaker
            # spin-orbit partner only 5--7 eV from the stronger component.
            # The normal survey spacing remains unchanged when the option is
            # off; the denser detection is enabled only for this extra mode.
            min_distance_fraction=(0.006 if self.settings.small_charging_possible else 0.012),
        )
        scale = str(getattr(payload, "energy_scale", "Unknown"))
        vb_cutoff = max(0.0, float(self.settings.valence_band_cutoff_eV))

        def outside_valence_band(peak) -> bool:
            if vb_cutoff <= 0:
                return True
            scale_low = scale.lower()
            if scale_low.startswith("bind"):
                return not (0.0 <= float(peak.energy) <= vb_cutoff)
            if scale_low.startswith("kin") and photon is not None:
                binding_energy = float(photon) - float(peak.energy)
                return not (0.0 <= binding_energy <= vb_cutoff)
            return True

        # The valence manifold is deliberately excluded from line matching and
        # from element-level companion scoring.  It is represented by one VB
        # region annotation instead of speculative atomic-orbital labels.
        detected = [peak for peak in detected_all if outside_valence_band(peak)]
        if scale.lower().startswith("kin") and photon is None:
            if show_messages:
                QMessageBox.information(
                    self.window,
                    "Identify signals",
                    "Photon energy is required to identify photoelectron signals on a kinetic-energy scale. "
                    "Open Signal settings and enter the photon energy.",
                )
            self.assignments = []
            return
        if not self.settings.elements:
            self.assignments = []
            if show_messages:
                QMessageBox.information(
                    self.window,
                    "Identify signals",
                    "Select at least one expected element in Signal settings.",
                )
            return
        expected_windows = _expected_core_windows(
            energy_scale=scale, photon_energy=photon, selected_elements=set(self.settings.elements or ()),
            tolerance_eV=float(self.settings.tolerance_eV), sample_mode=self.settings.sample_mode,
            vb_cutoff=vb_cutoff,
        )
        guided = detect_reference_guided_peaks(
            payload.x, payload.y, expected_windows=expected_windows, existing_peaks=detected,
            min_feature_fraction=max(self.settings.prominence_fraction, 0.001),
        )
        combined = list(detected) + [peak for peak in guided if all(abs(peak.energy - p.energy) > 0.4 for p in detected)]
        combined.sort(key=lambda peak: peak.energy)
        self.assignments = match_peaks(
            combined,
            energy_scale=scale,
            photon_energy=photon,
            tolerance_eV=self.settings.tolerance_eV,
            elements=self.settings.elements,
            include_auger=self.settings.include_auger and photon is not None,
            include_second_order=self.settings.include_second_order,
            small_charging_possible=self.settings.small_charging_possible,
            sample_mode=self.settings.sample_mode,
        )
        self.assignments = _refine_assignments_to_local_features(
            self.assignments, payload, tolerance_eV=float(self.settings.tolerance_eV)
        )
        companion_peaks = _companion_assisted_peaks(
            self.assignments, payload, energy_scale=scale, photon_energy=photon,
            sample_mode=self.settings.sample_mode,
        )
        if companion_peaks:
            new_companion_peaks = [
                peak for peak in companion_peaks
                if all(abs(float(peak.energy) - float(existing.energy)) > 0.4 for existing in combined)
            ]
            # Re-running the complete matcher is useful only when companion
            # recovery added a genuinely new measured feature.  Previous
            # versions repeated the whole matching/refinement pass even when
            # every proposed companion was already in ``combined``.
            if new_companion_peaks:
                combined.extend(new_companion_peaks)
                combined.sort(key=lambda peak: peak.energy)
                self.assignments = match_peaks(
                    combined, energy_scale=scale, photon_energy=photon,
                    tolerance_eV=self.settings.tolerance_eV, elements=self.settings.elements,
                    include_auger=self.settings.include_auger and photon is not None,
                    include_second_order=self.settings.include_second_order,
                    small_charging_possible=self.settings.small_charging_possible, sample_mode=self.settings.sample_mode,
                )
                self.assignments = _refine_assignments_to_local_features(
                    self.assignments, payload, tolerance_eV=float(self.settings.tolerance_eV)
                )
        # Resolve complete spin-orbit families and cross-shell consistency only
        # after all ordinary and companion-guided PE features are available.
        # Yeh-Lindau cross sections affect relative plausibility, but never
        # create a label without an independent measured maximum.
        self.assignments = apply_element_consistency(
            self.assignments, payload,
            selected_elements=set(self.settings.elements or ()),
            energy_scale=scale, photon_energy=photon,
            sample_mode=self.settings.sample_mode,
        )
        if self.settings.include_auger and photon is not None:
            # The normal matcher may use handbook Auger candidates while
            # resolving individual peaks, but visible Auger annotations are
            # produced only by the evidence-gated family detector.  Replace
            # direct candidates to avoid duplicate labels and theoretical
            # regions being shown without independent measured support.
            broad_assignments = _broad_auger_assignments(
                self.assignments, payload, energy_scale=scale, photon_energy=photon,
                selected_elements=set(self.settings.elements or ()),
                small_charging_possible=self.settings.small_charging_possible,
            )
            self.assignments = [
                assignment for assignment in self.assignments
                if assignment.best is None or assignment.best.kind != "Auger"
            ] + broad_assignments
        if show_messages and not detected_all and not guided and not companion_peaks:
            QMessageBox.information(self.window, "Identify signals", "No peaks passed the current prominence threshold.")

    def open_dialog(self) -> None:
        current = self.current_single_curve()
        if current is None:
            return
        payload, meta, key = current
        self._sync_photon_energy_for_spectrum(meta, key)
        dialog = SignalIdentificationDialog(
            self.window,
            settings=self.settings,
            assignments=self.assignments,
            energy_scale=str(getattr(payload, "energy_scale", "Unknown")),
        )
        def apply_and_identify() -> None:
            self.settings = dialog.settings()
            self._photon_spectrum_key = str(key or "")
            if not self.window.cb_identify_signals.isChecked():
                # Avoid depending on the checkbox signal for the dialog refresh.
                self.window.cb_identify_signals.blockSignals(True)
                self.window.cb_identify_signals.setChecked(True)
                self.window.cb_identify_signals.blockSignals(False)
            self.identify(show_messages=True)
            self.window._update_plot_from_selected()
            dialog.set_assignments(self.assignments)

        dialog.apply_requested.connect(apply_and_identify)
        dialog.exec()

    def clear(self) -> None:
        self.assignments = []
        self._active_key = None
        self._active_payload = None
        self._active_meta = None

    def reset_to_defaults(self) -> None:
        """Disable identification and restore its session settings.

        This is used by the top-level *Clear all* and *Close all* actions so
        signal annotations and settings from the previous selection cannot
        leak into the next spectrum.  The checkbox signal is blocked because
        those actions already own the plot reset.
        """
        checkbox = getattr(self.window, "cb_identify_signals", None)
        if checkbox is not None:
            try:
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
            finally:
                checkbox.blockSignals(False)

        show_auger = getattr(self.window, "cb_show_auger", None)
        if show_auger is not None:
            try:
                show_auger.blockSignals(True)
                show_auger.setChecked(True)
                show_auger.setEnabled(False)
            finally:
                show_auger.blockSignals(False)

        self.settings = IdentificationSettings()
        self._photon_spectrum_key = None
        self.clear()

    def draw_annotations(self) -> None:
        draw_signal_annotations(self)

