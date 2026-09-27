from __future__ import annotations

"""Generic snapshot model for comparing 1D traces extracted from 2D data.

The model deliberately knows nothing about ResPES, ROI, Lines, or any other
producer.  Producers supply an X/Y snapshot, axis identity/labels, and arbitrary
metadata; the UI layer only compares traces with compatible X quantities.
"""

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np


def _norm_token(value: str | None) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


@dataclass
class ComparisonTrace:
    """Immutable-numerics snapshot suitable for the generic comparison window."""

    x: np.ndarray
    y: np.ndarray
    x_label: str
    y_label: str = "Intensity"
    x_quantity: str = ""
    x_unit: str | None = None
    invert_x: bool = False
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        x = np.asarray(self.x, dtype=float).reshape(-1).copy()
        y = np.asarray(self.y, dtype=float).reshape(-1).copy()
        if x.size == 0 or x.size != y.size:
            raise ValueError("The comparison trace is empty or malformed.")
        # Snapshot semantics: later changes in the producer cannot mutate data.
        x.setflags(write=False)
        y.setflags(write=False)
        self.x = x
        self.y = y
        self.x_label = str(self.x_label or "X")
        self.y_label = str(self.y_label or "Intensity")
        self.x_quantity = str(self.x_quantity or "")
        self.x_unit = None if self.x_unit in (None, "") else str(self.x_unit)
        self.invert_x = bool(self.invert_x)
        self.label = str(self.label or "")
        self.metadata = dict(self.metadata or {})

    @property
    def x_axis_key(self) -> tuple[str, str]:
        """Compatibility identity independent of the human-readable label."""
        quantity = _norm_token(self.x_quantity)
        unit = _norm_token(self.x_unit)
        if not quantity:
            # Fallback for future producers that only know a display label.
            quantity = _norm_token(self.x_label)
        return quantity, unit

    def compatible_with(self, other: "ComparisonTrace") -> bool:
        return self.x_axis_key == other.x_axis_key

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ComparisonTrace":
        """Compatibility helper for producers that naturally build mappings."""
        return cls(
            x=data.get("x", []),
            y=data.get("y", []),
            x_label=str(data.get("x_label", "X")),
            y_label=str(data.get("y_label", "Intensity")),
            x_quantity=str(data.get("x_quantity", "")),
            x_unit=data.get("x_unit"),
            invert_x=bool(data.get("invert_x", False)),
            label=str(data.get("label", "")),
            metadata=dict(data.get("metadata", {}) or {}),
        )
