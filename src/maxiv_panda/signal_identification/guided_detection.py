from __future__ import annotations

from functools import lru_cache

import re
from typing import Any

import numpy as np

from .matcher import PeakAssignment, SignalCandidate
from .core_reference_families import (
    normalized_core_records, resolved_family_keys, family_component_offsets,
    family_pair_tolerance, strongest_component_line, component_axis_delta,
)
from .peak_detection import refine_peak_near_reference

def _base_transition(line: str) -> str:
    return re.sub(r"([spdf])[1357]/2$", r"\1", str(line).strip())

def _expected_core_windows(*, energy_scale: str, photon_energy: float | None, selected_elements: set[str],
                           tolerance_eV: float, sample_mode: str, vb_cutoff: float) -> list[tuple[float, float]]:
    records = normalized_core_records(sample_mode)
    resolved_families = resolved_family_keys(records)
    generic_families = {
        (str(record.get("element", "")), _base_transition(str(record.get("transition", record.get("line", "")))))
        for record in records
        if not re.search(r"[spdf][1357]/2$", str(record.get("transition", record.get("line", ""))).strip())
    }
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    major = {"1s", "2p", "3d", "4f", "4d", "3p", "2s", "3s"}
    mode = str(sample_mode or "Automatic").lower()
    for record in records:
        element = str(record.get("element", ""))
        if selected_elements and element not in selected_elements:
            continue
        line = str(record.get("transition", record.get("line", ""))).strip()
        family = _base_transition(line)
        family_key = (element, family)
        if re.search(r"[spdf][1357]/2$", line) and family_key in generic_families and family_key not in resolved_families:
            continue
        if family not in major:
            continue
        if (element, family) in resolved_families and not re.search(r"[spdf][1357]/2$", line):
            continue
        phase = str(record.get("phase", "")).lower()
        if mode.startswith("gas") and not ("gas" in phase or "atomic" in phase):
            continue
        if (mode.startswith("automatic") or mode.startswith("solid")) and ("gas" in phase or "atomic" in phase):
            continue
        try:
            be = float(record.get("representative_energy_eV", record.get("binding_energy_eV")))
        except Exception:
            try:
                be = 0.5 * (float(record["energy_min_eV"]) + float(record["energy_max_eV"]))
            except Exception:
                continue
        if energy_scale.lower().startswith("bind"):
            expected = be
        elif energy_scale.lower().startswith("kin") and photon_energy is not None:
            expected = float(photon_energy) - be
        else:
            continue
        if energy_scale.lower().startswith("bind") and 0.0 <= expected <= vb_cutoff:
            continue
        row = dict(record)
        row["_expected"] = expected
        groups.setdefault((element, line), []).append(row)

    # For a resolved spin-orbit family, guided *absolute-energy* searching is
    # performed only for the statistically stronger component.  Once that
    # measured anchor exists, weaker partners are searched from the observed
    # anchor position using the tabulated relative splitting.  This prevents a
    # weak accidental shoulder near an unshifted 1/2 (or lower-j) reference
    # from becoming the family anchor before a chemically shifted main peak.
    strongest_by_family: dict[tuple[str, str], str] = {}
    component_lines_by_family: dict[tuple[str, str], set[str]] = {}
    for element, line in groups:
        family_key = (element, _base_transition(line))
        if family_key in resolved_families and re.search(r"[spdf][1357]/2$", line):
            component_lines_by_family.setdefault(family_key, set()).add(line)
    for family_key, component_lines in component_lines_by_family.items():
        strongest = strongest_component_line(family_key[0], component_lines, photon_energy)
        if strongest is not None:
            strongest_by_family[family_key] = strongest

    windows: list[tuple[float, float]] = []
    category_priority = {
        "handbook_elemental": 0,
        "handbook_compound": 1,
        "xray_booklet": 2,
    }
    for (_element, line), rows in groups.items():
        family_key = (_element, _base_transition(line))
        strongest = strongest_by_family.get(family_key)
        if strongest is not None and line != strongest:
            continue
        # Use one representative condensed-state position for guided feature
        # detection.  Do not span the complete chemical-state database: that
        # can make a C 1s window overlap a neighboring intense metal line.
        best = min(
            rows,
            key=lambda row: (
                category_priority.get(str(row.get("category", "")), 3),
                abs(float(row["_expected"]) - np.median([float(r["_expected"]) for r in rows])),
            ),
        )
        expected = float(best["_expected"])
        family = _base_transition(line)
        if re.search(r"[spdf][1357]/2$", line):
            # Only the stronger j component receives an absolute guide window.
            # Give that anchor enough room for ordinary chemical shifts while
            # remaining local enough not to span a well-resolved doublet.
            half_width = 2.0
        else:
            half_width = max(2.5, min(float(tolerance_eV), 5.0))
            if family in {"3p", "3s"}:
                half_width = max(half_width, 4.0)
            elif family in {"4d", "4f"}:
                half_width = max(half_width, 3.0)
        windows.append((expected, half_width))
    return windows



def _raw_local_peak_prominence(x_arr: np.ndarray, y_arr: np.ndarray, index: int, half_width_eV: float) -> float:
    """Return a simple local prominence on the displayed (unsmoothed) survey data."""
    center = float(x_arr[index])
    mask = np.abs(x_arr - center) <= max(float(half_width_eV), 0.5)
    idx = np.nonzero(mask)[0]
    if idx.size < 3:
        return 0.0
    left = idx[idx < index]
    right = idx[idx > index]
    if left.size == 0 or right.size == 0:
        return 0.0
    # Use the lower local shoulder on each side rather than a global baseline.
    # This remains meaningful for close doublets sitting on a steep survey tail.
    left_floor = float(np.nanmin(y_arr[left]))
    right_floor = float(np.nanmin(y_arr[right]))
    floor = max(left_floor, right_floor)
    return max(0.0, float(y_arr[index]) - floor)


def _refine_strong_resolved_family_anchor(assignment: PeakAssignment, payload: Any, *, tolerance_eV: float) -> Any | None:
    """Rescue a strong resolved-family anchor by testing the doublet geometry directly.

    Global survey peak finding intentionally uses a fairly large minimum spacing.
    A close, intense doublet can therefore be represented initially by one smoothed
    maximum between its true components.  Generic local-noise refinement is a poor
    way to recover such a case because the doublet slopes themselves dominate the
    short-window roughness.  Here we use the known spin-orbit geometry only after a
    PE family candidate already exists: enumerate raw local maxima for the stronger
    component and retain an anchor only when a second measured maximum occurs at the
    expected relative splitting.
    """
    best = assignment.best
    if best is None or best.kind != "PE" or not re.search(r"[spdf][1357]/2$", str(best.line)):
        return None
    family = _base_transition(best.line)
    offsets = family_component_offsets(best.element, family)
    if best.line not in offsets or len(offsets) < 2:
        return None
    strongest = strongest_component_line(best.element, set(offsets), None)
    if strongest != best.line:
        return None

    x_arr = np.asarray(payload.x, dtype=float).ravel()
    y_arr = np.asarray(payload.y, dtype=float).ravel()
    finite = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr, y_arr = x_arr[finite], y_arr[finite]
    if x_arr.size < 7:
        return None
    order = np.argsort(x_arr)
    x_arr, y_arr = x_arr[order], y_arr[order]
    span = float(np.nanmax(y_arr) - np.nanmin(y_arr))
    if not np.isfinite(span) or span <= 0:
        return None

    expected_anchor = float(getattr(best, "expected_energy", assignment.peak.energy))
    anchor_half_width = max(2.5, min(float(tolerance_eV), 4.5))
    anchor_mask = np.abs(x_arr - expected_anchor) <= anchor_half_width
    anchor_indices = [
        i for i in np.nonzero(anchor_mask)[0]
        if 0 < i < x_arr.size - 1
        and float(y_arr[i]) >= float(y_arr[i - 1])
        and float(y_arr[i]) >= float(y_arr[i + 1])
    ]
    if not anchor_indices:
        return None

    energy_scale = str(getattr(payload, "energy_scale", "Binding") or "Binding")
    anchor_offset = offsets[best.line]
    min_prominence = max(0.0010 * span, np.finfo(float).eps)
    best_pair = None
    for anchor_i in anchor_indices:
        anchor_energy = float(x_arr[anchor_i])
        # A 2--4 eV local neighbourhood is enough to measure a close-doublet
        # apex without letting the full survey background dominate.
        anchor_prom = _raw_local_peak_prominence(x_arr, y_arr, anchor_i, 2.5)
        if anchor_prom < min_prominence:
            continue
        for partner_line, partner_offset in offsets.items():
            if partner_line == best.line:
                continue
            relative = component_axis_delta(anchor_offset, partner_offset, energy_scale)
            target = anchor_energy + float(relative)
            pair_tol = family_pair_tolerance(anchor_offset, partner_offset)
            partner_mask = np.abs(x_arr - target) <= pair_tol
            partner_indices = [
                i for i in np.nonzero(partner_mask)[0]
                if 0 < i < x_arr.size - 1 and i != anchor_i
                and float(y_arr[i]) >= float(y_arr[i - 1])
                and float(y_arr[i]) >= float(y_arr[i + 1])
            ]
            for partner_i in partner_indices:
                partner_prom = _raw_local_peak_prominence(x_arr, y_arr, partner_i, 2.5)
                if partner_prom < min_prominence:
                    continue
                mismatch = abs((float(x_arr[partner_i]) - anchor_energy) - float(relative))
                if mismatch > pair_tol:
                    continue
                # Family geometry dominates; prominence and closeness to the
                # absolute strong-line guide settle otherwise similar pairs.
                score = (
                    np.log1p(anchor_prom / min_prominence)
                    + 0.65 * np.log1p(partner_prom / min_prominence)
                    - 1.8 * (mismatch / max(pair_tol, 1e-9)) ** 2
                    - 0.25 * (abs(anchor_energy - expected_anchor) / anchor_half_width) ** 2
                )
                candidate = (float(score), anchor_i, anchor_prom)
                if best_pair is None or candidate[0] > best_pair[0]:
                    best_pair = candidate

    if best_pair is None:
        return None
    _score, idx, prominence = best_pair
    # Map the sorted/finite index back to the original displayed-data index.
    original_finite = np.nonzero(finite)[0]
    original_index = int(original_finite[order[idx]])
    return type(assignment.peak)(
        original_index, float(x_arr[idx]), float(y_arr[idx]), float(prominence)
    )

def _refine_assignments_to_local_features(assignments: list[PeakAssignment], payload: Any, *, tolerance_eV: float) -> list[PeakAssignment]:
    refined: list[PeakAssignment] = []
    for assignment in assignments:
        best = assignment.best
        if best is None or best.kind != 'PE':
            refined.append(assignment)
            continue
        # Charging-assisted candidates have already been anchored to an
        # observed shifted peak. Refining them around the unshifted reference
        # position would jump back to an unrelated feature and silently erase
        # the checkbox-dependent result. Keep the local search centred on the
        # detected shifted feature instead.
        charging_supported = "small-charging mode" in str(getattr(best, "reason", ""))
        # Refine around the observed feature, not around the database value.
        # The reference energy establishes the assignment; the annotation and
        # assignment table should report the measured local maximum.  This is
        # particularly important for chemically shifted, asymmetric and
        # multiplet-broadened transition-metal 2p peaks.
        center = float(assignment.peak.energy)
        region_span = 0.0
        if best.region_min is not None and best.region_max is not None:
            region_span = abs(float(best.region_max) - float(best.region_min))
        # Resolved spin-orbit components must be refined locally without
        # jumping to the stronger partner of the doublet.  A narrow window is
        # therefore used for explicit j components (for example 4f7/2 and
        # 4f5/2).  Unresolved family references retain the wider search.
        if re.search(r"[spdf][1357]/2$", str(best.line)):
            search_half_width = 1.6
        else:
            family = _base_transition(best.line)
            # The assignment is already centred on an independently detected
            # measured feature. Refinement therefore only needs a local window.
            # A full matching-tolerance window can include a steep substrate
            # background and overestimate noise, causing a clear C 1s peak to
            # be rejected on descending-energy survey spectra.
            if family == '2s':
                # Survey smoothing can displace a narrow 2s provisional maximum
                # by a few eV on a steep background.  Give singlet 2s lines a
                # slightly wider local refinement window so the raw apex is not
                # rejected merely because it lands on the search-window edge.
                search_half_width = max(3.5, min(4.0, 0.5 * region_span + 2.0))
            elif family in {'1s', '2p'}:
                search_half_width = max(2.5, min(3.0, 0.5 * region_span + 1.5))
            else:
                search_half_width = max(3.0, min(float(tolerance_eV), 4.5), 0.5 * region_span + 1.5)
            if family in {'3p', '3s', '4d', '4f'}:
                search_half_width = max(search_half_width, 4.5)
        # Weak K-shell singlets (C 1s, O 1s, N 1s, B 1s, ...) may be
        # recovered by the reference-guided detector on a curved survey
        # background.  Re-applying the historical first-difference noise gate
        # here could reject the very same measured feature a second time,
        # making nearly identical spectra behave discontinuously.  Use the
        # same peak-excluded, detrended evidence model for 1s refinement.
        use_detrended_evidence = (_base_transition(best.line) == "1s")
        refined_peak = refine_peak_near_reference(
            payload.x, payload.y, target_energy=center,
            search_half_width=search_half_width,
            detrend_background_noise=use_detrended_evidence,
        )
        if refined_peak is None and re.search(r"[spdf][1357]/2$", str(best.line)):
            # Close resolved doublets can be collapsed by the global survey
            # peak spacing into a provisional maximum between the two real
            # components.  Before rejecting such a strong-family candidate,
            # test the measured pair geometry directly on the raw data.
            refined_peak = _refine_strong_resolved_family_anchor(
                assignment, payload, tolerance_eV=float(tolerance_eV)
            )
        if refined_peak is None:
            # A reference match is not sufficient for a visible PE label.
            # Keep the assignment row for diagnostics, but mark its candidates
            # as unsupported when no independent local maximum rises above the
            # measured noise.  This preserves genuinely weak peaks while
            # preventing expected lines from being painted onto noise or a
            # smooth background/tail.
            rejected_candidates = [
                SignalCandidate(**{
                    **candidate.__dict__,
                    "confident": False,
                    "reason": "Rejected: no local PE feature above measured noise",
                })
                for candidate in assignment.candidates
            ]
            refined.append(PeakAssignment(
                peak=assignment.peak,
                candidates=rejected_candidates,
                rejection_reason="No local PE feature above measured noise",
            ))
            continue
        new_candidates = [SignalCandidate(**{**candidate.__dict__, 'delta_e': refined_peak.energy - candidate.expected_energy}) for candidate in assignment.candidates]
        refined.append(PeakAssignment(peak=refined_peak, candidates=new_candidates, rejection_reason=assignment.rejection_reason))

    # Different reference-guided windows can converge onto the same measured
    # local maximum during refinement.  Keep exactly one row per experimental
    # peak and merge the alternative assignments into that row.  Without this
    # canonicalisation, the same maximum can appear twice with different
    # provisional labels; later same-peak conflict handling may then discard a
    # chemically coherent alternative merely because it lives in the duplicate
    # row.  Peak index is the strongest identity criterion because all refined
    # peaks are mapped back onto the original spectrum grid.
    merged: list[PeakAssignment] = []
    by_index: dict[int, int] = {}
    for assignment in refined:
        peak_index = int(assignment.peak.index)
        existing_pos = by_index.get(peak_index)
        if existing_pos is None:
            by_index[peak_index] = len(merged)
            merged.append(assignment)
            continue

        existing = merged[existing_pos]
        candidates_by_label: dict[str, SignalCandidate] = {}
        for candidate in list(existing.candidates) + list(assignment.candidates):
            previous = candidates_by_label.get(candidate.label)
            if previous is None:
                candidates_by_label[candidate.label] = candidate
                continue
            # Preserve the more favourable representation of the same candidate.
            # A confident candidate outranks a rejected copy; otherwise the lower
            # matcher score is the stronger local match.
            if candidate.confident and not previous.confident:
                candidates_by_label[candidate.label] = candidate
            elif candidate.confident == previous.confident and float(candidate.score) < float(previous.score):
                candidates_by_label[candidate.label] = candidate

        candidates = sorted(
            candidates_by_label.values(),
            key=lambda candidate: (not bool(candidate.confident), float(candidate.score), abs(float(candidate.delta_e))),
        )
        rejection_reason = existing.rejection_reason or assignment.rejection_reason
        merged[existing_pos] = PeakAssignment(
            peak=max((existing.peak, assignment.peak), key=lambda peak: float(peak.prominence)),
            candidates=candidates,
            rejection_reason=rejection_reason,
        )
    return merged

@lru_cache(maxsize=4096)
def _reference_position_for_line(*, element: str, line: str, energy_scale: str, photon_energy: float | None, sample_mode: str) -> float | None:
    rows = []
    mode = str(sample_mode or "Automatic").lower()
    for record in normalized_core_records(sample_mode):
        if str(record.get("element", "")) != element:
            continue
        if str(record.get("transition", record.get("line", ""))).strip() != line:
            continue
        phase = str(record.get("phase", "")).lower()
        if mode.startswith("gas") and not ("gas" in phase or "atomic" in phase):
            continue
        if (mode.startswith("automatic") or mode.startswith("solid")) and ("gas" in phase or "atomic" in phase):
            continue
        try:
            be = float(record.get("representative_energy_eV", record.get("binding_energy_eV")))
        except Exception:
            try:
                be = 0.5 * (float(record["energy_min_eV"]) + float(record["energy_max_eV"]))
            except Exception:
                continue
        rows.append((str(record.get("category", "")), be))
    if not rows:
        return None
    priority = {"handbook_elemental": 0, "handbook_compound": 1, "xray_booklet": 2}
    _category, be = min(rows, key=lambda row: priority.get(row[0], 3))
    if energy_scale.lower().startswith("bind"):
        return be
    if energy_scale.lower().startswith("kin") and photon_energy is not None:
        return float(photon_energy) - be
    return None

def _companion_assisted_peaks(assignments: list[PeakAssignment], payload: Any, *, energy_scale: str,
                              photon_energy: float | None, sample_mode: str) -> list[Any]:
    """Find weaker spin-orbit partners from an observed stronger component.

    Resolved families are deliberately asymmetric: the statistically stronger
    component is the only allowed anchor.  The weaker component is searched at
    the measured anchor energy plus the tabulated relative splitting.  Absolute
    handbook positions of weak components are never used as independent guide
    windows, so common chemical shifts or charging cannot redirect the search
    onto an accidental shoulder near the unshifted weak-line reference.
    """
    accepted = [a for a in assignments if a.best is not None and a.best.kind == "PE"]
    found: list[Any] = []
    try:
        y_arr = np.asarray(payload.y, dtype=float).reshape(-1)
        global_span = float(np.nanmax(y_arr) - np.nanmin(y_arr))
    except Exception:
        global_span = 0.0

    component_re = re.compile(r"^(\d+[spdf])([1357]/2)$")
    # Only families already represented by an accepted measured component can
    # have a companion recovered.  v0.8.63 built spin-orbit geometry (and read
    # Yeh-Lindau cross sections) for every resolved family in the entire
    # reference database before discovering that almost all had no anchor in
    # the spectrum.  Restrict the work to observed families first.
    observed_family_keys = {
        (a.best.element, _base_transition(a.best.line))
        for a in accepted
        if a.best is not None and component_re.match(str(a.best.line))
    }
    if not observed_family_keys:
        return found

    by_family: dict[tuple[str, str], set[str]] = {}
    for record in normalized_core_records(sample_mode):
        element = str(record.get("element", ""))
        line = str(record.get("transition", record.get("line", ""))).strip()
        match = component_re.match(line)
        family_key = (element, match.group(1)) if match else None
        if family_key in observed_family_keys:
            by_family.setdefault(family_key, set()).add(line)

    for (element, family), lines in by_family.items():
        offsets = family_component_offsets(element, family)
        usable_lines = {line for line in lines if line in offsets}
        if len(usable_lines) < 2:
            continue
        strongest = strongest_component_line(element, usable_lines, photon_energy)
        if strongest is None or strongest not in offsets:
            continue

        strong_assignments = [
            a for a in accepted
            if a.best is not None and a.best.element == element and a.best.line == strongest
        ]
        if not strong_assignments:
            # Do not let a weak member bootstrap the family.  It will either be
            # supported after the stronger component is established elsewhere,
            # or rejected by the final family-consistency layer.
            continue
        anchor = max(
            strong_assignments,
            key=lambda a: (float(a.peak.prominence), a.best.reliability if a.best else 0),
        )
        anchor_offset = offsets[strongest]

        for partner_line in sorted(usable_lines, key=lambda line: offsets[line]):
            if partner_line == strongest:
                continue
            relative = component_axis_delta(anchor_offset, offsets[partner_line], energy_scale)
            target = float(anchor.peak.energy) + float(relative)
            tolerance = family_pair_tolerance(anchor_offset, offsets[partner_line])

            compatible = [
                a for a in accepted
                if a.best is not None and a.best.element == element and a.best.line == partner_line
                and abs(float(a.peak.energy) - target) <= tolerance
            ]
            if compatible:
                continue

            min_height = max(0.00012 * global_span, np.finfo(float).eps)
            splitting = abs(float(relative))
            search_half_width = max(1.0, min(4.0, 0.35 * splitting))
            partner = refine_peak_near_reference(
                payload.x, payload.y, target_energy=target,
                search_half_width=search_half_width, min_feature_height=min_height,
            )
            if partner is None:
                continue
            if abs(float(partner.energy) - float(anchor.peak.energy)) <= 0.7:
                continue
            if any(abs(float(partner.energy) - float(a.peak.energy)) <= 0.7 for a in accepted):
                continue
            if any(abs(float(partner.energy) - float(p.energy)) <= 0.7 for p in found):
                continue
            found.append(partner)
    return found

