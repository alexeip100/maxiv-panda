"""Common helpers and lightweight shared types.

Keep this module small and stable. Put only truly shared utilities/types here to
avoid circular imports as the codebase grows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class CalibrationHost:
    """Thin adapter around the MainWindow instance for workflows.

    Centralizes a few MainWindow-dependent operations to reduce coupling.
    """
    mw: Any

    def build_payload_by_key(self) -> Dict[str, Any]:
        """Return mapping key -> PlotPayload for all known curve leaves."""
        payload_by_key: Dict[str, Any] = {}
        mw = self.mw

        # Local import avoids hard import cycles at module import time.
        from .ui import PlotPayload  # type: ignore

        for leaf in mw._iter_curve_leaves():
            kd = leaf.data(0, mw.ROLE_KEY)
            pl = leaf.data(0, mw.ROLE_PAYLOAD)

            # ROLE_KEY is sometimes stored as (key, display); normalize.
            if isinstance(kd, (tuple, list)) and len(kd) > 0:
                key = kd[0]
            else:
                key = kd

            if key and pl is not None and isinstance(pl, PlotPayload):
                payload_by_key[str(key)] = pl

        return payload_by_key
