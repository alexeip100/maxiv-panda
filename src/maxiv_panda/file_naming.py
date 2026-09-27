from __future__ import annotations

from pathlib import Path
import re


def derive_file_tag(file_name: str) -> str:
    """Return the short acquisition identifier used in curve labels.

    FlexPES XPS files normally start with ``XPS_####``.  The four digits are
    the acquisition/file number and must take precedence over later numeric
    tokens that may belong to a region name (for example ``S2p_260``).
    """
    try:
        base = Path(str(file_name)).name
        match = re.search(r"XPS_(\d{4})", base)
        return match.group(1) if match else Path(base).stem
    except Exception:
        return Path(str(file_name)).stem


def file_number_sort_key(file_name: str) -> tuple[int, int, str]:
    """Return a stable sort key with numeric FlexPES acquisition IDs first.

    ``XPS_####`` file tags are compared numerically, so selected curves are
    ordered by acquisition/file number regardless of the order in which the
    user selected them. Non-numeric/generated names follow alphabetically.
    """
    tag = derive_file_tag(file_name)
    if str(tag).isdigit():
        return (0, int(tag), str(tag))
    return (1, 0, str(tag).casefold())


def format_curve_source_label(file_name: str, region_name: str, detail: str = "") -> str:
    """Format a selected-curve label as ``####: Region`` with optional detail."""
    tag = derive_file_tag(file_name)
    label = f"{tag}: {str(region_name)}"
    detail = str(detail or "").strip()
    if detail:
        label += f" ({detail})"
    return label


def curve_detail_sort_key(meta: dict | None, display: str) -> tuple[int, int, str]:
    """Return a natural ordering key for curves from the same source file.

    Iteration leaves are sorted by their numeric iteration index so labels such
    as ``Iteration 10`` no longer sort before ``Iteration 2``.  When metadata
    does not carry an iteration number, fall back to a natural numeric token
    parsed from the display label, then finally to case-insensitive text.
    """
    if isinstance(meta, dict):
        iteration = meta.get("iteration")
        try:
            if iteration is not None:
                return (0, int(iteration), str(display).casefold())
        except (TypeError, ValueError):
            pass

    match = re.search(r"\bIteration\s*(\d+)\b", str(display), flags=re.IGNORECASE)
    if match:
        return (0, int(match.group(1)), str(display).casefold())
    return (1, 0, str(display).casefold())


def make_loaded_curve_key(file_name: str, region_name: str, label: str, region_index: int | None = None) -> str:
    """Return a stable key for one raw loaded-tree curve.

    Region index is included when available because Scienta TXT files may contain
    several regions whose ``Spectrum Name``/display name is identical.  Without
    it, selecting a second such spectrum would overwrite the first in the
    selected-curve registry.
    """
    idx = f"#{int(region_index)}" if region_index is not None else ""
    return f"{file_name}:::{region_name}{idx}:::{label}"
