from __future__ import annotations

import re
from typing import Any


_PHOTON_KEYS = (
    "photon energy", "excitation energy", "beamline energy", "monochromator energy",
    "photonenergy", "excitationenergy", "hv", "hν",
)

def _number_from_value(value: Any) -> float | None:
    if value is None:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(value))
    if not match:
        return None
    try:
        number = float(match.group(0))
    except Exception:
        return None
    return number if number > 0 else None

def extract_photon_energy(meta: dict[str, Any] | None) -> float | None:
    if not isinstance(meta, dict):
        return None
    candidates: list[tuple[str, Any]] = []
    for key, value in meta.items():
        low = str(key).strip().lower().replace("_", " ")
        candidates.append((low, value))
    source = meta.get("source_metadata")
    if isinstance(source, dict):
        for key, value in source.items():
            low = str(key).strip().lower().replace("_", " ")
            candidates.append((low, value))

    # IBW acquisition notes are intentionally preserved as grouped sections
    # (for example ``section_meta["Info"]["Excitation Energy"]``) so the
    # metadata viewer remains structured and large wave notes are not copied
    # into every curve.  Signal identification still needs those acquisition
    # values, especially hν for Auger conversion on a binding-energy scale.
    # Search all grouped sections as well as the flat TXT-style metadata.
    sections = meta.get("section_meta")
    if isinstance(sections, dict):
        for values in sections.values():
            if not isinstance(values, dict):
                continue
            for key, value in values.items():
                low = str(key).strip().lower().replace("_", " ")
                candidates.append((low, value))
    for wanted in _PHOTON_KEYS:
        for key, value in candidates:
            if wanted == key or wanted in key:
                parsed = _number_from_value(value)
                if parsed is not None:
                    return parsed
    return None
