"""Normalize mixed generic/component core-level references into families.

The bundled databases sometimes contain a condensed-state family position
(e.g. ``Ca 2p``) together with resolved j components only in an atomic table.
Matching those rows independently makes assignment depend on candidate order.
This module creates one consistent record set before guided detection, matching,
companion recovery, and element-consistency checks.
"""
from __future__ import annotations

from typing import Any
from functools import lru_cache
import re

from .reference_data import core_level_records

_COMPONENT_RE = re.compile(r"([spdf])[1357]/2$")
_COMPONENT_J_RE = re.compile(r"([spdf])([1357])/2$")


def base_line(line: str) -> str:
    """Return the unresolved shell-family name for a transition label."""
    return _COMPONENT_RE.sub(r"\1", str(line).strip())


def strongest_component_line(
    element: str, lines: list[str] | tuple[str, ...] | set[str], photon_energy_eV: float | None = None
) -> str | None:
    """Return the statistically stronger member of a resolved spin-orbit family.

    When Yeh-Lindau component cross sections are available at the current photon
    energy, use them directly.  Otherwise fall back to the spin-orbit statistical
    weight (larger j / larger numerator), which gives p3/2 over p1/2, d5/2 over
    d3/2, and f7/2 over f5/2.  Identification code uses this member as the
    absolute-energy anchor; weaker siblings are searched only relative to the
    measured anchor position.
    """
    unique = tuple(dict.fromkeys(str(line).strip() for line in lines if str(line).strip()))
    if not unique:
        return None

    if photon_energy_eV is not None:
        try:
            from .cross_sections import cross_section_at
            weighted = []
            for line in unique:
                sigma = cross_section_at(str(element), line, float(photon_energy_eV))
                if sigma is not None and sigma > 0:
                    weighted.append((float(sigma), line))
            if len(weighted) == len(unique) and len(weighted) >= 2:
                return max(weighted, key=lambda item: item[0])[1]
        except Exception:
            pass

    def statistical_rank(line: str) -> tuple[int, str]:
        match = _COMPONENT_J_RE.search(line)
        return (int(match.group(2)) if match else -1, line)

    return max(unique, key=statistical_rank)


def component_axis_delta(offset_from: float, offset_to: float, energy_scale: str) -> float:
    """Convert a binding-energy family offset into the displayed energy-axis delta.

    Spin-orbit reference offsets are stored on the binding-energy scale.  On a
    kinetic-energy spectrum the ordering reverses because KE = hν - BE.
    """
    delta = float(offset_to) - float(offset_from)
    if str(energy_scale).lower().startswith("kin"):
        return -delta
    return delta


def representative_be(record: dict[str, Any]) -> float:
    """Return the representative binding energy stored in a reference row."""
    for key in ("representative_energy_eV", "binding_energy_eV", "energy_eV"):
        try:
            return float(record[key])
        except Exception:
            continue
    try:
        lo = float(record.get("energy_min_eV"))
        hi = float(record.get("energy_max_eV"))
        return 0.5 * (lo + hi)
    except Exception:
        return float("nan")


def _is_atomic(record: dict[str, Any]) -> bool:
    phase = str(record.get("phase", "")).lower()
    return "gas" in phase or "atomic" in phase


@lru_cache(maxsize=8)
def normalized_core_records(sample_mode: str) -> tuple[dict[str, Any], ...]:
    """Return a single coherent core-reference representation.

    Gas and ``Both`` modes keep the source records unchanged.  In Automatic or
    Solid mode, a family with a condensed-state generic anchor and only atomic
    resolved components is converted to condensed-state anchored component
    records.  The atomic table contributes only relative spin-orbit offsets.

    Families with genuine condensed-state component energies are left intact.
    Families whose atomic splitting is below 1.2 eV remain unresolved because
    a survey spectrum cannot normally distinguish their components.
    """
    records = [dict(record) for record in core_level_records()]
    mode = str(sample_mode or "Automatic").lower()
    if mode.startswith("gas") or mode.startswith("both"):
        return tuple(records)

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        element = str(record.get("element", ""))
        line = str(record.get("transition", record.get("line", ""))).strip()
        grouped.setdefault((element, base_line(line)), []).append(record)

    synthesized: list[dict[str, Any]] = []
    replaced: set[tuple[str, str]] = set()
    collapsed: set[tuple[str, str]] = set()
    relabel_generic: dict[tuple[str, str], str] = {}
    resolved_anchor_energy: dict[tuple[str, str], float] = {}

    for family_key, rows in grouped.items():
        generic = [
            row for row in rows
            if not _COMPONENT_RE.search(str(row.get("transition", row.get("line", ""))).strip())
            and not _is_atomic(row)
        ]
        explicit = [
            row for row in rows
            if _COMPONENT_RE.search(str(row.get("transition", row.get("line", ""))).strip())
        ]
        condensed_explicit = [row for row in explicit if not _is_atomic(row)]
        if not generic:
            continue

        explicit_energies: dict[str, float] = {}
        for row in explicit:
            line = str(row.get("transition", row.get("line", ""))).strip()
            energy = representative_be(row)
            if energy == energy:
                explicit_energies.setdefault(line, float(energy))
        if len(explicit_energies) < 2:
            continue

        anchor_line = min(explicit_energies, key=explicit_energies.get)
        anchor_energy = explicit_energies[anchor_line]
        offsets = {line: energy - anchor_energy for line, energy in explicit_energies.items()}
        splitting = max(offsets.values()) - min(offsets.values())
        family = family_key[1]
        shell_match = re.match(r"(\d+)([spdf])$", family)
        principal = int(shell_match.group(1)) if shell_match else 0
        orbital = shell_match.group(2) if shell_match else ""
        # Small p spin-orbit splittings are commonly unresolved in survey
        # spectra.  This applies not only to shallow transition-metal 3p
        # families but also to light-element 2p envelopes such as P 2p: a
        # ~1.3 eV tabulated split can appear as one measured survey feature.
        # Keep those as one generic family rather than forcing separate j
        # components and then rejecting the lone measured envelope.
        if orbital == "p" and principal >= 3:
            minimum_splitting = 3.0
        elif orbital == "p":
            minimum_splitting = 1.5
        else:
            minimum_splitting = 1.2
        if splitting < minimum_splitting:
            # Keep the condensed generic family and remove the atomic-only
            # j components, so later stages never see them as competitors.
            collapsed.add(family_key)
            continue

        if condensed_explicit:
            # A resolved condensed-state family must not expose an additional
            # unresolved label for the very same observable family.  Handbook
            # rows written simply as e.g. ``Mn 2p`` conventionally refer to
            # the main (lower-BE) component.  Keep their useful chemical-state
            # energies, but normalize the transition label to that resolved
            # anchor component.  This prevents one measured doublet from being
            # labelled simultaneously as ``2p``, ``2p3/2`` and ``2p1/2``.
            relabel_generic[family_key] = anchor_line
            resolved_anchor_energy[family_key] = float(anchor_energy)
            continue

        replaced.add(family_key)
        for base_record in generic:
            base_energy = representative_be(base_record)
            if base_energy != base_energy:
                continue
            for line, offset in offsets.items():
                energy = float(base_energy) + float(offset)
                row = dict(base_record)
                row.update({
                    "transition": line,
                    "energy_min_eV": energy,
                    "energy_max_eV": energy,
                    "representative_energy_eV": energy,
                    "normalized_family": family_key[1],
                    "normalized_anchor_transition": anchor_line,
                    "normalized_anchor_energy_eV": float(base_energy),
                    "normalized_component_offset_eV": float(offset),
                    "reference_normalization": "condensed anchor + atomic splitting",
                })
                row["environment"] = (
                    str(base_record.get("environment", "condensed-state reference"))
                    + "; spin-orbit splitting transferred from atomic reference"
                )
                row["source"] = (
                    str(base_record.get("source", "")) + " + LBNL spin-orbit splitting"
                ).strip(" +")
                synthesized.append(row)

    if not replaced and not collapsed:
        return tuple(records)

    kept: list[dict[str, Any]] = []
    for record in records:
        element = str(record.get("element", ""))
        line = str(record.get("transition", record.get("line", ""))).strip()
        key = (element, base_line(line))
        if key in replaced:
            continue
        if key in collapsed and _COMPONENT_RE.search(line):
            # The family is intentionally unresolved at survey resolution.
            # Remove all explicit j-component rows (including condensed-state
            # rows) so later matching cannot resurrect a weaker component and
            # reject it for lacking a separately resolved stronger partner.
            continue
        if key in relabel_generic and not _COMPONENT_RE.search(line) and not _is_atomic(record):
            # A generic condensed-state family row conventionally represents
            # the stronger/lower-BE spin-orbit component.  Keep useful
            # chemical-state variants near that explicit anchor, but reject
            # grossly inconsistent generic rows.  Otherwise an erroneous or
            # mis-tabulated family-level value can be relabelled as a second
            # resolved doublet (Sn 3d historically had a 497.2 eV generic
            # row alongside the correct 484.9/493.3 eV components).
            anchor_energy = resolved_anchor_energy.get(key)
            energy = representative_be(record)
            if (
                anchor_energy is not None
                and energy == energy
                and abs(float(energy) - float(anchor_energy)) > 6.0
            ):
                continue
            row = dict(record)
            row["transition"] = relabel_generic[key]
            row["normalized_family"] = key[1]
            row["normalized_anchor_transition"] = relabel_generic[key]
            row["reference_normalization"] = "generic condensed family relabelled to resolved main component"
            kept.append(row)
            continue
        kept.append(record)
    return tuple(kept + synthesized)



@lru_cache(maxsize=512)
def family_component_offsets(element: str, family: str) -> dict[str, float]:
    """Return robust relative energies for resolved members of one core family.

    Absolute binding energies may shift by several eV between chemical states,
    while spin-orbit splitting is much more stable.  Build the relative
    component geometry from explicit j-resolved reference rows and use medians
    so duplicate handbook/atomic entries cannot dominate it.  The lowest-BE
    component is the zero-energy anchor.
    """
    grouped: dict[str, list[float]] = {}
    for record in core_level_records():
        if str(record.get("element", "")) != str(element):
            continue
        line = str(record.get("transition", record.get("line", ""))).strip()
        if base_line(line) != str(family) or not _COMPONENT_RE.search(line):
            continue
        energy = representative_be(record)
        if energy == energy:
            grouped.setdefault(line, []).append(float(energy))
    if len(grouped) < 2:
        return {}
    medians = {line: float(__import__("statistics").median(values)) for line, values in grouped.items() if values}
    if len(medians) < 2:
        return {}
    anchor = min(medians.values())
    return {line: energy - anchor for line, energy in medians.items()}


def family_pair_tolerance(offset_a: float, offset_b: float) -> float:
    """Survey-scale tolerance for an observed spin-orbit separation."""
    splitting = abs(float(offset_b) - float(offset_a))
    # Allow coarse survey sampling and modest chemical/multiplet distortion,
    # but never enough for a neighbouring unrelated peak to substitute for a
    # well separated partner.
    return max(1.2, min(2.0, 0.14 * splitting + 0.35))

def resolved_family_keys(records: list[dict[str, Any]] | tuple[dict[str, Any], ...], *, minimum_splitting_eV: float = 1.2) -> set[tuple[str, str]]:
    """Return shell families whose component separation is survey-resolvable."""
    grouped: dict[tuple[str, str], list[float]] = {}
    for record in records:
        line = str(record.get("transition", record.get("line", ""))).strip()
        if not _COMPONENT_RE.search(line):
            continue
        energy = representative_be(record)
        if energy == energy:
            grouped.setdefault((str(record.get("element", "")), base_line(line)), []).append(float(energy))
    return {
        key for key, values in grouped.items()
        if values and max(values) - min(values) >= minimum_splitting_eV
    }
