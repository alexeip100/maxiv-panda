"""Energy-calibration workflow public API.

GUI objects are imported lazily so numerical fitters and calibration helpers
remain importable in headless environments.
"""

from __future__ import annotations

__all__ = ["open_calibrate_energy_dialog", "build_calibrate_control", "CalibrationLogic"]


def __getattr__(name: str):
    if name == "open_calibrate_energy_dialog":
        from .calibrate_dialog import open_calibrate_energy_dialog
        return open_calibrate_energy_dialog
    if name == "build_calibrate_control":
        from .ui_bits import build_calibrate_control
        return build_calibrate_control
    if name == "CalibrationLogic":
        from .calibrate_logic import CalibrationLogic
        return CalibrationLogic
    raise AttributeError(name)
