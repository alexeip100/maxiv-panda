from types import SimpleNamespace

import pytest
pytest.importorskip("PyQt6")

from maxiv_panda.signal_identification.controller import SignalIdentificationController
from maxiv_panda.signal_identification.dialogs import IdentificationSettings


class _Checkbox:
    def __init__(self):
        self.checked = True
        self.blocked = False
        self.calls = []

    def blockSignals(self, value):
        self.blocked = bool(value)
        self.calls.append(("block", bool(value)))

    def setChecked(self, value):
        self.checked = bool(value)
        self.calls.append(("checked", bool(value)))


def test_reset_to_defaults_unchecks_and_clears_session_state():
    checkbox = _Checkbox()
    controller = SignalIdentificationController(SimpleNamespace(cb_identify_signals=checkbox))
    controller.settings = IdentificationSettings(
        photon_energy=1215.0,
        tolerance_eV=8.0,
        prominence_fraction=0.02,
        include_auger=False,
        include_second_order=True,
        small_charging_possible=True,
        elements={"Ni", "O"},
        sample_mode="Gas phase",
        valence_band_cutoff_eV=10.0,
    )
    controller.assignments = [object()]
    controller._active_key = "curve"
    controller._active_payload = object()
    controller._active_meta = {"x": 1}
    controller._photon_spectrum_key = "curve"

    controller.reset_to_defaults()

    assert checkbox.checked is False
    assert checkbox.calls == [("block", True), ("checked", False), ("block", False)]
    assert controller.settings == IdentificationSettings()
    assert controller.assignments == []
    assert controller._active_key is None
    assert controller._active_payload is None
    assert controller._active_meta is None
    assert controller._photon_spectrum_key is None
