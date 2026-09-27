from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


def source_aware_curve_title(base_title: str, file_name: str) -> str:
    """Return a compact plotting title that includes the source-file tag."""
    from ...selection_tree import derive_file_tag

    title = str(base_title or "Curve").strip() or "Curve"
    file_tag = derive_file_tag(file_name) if file_name else ""
    if file_tag and file_tag not in title:
        return f"[{file_tag}] {title}"
    return title


@dataclass
class PlottedCurve:
    """Independent display snapshot used by the Plotted Data panel."""

    title: str
    x: np.ndarray
    y: np.ndarray
    xlabel: str = "Energy"
    ylabel: str = "Intensity"
    energy_scale: str = "Unknown"
    visible: bool = True
    color: str | None = None
    linestyle: str = "-"
    linewidth: float = 2.0
    custom_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: Any, *, color: str | None = None) -> "PlottedCurve | None":
        x = np.asarray(getattr(payload, "x", []), dtype=float).copy()
        y = np.asarray(getattr(payload, "y", []), dtype=float).copy()
        if x.size == 0 or y.size == 0 or x.shape != y.shape:
            return None
        title = str(getattr(payload, "title", ""))
        return cls(
            title=title,
            custom_name=str(getattr(payload, "custom_name", "") or ""),
            x=x,
            y=y,
            xlabel=str(getattr(payload, "xlabel", "Energy")),
            ylabel=str(getattr(payload, "ylabel", "Intensity")),
            energy_scale=str(getattr(payload, "energy_scale", "Unknown")),
            visible=bool(getattr(payload, "visible", True)),
            color=color if color is not None else getattr(payload, "color", None),
            linestyle=str(getattr(payload, "linestyle", "-")),
            linewidth=float(getattr(payload, "linewidth", 2.0)),
            metadata=dict(getattr(payload, "metadata", {}) or {}),
        )
