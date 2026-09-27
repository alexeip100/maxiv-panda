from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Any
import re

from .peak_detection import DetectedPeak
from .reference_data import auger_handbook_records, core_level_records
from .core_reference_families import (
    base_line, normalized_core_records, representative_be, resolved_family_keys,
    family_component_offsets, family_pair_tolerance,
)


@dataclass(frozen=True)
class AugerDisplayRegion:
    """Experimentally supported Auger component with uncertain soft tails."""

    peak_energy: float
    tail_lo: float
    core_lo: float
    core_hi: float
    tail_hi: float
    significance: float = 0.0


@dataclass(frozen=True)
class SignalCandidate:
    element: str
    line: str
    kind: str
    expected_energy: float
    delta_e: float
    score: float
    order: int = 1
    environment: str = ""
    region_min: float | None = None
    region_max: float | None = None
    soft_region_min: float | None = None
    soft_region_max: float | None = None
    reference_confidence: str = ""
    confident: bool = False
    reason: str = ""
    reference_category: str = ""
    reliability: int = 0
    reliability_pattern: float = 0.0
    reliability_shift: float = 0.0
    common_shift_eV: float | None = None
    residual_mismatch_eV: float | None = None
    reliability_peak: float = 0.0
    reliability_support: float = 0.0
    reliability_uniqueness: float = 0.0
    reliability_reference: float = 0.0
    auger_subregions: tuple[AugerDisplayRegion, ...] = ()

    @property
    def label(self) -> str:
        suffix = " (2nd)" if self.order == 2 else ""
        if self.kind == "Auger":
            return f"{self.element} {self.line}{suffix}"
        return f"{self.element} {self.line}{suffix}"


@dataclass
class PeakAssignment:
    peak: DetectedPeak
    candidates: list[SignalCandidate] = field(default_factory=list)
    rejection_reason: str = ""

    @property
    def best(self) -> SignalCandidate | None:
        if self.candidates and self.candidates[0].confident:
            return self.candidates[0]
        return None


def _base_line(line: str) -> str:
    return base_line(line)


def _matching_core_records(sample_mode: str) -> list[dict[str, Any]]:
    """Backward-compatible wrapper around family-normalized references."""
    return normalized_core_records(sample_mode)


def _resolved_family_keys(records: list[dict[str, Any]], *, minimum_splitting_eV: float = 1.2) -> set[tuple[str, str]]:
    return resolved_family_keys(records, minimum_splitting_eV=minimum_splitting_eV)


def _representative_be(record: dict[str, Any]) -> float:
    return representative_be(record)


def _stronger_component(line: str) -> bool:
    text = str(line).strip()
    return bool(re.search(r"p3/2$|d5/2$|f7/2$", text))


def _weaker_component(line: str) -> bool:
    text = str(line).strip()
    return bool(re.search(r"p1/2$|d3/2$|f5/2$", text))


def _representative_be(record: dict[str, Any]) -> float:
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
        return float('nan')


def _major_line_bonus(line: str) -> float:
    text = _base_line(line).lower().replace(" ", "")
    preferred = ("1s", "2p", "3d", "4f", "4d", "3p", "2s", "3s")
    for rank, token in enumerate(preferred):
        if token in text:
            return max(0.0, 0.30 - rank * 0.025)
    return 0.0


def _phase_penalty(record: dict[str, Any], sample_mode: str) -> float:
    phase = str(record.get("phase", "")).lower()
    mode = str(sample_mode or "automatic").lower()
    if mode.startswith("gas"):
        return 0.0 if "gas" in phase or "atomic" in phase else 10.0
    if mode.startswith("both"):
        return 0.05
    # Automatic currently favours condensed-state handbook values. Gas/atomic
    # values remain available, but cannot win over an equally good solid match.
    return 10.0 if "gas" in phase or "atomic" in phase else 0.0


def _expected_core_position(be: float, energy_scale: str, photon_energy: float | None, order: int) -> float | None:
    scale = str(energy_scale).lower()
    hv = None if photon_energy is None else float(photon_energy) * order
    if scale.startswith("bind"):
        return float(be)
    if scale.startswith("kin"):
        if hv is None:
            return None
        return hv - float(be)
    return None


def _expected_auger_position(ke: float, energy_scale: str, photon_energy: float | None) -> float | None:
    scale = str(energy_scale).lower()
    if scale.startswith("kin"):
        return float(ke)
    if scale.startswith("bind") and photon_energy is not None:
        return float(photon_energy) - float(ke)
    return None


def _distance_to_reference(observed: float, lo: float, hi: float) -> tuple[float, float]:
    if lo > hi:
        lo, hi = hi, lo
    if lo <= observed <= hi:
        return 0.0, observed
    edge = lo if observed < lo else hi
    return abs(observed - edge), edge


def _weighted_median(values: list[tuple[float, float]]) -> float:
    """Return a robust weighted median for (value, weight) pairs."""
    rows = sorted((float(v), max(float(w), 1e-9)) for v, w in values)
    if not rows:
        return 0.0
    half = 0.5 * sum(weight for _value, weight in rows)
    running = 0.0
    for value, weight in rows:
        running += weight
        if running >= half:
            return value
    return rows[-1][0]


def _shift_plausibility(shift_eV: float) -> float:
    """Soft plausibility penalty for a common PE binding-energy shift.

    Chemical shifts and charging of several eV remain plausible.  The factor is
    1 through 2 eV, 0.7 at 5 eV, 0.3 at 10 eV, and 0 at 15 eV.
    """
    value = abs(float(shift_eV))
    if value <= 2.0:
        return 1.0
    if value <= 5.0:
        return 1.0 - 0.10 * (value - 2.0)
    if value <= 10.0:
        return 0.70 - 0.08 * (value - 5.0)
    if value <= 15.0:
        return 0.30 - 0.06 * (value - 10.0)
    return 0.0


def _charging_component_references(
    element: str, family: str,
) -> dict[str, tuple[float, str, str]]:
    """Return stable absolute references for charging-anchor components.

    Charging inference must use one internally consistent resolved doublet.
    The ordinary matcher intentionally considers compound-state references too,
    but those can move the strong and weak components by different amounts and
    therefore are unsuitable for estimating a *common* charging shift.

    Prefer condensed-state elemental handbook values, then the X-ray booklet,
    and use other resolved rows only as a last resort.  The return mapping is
    ``line -> (binding_energy_eV, reference_category, environment)``.
    """
    priorities = {
        "handbook_elemental": 0,
        "xray_booklet": 1,
        "handbook_compound": 2,
    }
    chosen: dict[str, tuple[int, float, str, str]] = {}
    for record in core_level_records():
        if str(record.get("element", "")) != str(element):
            continue
        line = str(record.get("transition", record.get("line", ""))).strip()
        if _base_line(line) != str(family) or not re.search(r"[spdf][1357]/2$", line):
            continue
        energy = _representative_be(record)
        if energy != energy:
            continue
        category = str(record.get("category", ""))
        priority = priorities.get(category, 3)
        environment = str(record.get("environment", ""))
        current = chosen.get(line)
        if current is None or (priority, float(energy)) < (current[0], current[1]):
            chosen[line] = (priority, float(energy), category, environment)
    return {
        line: (energy, category, environment)
        for line, (_priority, energy, category, environment) in chosen.items()
    }


def _group_core_candidates(
    peak: DetectedPeak, *, energy_scale: str, photon_energy: float | None,
    tolerance_eV: float, selected: set[str], include_second_order: bool,
    sample_mode: str, small_charging_possible: bool = False,
    records: tuple[dict[str, Any], ...] | None = None,
    resolved_families: set[tuple[str, str]] | None = None,
    generic_families: set[tuple[str, str]] | None = None,
) -> list[SignalCandidate]:
    grouped: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    # Matching context is invariant across all measured peaks in one Identify
    # pass.  Older versions rebuilt these sets for every peak, which was a
    # sizeable O(N_peaks * N_reference_rows) cost on survey spectra.
    if records is None:
        records = tuple(
            record for record in _matching_core_records(sample_mode)
            if not selected or str(record.get("element", "")) in selected
        )
    if resolved_families is None:
        resolved_families = _resolved_family_keys(records)
    if generic_families is None:
        generic_families = {
            (str(record.get("element", "")), _base_line(str(record.get("transition", record.get("line", "")))))
            for record in records
            if not re.search(r"[spdf][1357]/2$", str(record.get("transition", record.get("line", ""))).strip())
        }
    for record in records:
        element = str(record.get("element", ""))
        if selected and element not in selected:
            continue
        line = str(record.get("transition", record.get("line", ""))).strip()
        family_key = (element, _base_line(line))
        if re.search(r"[spdf][1357]/2$", line) and family_key in generic_families and family_key not in resolved_families:
            # The splitting is too small for a survey spectrum: label the
            # unresolved family (for example Al 2p), not an arbitrary j branch.
            continue
        if family_key in resolved_families and not re.search(r"[spdf][1357]/2$", line):
            # Prefer explicit spin-orbit components over a generic family
            # record whenever the database provides both.
            continue
        try:
            lo = float(record.get("energy_min_eV", record.get("binding_energy_eV")))
            hi = float(record.get("energy_max_eV", record.get("binding_energy_eV")))
        except Exception:
            continue
        for order in (1, 2) if include_second_order else (1,):
            elo = _expected_core_position(lo, energy_scale, photon_energy, order)
            ehi = _expected_core_position(hi, energy_scale, photon_energy, order)
            if elo is None or ehi is None:
                continue
            if photon_energy is not None and min(lo, hi) >= float(photon_energy) * order:
                continue
            distance, nearest = _distance_to_reference(peak.energy, min(elo, ehi), max(elo, ehi))
            rep_be = _representative_be(record)
            rep_expected = _expected_core_position(rep_be, energy_scale, photon_energy, order) if rep_be == rep_be else None
            # Shallow core levels (n >= 3) can move several eV between an
            # elemental reference and a compound.  Keep them as provisional
            # candidates over a wider window; they are accepted later only
            # when an unambiguous anchor line of the same element is present.
            shell_match = re.match(r"(\d+)", line)
            shell_n = int(shell_match.group(1)) if shell_match else 0
            provisional_window = 8.0 if shell_n >= 3 else 6.0
            if small_charging_possible and str(energy_scale).lower().startswith("bind") and peak.energy >= min(elo, ehi):
                provisional_window = max(provisional_window, 10.0)
            if distance <= max(tolerance_eV, provisional_window):
                enriched = dict(record)
                enriched.update({"_distance": distance, "_nearest": nearest, "_elo": min(elo, ehi), "_ehi": max(elo, ehi), "_rep": rep_expected if rep_expected is not None else nearest})
                grouped.setdefault((element, line, order), []).append(enriched)
    result: list[SignalCandidate] = []
    for (element, line, order), rows in grouped.items():
        best = min(rows, key=lambda r: (float(r["_distance"]) / tolerance_eV + _phase_penalty(r, sample_mode)))
        distance = float(best["_distance"])
        rep_penalty = abs(float(best.get("_rep", best["_nearest"])) - peak.energy) / max(2.0 * tolerance_eV, 1e-9)
        score = distance / tolerance_eV + 0.18 * rep_penalty + _phase_penalty(best, sample_mode) - _major_line_bonus(line)
        envs = sorted({str(r.get("environment", "")) for r in rows if r.get("environment")})
        result.append(SignalCandidate(
            element=element, line=line, kind="PE", expected_energy=float(best.get("_rep", best["_nearest"])),
            delta_e=peak.energy - float(best["_nearest"]), score=score, order=order,
            environment=", ".join(envs[:4]), region_min=min(float(r["_elo"]) for r in rows),
            region_max=max(float(r["_ehi"]) for r in rows),
            reference_category=str(best.get("category", "")),
        ))
    return result


def match_peaks(
    peaks: Iterable[DetectedPeak], *, energy_scale: str, photon_energy: float | None,
    tolerance_eV: float = 2.0, elements: set[str] | None = None,
    include_auger: bool = True, include_second_order: bool = False,
    small_charging_possible: bool = False, alternatives: int = 4, sample_mode: str = "Automatic",
) -> list[PeakAssignment]:
    selected = set(elements or ())
    assignments = [PeakAssignment(peak=peak) for peak in peaks]
    if not assignments:
        return assignments
    tol = max(float(tolerance_eV), 0.05)
    max_prominence = max((max(float(a.peak.prominence), 0.0) for a in assignments), default=0.0)

    # First pass: environment-aware PE candidates grouped by element/transition.
    # Build the immutable reference context once per Identify operation and
    # pre-filter it to the user's selected elements.
    matching_records = tuple(
        record for record in _matching_core_records(sample_mode)
        if not selected or str(record.get("element", "")) in selected
    )
    resolved_families = _resolved_family_keys(matching_records)
    generic_families = {
        (str(record.get("element", "")), _base_line(str(record.get("transition", record.get("line", "")))))
        for record in matching_records
        if not re.search(r"[spdf][1357]/2$", str(record.get("transition", record.get("line", ""))).strip())
    }
    provisional = [
        _group_core_candidates(
            a.peak, energy_scale=energy_scale, photon_energy=photon_energy,
            tolerance_eV=tol, selected=selected, include_second_order=include_second_order,
            sample_mode=sample_mode, small_charging_possible=small_charging_possible,
            records=matching_records, resolved_families=resolved_families,
            generic_families=generic_families,
        )
        for a in assignments
    ]

    # Companion-line evidence: count distinct observed peaks that support each
    # element.  Also establish anchor elements from a close, characteristic
    # core line.  Wider compound shifts of shallow lines are trusted only when
    # such an anchor is present in the same spectrum.
    element_hits: dict[str, int] = {}
    anchor_hits: dict[str, int] = {}
    anchor_lines = {"1s", "2p", "3d", "4d", "4f"}
    for candidates in provisional:
        for element in {c.element for c in candidates}:
            element_hits[element] = element_hits.get(element, 0) + 1
        for c in candidates:
            if _base_line(c.line) in anchor_lines and abs(c.delta_e) <= max(tol, 4.0) and c.score < 5.0:
                anchor_hits[c.element] = anchor_hits.get(c.element, 0) + 1

    rescored_all: list[list[SignalCandidate]] = []
    for candidates in provisional:
        rescored=[]
        for c in candidates:
            companion_bonus=min(0.85, max(0, element_hits.get(c.element,0)-1)*0.14)
            selected_bonus=0.18 if selected and c.element in selected else 0.0
            score = c.score-companion_bonus-selected_bonus
            rescored.append(SignalCandidate(**{**c.__dict__, "score": score}))
        rescored_all.append(rescored)

    # Add Auger references only for elements independently supported by at least
    # two PE structures (or explicitly selected by the user). This prevents an
    # isolated energy coincidence from being labelled as Auger.
    supported={el for el,hits in element_hits.items() if hits>=2}
    if selected:
        supported |= selected
    if include_auger and photon_energy is not None:
        aug_by_family: dict[tuple[str, str], list[float]] = {}
        for record in auger_handbook_records():
            el = str(record.get("element", ""))
            family = str(record.get("family", "Auger")).strip() or "Auger"
            if el not in supported or (selected and el not in selected):
                continue
            try:
                expected = _expected_auger_position(float(record["kinetic_energy_eV"]), energy_scale, photon_energy)
            except Exception:
                continue
            if expected is not None:
                aug_by_family.setdefault((el, family), []).append(float(expected))
        for idx, a in enumerate(assignments):
            for (el, family), positions in aug_by_family.items():
                # The tabulated positions define a central expectation interval,
                # not a sharp physical boundary.  Add data-quality-dependent
                # soft tails that are fixed by reference coverage and never by
                # measured peak prominence.
                family_positions = sorted(set(float(p) for p in positions))
                core_min = min(family_positions)
                core_max = max(family_positions)
                n_ref = len(family_positions)
                if n_ref >= 5:
                    tail = 4.0
                    ref_confidence = "high"
                elif n_ref >= 3:
                    tail = 6.0
                    ref_confidence = "medium"
                else:
                    tail = 10.0
                    ref_confidence = "low"
                soft_min = core_min - tail
                soft_max = core_max + tail
                if not (soft_min <= a.peak.energy <= soft_max):
                    continue
                expected = min(family_positions, key=lambda p: abs(a.peak.energy - p))
                distance_to_core, nearest_core = _distance_to_reference(a.peak.energy, core_min, core_max)
                # Inside the central interval the energy contribution is zero;
                # through the tails it rises smoothly toward the outer limit.
                tail_fraction = min(1.0, distance_to_core / max(tail, 1e-9))
                score = 1.6 * tail_fraction - 0.10
                rescored_all[idx].append(SignalCandidate(
                    element=el, line=family, kind="Auger", expected_energy=nearest_core,
                    delta_e=a.peak.energy-nearest_core, score=score,
                    environment="handbook Auger family expectation",
                    region_min=core_min, region_max=core_max,
                    soft_region_min=soft_min, soft_region_max=soft_max,
                    reference_confidence=ref_confidence,
                    reference_category="auger_" + ref_confidence,
                ))

    # Estimate a robust common PE shift for each element before calculating
    # user-facing reliability.  A coherent chemical/charging shift should not
    # be mistaken for poor elemental identification.  Use only the leading PE
    # candidate at each measured structure and weight stronger peaks more.
    shift_samples: dict[str, list[tuple[float, float]]] = {}
    for assignment, candidates in zip(assignments, rescored_all):
        pe_candidates = [c for c in candidates if c.kind == "PE"]
        if not pe_candidates:
            continue
        candidate = min(pe_candidates, key=lambda c: (c.score, abs(c.delta_e)))
        if abs(candidate.delta_e) > 8.0 or candidate.score > 4.5:
            continue
        weight = max(float(assignment.peak.prominence), 1.0) ** 0.5
        shift_samples.setdefault(candidate.element, []).append((candidate.delta_e, weight))
    common_shifts = {element: _weighted_median(samples) for element, samples in shift_samples.items()}

    # Optional anchor-first charging assistance.  It is deliberately limited
    # to positive binding-energy shifts.  A resolved doublet must be found as a
    # physically consistent pair before any weaker line of that element may use
    # the inferred shift.
    charging_selected: dict[int, SignalCandidate] = {}
    charging_shifts: dict[str, float] = {}
    if small_charging_possible and str(energy_scale).lower().startswith("bind"):
        # Charging assistance is a fallback, never an alternative that may
        # replace a satisfactory unshifted interpretation.  Infer the common
        # shift from a resolved spin-orbit pair using one stable elemental
        # reference doublet.  Do not mix compound-state absolute energies into
        # this estimate: chemical-state rows are useful for ordinary matching,
        # but they need not move both j components rigidly and can mask a real
        # common charging shift.
        families: set[tuple[str, str]] = set()
        for record in core_level_records():
            element = str(record.get("element", ""))
            if selected and element not in selected:
                continue
            line = str(record.get("transition", record.get("line", ""))).strip()
            if re.search(r"[spdf][1357]/2$", line):
                families.add((element, _base_line(line)))

        unshifted_anchor_elements: set[str] = set()
        for element, family in sorted(families):
            refs = _charging_component_references(element, family)
            if len(refs) < 2:
                continue
            strong_line = next((line for line in refs if _stronger_component(line)), None)
            weak_line = next((line for line in refs if _weaker_component(line)), None)
            if strong_line is None or weak_line is None:
                continue
            strong_ref, strong_category, strong_env = refs[strong_line]
            weak_ref, weak_category, weak_env = refs[weak_line]
            expected_split = float(weak_ref) - float(strong_ref)
            if expected_split <= 0:
                continue

            best_pair = None
            for strong_idx, strong_assignment in enumerate(assignments):
                strong_shift = float(strong_assignment.peak.energy) - float(strong_ref)
                if not (0.0 <= strong_shift <= 10.0):
                    continue
                for weak_idx, weak_assignment in enumerate(assignments):
                    if weak_idx == strong_idx:
                        continue
                    weak_shift = float(weak_assignment.peak.energy) - float(weak_ref)
                    if not (0.0 <= weak_shift <= 10.0):
                        continue
                    observed_split = float(weak_assignment.peak.energy) - float(strong_assignment.peak.energy)
                    if observed_split <= 0 or abs(observed_split - expected_split) > 1.2:
                        continue
                    if abs(strong_shift - weak_shift) > 1.5:
                        continue
                    if strong_assignment.peak.prominence < 0.55 * weak_assignment.peak.prominence:
                        continue
                    shift = _weighted_median([
                        (strong_shift, max(strong_assignment.peak.prominence, 1.0)),
                        (weak_shift, max(weak_assignment.peak.prominence, 1.0)),
                    ])
                    split_error = abs(observed_split - expected_split)
                    quality = (
                        strong_assignment.peak.prominence + weak_assignment.peak.prominence
                        - 2.0 * split_error
                        - 0.25 * abs(strong_shift - weak_shift)
                    )
                    row = (quality, strong_idx, weak_idx, shift, strong_shift, weak_shift)
                    if best_pair is None or row[0] > best_pair[0]:
                        best_pair = row
            if best_pair is None:
                continue

            _quality, strong_idx, weak_idx, shift, strong_shift, weak_shift = best_pair
            # A pair already sitting at the stable reference energies is not
            # evidence for charging.  Mark the element as unshifted and do not
            # create fallback candidates for it.
            unshifted_limit = min(max(tol, 1.0), 2.0)
            if abs(strong_shift) <= unshifted_limit and abs(weak_shift) <= unshifted_limit:
                unshifted_anchor_elements.add(element)
                continue

            charging_shifts[element] = float(shift)
            strong_assignment = assignments[strong_idx]
            weak_assignment = assignments[weak_idx]
            charging_selected[strong_idx] = SignalCandidate(
                element=element, line=strong_line, kind="PE", expected_energy=float(strong_ref),
                delta_e=float(strong_shift), score=0.0, order=1,
                environment=strong_env, reference_category=strong_category,
                common_shift_eV=float(shift),
            )
            charging_selected[weak_idx] = SignalCandidate(
                element=element, line=weak_line, kind="PE", expected_energy=float(weak_ref),
                delta_e=float(weak_shift), score=0.0, order=1,
                environment=weak_env, reference_category=weak_category,
                common_shift_eV=float(shift),
            )

        # Once the strongest resolved anchor has established an element shift,
        # weaker lines may support it with a modest non-rigid allowance.
        for idx, (assignment, candidates) in enumerate(zip(assignments, rescored_all)):
            if idx in charging_selected:
                continue
            supported_candidates = [
                candidate for candidate in candidates
                if candidate.kind == "PE" and candidate.order == 1
                and candidate.element in charging_shifts
                and 0.0 <= candidate.delta_e <= 10.0
                and abs(candidate.delta_e - charging_shifts[candidate.element]) <= 3.0
            ]
            if supported_candidates:
                charging_selected[idx] = min(
                    supported_candidates,
                    key=lambda candidate: (abs(candidate.delta_e - charging_shifts[candidate.element]), candidate.score),
                )

        # Charging shifts established from PE anchors also move the corresponding
        # Auger family on a binding-energy axis.  Add a second, broadened Auger
        # search region rather than replacing the normal unshifted candidates.
        # This preserves current behaviour while allowing differential/chemical
        # effects around the PE-derived shift.
        if include_auger and photon_energy is not None and charging_shifts:
            aug_by_family: dict[tuple[str, str], list[float]] = {}
            for record in auger_handbook_records():
                element = str(record.get("element", ""))
                if element not in charging_shifts or (selected and element not in selected):
                    continue
                family = str(record.get("family", "Auger")).strip() or "Auger"
                try:
                    position = _expected_auger_position(
                        float(record["kinetic_energy_eV"]), energy_scale, photon_energy
                    )
                except Exception:
                    continue
                if position is not None:
                    aug_by_family.setdefault((element, family), []).append(float(position))

            for idx, assignment in enumerate(assignments):
                for (element, family), positions in aug_by_family.items():
                    shift = float(charging_shifts[element])
                    shifted_positions = sorted(set(float(value) + shift for value in positions))
                    core_min = min(shifted_positions)
                    core_max = max(shifted_positions)
                    n_ref = len(shifted_positions)
                    if n_ref >= 5:
                        base_tail = 4.0
                        ref_confidence = "high"
                    elif n_ref >= 3:
                        base_tail = 6.0
                        ref_confidence = "medium"
                    else:
                        base_tail = 10.0
                        ref_confidence = "low"
                    tail = base_tail + 4.0
                    soft_min = core_min - tail
                    soft_max = core_max + tail
                    if not (soft_min <= assignment.peak.energy <= soft_max):
                        continue
                    distance_to_core, nearest_core = _distance_to_reference(
                        assignment.peak.energy, core_min, core_max
                    )
                    tail_fraction = min(1.0, distance_to_core / max(tail, 1e-9))
                    score = 1.6 * tail_fraction - 0.14
                    rescored_all[idx].append(SignalCandidate(
                        element=element,
                        line=family,
                        kind="Auger",
                        expected_energy=nearest_core,
                        delta_e=assignment.peak.energy - nearest_core,
                        score=score,
                        environment="charging-shifted and broadened handbook Auger family expectation",
                        region_min=core_min,
                        region_max=core_max,
                        soft_region_min=soft_min,
                        soft_region_max=soft_max,
                        reference_confidence=ref_confidence,
                        reference_category="auger_" + ref_confidence,
                        common_shift_eV=shift,
                    ))

    # Conservative acceptance. A label is shown only when the best candidate is
    # sufficiently close and either clearly separated from alternatives or
    # strongly supported by companion lines. Auger additionally requires the
    # independently established element support above.
    for assignment_index, (assignment,candidates) in enumerate(zip(assignments,rescored_all)):
        ordered=sorted(candidates,key=lambda c:(c.score,abs(c.delta_e),c.element,c.line))
        if not ordered:
            assignment.rejection_reason="No reference match within tolerance"
            continue
        charging_candidate = charging_selected.get(assignment_index)
        if charging_candidate is not None:
            # Small-charging mode is a fallback.  It must not replace a
            # satisfactory unshifted interpretation with another element merely
            # because that other element has an inferred charging shift that
            # lands slightly closer to the measured peak.  This is especially
            # important for the crowded 3p region of neighbouring transition
            # metals.  Preserve the normal leading PE candidate when it already
            # matches within the ordinary acceptance window; charging may still
            # support the same element or rescue a peak that otherwise has no
            # adequate unshifted assignment.
            normal_best = ordered[0]
            normal_is_satisfactory = (
                normal_best.kind == "PE"
                and normal_best.order == 1
                and (not selected or normal_best.element in selected)
                and abs(normal_best.delta_e) <= max(tol, 4.0)
                and normal_best.score <= 3.2
            )
            if not normal_is_satisfactory or charging_candidate.element == normal_best.element:
                ordered = [charging_candidate] + [c for c in ordered if c is not charging_candidate]
        best=ordered[0]
        competitor=next((c for c in ordered[1:] if (c.element,c.line,c.kind)!=(best.element,best.line,best.kind)),None)
        margin=(competitor.score-best.score) if competitor else 9.0
        strong_companions=element_hits.get(best.element,0)>=3
        base_line = _base_line(best.line)
        shell_match = re.match(r"(\d+)", base_line)
        shell_n = int(shell_match.group(1)) if shell_match else 0
        has_anchor = anchor_hits.get(best.element, 0) >= 1

        # Normal core lines use the requested tolerance plus a small reference
        # allowance.  Shallow (n >= 3) levels may use a wider compound-shift
        # window, but only when a close anchor line and several companions of
        # the same element are independently present.  Deep lines such as 2s
        # do not receive this relaxation, preventing isolated weak matches.
        normal_close = abs(best.delta_e) <= max(tol, 4.0) and best.score <= 3.2
        shallow_supported = (
            best.kind == "PE" and shell_n >= 3 and best.expected_energy >= 15.0
            and abs(best.delta_e) <= 8.0 and has_anchor and strong_companions
            and best.score <= 4.5
        )
        close_enough = normal_close or shallow_supported
        anchor_line = base_line in anchor_lines
        unique_enough=((selected and best.element in selected) or (not selected and strong_companions and margin>=0.80 and anchor_line and abs(best.delta_e)<=0.75))
        confident=close_enough and unique_enough
        charging_supported = charging_candidate is not None and best.element in charging_shifts
        if charging_supported:
            confident = bool(selected and best.element in selected)

        if best.kind=="Auger":
            # Auger references represent broad families/regions.  Permit the
            # full family tolerance when the element has a close PE anchor and
            # companion evidence; otherwise leave the structure unidentified.
            in_soft_region = (
                best.soft_region_min is not None and best.soft_region_max is not None
                and best.soft_region_min <= assignment.peak.energy <= best.soft_region_max
            )
            confident = (
                best.element in supported and has_anchor and strong_companions
                and in_soft_region and best.score <= 1.55
            )
        if confident and charging_supported:
            reason = f"Accepted using small-charging mode; element anchor shift {charging_shifts[best.element]:+.2f} eV"
        elif confident and best.kind == "Auger" and best.common_shift_eV is not None:
            reason = (
                f"Accepted: Auger family shifted by PE anchor {best.common_shift_eV:+.2f} eV "
                "with broadened charging allowance"
            )
        else:
            reason="Accepted: close reference match with companion/uniqueness support" if confident else "Rejected as ambiguous or insufficiently supported"

        # User-facing reliability is deliberately independent of the legacy
        # ranking score.  For PE lines, energy evidence is split into (1)
        # consistency with a robust common element shift and (2) a much weaker
        # plausibility penalty for the magnitude of that common shift.
        element_sample_count = len(shift_samples.get(best.element, []))
        common_shift = (charging_shifts.get(best.element, common_shifts.get(best.element)) if best.kind == "PE" else None)
        if best.kind == "PE" and common_shift is not None and element_sample_count >= 2:
            residual_mismatch = abs(float(best.delta_e) - float(common_shift))
            pattern_factor = max(0.0, min(1.0, 1.0 - residual_mismatch / max(tol, 1e-9)))
            shift_factor = _shift_plausibility(common_shift)
        elif best.kind == "PE":
            # A single line cannot establish a common chemical-shift pattern,
            # but a close absolute match is still strong evidence. This matters
            # especially for light elements such as C, N and O, for which 1s is
            # normally the only non-valence core line available in a survey.
            residual_mismatch = None
            pattern_factor = max(0.0, min(1.0, 1.0 - abs(float(best.delta_e)) / max(tol, 1e-9)))
            shift_factor = _shift_plausibility(best.delta_e)
            common_shift = None
        else:
            # Broad Auger families do not necessarily follow PE chemical shifts
            # one-to-one.  Use their position within the expectation region for
            # pattern evidence and a neutral shift-plausibility contribution.
            common_shift = best.common_shift_eV
            residual_mismatch = abs(float(best.delta_e))
            width = max(
                tol,
                0.5 * abs(float(best.soft_region_max or best.expected_energy) - float(best.soft_region_min or best.expected_energy)),
            )
            pattern_factor = max(0.0, min(1.0, 1.0 - residual_mismatch / max(width, 1e-9)))
            shift_factor = 0.75

        prominence_ratio = (max(float(assignment.peak.prominence), 0.0) / max_prominence) if max_prominence > 0 else 0.0
        # Relative-to-maximum prominence alone severely underrates clear light-
        # element peaks on a strongly emitting metal substrate. Blend it with a
        # rank-independent floor once the feature has passed the measured-noise
        # gate and has a close, unique reference match.
        peak_factor = max(0.0, min(1.0, prominence_ratio ** 0.5))
        if best.kind == "PE" and abs(float(best.delta_e)) <= min(1.0, max(tol, 1.0)) and confident:
            peak_factor = max(peak_factor, 0.55)
        support_factor = max(0.0, min(1.0, (element_hits.get(best.element, 0) - 1) / 2.0))
        singleton_light_1s = best.kind == "PE" and best.line == "1s" and best.element in {"B", "C", "N", "O", "F", "Ne"}
        if singleton_light_1s and best.element in selected and confident:
            # Do not penalize an assignment for missing companion core lines
            # when none are physically available outside the protected valence
            # region. The measured 1s maximum itself is the element anchor.
            support_factor = max(support_factor, 0.75)
        uniqueness_factor = 1.0 if competitor is None else max(0.0, min(1.0, margin / 1.5))
        category = str(best.reference_category or "").lower()
        if category in {"handbook_elemental", "auger_high"}:
            reference_factor = 1.0
        elif category in {"handbook_compound", "auger_medium"}:
            reference_factor = 0.90
        elif category in {"xray_booklet", "auger_low"}:
            reference_factor = 0.80
        else:
            reference_factor = 0.75
        reliability_value = round(100.0 * (
            0.25 * pattern_factor
            + 0.25 * peak_factor
            + 0.20 * support_factor
            + 0.15 * uniqueness_factor
            + 0.10 * shift_factor
            + 0.05 * reference_factor
        ))
        reliability_value = int(max(0, min(100, reliability_value)))
        best=SignalCandidate(**{
            **best.__dict__, "confident": confident, "reason": reason,
            "reliability": reliability_value,
            "reliability_pattern": pattern_factor,
            "reliability_shift": shift_factor,
            "common_shift_eV": common_shift,
            "residual_mismatch_eV": residual_mismatch,
            "reliability_peak": peak_factor,
            "reliability_support": support_factor,
            "reliability_uniqueness": uniqueness_factor,
            "reliability_reference": reference_factor,
        })
        assignment.candidates=[best]+ordered[1:max(1,alternatives)]
        if not confident:
            assignment.rejection_reason=reason

    # Never retain a weaker resolved spin-orbit component by itself.  This
    # prevents physically impossible labels such as a strong Ti 2p1/2 with no
    # detectable Ti 2p3/2.
    accepted_keys = {(a.best.element, _base_line(a.best.line), a.best.line) for a in assignments if a.best is not None and a.best.kind == "PE"}
    for assignment in assignments:
        best = assignment.best
        if best is None or best.kind != "PE" or not _weaker_component(best.line):
            continue
        family = _base_line(best.line)
        stronger_present = any(
            element == best.element and base == family and _stronger_component(line)
            for element, base, line in accepted_keys
        )
        if not stronger_present:
            assignment.candidates = []
            assignment.rejection_reason = "Weaker spin-orbit component rejected because the stronger partner is absent"

    # A discrete PE transition may be assigned only once.  Wider provisional
    # windows are useful for compound-shifted shallow levels, but without this
    # final de-duplication two nearby structures could both acquire the same
    # label.  Auger families are exempt because a broad family may contain
    # several resolved maxima and is drawn as one combined region.
    accepted_by_transition: dict[tuple[str, str, int], list[PeakAssignment]] = {}
    for assignment in assignments:
        best = assignment.best
        if best is not None and best.kind == "PE":
            accepted_by_transition.setdefault((best.element, best.line, best.order), []).append(assignment)
    def _duplicate_family_pair_mismatch(assignment: PeakAssignment) -> float | None:
        """Return the best normalized spin-orbit mismatch supporting one duplicate.

        A duplicate transition must not be chosen only because it is closest to
        one absolute reference energy.  In charged/chemically shifted spectra a
        stronger observed peak can be the correct member of a doublet even when
        a weak shoulder lies nearer the unshifted database position.  Relative
        spin-orbit geometry is much more stable, so use any plausible sibling
        candidate as independent support before considering absolute BE error.
        """
        best = assignment.best
        if best is None or best.kind != "PE" or not re.search(r"[spdf][1357]/2$", best.line):
            return None
        family = _base_line(best.line)
        offsets = family_component_offsets(best.element, family)
        if best.line not in offsets or len(offsets) < 2:
            return None
        own_offset = offsets[best.line]
        best_norm: float | None = None
        for other in assignments:
            if other is assignment:
                continue
            for candidate in other.candidates:
                if candidate.kind != "PE" or candidate.element != best.element:
                    continue
                if _base_line(candidate.line) != family or candidate.line == best.line or candidate.line not in offsets:
                    continue
                expected_delta = offsets[candidate.line] - own_offset
                observed_delta = float(other.peak.energy) - float(assignment.peak.energy)
                tol_pair = family_pair_tolerance(own_offset, offsets[candidate.line])
                norm = abs(observed_delta - expected_delta) / max(tol_pair, 1e-9)
                if best_norm is None or norm < best_norm:
                    best_norm = norm
        return best_norm

    for group in accepted_by_transition.values():
        if len(group) <= 1:
            continue

        # Transition-metal 2p3/2 envelopes can contain several real measured
        # maxima (metal, oxide/multiplet shoulders, etc.).  Do not collapse
        # competing strong-component anchors here using only absolute reference
        # proximity.  The element-consistency layer has access to the full
        # measured spectrum and can test each anchor against the expected 2p1/2
        # partner before choosing the physically coherent family.
        first_best = group[0].best
        if (
            first_best is not None
            and first_best.element in {"Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu"}
            and first_best.line == "2p3/2"
        ):
            continue

        pair_mismatch = {id(a): _duplicate_family_pair_mismatch(a) for a in group}
        coherent = [a for a in group if pair_mismatch[id(a)] is not None and pair_mismatch[id(a)] <= 1.0]
        if coherent:
            # First preserve the candidate that participates in the best
            # tabulated spin-orbit pair.  Prominence breaks near-ties.  This is
            # deliberately insensitive to a common charging shift.
            keep = min(
                coherent,
                key=lambda a: (
                    pair_mismatch[id(a)],
                    -float(a.peak.prominence),
                    a.best.score if a.best is not None else float("inf"),
                ),
            )
        elif small_charging_possible and str(energy_scale).lower().startswith("bind"):
            # With charging enabled, absolute BE proximity is only secondary.
            # Among plausible instances of the same transition, prefer the
            # stronger measured structure; a weak accidental shoulder must not
            # suppress a prominent shifted line merely because it sits nearer
            # the unshifted handbook value.
            keep = min(
                group,
                key=lambda a: (
                    -float(a.peak.prominence),
                    a.best.score if a.best is not None else float("inf"),
                    abs(a.best.delta_e) if a.best is not None else float("inf"),
                ),
            )
        else:
            keep = min(
                group,
                key=lambda a: (
                    0 if (a.best is not None and "small-charging mode" in str(a.best.reason)) else 1,
                    abs((a.best.delta_e if a.best is not None else 0.0) - charging_shifts.get(a.best.element if a.best is not None else "", 0.0))
                    if (a.best is not None and a.best.element in charging_shifts) else abs(a.best.delta_e) if a.best is not None else float("inf"),
                    a.best.score if a.best is not None else float("inf"),
                    -a.peak.prominence,
                ),
            )
        for assignment in group:
            if assignment is keep:
                continue
            assignment.candidates = []
            assignment.rejection_reason = "Duplicate transition: a better-supported measured peak was retained"

    # Reference-guided searches for overlapping transitions can converge on the
    # same measured maximum.  Keep only the physically better-supported label
    # at one observed peak.  This prevents, for example, Ir 5p1/2 from being
    # drawn on top of the Ir 4f5/2 component when both references overlap.
    accepted = [a for a in assignments if a.best is not None and a.best.kind == "PE"]
    accepted.sort(key=lambda a: float(a.peak.energy))
    clusters: list[list[PeakAssignment]] = []
    for assignment in accepted:
        if not clusters or abs(float(assignment.peak.energy) - float(clusters[-1][-1].peak.energy)) > 0.6:
            clusters.append([assignment])
        else:
            clusters[-1].append(assignment)
    for cluster in clusters:
        if len(cluster) <= 1:
            continue
        keep = min(
            cluster,
            key=lambda a: (
                a.best.score - _major_line_bonus(a.best.line) if a.best is not None else float("inf"),
                abs(a.best.delta_e) if a.best is not None else float("inf"),
                -a.peak.prominence,
            ),
        )
        for assignment in cluster:
            if assignment is keep:
                continue
            assignment.candidates = []
            assignment.rejection_reason = "Overlapping reference: a better-supported assignment at the same peak was retained"
    return assignments
