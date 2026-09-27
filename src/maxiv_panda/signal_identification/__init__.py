"""Signal identification for survey and other single PES spectra.

The GUI controller is loaded lazily so matching and peak-detection utilities
can be imported without PyQt6.
"""

from __future__ import annotations

__all__ = ["SignalIdentificationController"]


def __getattr__(name: str):
    if name == "SignalIdentificationController":
        from .controller import SignalIdentificationController
        return SignalIdentificationController
    raise AttributeError(name)
