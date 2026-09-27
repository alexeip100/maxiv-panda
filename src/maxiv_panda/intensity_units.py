from __future__ import annotations

from typing import Any

import numpy as np


COUNTS = "counts"
CPS = "cps"


def time_per_spectrum_channel(metadata: Any) -> float | None:
    """Return the effective acquisition time per final spectrum channel in seconds.

    Scienta TXT/IBW metadata names the field ``Time per Spectrum Channel``.
    From v0.10.80 curve metadata also carries an explicit normalized
    ``time_per_spectrum_channel`` value so the acquisition time survives every
    tree-copy/Processed-data path.  The recursive fallback keeps older metadata
    and both TXT/IBW section layouts compatible.
    """
    candidates: list[Any] = []
    if isinstance(metadata, dict):
        # Prefer the explicit curve-level value introduced for CPS handling.
        candidates.extend((
            metadata.get("time_per_spectrum_channel"),
            metadata.get("Time per Spectrum Channel"),
        ))

        wanted = "timeperspectrumchannel"

        def collect(mapping: dict[str, Any], depth: int = 0) -> None:
            if depth > 4:
                return
            for key, value in mapping.items():
                normalized = "".join(ch for ch in str(key).lower() if ch.isalnum())
                if normalized == wanted:
                    candidates.append(value)
                elif isinstance(value, dict):
                    collect(value, depth + 1)

        collect(metadata)

    for raw in candidates:
        if raw is None:
            continue
        try:
            value = float(str(raw).strip())
        except (TypeError, ValueError):
            continue
        if np.isfinite(value) and value > 0.0:
            return value
    return None


def scale_payload(payload: Any, *, seconds: float, mode: str) -> Any:
    """Return *payload* represented in counts or counts per second.

    The original payload is never modified.  Counts mode returns the original
    object because raw/processed stored arrays are intentionally kept in counts.
    """
    if str(mode).lower() != CPS:
        return payload
    if not np.isfinite(seconds) or float(seconds) <= 0.0:
        raise ValueError("seconds must be a positive finite number")
    cls = type(payload)
    result = cls(
        title=getattr(payload, "title", ""),
        x=getattr(payload, "x", []),
        y=np.asarray(getattr(payload, "y", []), dtype=float) / float(seconds),
        xlabel=getattr(payload, "xlabel", "x"),
        ylabel="Intensity [counts/s]",
        energy_scale=getattr(payload, "energy_scale", "Unknown"),
    )
    try:
        result.metadata = dict(getattr(payload, "metadata", {}) or {})
    except Exception:
        pass
    return result
