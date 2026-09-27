from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

from maxiv_panda.version import __version__
from .state_models import FitSetupState, StateValidationError
from . import fit_schema

FORMAT_NAME = fit_schema.FORMAT_NAME
FORMAT_VERSION = fit_schema.CURRENT_FORMAT_VERSION


def _clean_for_json(obj: Any) -> Any:
    """Return a JSON-serializable copy of a fit setup/state object."""
    if isinstance(obj, dict):
        return {str(k): _clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_for_json(v) for v in obj]
    if isinstance(obj, set):
        return sorted(_clean_for_json(v) for v in obj)
    # NumPy scalars are common in scientific GUI state dictionaries.
    try:
        import numpy as np  # type: ignore
        if isinstance(obj, np.generic):
            return obj.item()
    except Exception:
        pass
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)


def save_fit_setup_json(path: str | Path, setup: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> None:
    """Save a complete peak-fit setup to a human-readable JSON file."""
    payload = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "software": "maxiv-panda",
        "software_version": __version__,
        "exported": datetime.now().isoformat(timespec="seconds"),
        "metadata": _clean_for_json(metadata or {}),
        "fit_setup": _clean_for_json(FitSetupState.from_mapping(setup or {}).to_mapping()),
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def load_fit_setup_json(path: str | Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Load a peak-fit setup JSON file.

    Returns ``(fit_setup, metadata)``.  For convenience during development, a raw
    dictionary containing ``peak_states`` and ``bg_state`` is also accepted.
    """
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    try:
        payload = fit_schema.canonicalize_fit_setup_payload(data)
        normalized_setup = FitSetupState.from_mapping(payload["fit_setup"]).to_mapping()
    except (fit_schema.FitSetupSchemaError, StateValidationError) as exc:
        raise ValueError(str(exc)) from exc
    return normalized_setup, dict(payload.get("metadata") or {})


def sanitize_filename_part(text: Any, *, fallback: str = "fit") -> str:
    """Return a compact filesystem-safe filename part."""
    raw = str(text or "").strip()
    if not raw:
        raw = fallback
    raw = raw.replace("—", "-").replace("–", "-")
    raw = re.sub(r"[\\/:*?\"<>|]+", "_", raw)
    raw = re.sub(r"\s+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_.-")
    return raw or fallback


def _compact_anchor_label(text: Any) -> str:
    """Extract a short anchor name such as Start/Middle/End from UI labels."""
    raw = str(text or "").strip()
    for name in ("Start", "Middle", "End"):
        if re.search(rf"\b{name}\b", raw, flags=re.IGNORECASE):
            return name
    raw = re.sub(r"\s*anchor\b.*$", "", raw, flags=re.IGNORECASE).strip()
    return raw or "anchor"


def _compact_range_label(text: Any) -> str:
    """Extract a compact range token from anchor range text, e.g. 1-10."""
    raw = str(text or "").strip()
    if not raw or raw == "—":
        return ""
    raw = raw.replace("—", "-").replace("–", "-")
    m = re.match(r"\s*(\d+)\s*-\s*(\d+)", raw)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.match(r"\s*(\d+)\s*:", raw)
    if m:
        return m.group(1)
    m = re.search(r"\bbin(?:s)?[_ ]?(\d+)\s*-\s*(\d+)\b", raw, flags=re.IGNORECASE)
    if m:
        return f"bins{int(m.group(1)):03d}-{int(m.group(2)):03d}"
    return ""


def _compact_curve_label(text: Any) -> str:
    """Return a short curve identifier for normal single-curve fits."""
    raw = str(text or "").strip()
    if not raw:
        return "curve"
    m = re.search(r"Iteration[_\s]*(\d+)", raw, flags=re.IGNORECASE)
    if m:
        return f"it{int(m.group(1)):03d}"
    m = re.search(r"\bit[_\s]*(\d+)\b", raw, flags=re.IGNORECASE)
    if m:
        return f"it{int(m.group(1)):03d}"
    # Avoid using long display strings such as "Iteration 1 in file ...".
    raw = re.sub(r"\s+in\s+.+$", "", raw, flags=re.IGNORECASE).strip()
    return raw[:60].rstrip("_.- ") or "curve"


def _normalized_filename_identity(text: Any) -> str:
    """Normalize a filename/region token for duplicate-suffix comparison.

    The comparison is intentionally forgiving about punctuation and separators
    so e.g. ``Ir4f_170eV``, ``Ir4f-170eV`` and ``Ir4f 170eV`` are treated as
    the same trailing identity. The original spelling is preserved in the
    generated filename.
    """
    return re.sub(r"[^a-z0-9]+", "", str(text or "").casefold())


def _source_already_contains_region(source_stem: str, region: str) -> bool:
    """Return True when *region* is already the trailing source identity.

    A trailing ``(N)`` copy suffix is ignored for comparison only, because file
    managers/browsers commonly add it to duplicate local copies.  The suffix is
    still preserved in the generated filename.
    """
    compare_stem = re.sub(r"\s*\(\d+\)$", "", str(source_stem or "").strip())
    source_key = _normalized_filename_identity(compare_stem)
    region_key = _normalized_filename_identity(region)
    return bool(source_key and region_key and source_key.endswith(region_key))


def _split_region_index(region: Any) -> tuple[str, str]:
    """Split PANDA's internal trailing ``#N`` region index from a region name.

    Loaded-curve keys use ``region#N`` to keep otherwise identical regions
    distinct.  The ``#N`` suffix is an internal curve-selection detail rather
    than part of the physical region identity.  Filename deduplication should
    therefore compare the source stem against the base region while retaining
    the index in the final curve identity.
    """
    raw = str(region or "").strip()
    if not raw:
        return "", ""
    match = re.match(r"^(.*?)(#\d+)$", raw)
    if not match:
        return raw, ""
    return match.group(1).rstrip(" _.-"), match.group(2)


def _strip_leading_identity(text: Any, identity: Any) -> str:
    """Strip a repeated leading metadata identity while ignoring separators.

    This is used when a curve/display label already starts with the region
    name, e.g. ``Ir4f_170eV#1_Trace``.  The comparison ignores punctuation
    and separator differences, but the remainder keeps its original spelling.
    """
    raw = str(text or "").strip()
    identity_key = _normalized_filename_identity(identity)
    if not raw or not identity_key:
        return raw

    consumed_key = ""
    for idx, char in enumerate(raw):
        if char.isalnum():
            consumed_key += char.casefold()
            if not identity_key.startswith(consumed_key):
                return raw
            if consumed_key == identity_key:
                return raw[idx + 1:].lstrip(" _.-")
    return raw


def _strip_curve_region_prefix_from_source(curve: Any, source_stem: str) -> str:
    """Strip a region-like curve prefix already present at the source end.

    This is a fallback for single-curve metadata where a separate ``region``
    field is unavailable.  It intentionally acts only on a prefix immediately
    followed by PANDA's ``#N`` region discriminator, e.g.
    ``Ir4f_170eV#1_Trace``.
    """
    raw = str(curve or "").strip()
    match = re.match(r"^(.+?)(#\d+)(.*)$", raw)
    if not match:
        return raw
    prefix, index, remainder = match.groups()
    if _source_already_contains_region(source_stem, prefix.rstrip(" _.-")):
        return f"{index}{remainder}".lstrip(" _.-")
    return raw


def compact_fit_identity_parts(
    metadata: Dict[str, Any] | None = None,
    *,
    curve_keys: tuple[str, ...] = ("curve_label", "curve_id"),
    include_anchor: bool = True,
) -> list[str]:
    """Return compact deduplicated source/region/curve-or-anchor filename parts.

    This is the shared naming primitive for fit-setup and fit-export filenames.
    It keeps source/region identity deduplication in one place so the two save
    paths cannot drift apart.
    """
    md = metadata or {}
    parts: list[str] = []
    source_file = str(md.get("source_file") or "").strip()
    source_stem = Path(source_file).stem if source_file else ""
    if source_stem:
        parts.append(source_stem)

    region = str(md.get("region") or "").strip()
    region_base, region_index = _split_region_index(region)
    region_already_in_source = bool(
        region_base and _source_already_contains_region(source_stem, region_base)
    )
    if region_base and not region_already_in_source:
        parts.append(f"{region_base}{region_index}")
    elif region_index:
        # Keep the loaded-curve discriminator without repeating the physical
        # region already present in the source filename.
        parts.append(region_index)

    anchor = str(md.get("anchor_label") or "").strip() if include_anchor else ""
    if anchor:
        parts.append("anchor")
        parts.append(_compact_anchor_label(anchor))
        range_token = _compact_range_label(md.get("anchor_range") or md.get("anchor_range_text"))
        if range_token:
            parts.append(range_token)
        return parts

    curve = ""
    for key in curve_keys:
        curve = str(md.get(key) or "").strip()
        if curve:
            break
    if curve and not region_base:
        curve = _strip_curve_region_prefix_from_source(curve, source_stem)
    if curve and region_base:
        curve = _strip_leading_identity(curve, region_base)
    # Avoid writing the region index twice when a display/curve label already
    # starts with the same ``#N`` discriminator from the loaded-curve key.
    if curve and region_index:
        curve = _strip_leading_identity(curve, region_index)
    if curve:
        parts.append(_compact_curve_label(curve))
    return parts


def suggest_fit_setup_filename(metadata: Dict[str, Any] | None = None) -> str:
    """Suggest a compact descriptive filename for a persistent fit setup.

    Full provenance is stored inside the JSON. The filename intentionally keeps
    only a short source/region/curve-or-anchor identity and uses the
    ``.fit.json`` suffix, so it does not repeat ``fit`` in the stem. Region
    identity is deduplicated consistently across source, region and curve label.
    """
    parts = compact_fit_identity_parts(metadata)
    if not parts:
        parts.append("flexpes_fit")
    stem = "_".join(sanitize_filename_part(p, fallback="fit") for p in parts if p)
    return f"{stem}.fit.json"


def suggest_fit_setup_path(directory: str | Path, metadata: Dict[str, Any] | None = None) -> Path:
    """Return the exact initial path supplied to the Save fit setup dialog."""
    return Path(directory) / suggest_fit_setup_filename(metadata)

