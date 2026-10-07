"""Element- and family-level consistency checks for survey assignments."""
from __future__ import annotations

from dataclasses import replace
from typing import Any
import re

import numpy as np

from .cross_sections import cross_section_at, family_cross_section_at
from .guided_detection import _base_transition, _reference_position_for_line
from .core_reference_families import (
    normalized_core_records, family_component_offsets, family_pair_tolerance,
    strongest_component_line, component_axis_delta,
)
from .matcher import PeakAssignment, SignalCandidate
from .peak_detection import DetectedPeak, refine_peak_near_reference
from scipy.signal import find_peaks, savgol_filter

_TRANSITION_METALS = {"Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu"}
_COMPONENTS = ("3/2", "1/2")


def _accepted_pe(assignments: list[PeakAssignment]) -> list[PeakAssignment]:
    return [a for a in assignments if a.best is not None and a.best.kind == "PE"]


def _element_shift(assignments: list[PeakAssignment], element: str) -> float:
    # Charging anchors must come from characteristic deep families.  A dubious
    # shallow s assignment must never shift the 2p search window for an entire
    # element.
    anchors = {"1s", "2p", "3d", "4d", "4f"}
    values = [
        float(a.best.delta_e) for a in _accepted_pe(assignments)
        if a.best.element == element and _base_transition(a.best.line) in anchors
    ]
    return float(np.median(values)) if values else 0.0


def _candidate_assignment(*, peak, element: str, line: str, expected: float, reason: str,
                          photon_energy: float | None, support: float = 0.8) -> PeakAssignment:
    cross = cross_section_at(element, line, photon_energy) if photon_energy is not None else None
    reference_factor = 0.85 if cross is not None else 0.72
    reliability = int(round(100 * (0.35 * min(1.0, max(0.0, support)) + 0.30 + 0.20 + 0.15 * reference_factor)))
    candidate = SignalCandidate(
        element=element,
        line=line,
        kind="PE",
        expected_energy=float(expected),
        delta_e=float(peak.energy) - float(expected),
        score=max(0.0, abs(float(peak.energy) - float(expected)) / 3.0 - 0.4 * support),
        confident=True,
        reason=reason,
        reference_category="yeh_lindau_consistency",
        reliability=max(0, min(100, reliability)),
        reliability_pattern=min(1.0, support),
        reliability_shift=0.8,
        common_shift_eV=float(peak.energy) - float(expected),
        residual_mismatch_eV=0.0,
        reliability_peak=0.8,
        reliability_support=min(1.0, support),
        reliability_uniqueness=0.8,
        reliability_reference=reference_factor,
    )
    return PeakAssignment(peak=peak, candidates=[candidate])




def _reject_but_keep_peak(assignment: PeakAssignment, reason: str) -> PeakAssignment:
    """Reject an identification without deleting the measured peak row.

    The peak table represents experimental peak evidence as well as accepted
    assignments.  Consistency rules may reject a candidate, but they must not
    make the underlying detected maximum disappear from the table.
    """
    candidates = [replace(candidate, confident=False) for candidate in assignment.candidates]
    return PeakAssignment(peak=assignment.peak, candidates=candidates, rejection_reason=str(reason))


def _upsert_assignment_at_peak(
    assignments: list[PeakAssignment], new_assignment: PeakAssignment, *, tolerance_eV: float = 0.8
) -> list[PeakAssignment]:
    """Replace the nearest row for a measured feature, or append if absent.

    Recovery layers should strengthen/reassign an already detected feature,
    not create a second table row for essentially the same maximum.
    """
    result = list(assignments)
    matches = [
        (abs(float(old.peak.energy) - float(new_assignment.peak.energy)), index)
        for index, old in enumerate(result)
        if abs(float(old.peak.energy) - float(new_assignment.peak.energy)) <= float(tolerance_eV)
    ]
    if not matches:
        result.append(new_assignment)
        return result
    _distance, index = min(matches)
    old = result[index]
    new_labels = {candidate.label for candidate in new_assignment.candidates}
    alternatives = [
        replace(candidate, confident=False) for candidate in old.candidates
        if candidate.label not in new_labels
    ]
    result[index] = PeakAssignment(
        peak=new_assignment.peak,
        candidates=list(new_assignment.candidates) + alternatives,
        rejection_reason=new_assignment.rejection_reason,
    )
    return result



def _raw_local_maximum(payload: Any, target: float, *, half_width: float = 2.2):
    """Return a measured raw-data local maximum near ``target``.

    This helper is deliberately simple and is used only after a resolved family
    is already plausible.  It avoids smoothing together close, intense doublets.
    """
    x = np.asarray(payload.x, dtype=float).ravel()
    y = np.asarray(payload.y, dtype=float).ravel()
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    if x.size < 5:
        return None
    order = np.argsort(x)
    x, y = x[order], y[order]
    mask = np.abs(x - float(target)) <= float(half_width)
    indices = [
        i for i in np.nonzero(mask)[0]
        if 0 < i < x.size - 1 and y[i] >= y[i - 1] and y[i] >= y[i + 1]
    ]
    if not indices:
        return None
    best = None
    for i in indices:
        shoulder = max(1.5, min(3.0, float(half_width)))
        local = np.nonzero(np.abs(x - x[i]) <= shoulder)[0]
        left = local[local < i]
        right = local[local > i]
        if left.size == 0 or right.size == 0:
            continue
        floor = max(float(np.nanmin(y[left])), float(np.nanmin(y[right])))
        prominence = max(0.0, float(y[i]) - floor)
        candidate = (prominence, -abs(float(x[i]) - float(target)), i)
        if best is None or candidate > best:
            best = candidate
    if best is None:
        return None
    prominence, _neg_distance, i = best
    original_finite = np.nonzero(finite)[0]
    original_index = int(original_finite[order[i]])
    return DetectedPeak(original_index, float(x[i]), float(y[i]), float(prominence))


def _lock_dominant_resolved_families(
    assignments: list[PeakAssignment], payload: Any, *, selected_elements: set[str],
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> list[PeakAssignment]:
    """Lock strong coherent doublets before weaker overlapping families are recovered.

    Heavy-element surveys can contain a weak family whose expected partner lies
    directly under a much stronger family (Ir 5p1/2 under Ir 4f is the motivating
    example).  Families are therefore proposed from raw measured pair geometry and
    accepted in descending measured-strength/cross-section order.  Once a peak is
    locked by a dominant family, a weaker family may not reuse it as its partner.
    """
    records = normalized_core_records(sample_mode)
    component_re = re.compile(r"^(\d+[spdf])([1357]/2)$")
    families: dict[tuple[str, str], set[str]] = {}
    for record in records:
        element = str(record.get("element", ""))
        if selected_elements and element not in selected_elements:
            continue
        line = str(record.get("transition", record.get("line", ""))).strip()
        m = component_re.match(line)
        if m:
            families.setdefault((element, m.group(1)), set()).add(line)

    accepted_elements = {a.best.element for a in _accepted_pe(assignments) if a.best is not None}
    proposals = []
    span = _global_span(payload)
    min_prominence = max(0.0008 * span, np.finfo(float).eps)
    for (element, family), lines in families.items():
        if element not in accepted_elements:
            continue
        # Transition-metal 2p multiplets require their dedicated broad,
        # charging-aware family search; raw close-doublet locking is not
        # appropriate for those chemically shifted/multiplet-broadened envelopes.
        if element in _TRANSITION_METALS and family == "2p":
            continue
        offsets = family_component_offsets(element, family)
        usable = {line for line in lines if line in offsets}
        if len(usable) < 2:
            continue
        strongest = strongest_component_line(element, usable, photon_energy)
        if strongest is None:
            continue
        strong_ref = _reference_position_for_line(
            element=element, line=strongest, energy_scale=energy_scale,
            photon_energy=photon_energy, sample_mode=sample_mode,
        )
        if strong_ref is None:
            continue
        strong_peak = _raw_local_maximum(payload, strong_ref, half_width=2.5)
        if strong_peak is None or float(strong_peak.prominence) < min_prominence:
            continue
        for weak in usable:
            if weak == strongest:
                continue
            relative = component_axis_delta(offsets[strongest], offsets[weak], energy_scale)
            # Dominant-family locking is for experimentally resolved families.
            # Do not split a single broad survey maximum into two j components
            # merely because the atomic reference contains a small spin-orbit
            # separation (Si 2p is the important example).  Require the
            # reference separation to span at least two sampled energy intervals
            # (and at least 0.35 eV) before attempting resolved-family locking.
            axis = np.asarray(getattr(payload, "x", []), dtype=float)
            finite_axis = np.sort(axis[np.isfinite(axis)])
            if finite_axis.size >= 2:
                diffs = np.diff(finite_axis)
                diffs = diffs[diffs > 0]
                axis_step = float(np.median(diffs)) if diffs.size else 0.0
            else:
                axis_step = 0.0
            resolvable_separation = max(0.35, 2.0 * axis_step)
            if abs(float(relative)) < resolvable_separation:
                continue
            # Very widely split deep doublets (for example Ir 4p) retain the
            # ordinary evidence rules; otherwise a broad background fluctuation
            # near the remote partner can be promoted incorrectly.
            if abs(float(relative)) > 25.0:
                continue
            target = float(strong_peak.energy) + float(relative)
            weak_peak = _raw_local_maximum(payload, target, half_width=max(1.5, min(2.5, 0.25 * abs(relative))))
            if weak_peak is None or float(weak_peak.prominence) < min_prominence:
                continue
            # Even when the tabulated splitting is in principle resolvable, the
            # measured pair must contain two distinct maxima.  Reusing the same
            # experimental maximum for both j components later creates an
            # artificial same-peak conflict and can erase a correct unresolved
            # family assignment.
            if abs(float(weak_peak.energy) - float(strong_peak.energy)) < resolvable_separation:
                continue
            tol = family_pair_tolerance(offsets[strongest], offsets[weak])
            mismatch = abs((float(weak_peak.energy) - float(strong_peak.energy)) - float(relative))
            if mismatch > tol:
                continue
            sigma = family_cross_section_at(element, family, photon_energy) if photon_energy is not None else None
            sigma_weight = max(float(sigma), 1e-6) if sigma is not None else 1.0
            measured = float(strong_peak.prominence) + 0.7 * float(weak_peak.prominence)
            score = np.log1p(measured / min_prominence) + 0.25 * np.log1p(sigma_weight) - 1.5 * (mismatch / max(tol, 1e-9)) ** 2
            proposals.append((float(score), measured, element, family, strongest, weak, strong_peak, weak_peak))

    result = list(assignments)
    locked: list[tuple[float, str, str]] = []
    for _score, _measured, element, family, strong_line, weak_line, strong_peak, weak_peak in sorted(
        proposals, key=lambda row: (row[0], row[1]), reverse=True
    ):
        # Do not let a weaker family reuse a peak already claimed by a stronger
        # coherent family.  A separate, experimentally resolved peak remains allowed.
        if any(abs(float(peak.energy) - e) <= 1.0 for e, _el, _fam in locked for peak in (strong_peak, weak_peak)):
            continue
        for line, peak in ((strong_line, strong_peak), (weak_line, weak_peak)):
            expected = _reference_position_for_line(
                element=element, line=line, energy_scale=energy_scale,
                photon_energy=photon_energy, sample_mode=sample_mode,
            )
            if expected is None:
                expected = float(peak.energy)
            recovered = _candidate_assignment(
                peak=peak, element=element, line=line, expected=float(expected),
                reason="Accepted by dominant-family locking: coherent measured resolved family",
                photon_energy=photon_energy, support=0.98,
            )
            result = _upsert_assignment_at_peak(result, recovered, tolerance_eV=0.8)
            locked.append((float(peak.energy), element, family))
    return result


def _partner_target_is_obscured(
    assignments: list[PeakAssignment], *, element: str, family: str, target: float,
    anchor_prominence: float, photon_energy: float | None,
) -> bool:
    """Return True when a predicted weak partner falls under a dominant family peak."""
    own_sigma = family_cross_section_at(element, family, photon_energy) if photon_energy is not None else None
    for other in _accepted_pe(assignments):
        if other.best is None or other.best.element != element:
            continue
        other_family = _base_transition(other.best.line)
        if other_family == family or abs(float(other.peak.energy) - float(target)) > 1.5:
            continue
        other_sigma = family_cross_section_at(element, other_family, photon_energy) if photon_energy is not None else None
        prominence_ratio = float(other.peak.prominence) / max(float(anchor_prominence), 1e-9)
        sigma_ratio = (float(other_sigma) / float(own_sigma)) if (other_sigma and own_sigma and own_sigma > 0) else 1.0
        if prominence_ratio >= 3.0 or sigma_ratio >= 3.0:
            return True
    return False

def _family_present(assignments: list[PeakAssignment], element: str, family: str) -> bool:
    return any(
        a.best is not None and a.best.kind == "PE" and a.best.element == element
        and _base_transition(a.best.line) == family
        for a in assignments
    )


def _find_feature(payload: Any, target: float, *, half_width: float, min_height: float):
    return refine_peak_near_reference(
        payload.x, payload.y,
        target_energy=float(target),
        search_half_width=float(half_width),
        min_feature_height=float(min_height),
    )





def _measured_peak_near_target(
    assignments: list[PeakAssignment], target: float, *, tolerance_eV: float,
    min_prominence: float = 0.0,
):
    """Return an already detected measured peak compatible with ``target``.

    Family recovery runs after the ordinary/guided detector, so a sharp partner
    that already passed peak detection should be reused before applying a broad
    smoothing detector.  This is important for transition-metal 2p families:
    broad multiplet envelopes and relatively sharp metallic components can occur
    in the same survey, and heavy smoothing may erase the latter.
    """
    candidates = []
    for assignment in assignments:
        peak = assignment.peak
        distance = abs(float(peak.energy) - float(target))
        if distance > float(tolerance_eV):
            continue
        prominence = max(float(peak.prominence), 0.0)
        if prominence < float(min_prominence):
            continue
        candidates.append((distance, -prominence, peak))
    if not candidates:
        return None
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def _tm_2p_anchor_rank(
    assignments: list[PeakAssignment], element: str, *, energy_scale: str = "Binding"
) -> int:
    """Return 0/1/2 for absent/single/coherent resolved TM 2p evidence."""
    rows = [
        a for a in _accepted_pe(assignments)
        if a.best is not None and a.best.element == element
        and _base_transition(a.best.line) == "2p"
    ]
    if not rows:
        return 0
    offsets = family_component_offsets(element, "2p")
    for left in rows:
        if left.best is None or left.best.line not in offsets:
            continue
        for right in rows:
            if right is left or right.best is None or right.best.line not in offsets:
                continue
            if right.best.line == left.best.line:
                continue
            expected_delta = component_axis_delta(
                offsets[left.best.line], offsets[right.best.line], energy_scale
            )
            observed_delta = float(right.peak.energy) - float(left.peak.energy)
            tolerance = family_pair_tolerance(
                offsets[left.best.line], offsets[right.best.line]
            )
            if abs(observed_delta - expected_delta) <= tolerance:
                return 2
    return 1


def _tm_2p_intensity_evidence(
    assignments: list[PeakAssignment], element: str, *, photon_energy: float | None,
    energy_scale: str = "Binding",
) -> tuple[float | None, float]:
    """Return (sensitivity-normalized 2p strength, confidence) for a TM element.

    The strength is based on measured peak prominence rather than raw peak
    height.  It is normalized by the Yeh-Lindau 2p family cross section so it
    acts only as a rough abundance proxy.  Confidence is deliberately
    conservative: a coherent resolved 2p pair is trusted most, while a single
    component, an implausible component ratio, or low-reliability assignments
    strongly reduce the weight.  The result is intended only as a soft
    discriminator between otherwise plausible shallow-line identities.
    """
    if photon_energy is None:
        return None, 0.0
    rows = [
        a for a in _accepted_pe(assignments)
        if a.best is not None and a.best.element == element
        and _base_transition(a.best.line) == "2p"
    ]
    if not rows:
        return None, 0.0

    sigma = family_cross_section_at(element, "2p", photon_energy)
    if sigma is None or not np.isfinite(float(sigma)) or float(sigma) <= 0.0:
        return None, 0.0

    # Prominence already subtracts the local baseline and is therefore much
    # safer than absolute survey intensity for spectra with a strong slope.
    prominences = [max(float(a.peak.prominence), 0.0) for a in rows]
    total_prominence = float(sum(prominences))
    if total_prominence <= 0.0:
        return None, 0.0

    rank = _tm_2p_anchor_rank(assignments, element, energy_scale=energy_scale)
    reliabilities = [float(a.best.reliability) / 100.0 for a in rows if a.best is not None]
    reliability_factor = float(np.clip(np.mean(reliabilities) if reliabilities else 0.0, 0.0, 1.0))

    # A clean resolved doublet normally has two measurable components.  Do not
    # require a precise theoretical ratio (multiplets/satellites can alter it),
    # but down-weight extreme ratios that often indicate masking or accidental
    # overlap.
    ratio_factor = 0.55
    if len(prominences) >= 2:
        ordered = sorted((p for p in prominences if p > 0.0), reverse=True)
        if len(ordered) >= 2:
            ratio = ordered[1] / max(ordered[0], 1e-30)
            if 0.18 <= ratio <= 1.10:
                ratio_factor = 1.0
            elif 0.08 <= ratio <= 1.60:
                ratio_factor = 0.72
            else:
                ratio_factor = 0.35

    rank_factor = 1.0 if rank >= 2 else 0.35 if rank == 1 else 0.0
    confidence = float(np.clip(rank_factor * reliability_factor * ratio_factor, 0.0, 1.0))
    normalized_strength = total_prominence / float(sigma)
    return float(normalized_strength), confidence


def _tm_relative_2p_intensity_bonus(
    assignments: list[PeakAssignment], element: str, competitor_element: str, *,
    photon_energy: float | None, energy_scale: str,
) -> float:
    """Bounded secondary bonus from relative 2p strength.

    This must never be the primary decision-maker.  The bonus is therefore
    limited to +/-0.75 score units and fades toward zero whenever either 2p
    family is uncertain.
    """
    own, own_conf = _tm_2p_intensity_evidence(
        assignments, element, photon_energy=photon_energy, energy_scale=energy_scale
    )
    other, other_conf = _tm_2p_intensity_evidence(
        assignments, competitor_element, photon_energy=photon_energy, energy_scale=energy_scale
    )
    if own is None or other is None or own <= 0.0 or other <= 0.0:
        return 0.0
    confidence = min(float(own_conf), float(other_conf))
    if confidence <= 0.0:
        return 0.0
    log_ratio = float(np.log10(float(own) / float(other)))
    return float(np.clip(0.75 * confidence * log_ratio, -0.75, 0.75))


def _tm_shallow_alignment_residual(
    assignments: list[PeakAssignment], assignment: PeakAssignment, *,
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> float:
    """Residual of a shallow TM line after transferring the deep-core shift."""
    best = assignment.best
    if best is None:
        return float("inf")
    family = _base_transition(best.line)
    expected = _reference_position_for_line(
        element=best.element, line=family, energy_scale=energy_scale,
        photon_energy=photon_energy, sample_mode=sample_mode,
    )
    if expected is None:
        return abs(float(best.delta_e))
    target = float(expected) + _element_shift(assignments, best.element)
    return abs(float(assignment.peak.energy) - target)


def _prefer_tm_shallow_assignment(
    existing: PeakAssignment, challenger: PeakAssignment, assignments: list[PeakAssignment], *,
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> PeakAssignment:
    """Choose between competing TM 3p/3s identities at one measured feature.

    Energy/deep-core shift agreement is the main discriminator.  Independent
    2p-family evidence is next.  Relative 2p intensity contributes only a
    bounded, confidence-weighted secondary bonus, so noisy or masked 2p regions
    cannot dominate the shallow-line identity.
    """
    pair = (existing, challenger)

    def score(assignment: PeakAssignment, competitor: PeakAssignment):
        best = assignment.best
        other = competitor.best
        if best is None or other is None:
            return float("-inf"), (-1, -1, -1.0)
        family = _base_transition(best.line)
        residual = _tm_shallow_alignment_residual(
            assignments, assignment, energy_scale=energy_scale,
            photon_energy=photon_energy, sample_mode=sample_mode,
        )
        deep_rank = _tm_2p_anchor_rank(
            assignments, best.element, energy_scale=energy_scale
        )
        corroboration = _tm_element_evidence(
            assignments, best.element, exclude_family=family
        )
        intensity_bonus = _tm_relative_2p_intensity_bonus(
            assignments, best.element, other.element,
            photon_energy=photon_energy, energy_scale=energy_scale,
        )
        # One eV of shallow-line mismatch remains more important than a large
        # 2p-intensity advantage.  Coherent 2p evidence helps, while intensity
        # can only nudge close cases.
        value = (
            -1.0 * float(residual)
            + 1.20 * float(deep_rank)
            + 0.30 * float(corroboration)
            + float(intensity_bonus)
        )
        tie = (int(best.reliability), int(deep_rank), float(assignment.peak.prominence))
        return value, tie

    return max(pair, key=lambda a: score(a, challenger if a is existing else existing))


def _find_broad_component(payload: Any, target: float, *, half_width: float, min_height: float):
    x = np.asarray(payload.x, dtype=float).reshape(-1)
    y = np.asarray(payload.y, dtype=float).reshape(-1)
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    order = np.argsort(x)
    x, y = x[order], y[order]
    mask = (x >= float(target) - half_width) & (x <= float(target) + half_width)
    if np.count_nonzero(mask) < 9:
        return None
    xl, yl = x[mask], y[mask]
    step = max(float(np.median(np.diff(xl))), 1e-6)
    window = max(5, int(round(4.0 / step)) | 1)
    window = min(window, xl.size if xl.size % 2 else xl.size - 1)
    smooth = savgol_filter(yl, window, min(2, window - 2)) if window >= 5 else yl
    baseline = np.interp(xl, [xl[0], xl[-1]], [smooth[0], smooth[-1]])
    residual = smooth - baseline
    peaks, props = find_peaks(residual, prominence=max(0.35 * min_height, np.finfo(float).eps))
    if peaks.size == 0:
        return None
    candidates = []
    for idx, prom in zip(peaks, props.get("prominences", np.zeros(peaks.size))):
        if residual[idx] < min_height:
            continue
        distance = abs(float(xl[idx]) - float(target))
        candidates.append((distance, -float(prom), int(idx), float(prom)))
    if not candidates:
        return None
    _, _, idx, prominence = min(candidates)
    raw_local = np.where(np.abs(xl - xl[idx]) <= max(1.5, 2.0 * step))[0]
    raw_idx = int(raw_local[np.argmax(yl[raw_local])]) if raw_local.size else idx
    global_index = int(np.argmin(np.abs(x - xl[raw_idx])))
    return DetectedPeak(global_index, float(xl[raw_idx]), float(yl[raw_idx]), prominence)

def _global_span(payload: Any) -> float:
    y = np.asarray(payload.y, dtype=float).reshape(-1)
    finite = y[np.isfinite(y)]
    return max(float(np.ptp(finite)), 1.0) if finite.size else 1.0




def _find_multiple_components(payload: Any, lo: float, hi: float, *, min_prominence: float, max_components: int = 3):
    """Return distinct measured maxima in a chemically broadened core-level window.

    A gently smoothed, endpoint-baseline-subtracted trace is used so nearby
    chemical-state components can be separated without treating every noisy
    fluctuation as a core line.
    """
    x = np.asarray(payload.x, dtype=float).reshape(-1)
    y = np.asarray(payload.y, dtype=float).reshape(-1)
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    order = np.argsort(x)
    x, y = x[order], y[order]
    mask = (x >= float(lo)) & (x <= float(hi))
    if np.count_nonzero(mask) < 9:
        return []
    xl, yl = x[mask], y[mask]
    step = max(float(np.median(np.diff(xl))), 1e-6)
    window = max(5, int(round(1.5 / step)) | 1)
    window = min(window, xl.size if xl.size % 2 else xl.size - 1)
    smooth = savgol_filter(yl, window, min(2, window - 2)) if window >= 5 else yl
    baseline = np.interp(xl, [xl[0], xl[-1]], [smooth[0], smooth[-1]])
    residual = smooth - baseline
    distance = max(1, int(round(1.2 / step)))
    peaks, props = find_peaks(residual, prominence=max(float(min_prominence), np.finfo(float).eps), distance=distance)
    found = []
    for idx, prom in zip(peaks, props.get("prominences", np.zeros(peaks.size))):
        if residual[idx] <= 0:
            continue
        raw_local = np.where(np.abs(xl - xl[idx]) <= max(0.75, 1.5 * step))[0]
        raw_idx = int(raw_local[np.argmax(yl[raw_local])]) if raw_local.size else int(idx)
        found.append(DetectedPeak(
            int(np.argmin(np.abs(x - xl[raw_idx]))),
            float(xl[raw_idx]), float(yl[raw_idx]), float(prom),
        ))
    found.sort(key=lambda peak: float(peak.prominence), reverse=True)
    selected = []
    for peak in found:
        if all(abs(float(peak.energy) - float(other.energy)) >= 1.2 for other in selected):
            selected.append(peak)
        if len(selected) >= max_components:
            break
    return sorted(selected, key=lambda peak: float(peak.energy))


def _recover_paired_chemical_states(
    assignments: list[PeakAssignment], payload: Any, *, selected_elements: set[str],
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> list[PeakAssignment]:
    """Recover repeated s/p core lines from two chemical states.

    This addresses systems such as Si + SiOx, where both Si 2p and Si 2s
    contain two components with nearly the same chemical-state separation.
    The paired separation is much stronger evidence than either extra peak on
    its own.
    """
    if photon_energy is None or not str(energy_scale).lower().startswith("bind"):
        return assignments
    result = list(assignments)
    span = _global_span(payload)
    records = normalized_core_records(sample_mode)
    for element in sorted(selected_elements):
        p_rows = []
        for record in records:
            if str(record.get("element", "")) != element:
                continue
            if str(record.get("transition", record.get("line", ""))).strip() != "2p":
                continue
            phase = str(record.get("phase", "")).lower()
            if "gas" in phase or "atomic" in phase:
                continue
            try:
                p_rows.append(float(record.get("representative_energy_eV", record.get("binding_energy_eV"))))
            except Exception:
                pass
        if len(p_rows) < 2 or max(p_rows) - min(p_rows) < 1.8:
            continue
        s_ref = _reference_position_for_line(
            element=element, line="2s", energy_scale=energy_scale,
            photon_energy=photon_energy, sample_mode=sample_mode,
        )
        if s_ref is None:
            continue
        p_lo, p_hi = min(p_rows) - 2.5, max(p_rows) + 2.5
        max_state_shift = min(7.0, max(4.0, max(p_rows) - min(p_rows) + 2.0))
        local_floor = max(span * 0.00020, np.finfo(float).eps)
        p_peaks = _find_multiple_components(payload, p_lo, p_hi, min_prominence=local_floor, max_components=3)
        s_peaks = _find_multiple_components(payload, s_ref - 3.0, s_ref + max_state_shift, min_prominence=local_floor, max_components=3)
        if len(p_peaks) < 2 or len(s_peaks) < 2:
            continue
        best_pair = None
        for i in range(len(p_peaks)):
            for j in range(i + 1, len(p_peaks)):
                p_sep = float(p_peaks[j].energy - p_peaks[i].energy)
                if not 1.5 <= p_sep <= 6.0:
                    continue
                for k in range(len(s_peaks)):
                    for m in range(k + 1, len(s_peaks)):
                        s_sep = float(s_peaks[m].energy - s_peaks[k].energy)
                        mismatch = abs(p_sep - s_sep)
                        if mismatch > 1.25:
                            continue
                        strength = sum(float(v.prominence) for v in (p_peaks[i], p_peaks[j], s_peaks[k], s_peaks[m]))
                        key = (mismatch, -strength)
                        if best_pair is None or key < best_pair[0]:
                            best_pair = (key, (p_peaks[i], p_peaks[j], s_peaks[k], s_peaks[m], 0.5 * (p_sep + s_sep)))
        if best_pair is None:
            continue
        p1, p2, s1, s2, state_shift = best_pair[1]

        # A matching separation alone is not enough to claim a second chemical
        # state.  Weak shoulders/noise can accidentally reproduce the same
        # p/s spacing (notably S 2p/2s in survey spectra).  Require the weaker
        # component to carry a meaningful fraction of the dominant component
        # in both shells before promoting a four-line two-state solution.
        p_strengths = sorted((float(p1.prominence), float(p2.prominence)))
        s_strengths = sorted((float(s1.prominence), float(s2.prominence)))
        if p_strengths[1] <= 0.0 or s_strengths[1] <= 0.0:
            continue
        if (p_strengths[0] / p_strengths[1] < 0.15 or
                s_strengths[0] / s_strengths[1] < 0.15):
            continue

        # Replace provisional single-state or duplicate assignments in these
        # windows with the four mutually supporting measured components.
        kept = []
        for assignment in result:
            best = assignment.best
            if best is not None and best.kind == "PE" and best.element == element and best.line in {"2p", "2s"}:
                continue
            if best is None and assignment.rejection_reason.startswith("Duplicate transition") and (p_lo <= assignment.peak.energy <= p_hi or s_ref - 3.0 <= assignment.peak.energy <= s_ref + max_state_shift):
                continue
            kept.append(assignment)
        result = kept
        p_ref = min(p_rows, key=lambda value: abs(value - float(p1.energy)))
        for peak, line, expected, support in (
            (p1, "2p", p_ref, 1.0),
            (p2, "2p", p_ref + state_shift, 1.0),
            (s1, "2s", float(s_ref), 1.0),
            (s2, "2s", float(s_ref) + state_shift, 1.0),
        ):
            result.append(_candidate_assignment(
                peak=peak, element=element, line=line, expected=expected,
                photon_energy=photon_energy, support=support,
                reason=("Accepted by element-consistency layer: two chemical states give "
                        "matching 2p and 2s separations"),
            ))
    return result


def _recover_same_shell_sp_pairs(
    assignments: list[PeakAssignment], payload: Any, *, selected_elements: set[str],
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> list[PeakAssignment]:
    """Recover an ambiguous ``np`` line together with its ``ns`` companion.

    Every plausible p-family candidate at a measured peak is considered, not
    only the candidate that happened to rank first in single-line matching.
    A coherent measured p/s separation can therefore resolve an overlap while
    remaining insensitive to a common charging shift.
    """
    if photon_energy is None:
        return assignments
    result = list(assignments)
    span = _global_span(payload)
    base_floor = max(span * 0.00012, np.finfo(float).eps)
    pair_re = re.compile(r"^(\d+)p$")
    tested: set[tuple[int, str, str]] = set()

    for assignment_index, assignment in enumerate(list(assignments)):
        if not assignment.candidates:
            continue
        # Consider several locally plausible alternatives.  This is crucial in
        # crowded surveys, where the correct element can be candidate 2--4 at
        # one line but is strongly confirmed by its independent companion.
        for provisional in assignment.candidates[:8]:
            if provisional.kind != "PE" or provisional.order != 1:
                continue
            p_line = _base_transition(str(provisional.line).strip())
            match = pair_re.fullmatch(p_line)
            if match is None:
                continue
            element = provisional.element
            if selected_elements and element not in selected_elements:
                continue
            token = (assignment_index, element, p_line)
            if token in tested:
                continue
            tested.add(token)
            if abs(float(provisional.delta_e)) > 6.0 or float(provisional.score) > 3.5:
                continue

            s_line = f"{match.group(1)}s"
            if _family_present(result, element, p_line) and _family_present(result, element, s_line):
                continue
            p_ref = _reference_position_for_line(
                element=element, line=p_line, energy_scale=energy_scale,
                photon_energy=photon_energy, sample_mode=sample_mode,
            )
            s_ref = _reference_position_for_line(
                element=element, line=s_line, energy_scale=energy_scale,
                photon_energy=photon_energy, sample_mode=sample_mode,
            )
            if p_ref is None or s_ref is None:
                continue
            expected_separation = float(s_ref) - float(p_ref)
            if abs(expected_separation) < 4.0:
                continue

            p_peak = _find_feature(
                payload, float(assignment.peak.energy), half_width=2.5,
                min_height=base_floor,
            )
            if p_peak is None:
                continue
            target_s = float(p_peak.energy) + expected_separation

            sigma_p = family_cross_section_at(element, p_line, photon_energy)
            sigma_s = family_cross_section_at(element, s_line, photon_energy)
            if sigma_p is not None and sigma_s is not None and sigma_p > 0:
                expected_ratio = max(0.08, min(4.0, float(sigma_s) / float(sigma_p)))
                s_floor = base_floor / max(0.65, min(2.0, expected_ratio ** 0.5))
            else:
                s_floor = base_floor
            s_peak = _find_feature(payload, target_s, half_width=2.5, min_height=s_floor)
            if s_peak is None:
                # An ns companion can sit on top of a broad Auger envelope.
                # In that case the smoothed local-background detector may
                # reject a genuine measured shoulder.  Fall back to a raw
                # local maximum only inside this family-constrained search;
                # the expected np/ns separation is still enforced below.
                raw_peak = _raw_local_maximum(payload, target_s, half_width=2.5)
                raw_floor = max(base_floor, 0.0005 * span)
                if raw_peak is not None and float(raw_peak.prominence) >= raw_floor:
                    s_peak = raw_peak
            if s_peak is None or abs(float(s_peak.energy) - float(p_peak.energy)) < 1.0:
                continue
            observed_separation = float(s_peak.energy) - float(p_peak.energy)
            mismatch = abs(observed_separation - expected_separation)
            if mismatch > 1.5:
                continue

            common_shift = 0.5 * (
                (float(p_peak.energy) - float(p_ref))
                + (float(s_peak.energy) - float(s_ref))
            )
            reason = (
                "Accepted by element-consistency layer: independently measured same-shell "
                f"{p_line}/{s_line} pair has the expected separation "
                f"(mismatch {mismatch:.2f} eV); common shifts such as charging cancel in this test"
            )
            p_assignment = _candidate_assignment(
                peak=p_peak, element=element, line=p_line, expected=float(p_ref) + common_shift,
                photon_energy=photon_energy, support=0.95, reason=reason,
            )
            s_assignment = _candidate_assignment(
                peak=s_peak, element=element, line=s_line, expected=float(s_ref) + common_shift,
                photon_energy=photon_energy, support=0.95, reason=reason,
            )
            result = _upsert_assignment_at_peak(result, p_assignment, tolerance_eV=0.8)
            result = _upsert_assignment_at_peak(result, s_assignment, tolerance_eV=0.8)
    return result


def _recover_cross_shell_family_members(
    assignments: list[PeakAssignment], payload: Any, *, selected_elements: set[str],
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> list[PeakAssignment]:
    """Recover a missing core family once an element is independently established.

    This is deliberately a *second-stage* element-family check.  It never creates
    an element from a single reference-near fluctuation.  At least two independent
    photoelectron families from the same element must already be accepted.  The
    remaining accessible core families are then searched for measured local maxima.

    Yeh-Lindau cross sections provide only a broad intensity prior: analyzer
    transmission, IMFP, angular distributions and chemistry can change measured
    ratios substantially.  Consequently the cross-section comparison is used to
    tune confidence/thresholds over orders of magnitude, never as a hard expected
    intensity ratio.
    """
    if photon_energy is None:
        return assignments

    result = list(assignments)
    span = _global_span(payload)
    x = np.asarray(payload.x, dtype=float).reshape(-1)
    finite_x = x[np.isfinite(x)]
    if finite_x.size < 5:
        return result
    x_lo, x_hi = float(np.min(finite_x)), float(np.max(finite_x))

    records = normalized_core_records(sample_mode)
    families_by_element: dict[str, set[str]] = {}
    for record in records:
        element = str(record.get("element", "")).strip()
        if not element or (selected_elements and element not in selected_elements):
            continue
        line = str(record.get("transition", record.get("line", ""))).strip()
        family = _base_transition(line)
        if re.fullmatch(r"\d+[spdf]", family):
            families_by_element.setdefault(element, set()).add(family)

    for element in sorted(selected_elements):
        accepted = [
            a for a in _accepted_pe(result)
            if a.best is not None and a.best.element == element
        ]
        present_families = {_base_transition(a.best.line) for a in accepted if a.best is not None}
        # Two independent PE families are the minimum evidence required before
        # absolute-energy recovery of another shell is allowed.  Na 2p + 2s is
        # the motivating example.
        if len(present_families) < 2:
            continue

        # Estimate a very rough measured-prominence / cross-section scale from
        # established families.  Use one representative (strongest measured)
        # feature per family so resolved doublets are not double-counted.
        anchor_scales: list[float] = []
        anchor_prominences: list[float] = []
        for family in sorted(present_families):
            members = [
                a for a in accepted
                if a.best is not None and _base_transition(a.best.line) == family
            ]
            if not members:
                continue
            prominence = max(max(float(a.peak.prominence), 0.0) for a in members)
            sigma = family_cross_section_at(element, family, photon_energy)
            if prominence > 0:
                anchor_prominences.append(prominence)
            if sigma is not None and sigma > 0 and prominence > 0:
                anchor_scales.append(prominence / float(sigma))

        median_scale = float(np.median(anchor_scales)) if anchor_scales else None
        typical_anchor = float(np.median(anchor_prominences)) if anchor_prominences else span * 0.001
        shift = _element_shift(result, element)

        for family in sorted(families_by_element.get(element, set())):
            if family in present_families:
                continue
            expected = _reference_position_for_line(
                element=element, line=family, energy_scale=energy_scale,
                photon_energy=photon_energy, sample_mode=sample_mode,
            )
            if expected is None:
                continue
            target = float(expected) + float(shift)
            # Skip core levels outside the actually displayed/measured axis.
            if target < x_lo - 0.5 or target > x_hi + 0.5:
                continue
            if str(energy_scale).lower().startswith("bind") and target <= 15.0:
                continue

            sigma_target = family_cross_section_at(element, family, photon_energy)
            # Baseline evidence floor stays conservative.  Cross sections may
            # lower it modestly for a family expected stronger than established
            # anchors, but never enough to turn noise into a line.
            base_floor = max(span * 0.00012, np.finfo(float).eps)
            predicted = None
            if median_scale is not None and sigma_target is not None and sigma_target > 0:
                predicted = median_scale * float(sigma_target)
                # A huge theoretical ratio (e.g. Na 1s vs 2p at 1.2 keV) is
                # informative, but analyzer/IMFP effects forbid using it
                # literally.  At most relax/tighten the floor by ~3x.
                relative = predicted / max(typical_anchor, np.finfo(float).eps)
                sensitivity = float(np.clip(relative ** 0.25, 0.35, 3.0))
                min_height = base_floor / sensitivity
            else:
                min_height = base_floor

            peak = _find_feature(payload, target, half_width=5.0, min_height=min_height)
            if peak is None:
                continue

            # Require a genuinely measured local feature, then use the
            # cross-section comparison only as a broad plausibility/support
            # term.  Ratios within one decade receive strong support; even two
            # decades are not a veto because kinetic-energy-dependent response
            # can be substantial in survey spectra.
            support = 0.84
            intensity_note = ""
            if predicted is not None and predicted > 0 and peak.prominence > 0:
                measured_ratio = float(peak.prominence) / float(predicted)
                log_mismatch = abs(float(np.log10(max(measured_ratio, 1e-12))))
                if log_mismatch <= 1.0:
                    support = 0.98
                elif log_mismatch <= 2.0:
                    support = 0.91
                else:
                    support = 0.82
                intensity_note = (
                    f"; measured/cross-section-scaled prominence ratio ~{measured_ratio:.2g}"
                )

            reason = (
                "Accepted by element-family consistency: the element is independently "
                f"established by {', '.join(sorted(present_families))}; a measured "
                f"{family} feature is present near its expected energy and is broadly "
                f"compatible with Yeh-Lindau cross-section evidence{intensity_note}"
            )
            recovered = _candidate_assignment(
                peak=peak, element=element, line=family, expected=target,
                photon_energy=photon_energy, support=support, reason=reason,
            )
            result = _upsert_assignment_at_peak(result, recovered, tolerance_eV=0.8)
            present_families.add(family)

    return result

def _recover_transition_metal_2p(
    assignments: list[PeakAssignment], payload: Any, *, selected_elements: set[str],
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> list[PeakAssignment]:
    """Recover transition-metal 2p doublets from the stronger component first.

    Transition-metal 2p envelopes are often broad and chemically shifted.  The
    statistically stronger member (normally 2p3/2) is therefore established as
    the family anchor before the weaker member is considered.  The weaker line
    is searched only at the *measured* anchor position plus the tabulated
    spin-orbit splitting.  A provisional weaker assignment at an incompatible
    separation is ignored and cannot block recovery of the real partner.
    """
    if photon_energy is None:
        return assignments
    result = list(assignments)
    span = _global_span(payload)

    for element in sorted(selected_elements & _TRANSITION_METALS):
        raw_expected: dict[str, float] = {}
        for suffix in _COMPONENTS:
            line = f"2p{suffix}"
            expected = _reference_position_for_line(
                element=element, line=line, energy_scale=energy_scale,
                photon_energy=photon_energy, sample_mode=sample_mode,
            )
            if expected is not None:
                raw_expected[line] = float(expected)
        if len(raw_expected) < 2:
            continue

        offsets = family_component_offsets(element, "2p")
        usable_lines = {line for line in raw_expected if line in offsets}
        if len(usable_lines) < 2:
            continue
        strong_line = strongest_component_line(element, usable_lines, photon_energy)
        if strong_line is None or strong_line not in offsets:
            continue

        # Step 1: establish the stronger measured component.  Prefer an already
        # accepted strong-line assignment; if none exists, perform one broad
        # absolute-energy search for the strong component only.
        strong_existing = [
            a for a in _accepted_pe(result)
            if a.best is not None and a.best.element == element and a.best.line == strong_line
        ]
        if strong_existing:
            # Several real maxima can legitimately compete for the strong 2p
            # component (metal/oxide/multiplet structure).  Choose the anchor
            # that forms the best *measured family* rather than the one nearest
            # an absolute compound reference.  Relative spin-orbit splitting is
            # much more robust against chemistry and charging.
            anchor_offset = offsets[strong_line]

            def anchor_pair_key(anchor: PeakAssignment):
                best_pair = None
                for sibling in usable_lines:
                    if sibling == strong_line:
                        continue
                    relative = component_axis_delta(anchor_offset, offsets[sibling], energy_scale)
                    target = float(anchor.peak.energy) + relative
                    tol = family_pair_tolerance(anchor_offset, offsets[sibling])
                    sibling_existing = [
                        a for a in _accepted_pe(result)
                        if a.best is not None and a.best.element == element and a.best.line == sibling
                        and abs(float(a.peak.energy) - target) <= tol
                    ]
                    if sibling_existing:
                        partner = max(sibling_existing, key=lambda a: float(a.peak.prominence)).peak
                    else:
                        sigma = cross_section_at(element, sibling, photon_energy) or 0.0
                        family_sigma = family_cross_section_at(element, "2p", photon_energy) or sigma or 1.0
                        sensitivity = max(0.35, min(1.0, sigma / family_sigma * 2.0))
                        min_height = max(span * 0.00010 / sensitivity, np.finfo(float).eps)
                        partner = _measured_peak_near_target(
                            result, target, tolerance_eV=tol,
                            min_prominence=max(0.35 * min_height, np.finfo(float).eps),
                        )
                        if partner is None:
                            splitting = abs(relative)
                            partner = _find_broad_component(
                                payload, target, half_width=max(2.5, min(4.0, 0.35 * splitting)),
                                min_height=min_height,
                            )
                    if partner is None:
                        continue
                    mismatch = abs((float(partner.energy) - float(anchor.peak.energy)) - relative)
                    norm = mismatch / max(tol, 1e-9)
                    candidate = (norm, -float(partner.prominence))
                    if best_pair is None or candidate < best_pair:
                        best_pair = candidate
                # A coherent partner is the primary criterion.  Prominence then
                # chooses between comparably coherent family hypotheses.
                if best_pair is None:
                    return (1, float("inf"), -float(anchor.peak.prominence))
                norm, neg_partner_prom = best_pair
                return (0 if norm <= 1.0 else 1, norm, -float(anchor.peak.prominence), neg_partner_prom)

            strong_assignment = min(strong_existing, key=anchor_pair_key)
            strong_peak = strong_assignment.peak
            # Keep the measured losing maxima in the peak table, but remove the
            # duplicate Ni/TM strong-line labels before shallow-line recovery.
            replaced = []
            for assignment in result:
                if assignment in strong_existing and assignment is not strong_assignment:
                    replaced.append(_reject_but_keep_peak(
                        assignment,
                        "Duplicate transition: another measured strong component forms a more coherent spin-orbit family",
                    ))
                else:
                    replaced.append(assignment)
            result = replaced
        else:
            shift = _element_shift(result, element)
            strong_target = raw_expected[strong_line] + shift
            strong_sigma = cross_section_at(element, strong_line, photon_energy) or 0.0
            family_sigma = family_cross_section_at(element, "2p", photon_energy) or strong_sigma or 1.0
            sensitivity = max(0.35, min(1.0, strong_sigma / family_sigma * 2.0))
            strong_peak = _find_broad_component(
                payload, strong_target, half_width=10.0,
                min_height=max(span * 0.00010 / sensitivity, np.finfo(float).eps),
            )
            if strong_peak is None:
                continue
            strong_assignment = _candidate_assignment(
                peak=strong_peak, element=element, line=strong_line,
                expected=raw_expected[strong_line], photon_energy=photon_energy,
                support=0.95,
                reason=("Accepted by element-consistency layer: strongest transition-metal "
                        "2p component measured before spin-orbit partner search"),
            )
            result = _upsert_assignment_at_peak(result, strong_assignment, tolerance_eV=0.8)

        anchor_offset = offsets[strong_line]

        # Step 2: search every weaker sibling from the measured strong anchor.
        for line in sorted(usable_lines, key=lambda item: offsets[item]):
            if line == strong_line:
                continue
            relative = component_axis_delta(anchor_offset, offsets[line], energy_scale)
            target = float(strong_peak.energy) + relative
            tolerance = family_pair_tolerance(anchor_offset, offsets[line])

            compatible = [
                a for a in _accepted_pe(result)
                if a.best is not None and a.best.element == element and a.best.line == line
                and abs(float(a.peak.energy) - target) <= tolerance
            ]
            if compatible:
                continue

            sigma = cross_section_at(element, line, photon_energy) or 0.0
            family_sigma = family_cross_section_at(element, "2p", photon_energy) or sigma or 1.0
            sensitivity = max(0.35, min(1.0, sigma / family_sigma * 2.0))
            splitting = abs(relative)
            half_width = max(2.5, min(4.0, 0.35 * splitting))
            min_height = max(span * 0.00010 / sensitivity, np.finfo(float).eps)
            # Reuse a peak that the normal detector already measured at the
            # family-predicted position before applying the broad TM detector.
            # The latter intentionally smooths over multiplet envelopes and can
            # otherwise suppress a relatively sharp metallic component (for
            # example Ni 2p1/2 in a mixed-metal survey).
            partner_peak = _measured_peak_near_target(
                result, target, tolerance_eV=tolerance,
                min_prominence=max(0.35 * min_height, np.finfo(float).eps),
            )
            if partner_peak is None:
                partner_peak = _find_broad_component(
                    payload, target, half_width=half_width, min_height=min_height,
                )
            if partner_peak is None:
                continue
            if abs(float(partner_peak.energy) - float(strong_peak.energy)) <= 0.7:
                continue
            mismatch = abs((float(partner_peak.energy) - float(strong_peak.energy)) - relative)
            if mismatch > tolerance:
                continue

            partner_assignment = _candidate_assignment(
                peak=partner_peak, element=element, line=line,
                expected=target, photon_energy=photon_energy, support=1.0,
                reason=("Accepted by element-consistency layer: weaker transition-metal 2p "
                        "component measured at the tabulated separation from the stronger anchor"),
            )
            # Upsert at the recovered *measured* partner.  An incompatible old
            # assignment with the same line label at another energy remains as a
            # rejected peak-table row after the final separation check; it does
            # not suppress this physically coherent replacement.
            result = _upsert_assignment_at_peak(result, partner_assignment, tolerance_eV=0.8)

    return result

def _recover_p_from_s(
    assignments: list[PeakAssignment], payload: Any, *, energy_scale: str,
    photon_energy: float | None, sample_mode: str,
) -> list[PeakAssignment]:
    """Recover a corresponding p family before allowing an observed s line."""
    if photon_energy is None:
        return assignments
    result = list(assignments)
    span = _global_span(payload)
    for assignment in list(_accepted_pe(result)):
        best = assignment.best
        assert best is not None
        match = re.fullmatch(r"(\d+)s", best.line)
        if not match:
            continue
        shell = match.group(1)
        p_family = f"{shell}p"
        if _family_present(result, best.element, p_family):
            continue
        shift = float(best.delta_e)
        # Resolve explicit components where available; for small splittings the
        # two searches converge on one measured maximum and are collapsed.
        recovered = []
        for suffix in ("3/2", "1/2", ""):
            line = f"{p_family}{suffix}"
            expected = _reference_position_for_line(
                element=best.element, line=line, energy_scale=energy_scale,
                photon_energy=photon_energy, sample_mode=sample_mode,
            )
            if expected is None:
                continue
            expected += shift
            if str(energy_scale).lower().startswith("bind") and 0.0 <= expected <= 15.0:
                continue
            sigma_p = cross_section_at(best.element, line, photon_energy)
            sigma_s = cross_section_at(best.element, best.line, photon_energy)
            if sigma_p is not None and sigma_s is not None:
                ratio = max(0.1, sigma_p / max(sigma_s, 1e-30))
            else:
                ratio = 1.0
            min_height = max(span * 0.00010 / min(4.0, max(0.5, ratio)), np.finfo(float).eps)
            peak = _find_feature(payload, expected, half_width=5.0, min_height=min_height)
            if peak is not None and all(abs(float(peak.energy) - float(p.energy)) > 0.8 for p, _, _ in recovered):
                recovered.append((peak, line, expected))
        if recovered:
            peak, line, expected = max(recovered, key=lambda item: item[0].prominence)
            # Use unresolved family label for small-splitting shallow p lines.
            display_line = p_family if len(recovered) == 1 else line
            result.append(_candidate_assignment(
                peak=peak, element=best.element, line=display_line,
                expected=expected, photon_energy=photon_energy, support=0.9,
                reason=("Accepted by element-consistency layer: p-family feature required by "
                        "the observed s line and supported by Yeh-Lindau cross sections"),
            ))
    return result



def _tm_element_evidence(
    assignments: list[PeakAssignment], element: str, *, exclude_family: str | None = None,
) -> float:
    """Return independent evidence that a transition metal is really present.

    Deep/core families are intentionally weighted much more strongly than the
    crowded shallow 3p/3s region.  A coherent 2p doublet is the primary anchor;
    a lone 2p member is useful but deliberately weaker because overlap with an
    Auger band or another core line can create accidental single-line matches.
    The opposite shallow family (3s for a 3p candidate, or vice versa) may add a
    small corroborating vote, but shallow lines never outweigh a resolved 2p
    family by themselves.
    """
    if element not in _TRANSITION_METALS:
        return 0.0
    by_family: dict[str, list[PeakAssignment]] = {}
    for assignment in _accepted_pe(assignments):
        best = assignment.best
        if best is None or best.element != element:
            continue
        family = _base_transition(best.line)
        if family == exclude_family:
            continue
        by_family.setdefault(family, []).append(assignment)

    evidence = 0.0
    two_p = by_family.get("2p", [])
    if two_p:
        component_lines = {a.best.line for a in two_p if a.best is not None}
        # A resolved pair is much stronger evidence than one provisional member.
        evidence += 3.0 if len(component_lines) >= 2 else 1.25

    # Other non-shallow core families can support an element when available,
    # though for 3d transition metals they are normally secondary to 2p.
    for family in ("1s", "2s", "3d", "4d", "4f"):
        if family in by_family:
            evidence += 1.0

    # 3p and 3s are useful mutual confirmation, but only as a small extra vote.
    for family in ("3p", "3s"):
        if family != exclude_family and family in by_family:
            evidence += 0.65
    return evidence


def _recover_transition_metal_shallow_families(
    assignments: list[PeakAssignment], payload: Any, *, selected_elements: set[str],
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> list[PeakAssignment]:
    """Recover measured TM 3p/3s features from independently established 2p.

    The 2p family establishes the element first.  Shallow lines are then sought
    near their reference position, shifted by the element's measured deep-core
    offset.  The transfer of shift is deliberately soft: 3p/3s chemical shifts
    need not equal the 2p shift, so a several-eV local window is retained.
    Cross sections control the evidence threshold only; a measured maximum is
    always required.
    """
    if photon_energy is None:
        return assignments
    result = list(assignments)
    span = _global_span(payload)

    for element in sorted(selected_elements & _TRANSITION_METALS):
        anchors = [
            a for a in _accepted_pe(result)
            if a.best is not None and a.best.element == element
            and _base_transition(a.best.line) == "2p"
        ]
        if not anchors:
            continue

        shift = _element_shift(result, element)
        sigma_2p = family_cross_section_at(element, "2p", photon_energy)
        anchor_prominence = sum(max(float(a.peak.prominence), 0.0) for a in anchors)

        for family, half_width in (("3p", 6.5), ("3s", 5.5)):
            expected = _reference_position_for_line(
                element=element, line=family, energy_scale=energy_scale,
                photon_energy=photon_energy, sample_mode=sample_mode,
            )
            if expected is None:
                continue
            target = float(expected) + float(shift)

            # Do not redo a search when the same family is already measured in
            # the neighbourhood predicted from the deep-core anchor.  A shallow
            # assignment far away does not block recovery of a better feature.
            compatible_existing_tolerance = 3.0
            existing = [
                a for a in _accepted_pe(result)
                if a.best is not None and a.best.element == element
                and _base_transition(a.best.line) == family
                and abs(float(a.peak.energy) - target) <= compatible_existing_tolerance
            ]
            if existing:
                continue

            sigma_shallow = family_cross_section_at(element, family, photon_energy)
            if sigma_shallow is None:
                continue
            ratio = sigma_shallow / max(sigma_2p or sigma_shallow, 1e-30)
            expected_prominence = anchor_prominence * max(0.008, min(0.30, ratio))
            min_height = max(
                span * 0.00008, 0.10 * expected_prominence, np.finfo(float).eps
            )
            peak = _find_feature(
                payload, target, half_width=half_width, min_height=min_height
            )
            if peak is None:
                continue

            recovered = _candidate_assignment(
                peak=peak, element=element, line=family, expected=target,
                photon_energy=photon_energy, support=min(1.0, 0.72 + 1.5 * ratio),
                reason=(
                    "Accepted by element-consistency layer: measured shallow "
                    f"{family} feature supported by the independently established "
                    "2p family and Yeh-Lindau cross sections"
                ),
            )

            # A single shallow maximum can lie inside the broad reference
            # windows of neighbouring 3d metals.  Do not let whichever element
            # happens to be processed later overwrite the existing identity.
            # Compare the candidates using coherent 2p evidence first and the
            # element-specific deep-to-shallow shift alignment second.
            competitors = [
                a for a in _accepted_pe(result)
                if a.best is not None
                and a.best.element in _TRANSITION_METALS
                and _base_transition(a.best.line) in {"3p", "3s"}
                and abs(float(a.peak.energy) - float(peak.energy)) <= 0.8
            ]
            if competitors:
                existing_competitor = min(
                    competitors, key=lambda a: abs(float(a.peak.energy) - float(peak.energy))
                )
                winner = _prefer_tm_shallow_assignment(
                    existing_competitor, recovered, result,
                    energy_scale=energy_scale, photon_energy=photon_energy,
                    sample_mode=sample_mode,
                )
                if winner is existing_competitor:
                    continue

            result = _upsert_assignment_at_peak(result, recovered, tolerance_eV=0.8)
    return result


def _recover_cross_section_supported_p(
    assignments: list[PeakAssignment], payload: Any, *, selected_elements: set[str],
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> list[PeakAssignment]:
    """Backward-compatible internal alias for the TM shallow-family recovery."""
    return _recover_transition_metal_shallow_families(
        assignments, payload, selected_elements=selected_elements,
        energy_scale=energy_scale, photon_energy=photon_energy, sample_mode=sample_mode,
    )

def _resolve_same_peak_conflicts(
    assignments: list[PeakAssignment], photon_energy: float | None, *,
    energy_scale: str = "Binding", sample_mode: str = "Automatic (prefer solids)",
) -> list[PeakAssignment]:
    accepted = _accepted_pe(assignments)
    clusters: list[list[PeakAssignment]] = []
    for assignment in sorted(accepted, key=lambda a: float(a.peak.energy)):
        if not clusters or abs(float(assignment.peak.energy) - float(clusters[-1][-1].peak.energy)) > 0.9:
            clusters.append([assignment])
        else:
            clusters[-1].append(assignment)
    remove_ids: set[int] = set()
    for cluster in clusters:
        if len(cluster) < 2:
            continue
        shallow_tm_cluster = all(
            a.best is not None
            and a.best.element in _TRANSITION_METALS
            and _base_transition(a.best.line) in {"3p", "3s"}
            for a in cluster
        )
        if shallow_tm_cluster:
            # Resolve neighbouring-metal shallow identities pairwise with the
            # same hierarchy used during recovery.  This preserves the soft 2p
            # intensity prior without allowing absolute cross sections to choose
            # elemental identity in the crowded 3p/3s region.
            keep = cluster[0]
            for challenger in cluster[1:]:
                keep = _prefer_tm_shallow_assignment(
                    keep, challenger, accepted, energy_scale=energy_scale,
                    photon_energy=photon_energy, sample_mode=sample_mode,
                )
            remove_ids.update(id(a) for a in cluster if a is not keep)
            continue

        def quality(a: PeakAssignment):
            best = a.best
            assert best is not None
            family = _base_transition(best.line)
            # Count independent companion *families*, not individual resolved
            # spin-orbit components.  Otherwise an element with (for example)
            # both 2p3/2 and 2p1/2 accepted receives two votes for the same
            # physical 2p family and can incorrectly beat another element
            # supported by an equally independent ns/np companion.
            companion_families = {
                _base_transition(other.best.line)
                for other in accepted
                if other is not a and other.best is not None
                and other.best.element == best.element
                and _base_transition(other.best.line) != family
            }
            companion = len(companion_families)
            # Do not prefer an orbital family merely because it is a p line.
            # At overlaps the physically relevant discriminator is the
            # photoionization strength of the whole family at the actual
            # photon energy.  This matters strongly for cases such as Ir,
            # where 4f is much more intense than the overlapping 5p1/2 line.
            sigma_family = (
                family_cross_section_at(best.element, family, photon_energy)
                if photon_energy is not None else None
            )
            cross_section_support = (
                0.75 * np.log10(max(float(sigma_family), 1e-9))
                if sigma_family is not None else 0.0
            )
            # The crowded 3p/3s region of neighbouring transition metals is
            # not allowed to decide element identity independently.  Deep-core
            # evidence, especially a coherent 2p doublet, acts as a strong
            # prior.  This is asymmetric on purpose: missing 2p does not ban a
            # shallow assignment, but a shallow candidate backed by measured
            # 2p should beat an otherwise similar unsupported neighbour.
            tm_element_prior = 0.0
            if shallow_tm_cluster and best.element in _TRANSITION_METALS and family in {"3p", "3s"}:
                tm_element_prior = 1.25 * _tm_element_evidence(
                    accepted, best.element, exclude_family=family
                )
            return (companion + cross_section_support + tm_element_prior,
                    best.reliability, -abs(best.delta_e), a.peak.prominence)
        keep = max(cluster, key=quality)
        remove_ids.update(id(a) for a in cluster if a is not keep)
    return [
        (_reject_but_keep_peak(a, "Competing assignment rejected in favour of a better-supported candidate at the same measured feature")
         if id(a) in remove_ids else a)
        for a in assignments
    ]


def _enforce_s_requires_p(assignments: list[PeakAssignment]) -> list[PeakAssignment]:
    result = []
    for assignment in assignments:
        best = assignment.best
        if best is None or best.kind != "PE":
            result.append(assignment)
            continue
        match = re.fullmatch(r"(\d+)s", best.line)
        if match:
            shell = int(match.group(1))
            # 1s has no p companion.  For light elements, 2p belongs to the
            # protected valence manifold, so an O/C/N/F 2s line is not rejected
            # merely because individual valence orbitals are intentionally not
            # labelled.
            valence_exception = shell == 1 or (shell == 2 and best.element in {"B", "C", "N", "O", "F", "Ne"})
            if not valence_exception and not _family_present(assignments, best.element, f"{shell}p"):
                result.append(_reject_but_keep_peak(
                    assignment,
                    "s-line assignment rejected because the expected p-family companion is absent",
                ))
                continue
        result.append(assignment)
    return result


def _enforce_stronger_spin_orbit(assignments: list[PeakAssignment]) -> list[PeakAssignment]:
    """Reject a weaker resolved component when the stronger family member is absent.

    This rule is generic for p, d and f spin-orbit families rather than being
    limited to p1/2.  It mirrors the search order used by guided detection and
    family recovery: p3/2, d5/2, f7/2 (or the cross-section-equivalent stronger
    member) establishes the family before the weaker member can survive.
    """
    accepted = _accepted_pe(assignments)
    result: list[PeakAssignment] = []
    component_re = re.compile(r"^(\d+[spdf])([1357]/2)$")
    for assignment in assignments:
        best = assignment.best
        if best is None or best.kind != "PE":
            result.append(assignment)
            continue
        match = component_re.match(str(best.line))
        if not match:
            result.append(assignment)
            continue
        family = match.group(1)
        offsets = family_component_offsets(best.element, family)
        if best.line not in offsets or len(offsets) < 2:
            result.append(assignment)
            continue
        stronger = strongest_component_line(best.element, set(offsets), None)
        if stronger is None or best.line == stronger:
            result.append(assignment)
            continue
        if any(
            a.best is not None and a.best.element == best.element and a.best.line == stronger
            for a in accepted
        ):
            result.append(assignment)
        else:
            result.append(_reject_but_keep_peak(
                assignment,
                "Weaker spin-orbit component rejected because the stronger partner is absent",
            ))
    return result

def _recover_resolved_family_partners(
    assignments: list[PeakAssignment], payload: Any, *, selected_elements: set[str],
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> list[PeakAssignment]:
    """Recover weaker members of resolvable spin-orbit families from the strong anchor.

    Absolute core-level energies can move with chemistry or charging, while the
    intra-family spin-orbit separation is much more stable.  The statistically
    stronger component is therefore the only family anchor.  Existing weaker
    assignments count as partners only when their measured separation is
    compatible with the tabulated geometry; otherwise they are ignored and a
    replacement is searched at the pair-predicted position.
    """
    component_re = re.compile(r"^(\d+[spdf])([1357]/2)$")
    records = normalized_core_records(sample_mode)
    families: dict[tuple[str, str], set[str]] = {}
    for record in records:
        element = str(record.get("element", ""))
        if selected_elements and element not in selected_elements:
            continue
        line = str(record.get("transition", record.get("line", ""))).strip()
        match = component_re.match(line)
        if match:
            families.setdefault((element, match.group(1)), set()).add(line)

    result = list(assignments)
    span = _global_span(payload)
    min_height = max(0.00012 * span, np.finfo(float).eps)

    for (element, family), lines in families.items():
        # Transition-metal 2p families need a broader multiplet-aware detector
        # and are handled by _recover_transition_metal_2p immediately before
        # this generic sharp-feature recovery.
        if element in _TRANSITION_METALS and family == "2p":
            continue

        offsets = family_component_offsets(element, family)
        usable_lines = {line for line in lines if line in offsets}
        if len(usable_lines) < 2:
            continue
        strongest = strongest_component_line(element, usable_lines, photon_energy)
        if strongest is None or strongest not in offsets:
            continue

        strong_assignments = [
            a for a in _accepted_pe(result)
            if a.best is not None and a.best.element == element and a.best.line == strongest
        ]
        if not strong_assignments:
            # A weak component never bootstraps a family.  This avoids exactly
            # the failure mode where a shoulder near an unshifted weak-line
            # reference forces the subsequent search in the wrong direction.
            continue
        anchor = max(
            strong_assignments,
            key=lambda a: (float(a.peak.prominence), a.best.reliability if a.best else 0),
        )
        anchor_offset = offsets[strongest]

        for line in sorted(usable_lines, key=lambda item: offsets[item]):
            if line == strongest:
                continue
            relative = component_axis_delta(anchor_offset, offsets[line], energy_scale)
            target = float(anchor.peak.energy) + relative
            tolerance = family_pair_tolerance(anchor_offset, offsets[line])

            compatible = [
                a for a in _accepted_pe(result)
                if a.best is not None and a.best.element == element and a.best.line == line
                and abs(float(a.peak.energy) - target) <= tolerance
            ]
            if compatible:
                continue

            splitting = abs(relative)
            half_width = max(1.5, min(3.0, 0.25 * splitting))
            if _partner_target_is_obscured(
                result, element=element, family=family, target=target,
                anchor_prominence=float(anchor.peak.prominence), photon_energy=photon_energy,
            ):
                # A much stronger already-established family occupies the predicted
                # partner energy.  Treat the weak component as unresolved/obscured
                # rather than relabelling the dominant peak.
                continue
            peak = _find_feature(payload, target, half_width=half_width, min_height=min_height)
            if peak is None:
                continue
            if abs(float(peak.energy) - float(anchor.peak.energy)) <= 0.7:
                continue
            mismatch = abs((float(peak.energy) - float(anchor.peak.energy)) - relative)
            if mismatch > tolerance:
                continue

            recovered = _candidate_assignment(
                peak=peak, element=element, line=line, expected=target,
                reason=("Accepted by family-consistency layer: weaker measured spin-orbit "
                        "partner at the tabulated separation from the stronger component"),
                photon_energy=photon_energy, support=0.90,
            )
            result = _upsert_assignment_at_peak(result, recovered, tolerance_eV=0.8)

    return result

def _statistical_component_weight(line: str) -> float:
    """Return the 2j+1 statistical weight for a resolved j component."""
    match = re.search(r"([1357])/2$", str(line))
    if not match:
        return 1.0
    return float(int(match.group(1)) + 1)


def _weak_to_strong_cross_section_ratio(
    element: str, family: str, offsets: dict[str, float], photon_energy: float | None
) -> float:
    """Estimate how visible the strongest missing sibling should be.

    Cross sections are preferred when available.  Statistical weights provide a
    stable fallback (p: 1/2, d: 2/3, f: 3/4 for weak/strong).  The result is
    used only as a soft missing-partner penalty; it never creates a peak.
    """
    lines = set(offsets)
    strongest = strongest_component_line(element, lines, photon_energy)
    if strongest is None:
        return 1.0
    strong_sigma = cross_section_at(element, strongest, photon_energy) if photon_energy is not None else None
    ratios: list[float] = []
    for line in lines:
        if line == strongest:
            continue
        sigma = cross_section_at(element, line, photon_energy) if photon_energy is not None else None
        if strong_sigma is not None and strong_sigma > 0 and sigma is not None and sigma > 0:
            ratios.append(float(sigma) / float(strong_sigma))
        else:
            ratios.append(_statistical_component_weight(line) / _statistical_component_weight(strongest))
    return float(max(ratios)) if ratios else 1.0


def _independent_element_family_count(
    assignments: list[PeakAssignment], element: str, excluded_family: str
) -> int:
    """Count independent accepted PE families supporting an element."""
    families = {
        _base_transition(a.best.line)
        for a in _accepted_pe(assignments)
        if a.best is not None and a.best.element == element
        and _base_transition(a.best.line) != excluded_family
    }
    return len(families)


def _retain_strong_anchor_without_partner(
    assignment: PeakAssignment, assignments: list[PeakAssignment], *,
    family: str, offsets: dict[str, float], photon_energy: float | None,
) -> PeakAssignment | None:
    """Keep a convincing strong j component when only its weaker sibling is absent.

    A missing weak member is negative evidence, not an automatic veto.  The
    strong anchor may survive only when the element is independently established
    elsewhere and the anchor itself is reliable.  Its reliability/support score
    is reduced in proportion to the expected weak/strong cross-section ratio.
    """
    best = assignment.best
    if best is None:
        return None
    strongest = strongest_component_line(best.element, set(offsets), photon_energy)
    if strongest is None or best.line != strongest:
        return None

    independent_families = _independent_element_family_count(assignments, best.element, family)
    # One independent family plus a good anchor is enough; two independent
    # families allow a somewhat weaker anchor to survive.  This prevents a lone
    # reference-guided fluctuation from establishing a resolved family by itself.
    min_reliability = 70 if independent_families == 1 else 60
    if independent_families < 1 or int(best.reliability) < min_reliability:
        return None

    ratio = max(0.0, min(1.25, _weak_to_strong_cross_section_ratio(
        best.element, family, offsets, photon_energy
    )))
    # Missing a nearly equally strong sibling should hurt more than missing a
    # component expected at only half the intensity.  Keep the penalty soft so
    # broad/noisy deep levels do not erase a clean strong component.
    reliability_penalty = int(round(5.0 + 12.0 * min(1.0, ratio)))
    support_penalty = 0.08 + 0.18 * min(1.0, ratio)
    penalized_reliability = max(0, int(best.reliability) - reliability_penalty)
    # A soft penalty must still be able to turn a marginal anchor into a rejection;
    # otherwise low-BE shoulders such as Ir 5p3/2 can survive merely because Ir
    # is strongly established elsewhere.
    strongest_other_prominence = max(
        [float(a.peak.prominence) for a in _accepted_pe(assignments) if a is not assignment] or [1.0]
    )
    relative_prominence = float(assignment.peak.prominence) / max(strongest_other_prominence, 1e-9)
    # A separately resolved weak-family anchor (for example Ir 5p3/2) may be
    # only a percent or less of the dominant 4f signal.  If it is nevertheless
    # a genuine measured local maximum, allow a slightly lower penalized score.
    min_after_penalty = 50 if relative_prominence >= 0.003 else 60
    if penalized_reliability < min_after_penalty:
        return None
    updated = replace(
        best,
        reliability=penalized_reliability,
        reliability_support=max(0.0, float(best.reliability_support) - support_penalty),
        reason=(str(best.reason).rstrip("; ")
                + f"; stronger spin-orbit anchor retained without weaker partner "
                  f"(expected weak/strong cross-section ratio ~{ratio:.2f})"),
    )
    alternatives = [replace(candidate, confident=False) for candidate in assignment.candidates[1:]]
    return PeakAssignment(
        peak=assignment.peak, candidates=[updated] + alternatives,
        rejection_reason="",
    )


def _enforce_resolved_family_separations(
    assignments: list[PeakAssignment], energy_scale: str = "Binding",
    photon_energy: float | None = None,
) -> list[PeakAssignment]:
    """Enforce measured spin-orbit geometry with asymmetric strong-first logic.

    A weaker resolved component still requires the stronger family member.  A
    convincing stronger component, however, may remain identified when its
    weaker partner is not measurable, provided that the element is independently
    established by another PE family.  Missing-partner evidence is then applied
    as a soft cross-section-weighted reliability penalty rather than a veto.
    """
    accepted = _accepted_pe(assignments)
    result: list[PeakAssignment] = []
    for assignment in assignments:
        best = assignment.best
        if best is None or best.kind != "PE" or not re.search(r"[spdf][1357]/2$", best.line):
            result.append(assignment)
            continue
        family = _base_transition(best.line)
        offsets = family_component_offsets(best.element, family)
        if best.line not in offsets or len(offsets) < 2:
            result.append(assignment)
            continue
        own_offset = offsets[best.line]
        partners = [
            a for a in accepted
            if a is not assignment and a.best is not None
            and a.best.element == best.element
            and _base_transition(a.best.line) == family
            and a.best.line in offsets and a.best.line != best.line
        ]
        compatible = False
        for partner in partners:
            expected_delta = component_axis_delta(own_offset, offsets[partner.best.line], energy_scale)
            observed_delta = float(partner.peak.energy) - float(assignment.peak.energy)
            tol = family_pair_tolerance(own_offset, offsets[partner.best.line])
            if abs(observed_delta - expected_delta) <= tol:
                compatible = True
                break
        if compatible:
            result.append(assignment)
            continue

        retained = _retain_strong_anchor_without_partner(
            assignment, accepted, family=family, offsets=offsets, photon_energy=photon_energy,
        )
        if retained is not None:
            result.append(retained)
        else:
            result.append(_reject_but_keep_peak(
                assignment,
                "Resolved spin-orbit assignment rejected because no measured partner has the tabulated separation",
            ))
    return result


def _collapse_duplicate_synthesized_resolved_families(
    assignments: list[PeakAssignment], *, sample_mode: str, energy_scale: str,
    photon_energy: float | None,
) -> list[PeakAssignment]:
    """Keep one coherent measured instance of synthesized resolved families.

    Some solid-state references contain only an unresolved condensed-state
    family while atomic tables provide its j-resolved splitting.  PANDA
    synthesizes the resolved solid-state components from those two sources.
    Recovery passes can otherwise attach the same component labels to a second
    nearby pair of maxima, producing two apparent copies of one family (Yb 5p
    is a real survey-spectrum example).

    Only families explicitly marked as such synthesized references are handled
    here.  Native condensed-state component references and the dedicated
    chemical-state recovery logic are therefore unaffected.
    """
    records = normalized_core_records(sample_mode)
    synthesized_families: dict[tuple[str, str], set[str]] = {}
    for record in records:
        if str(record.get("reference_normalization", "")) != "condensed anchor + atomic splitting":
            continue
        element = str(record.get("element", ""))
        line = str(record.get("transition", record.get("line", ""))).strip()
        family = _base_transition(line)
        if element and line and line != family:
            synthesized_families.setdefault((element, family), set()).add(line)

    result = list(assignments)
    for (element, family), component_lines in synthesized_families.items():
        if len(component_lines) < 2:
            continue
        members = [
            assignment for assignment in result
            if assignment.best is not None and assignment.best.kind == "PE"
            and assignment.best.element == element
            and _base_transition(assignment.best.line) == family
            and assignment.best.line in component_lines
        ]
        counts = {line: sum(1 for a in members if a.best is not None and a.best.line == line) for line in component_lines}
        if not any(count > 1 for count in counts.values()):
            continue

        offsets = family_component_offsets(element, family)
        usable = [line for line in component_lines if line in offsets]
        if len(usable) < 2:
            continue
        anchor_line = strongest_component_line(element, usable, photon_energy) or min(usable, key=lambda line: offsets[line])
        anchors = [a for a in members if a.best is not None and a.best.line == anchor_line]
        if not anchors:
            continue

        best_choice = None
        for anchor in anchors:
            chosen = {anchor_line: anchor}
            total_mismatch = 0.0
            total_strength = float(anchor.peak.prominence)
            total_reliability = float(anchor.best.reliability if anchor.best is not None else 0.0)
            complete = True
            for line in usable:
                if line == anchor_line:
                    continue
                expected_delta = component_axis_delta(offsets[anchor_line], offsets[line], energy_scale)
                candidates = [a for a in members if a.best is not None and a.best.line == line]
                if not candidates:
                    complete = False
                    break
                partner = min(
                    candidates,
                    key=lambda a: (
                        abs((float(a.peak.energy) - float(anchor.peak.energy)) - expected_delta),
                        -float(a.peak.prominence),
                    ),
                )
                mismatch = abs((float(partner.peak.energy) - float(anchor.peak.energy)) - expected_delta)
                tolerance = family_pair_tolerance(offsets[anchor_line], offsets[line])
                if mismatch > max(1.25, tolerance):
                    complete = False
                    break
                chosen[line] = partner
                total_mismatch += mismatch / max(tolerance, 1e-9)
                total_strength += float(partner.peak.prominence)
                total_reliability += float(partner.best.reliability if partner.best is not None else 0.0)
            if not complete or len(chosen) < 2:
                continue
            # Geometry is primary; within similarly coherent pairs prefer the
            # stronger measured family, then the more reliable assignments.
            key = (round(total_mismatch, 3), -total_strength, -total_reliability)
            if best_choice is None or key < best_choice[0]:
                best_choice = (key, set(id(a) for a in chosen.values()))

        if best_choice is None:
            continue
        keep_ids = best_choice[1]
        updated: list[PeakAssignment] = []
        for assignment in result:
            if assignment not in members or id(assignment) in keep_ids:
                updated.append(assignment)
                continue
            best = assignment.best
            if best is None:
                updated.append(assignment)
                continue
            updated.append(PeakAssignment(
                peak=assignment.peak,
                candidates=[],
                rejection_reason=(
                    f"Duplicate synthesized {element} {family} family: a stronger, "
                    "more coherent measured spin-orbit family was retained"
                ),
            ))
        result = updated
    return result


def apply_element_consistency(
    assignments: list[PeakAssignment], payload: Any, *, selected_elements: set[str],
    energy_scale: str, photon_energy: float | None, sample_mode: str,
) -> list[PeakAssignment]:
    """Apply cross-section-aware family consistency to provisional PE labels."""
    # Establish the characteristic transition-metal 2p family before letting
    # crowded shallow 3p/3s lines influence element identity.
    result = _recover_transition_metal_2p(
        assignments, payload, selected_elements=selected_elements,
        energy_scale=energy_scale, photon_energy=photon_energy, sample_mode=sample_mode,
    )
    result = _recover_transition_metal_shallow_families(
        result, payload, selected_elements=selected_elements,
        energy_scale=energy_scale, photon_energy=photon_energy, sample_mode=sample_mode,
    )
    # Same-shell p/s pairing remains useful as independent corroboration after
    # the deep-core hierarchy has been established.
    result = _recover_same_shell_sp_pairs(
        result, payload, selected_elements=selected_elements,
        energy_scale=energy_scale, photon_energy=photon_energy, sample_mode=sample_mode,
    )
    # Complete obvious within-shell family relationships before asking
    # whether an element is established strongly enough for cross-shell
    # recovery.  This makes the result independent of which member happened
    # to survive the first single-line matching pass.
    result = _recover_p_from_s(
        result, payload, energy_scale=energy_scale,
        photon_energy=photon_energy, sample_mode=sample_mode,
    )
    # Once two independent PE families establish an element, search other
    # accessible core shells with a deliberately broad cross-section-informed
    # intensity prior.  This is the generic family pass needed for cases such
    # as Na 2p + Na 2s corroborating an otherwise missed Na 1s line.
    result = _recover_cross_shell_family_members(
        result, payload, selected_elements=selected_elements,
        energy_scale=energy_scale, photon_energy=photon_energy, sample_mode=sample_mode,
    )
    result = _recover_paired_chemical_states(
        result, payload, selected_elements=selected_elements,
        energy_scale=energy_scale, photon_energy=photon_energy, sample_mode=sample_mode,
    )
    result = _lock_dominant_resolved_families(
        result, payload, selected_elements=selected_elements,
        energy_scale=energy_scale, photon_energy=photon_energy, sample_mode=sample_mode,
    )
    result = _recover_resolved_family_partners(
        result, payload, selected_elements=selected_elements,
        energy_scale=energy_scale, photon_energy=photon_energy, sample_mode=sample_mode,
    )
    result = _resolve_same_peak_conflicts(
        result, photon_energy, energy_scale=energy_scale, sample_mode=sample_mode
    )
    result = _enforce_s_requires_p(result)
    result = _enforce_resolved_family_separations(
        result, energy_scale=energy_scale, photon_energy=photon_energy
    )
    result = _enforce_stronger_spin_orbit(result)
    result = _collapse_duplicate_synthesized_resolved_families(
        result, sample_mode=sample_mode, energy_scale=energy_scale, photon_energy=photon_energy
    )
    return sorted(result, key=lambda a: float(a.peak.energy))
