from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

import numpy as np
from scipy.integrate import trapezoid
from scipy.ndimage import gaussian_filter1d, percentile_filter
from scipy.signal import find_peaks

from .matcher import AugerDisplayRegion, PeakAssignment, SignalCandidate
from .peak_detection import DetectedPeak
from .reference_data import auger_eadl_records, auger_handbook_records, core_level_records


def _expected_auger_position(ke: float, energy_scale: str, photon_energy: float | None) -> float | None:
    scale = str(energy_scale).lower()
    if scale.startswith("kin"):
        return float(ke)
    if scale.startswith("bind") and photon_energy is not None:
        return float(photon_energy) - float(ke)
    return None


def _record_interval(record: dict[str, Any], energy_scale: str, photon_energy: float) -> tuple[float, float, float] | None:
    try:
        center_ke = float(record["kinetic_energy_eV"])
    except Exception:
        return None
    try:
        lo_ke = float(record.get("kinetic_energy_min_eV", center_ke))
        hi_ke = float(record.get("kinetic_energy_max_eV", center_ke))
    except Exception:
        lo_ke = hi_ke = center_ke
    values = [
        _expected_auger_position(value, energy_scale, photon_energy)
        for value in (lo_ke, center_ke, hi_ke)
    ]
    if any(value is None for value in values):
        return None
    lo, center, hi = (float(value) for value in values)
    return min(lo, hi), center, max(lo, hi)


@dataclass(frozen=True)
class _ReferencePoint:
    center: float
    core_lo: float
    core_hi: float
    source: str
    handbook_supported: bool
    probability: float


@dataclass(frozen=True)
class _FamilyPriorIsland:
    element: str
    family: str
    core_lo: float
    core_hi: float
    search_lo: float
    search_hi: float
    reference_centers: tuple[float, ...]
    sources: tuple[str, ...]
    handbook_supported: bool
    summed_probability: float


@dataclass(frozen=True)
class _BroadFeature:
    peak_energy: float
    peak_intensity: float
    prominence: float
    core_lo: float
    core_hi: float
    tail_lo: float
    tail_hi: float
    integrated_excess: float
    significance: float
    broad_scale_ratio: float
    strength: float
    reference_centers: tuple[float, ...]
    sources: tuple[str, ...]
    handbook_supported: bool
    summed_probability: float

    @property
    def width(self) -> float:
        return float(self.tail_hi - self.tail_lo)


def _record_probability(record: dict[str, Any]) -> float:
    for key in ("summed_transition_probability", "summed_probability", "relative_probability"):
        try:
            return max(0.0, float(record.get(key, 0.0) or 0.0))
        except Exception:
            continue
    return 0.0


def _filtered_reference_records(allow_eadl_only_elements: set[str] | None = None) -> list[dict[str, Any]]:
    """Return handbook records plus a conservative EADL complement.

    EADL normally extends families represented by the experimental handbook.
    It may also introduce a family for an element that is already established
    by at least two confident PE lines.  Such EADL-only families still require
    a broad measured envelope and receive lower reference confidence.
    """
    allow_eadl_only_elements = set(allow_eadl_only_elements or ())
    handbook_records = list(auger_handbook_records())
    handbook_families = {
        (str(record.get("element", "")), str(record.get("family", "Auger")).strip() or "Auger")
        for record in handbook_records
    }
    raw_eadl_records = [
        record for record in auger_eadl_records()
        if (str(record.get("element", "")), str(record.get("family", "Auger")).strip() or "Auger")
        in handbook_families or str(record.get("element", "")) in allow_eadl_only_elements
    ]
    family_probability_max: dict[tuple[str, str], float] = {}
    for record in raw_eadl_records:
        key = (str(record.get("element", "")), str(record.get("family", "Auger")).strip() or "Auger")
        family_probability_max[key] = max(family_probability_max.get(key, 0.0), _record_probability(record))

    eadl_records: list[dict[str, Any]] = []
    for record in raw_eadl_records:
        key = (str(record.get("element", "")), str(record.get("family", "Auger")).strip() or "Auger")
        probability = _record_probability(record)
        maximum = family_probability_max.get(key, 0.0)
        handbook_supported = key in handbook_families
        transition_count = int(record.get("transition_count", 0) or 0)
        strong_enough = maximum <= 0.0 or probability >= 0.30 * maximum
        sufficiently_clustered = handbook_supported or transition_count >= 3
        if strong_enough and sufficiently_clustered:
            eadl_records.append(record)
    return handbook_records + eadl_records


def _family_margin(family: str, core_width: float, charging_shift: float) -> float:
    shell = str(family).strip().upper()[:1]
    base = {"K": 20.0, "L": 22.0, "M": 24.0}.get(shell, 22.0)
    base += min(5.0, 0.15 * max(core_width, 0.0))
    if charging_shift != 0.0:
        base += 4.0
    return base


def _initial_shell_accessible(element: str, family: str, photon_energy: float) -> bool:
    """Return whether the photon can create the initial Auger shell hole.

    Auger notation starts with the shell containing the initial vacancy
    (KLL, LMM, MMN, NOO, ...).  Atomic relaxation tables contain transitions
    irrespective of the exciting photon energy, so without this gate a survey
    can display physically impossible families (for example Ir MMN at 700 eV,
    while the shallowest Ir M level is around 2 keV).
    """
    shell = str(family).strip().upper()[:1]
    principal = {"K": "1", "L": "2", "M": "3", "N": "4", "O": "5"}.get(shell)
    if principal is None:
        return True
    energies: list[float] = []
    for record in core_level_records():
        if str(record.get("element", "")) != str(element):
            continue
        transition = str(record.get("transition", ""))
        if not transition.startswith(principal):
            continue
        try:
            value = float(record.get("representative_energy_eV"))
        except Exception:
            continue
        if np.isfinite(value) and value > 0:
            energies.append(value)
    if not energies:
        return True
    # Use the shallowest subshell as the conservative threshold.  A few eV of
    # work-function/solid-state uncertainty should not switch the family on or
    # off, so keep a small allowance rather than a hard equality threshold.
    return float(photon_energy) + 5.0 >= min(energies)


def _localise_eadl_interval(lo: float, center: float, hi: float, source: str) -> tuple[float, float]:
    """Keep theoretical EADL aggregate clusters local around their centroid.

    Some EADL records are single-linkage aggregates whose min/max span more
    than 100 eV.  Those limits are not a continuous experimental Auger band.
    Handbook ranges are retained; very broad EADL aggregates are used as local
    cluster centres with a conservative +/-16 eV core prior.
    """
    if "EADL" not in str(source):
        return float(lo), float(hi)
    width = float(hi) - float(lo)
    if width <= 32.0:
        return float(lo), float(hi)
    half_width = 16.0
    return float(center) - half_width, float(center) + half_width


def _build_family_priors(
    *,
    supported: set[str],
    energy_scale: str,
    photon_energy: float,
    charging_shifts: dict[str, float],
    allow_eadl_only_elements: set[str] | None = None,
) -> dict[tuple[str, str], list[_FamilyPriorIsland]]:
    """Build broad family search priors without predicting measured shapes."""
    grouped: dict[tuple[str, str], list[_ReferencePoint]] = {}
    for record in _filtered_reference_records(allow_eadl_only_elements):
        element = str(record.get("element", ""))
        if element not in supported:
            continue
        family = str(record.get("family", "Auger")).strip() or "Auger"
        if not _initial_shell_accessible(element, family, photon_energy):
            continue
        interval = _record_interval(record, energy_scale, photon_energy)
        if interval is None:
            continue
        lo, center, hi = interval
        source = str(record.get("source", ""))
        lo, hi = _localise_eadl_interval(lo, center, hi, source)
        shift = float(charging_shifts.get(element, 0.0))
        lo += shift
        center += shift
        hi += shift
        grouped.setdefault((element, family), []).append(_ReferencePoint(
            center=float(center),
            core_lo=float(lo),
            core_hi=float(hi),
            source=source,
            handbook_supported="XPS International Handbook" in source,
            probability=_record_probability(record),
        ))

    priors: dict[tuple[str, str], list[_FamilyPriorIsland]] = {}
    # Atomic clusters separated by more than about 32 eV normally represent
    # distinct broad groups in a survey spectrum.  Closer atomic transitions
    # are treated as one plausibility island; their exact solid-state splitting
    # and intensity distribution are deliberately not predicted.
    cluster_gap_eV = 18.0
    for key, points in grouped.items():
        points = sorted(points, key=lambda item: (item.core_lo, item.core_hi, item.center))
        clusters: list[list[_ReferencePoint]] = []
        for point in points:
            if not clusters or point.core_lo > max(item.core_hi for item in clusters[-1]) + cluster_gap_eV:
                clusters.append([point])
            else:
                clusters[-1].append(point)

        element, family = key
        family_islands: list[_FamilyPriorIsland] = []
        for cluster in clusters:
            core_lo = min(item.core_lo for item in cluster)
            core_hi = max(item.core_hi for item in cluster)
            margin = _family_margin(family, core_hi - core_lo, float(charging_shifts.get(element, 0.0)))
            family_islands.append(_FamilyPriorIsland(
                element=element,
                family=family,
                core_lo=float(core_lo),
                core_hi=float(core_hi),
                search_lo=float(core_lo - margin),
                search_hi=float(core_hi + margin),
                reference_centers=tuple(sorted({float(item.center) for item in cluster})),
                sources=tuple(sorted({item.source for item in cluster if item.source})),
                handbook_supported=any(item.handbook_supported for item in cluster),
                summed_probability=float(sum(item.probability for item in cluster)),
            ))
        priors[key] = family_islands
    return priors


def _odd_points(width_eV: float, step_eV: float, minimum: int = 3) -> int:
    points = max(minimum, int(round(float(width_eV) / max(float(step_eV), 1e-9))))
    if points % 2 == 0:
        points += 1
    return points


def _prepare_auger_trace(x: np.ndarray, y: np.ndarray, pe_lines: list[tuple[float, str, str]]) -> np.ndarray:
    """Interpolate PE peaks without turning their residual flanks into Auger bands.

    Broad transition-metal 2p families can genuinely overlap O KLL, so only
    their sharp apex is suppressed.  Ordinary 2p lines such as S 2p are
    treated like other narrow core levels and receive the wider mask.
    """
    y_test = np.asarray(y, dtype=float).copy()
    pe_mask = np.zeros(x.shape, dtype=bool)
    transition_metals = {"Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu"}
    for energy, line, element in pe_lines:
        is_transition_metal_2p = str(line).startswith("2p") and str(element) in transition_metals
        width = 1.25 if is_transition_metal_2p else 3.5
        pe_mask |= np.abs(x - float(energy)) <= width
    keep = ~pe_mask
    if np.any(pe_mask) and np.count_nonzero(keep) >= 7:
        y_test[pe_mask] = np.interp(x[pe_mask], x[keep], y_test[keep])
    return y_test


def _robust_noise(residual: np.ndarray) -> float:
    differences = np.diff(np.asarray(residual, dtype=float))
    differences = differences[np.isfinite(differences)]
    if differences.size == 0:
        return 0.0
    median = float(np.nanmedian(differences))
    return 1.4826 * float(np.nanmedian(np.abs(differences - median))) / np.sqrt(2.0)


def _auger_noise(residual: np.ndarray, fine: np.ndarray) -> float:
    """Estimate point noise without treating real Auger fine structure as noise.

    The raw first-difference estimator is deliberately retained as a guardrail,
    but the main estimate is taken from the high-frequency remainder after a
    light smoothing.  This prevents structured, noisy KLL/LMM envelopes from
    inflating their own rejection threshold.
    """
    raw_noise = _robust_noise(residual)
    high_frequency = np.asarray(residual, dtype=float) - np.asarray(fine, dtype=float)
    high_frequency_noise = _robust_noise(high_frequency)
    if raw_noise <= 0.0:
        return max(0.0, high_frequency_noise)
    if high_frequency_noise <= 0.0:
        return raw_noise
    return max(high_frequency_noise, 0.55 * raw_noise)


def _outward_boundary(trace: np.ndarray, start: int, direction: int, threshold: float, hold_points: int) -> int:
    """Walk from a peak until the trace stays below a support threshold."""
    i = int(start)
    below = 0
    last_supported = i
    while 0 <= i + direction < trace.size:
        i += direction
        if float(trace[i]) >= float(threshold):
            below = 0
            last_supported = i
        else:
            below += 1
            if below >= hold_points:
                break
    return int(last_supported)


def _feature_from_peak(
    *,
    peak_index: int,
    x: np.ndarray,
    y_original: np.ndarray,
    residual: np.ndarray,
    fine: np.ndarray,
    medium: np.ndarray,
    broad: np.ndarray,
    noise: float,
    threshold: float,
    prior: _FamilyPriorIsland,
) -> _BroadFeature | None:
    height = float(medium[peak_index])
    if not np.isfinite(height) or height < threshold:
        return None
    step = max(float(np.nanmedian(np.diff(x))), 1e-9)
    broad_ratio = max(0.0, float(broad[peak_index])) / max(height, 1e-12)
    if broad_ratio < 0.38:
        return None

    # A narrow spectral line can look deceptively broad after the 4--8 eV
    # detection smoothing.  Verify that the lightly smoothed measured excess
    # itself has a substantial width before accepting an Auger envelope.
    fine_height = float(fine[peak_index])
    fine_threshold = min(0.78 * fine_height, max(2.5 * noise, 0.20 * fine_height))
    fine_left = _outward_boundary(fine, peak_index, -1, fine_threshold, max(2, int(round(1.0 / step))))
    fine_right = _outward_boundary(fine, peak_index, +1, fine_threshold, max(2, int(round(1.0 / step))))
    fine_width = float(x[fine_right] - x[fine_left])
    # Fine width protects against isolated PE-like spikes.  A coherent feature
    # that survives the broad scale may still be accepted in a noisy survey,
    # where a high local threshold otherwise reduces the apex to only a few eV.
    if fine_width < 7.0 and broad_ratio < 0.63:
        return None

    core_threshold = min(0.78 * height, max(2.5 * noise, 0.20 * height))
    tail_threshold = min(0.45 * height, max(1.0 * noise, 0.05 * height))
    hold_points = max(3, int(round(1.5 / step)))
    core_left = _outward_boundary(medium, peak_index, -1, core_threshold, hold_points)
    core_right = _outward_boundary(medium, peak_index, +1, core_threshold, hold_points)
    tail_left = _outward_boundary(medium, peak_index, -1, tail_threshold, hold_points)
    tail_right = _outward_boundary(medium, peak_index, +1, tail_threshold, hold_points)

    core_lo, core_hi = float(x[core_left]), float(x[core_right])
    tail_lo, tail_hi = float(x[tail_left]), float(x[tail_right])
    if core_hi - core_lo < 6.0 or tail_hi - tail_lo < 12.0:
        return None

    peak_energy = float(x[peak_index])
    distance = 0.0 if prior.core_lo <= peak_energy <= prior.core_hi else min(
        abs(peak_energy - prior.core_lo), abs(peak_energy - prior.core_hi)
    )
    available_margin = max(prior.core_lo - prior.search_lo, prior.search_hi - prior.core_hi, 1.0)
    if distance > 0.92 * available_margin:
        return None

    local = (x >= tail_lo) & (x <= tail_hi)
    positive = np.clip(residual[local], 0.0, None)
    integrated = float(trapezoid(positive, x[local])) if np.count_nonzero(local) >= 2 else 0.0
    significance = height / max(threshold, 1e-12)
    width_factor = min(1.5, (tail_hi - tail_lo) / 24.0)
    distance_factor = max(0.0, 1.0 - distance / max(available_margin, 1.0))
    strength = float(
        min(3.0, significance)
        + 0.35 * width_factor
        + 0.30 * broad_ratio
        + 0.20 * distance_factor
        + (0.12 if prior.handbook_supported else 0.0)
    )
    return _BroadFeature(
        peak_energy=peak_energy,
        peak_intensity=float(y_original[peak_index]),
        prominence=height,
        core_lo=core_lo,
        core_hi=core_hi,
        tail_lo=tail_lo,
        tail_hi=tail_hi,
        integrated_excess=integrated,
        significance=float(significance),
        broad_scale_ratio=float(broad_ratio),
        strength=strength,
        reference_centers=prior.reference_centers,
        sources=prior.sources,
        handbook_supported=prior.handbook_supported,
        summed_probability=prior.summed_probability,
    )


def _merge_features(features: list[_BroadFeature], x: np.ndarray, medium: np.ndarray) -> list[_BroadFeature]:
    """Merge connected shoulders but retain components separated by real valleys."""
    if not features:
        return []
    features = sorted(features, key=lambda item: item.peak_energy)
    merged: list[_BroadFeature] = [features[0]]
    for feature in features[1:]:
        previous = merged[-1]
        overlap = min(previous.tail_hi, feature.tail_hi) - max(previous.tail_lo, feature.tail_lo)
        between = (x >= min(previous.peak_energy, feature.peak_energy)) & (x <= max(previous.peak_energy, feature.peak_energy))
        valley = float(np.nanmin(medium[between])) if np.any(between) else -np.inf
        shallow_valley = valley >= 0.45 * min(previous.prominence, feature.prominence)
        if overlap >= 0.0 and shallow_valley:
            strongest = previous if previous.strength >= feature.strength else feature
            merged[-1] = _BroadFeature(
                peak_energy=strongest.peak_energy,
                peak_intensity=strongest.peak_intensity,
                prominence=max(previous.prominence, feature.prominence),
                core_lo=min(previous.core_lo, feature.core_lo),
                core_hi=max(previous.core_hi, feature.core_hi),
                tail_lo=min(previous.tail_lo, feature.tail_lo),
                tail_hi=max(previous.tail_hi, feature.tail_hi),
                integrated_excess=previous.integrated_excess + feature.integrated_excess,
                significance=max(previous.significance, feature.significance),
                broad_scale_ratio=max(previous.broad_scale_ratio, feature.broad_scale_ratio),
                strength=max(previous.strength, feature.strength) + 0.10,
                reference_centers=tuple(sorted(set(previous.reference_centers + feature.reference_centers))),
                sources=tuple(sorted(set(previous.sources + feature.sources))),
                handbook_supported=previous.handbook_supported or feature.handbook_supported,
                summed_probability=max(previous.summed_probability, feature.summed_probability),
            )
        else:
            merged.append(feature)
    return merged


def _detect_features_for_prior(
    *,
    prior: _FamilyPriorIsland,
    x: np.ndarray,
    y_original: np.ndarray,
    y_test: np.ndarray,
    global_span: float,
) -> list[_BroadFeature]:
    local = (x >= prior.search_lo) & (x <= prior.search_hi)
    if np.count_nonzero(local) < 17:
        return []
    xl = x[local]
    yl = y_test[local]
    y_raw = y_original[local]
    step = max(float(np.nanmedian(np.diff(xl))), 1e-9)
    search_width = max(float(xl[-1] - xl[0]), step)

    baseline_width = min(70.0, max(42.0, 0.65 * search_width))
    baseline_points = min(_odd_points(baseline_width, step, 9), xl.size if xl.size % 2 == 1 else xl.size - 1)
    baseline_points = max(5, baseline_points)
    baseline = percentile_filter(yl, percentile=20.0, size=baseline_points, mode="nearest")
    baseline = gaussian_filter1d(baseline, sigma=max(1.0, 6.0 / step), mode="nearest")
    residual = yl - baseline

    fine = gaussian_filter1d(residual, sigma=max(1.0, 1.2 / step), mode="nearest")
    medium = gaussian_filter1d(residual, sigma=max(1.0, 4.0 / step), mode="nearest")
    broad = gaussian_filter1d(residual, sigma=max(1.0, 8.0 / step), mode="nearest")
    noise = _auger_noise(residual, fine)
    threshold = max(0.0035 * global_span, 2.5 * noise)

    minimum_distance = max(1, int(round(8.0 / step)))
    minimum_width = max(1, int(round(4.0 / step)))
    peak_indices, _properties = find_peaks(
        medium,
        height=threshold,
        prominence=max(0.70 * threshold, 1e-12),
        distance=minimum_distance,
        width=minimum_width,
    )

    features: list[_BroadFeature] = []
    for index in peak_indices:
        # A feature whose maximum lies almost on a search-window edge is more
        # likely a background slope or a truncated unrelated structure.
        edge_distance = min(float(xl[index] - xl[0]), float(xl[-1] - xl[index]))
        if edge_distance < min(4.0, 0.08 * search_width):
            continue
        feature = _feature_from_peak(
            peak_index=int(index),
            x=xl,
            y_original=y_raw,
            residual=residual,
            fine=fine,
            medium=medium,
            broad=broad,
            noise=noise,
            threshold=threshold,
            prior=prior,
        )
        if feature is not None:
            features.append(feature)
    return _merge_features(features, xl, medium)


def _overlap_fraction(first: _BroadFeature, second: _BroadFeature) -> float:
    overlap = max(0.0, min(first.tail_hi, second.tail_hi) - max(first.tail_lo, second.tail_lo))
    return overlap / max(min(first.width, second.width), 1e-9)


def _element_pe_evidence(assignments: list[PeakAssignment]) -> dict[str, float]:
    """Return a 0..1 survey-level PE evidence score for each identified element.

    The score deliberately uses only *measured, accepted photoelectron* evidence.
    It is not an Auger detector and cannot activate a family by itself.  Its
    purpose is to break otherwise ambiguous competition when two physically
    plausible Auger families try to borrow the same measured broad envelope.
    Strong PE intensity and support by several independent core families both
    increase the score.
    """
    prominences: dict[str, list[float]] = {}
    families: dict[str, set[str]] = {}
    for assignment in assignments:
        best = assignment.best
        if best is None or best.kind != "PE" or not best.confident:
            continue
        element = str(best.element)
        prominence = max(0.0, float(getattr(assignment.peak, "prominence", 0.0) or 0.0))
        if prominence > 0.0:
            prominences.setdefault(element, []).append(prominence)
        # Family-level counting prevents a resolved spin-orbit doublet from
        # counting as two independent proofs of the element.
        line = str(best.line)
        family = re.sub(r"([spdf])[1357]/2$", r"\1", line)
        families.setdefault(element, set()).add(family)

    raw_strength: dict[str, float] = {}
    for element, values in prominences.items():
        # A few strongest PE lines carry most of the abundance information in a
        # survey; limiting the sum avoids crowded shallow multiplets dominating.
        strongest = sorted(values, reverse=True)[:4]
        raw_strength[element] = float(sum(strongest))
    if not raw_strength:
        return {}
    max_strength = max(raw_strength.values()) or 1.0
    max_families = max((len(families.get(element, ())) for element in raw_strength), default=1) or 1
    evidence: dict[str, float] = {}
    for element, strength in raw_strength.items():
        intensity_factor = min(1.0, max(0.0, strength / max_strength)) ** 0.5
        family_factor = min(1.0, len(families.get(element, ())) / max_families)
        evidence[element] = 0.72 * intensity_factor + 0.28 * family_factor
    return evidence


def _suppress_competing_features(
    family_features: dict[tuple[str, str], list[_BroadFeature]],
    *, element_evidence: dict[str, float] | None = None,
) -> dict[tuple[str, str], list[_BroadFeature]]:
    """Prevent different families from borrowing the same measured envelope.

    When two families genuinely compete for the same broad measured feature,
    survey-wide PE evidence is used as a tie-breaker.  This is important for
    weak-overlayer elements whose theoretical Auger region overlaps a dominant
    substrate/overlayer element: a huge envelope should not be assigned first
    to the weak element merely because its reference island happens to fit.
    """
    element_evidence = dict(element_evidence or {})
    entries: list[tuple[tuple[str, str], int, _BroadFeature]] = []
    for key, features in family_features.items():
        for index, feature in enumerate(features):
            entries.append((key, index, feature))
    retained = {(key, index) for key, index, _feature in entries}
    for i, (key, index, feature) in enumerate(entries):
        if (key, index) not in retained:
            continue
        for other_key, other_index, other in entries[i + 1:]:
            if key == other_key or (other_key, other_index) not in retained:
                continue
            # Different physical families may genuinely overlap at one photon
            # energy.  In particular O KLL often lies under transition-metal
            # LMM/2p structure.  Competition suppression is retained for
            # alternative assignments of the same family type, but KLL is not
            # erased merely because an LMM envelope uses the same measured
            # intensity range.
            if {str(key[1]).upper(), str(other_key[1]).upper()} and (
                (str(key[1]).upper().endswith("KLL") and str(other_key[1]).upper().endswith("LMM"))
                or (str(other_key[1]).upper().endswith("KLL") and str(key[1]).upper().endswith("LMM"))
            ):
                continue
            same_peak = abs(feature.peak_energy - other.peak_energy) <= max(7.0, 0.25 * min(feature.width, other.width))
            if not same_peak or _overlap_fraction(feature, other) < 0.45:
                continue
            first_score = (
                feature.strength
                + (0.12 if feature.handbook_supported else 0.0)
                + 0.18 * np.log1p(max(feature.summed_probability, 0.0))
                + 0.85 * float(element_evidence.get(key[0], 0.0))
            )
            second_score = (
                other.strength
                + (0.12 if other.handbook_supported else 0.0)
                + 0.18 * np.log1p(max(other.summed_probability, 0.0))
                + 0.85 * float(element_evidence.get(other_key[0], 0.0))
            )
            if first_score >= second_score:
                retained.discard((other_key, other_index))
            else:
                retained.discard((key, index))
                break
    return {
        key: [feature for index, feature in enumerate(features) if (key, index) in retained]
        for key, features in family_features.items()
    }


def _deduplicate_family_features(features: list[_BroadFeature]) -> list[_BroadFeature]:
    """Remove duplicates caused by overlapping search priors of one family."""
    retained: list[_BroadFeature] = []
    for feature in sorted(features, key=lambda item: item.strength, reverse=True):
        duplicate = any(
            abs(feature.peak_energy - other.peak_energy) <= 6.0
            and _overlap_fraction(feature, other) >= 0.50
            for other in retained
        )
        if not duplicate:
            retained.append(feature)
    return sorted(retained, key=lambda item: item.peak_energy)


def _broad_auger_assignments(
    assignments: list[PeakAssignment],
    payload: Any,
    *,
    energy_scale: str,
    photon_energy: float | None,
    selected_elements: set[str],
    small_charging_possible: bool = False,
) -> list[PeakAssignment]:
    """Return experimentally supported, family-level Auger assignments.

    Reference data define broad plausibility/search areas only.  Final displayed
    subregions are extracted from broad measured excess after accepted narrow PE
    lines are interpolated away.  Each subregion carries a strongly supported
    core and softer, asymmetric tails; the limits are display/support limits,
    not claimed compound-specific Auger boundaries.
    """
    if photon_energy is None:
        return []
    supported = {
        assignment.best.element
        for assignment in assignments
        if assignment.best is not None and assignment.best.kind == "PE"
    }
    supported &= set(selected_elements or supported)
    if not supported:
        return []

    charging_shifts: dict[str, float] = {}
    if small_charging_possible and str(energy_scale).lower().startswith("bind"):
        for assignment in assignments:
            best = assignment.best
            if best is None or best.kind != "PE" or best.common_shift_eV is None:
                continue
            if "small-charging mode" not in str(best.reason):
                continue
            charging_shifts[best.element] = float(best.common_shift_eV)

    try:
        x = np.asarray(payload.x, dtype=float).reshape(-1)
        y = np.asarray(payload.y, dtype=float).reshape(-1)
        finite = np.isfinite(x) & np.isfinite(y)
        x, y = x[finite], y[finite]
    except Exception:
        return []
    if x.size < 17:
        return []
    order = np.argsort(x)
    x, y = x[order], y[order]
    global_span = max(float(np.nanmax(y) - np.nanmin(y)), 1.0)
    pe_lines = [
        (float(assignment.peak.energy), str(assignment.best.line), str(assignment.best.element))
        for assignment in assignments
        if assignment.best is not None and assignment.best.kind == "PE" and assignment.best.confident
    ]
    y_test = _prepare_auger_trace(x, y, pe_lines)

    pe_support_counts: dict[str, int] = {}
    for assignment in assignments:
        best = assignment.best
        if best is None or best.kind != "PE" or not best.confident:
            continue
        pe_support_counts[best.element] = pe_support_counts.get(best.element, 0) + 1
    handbook_elements = {
        str(record.get("element", "")) for record in auger_handbook_records()
    }
    allow_eadl_only_elements = {
        element for element, count in pe_support_counts.items()
        if count >= 2 and element not in handbook_elements
    }

    priors = _build_family_priors(
        supported=supported,
        energy_scale=energy_scale,
        photon_energy=float(photon_energy),
        charging_shifts=charging_shifts,
        allow_eadl_only_elements=allow_eadl_only_elements,
    )
    family_features: dict[tuple[str, str], list[_BroadFeature]] = {}
    for key, islands in priors.items():
        detected: list[_BroadFeature] = []
        for prior in islands:
            # A narrow, isolated Auger reference island that lies directly on
            # top of a confidently identified PE line from another element is
            # not experimentally distinguishable in an ordinary survey.  Do
            # not let residual PE tails or nearby contamination peaks create a
            # second, misleading Auger assignment there.  Broad/multi-centre
            # Auger islands are deliberately retained because genuine Auger
            # envelopes can overlap narrow PE lines (for example Na KLL and
            # S 2s in the present regression spectra).
            narrow_isolated = (
                (prior.core_hi - prior.core_lo) <= 8.0
                and len(prior.reference_centers) <= 2
            )
            if narrow_isolated:
                obscured = any(
                    pe_element != key[0]
                    and min(abs(float(pe_energy) - float(center)) for center in prior.reference_centers) <= 5.0
                    for pe_energy, _pe_line, pe_element in pe_lines
                )
                if obscured:
                    continue
            detected.extend(_detect_features_for_prior(
                prior=prior,
                x=x,
                y_original=y,
                y_test=y_test,
                global_span=global_span,
            ))
        detected = _deduplicate_family_features(detected)
        # EADL-only families have no experimental handbook anchor.  They are
        # already enabled only for elements established by at least two
        # confident PE assignments (see ``allow_eadl_only_elements`` above).
        # Requiring the Auger feature itself to overlap one of those PE lines
        # would wrongly suppress perfectly valid, well separated Auger bands
        # such as S LMM at hnu = 1000 eV (apparent BE about 853 eV).  Keep the
        # additional safeguard that the measured broad-feature maximum must lie
        # close to an EADL atomic cluster; this prevents an arbitrary broad
        # background structure elsewhere in the search island from activating
        # the theoretical family.
        if detected and not any(feature.handbook_supported for feature in detected):
            detected = [
                feature for feature in detected
                if feature.reference_centers
                and min(abs(feature.peak_energy - center) for center in feature.reference_centers) <= 12.0
            ]
        family_features[key] = detected

    family_features = _suppress_competing_features(
        family_features, element_evidence=_element_pe_evidence(assignments)
    )
    result: list[PeakAssignment] = []
    for (element, family), features in sorted(family_features.items()):
        if not features:
            continue
        strongest = max(features, key=lambda item: item.strength)
        reference_centers = sorted({center for feature in features for center in feature.reference_centers})
        if not reference_centers:
            continue
        expected = min(reference_centers, key=lambda value: abs(value - strongest.peak_energy))
        sources = sorted({source for feature in features for source in feature.sources})
        source_tags = []
        if any("XPS International Handbook" in source for source in sources):
            source_tags.append("handbook")
        if any("EADL" in source for source in sources):
            source_tags.append("EADL")
        source_text = "+".join(source_tags) or "reference data"
        handbook_supported = any(feature.handbook_supported for feature in features)
        support_count = sum(
            1 for assignment in assignments
            if assignment.best is not None and assignment.best.kind == "PE" and assignment.best.element == element
        )
        pattern_factor = max(0.0, min(1.0, len(features) / 3.0))
        peak_factor = max(0.0, min(1.0, strongest.significance / 3.0))
        support_factor = max(0.0, min(1.0, support_count / 3.0))
        reference_factor = 1.0 if handbook_supported else 0.72
        reliability = int(max(0, min(100, round(100.0 * (
            0.35 * pattern_factor + 0.30 * peak_factor + 0.20 * support_factor + 0.15 * reference_factor
        )))))
        if not handbook_supported:
            reliability = min(reliability, 70)
        charging_shift = float(charging_shifts.get(element, 0.0))
        n_regions = len(features)
        reason = (
            f"Accepted: {n_regions} experimentally supported broad Auger subregion"
            f"{'s' if n_regions != 1 else ''}; references {source_text}; "
            "soft display tails follow the measured envelope"
        )
        if not handbook_supported:
            reason += "; EADL-only family accepted because the element is supported by multiple PE lines"
        if charging_shift != 0.0:
            reason += f"; shifted by PE anchor {charging_shift:+.2f} eV"

        display_regions = tuple(
            AugerDisplayRegion(
                peak_energy=float(feature.peak_energy),
                tail_lo=float(feature.tail_lo),
                core_lo=float(feature.core_lo),
                core_hi=float(feature.core_hi),
                tail_hi=float(feature.tail_hi),
                significance=float(feature.significance),
            )
            for feature in sorted(features, key=lambda item: item.peak_energy)
        )
        candidate = SignalCandidate(
            element=element,
            line=family,
            kind="Auger",
            expected_energy=float(expected),
            delta_e=float(strongest.peak_energy - expected),
            score=0.0,
            environment=f"measured-envelope Auger family ({source_text})",
            region_min=float(min(feature.core_lo for feature in features)),
            region_max=float(max(feature.core_hi for feature in features)),
            soft_region_min=float(min(feature.tail_lo for feature in features)),
            soft_region_max=float(max(feature.tail_hi for feature in features)),
            reference_confidence=("high" if handbook_supported and n_regions >= 2 else "medium" if handbook_supported else "low"),
            confident=True,
            reason=reason,
            reference_category=("auger_high" if handbook_supported and n_regions >= 2 else "auger_medium" if handbook_supported else "auger_low"),
            reliability=reliability,
            common_shift_eV=(charging_shift if charging_shift != 0.0 else None),
            reliability_pattern=pattern_factor,
            reliability_shift=0.75,
            residual_mismatch_eV=abs(float(strongest.peak_energy - expected)),
            reliability_peak=peak_factor,
            reliability_support=support_factor,
            reliability_uniqueness=1.0,
            reliability_reference=reference_factor,
            auger_subregions=display_regions,
        )
        peak = DetectedPeak(
            index=int(np.argmin(np.abs(x - strongest.peak_energy))),
            energy=float(strongest.peak_energy),
            intensity=float(strongest.peak_intensity),
            prominence=float(strongest.prominence),
        )
        result.append(PeakAssignment(peak=peak, candidates=[candidate]))
    return result
