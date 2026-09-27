"""Peak-fitting workflow public API.

GUI entry points are imported lazily so numerical helper modules can be used in
headless environments, including the automated test suite.
"""

from __future__ import annotations

__all__ = ["open_fit_corelevel_dialog", "open_batch_fit_dialog"]


def __getattr__(name: str):
    if name == "open_fit_corelevel_dialog":
        from .fit_dialog import open_fit_corelevel_dialog
        return open_fit_corelevel_dialog
    if name == "open_batch_fit_dialog":
        from .batch_dialog import open_batch_fit_dialog
        return open_batch_fit_dialog
    raise AttributeError(name)
