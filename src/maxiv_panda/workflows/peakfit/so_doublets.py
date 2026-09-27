from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .fit_models import is_kinetic_energy_scale
from .state_models import DoubletState, statistical_ratio


def normalize_state(state: Mapping[str, Any], *, ordinal: int = 1) -> dict[str, Any]:
    """Normalize one SO-doublet through the shared typed state model."""
    return DoubletState.from_mapping(state, ordinal=ordinal).to_mapping()


def derive_state_from_peaks(major_index: int, minor_index: int, peak_states: Sequence[Mapping[str, Any]], *, ordinal: int = 1, orbital: str = "p") -> dict[str, Any]:
    major = dict(peak_states[int(major_index) - 1])
    minor = dict(peak_states[int(minor_index) - 1])
    split = abs(float(minor.get("E", 0.0)) - float(major.get("E", 0.0)))
    hmaj = max(float(major.get("H", 0.0)), 1e-12)
    hmin = max(float(minor.get("H", 0.0)), 1e-12)
    measured_ratio = hmaj / hmin
    # For p/d/f, the orbital selector deliberately supplies the textbook
    # statistical ratio as the initial physical guess.  It is never a hard
    # rule: the doublet editor exposes Free/Fixed plus min/max bounds.  Custom
    # doublets preserve the ratio already suggested by the two selected peaks.
    ratio = statistical_ratio(orbital) if orbital in ("p", "d", "f") else measured_ratio
    if not (ratio > 0.0):
        ratio = max(measured_ratio, 1.0)
    label = str(major.get("label") or f"Doublet #{ordinal}")
    # Newly initialized peaks normally have equal L/G/A.  Preserve genuinely
    # different post-fit values by defaulting those relationships to Independent.
    rel = {}
    for p in ("L", "G", "A"):
        a, b = float(major.get(p, 0.0)), float(minor.get(p, 0.0))
        tol = max(1e-6, 0.01 * max(abs(a), abs(b), 1.0))
        rel[f"{p}_relation"] = "Same" if abs(a - b) <= tol else "Independent"
    return normalize_state({
        "id": ordinal, "major": int(major_index), "minor": int(minor_index), "label": label,
        "orbital": orbital, "split": split,
        "split_min": max(0.0, split * 0.8), "split_max": max(split * 1.2, split + 0.1), "split_mode": "Fixed", "split_tie_target": None,
        "ratio": ratio, "ratio_min": max(0.1, ratio * 0.75), "ratio_max": max(ratio * 1.25, ratio + 0.2), "ratio_mode": "Fixed", "ratio_tie_target": None,
        **rel,
    }, ordinal=ordinal)


def derived_minor_values(state: Mapping[str, Any], major_values: Mapping[str, float], *, energy_scale: str = "") -> dict[str, float]:
    s = normalize_state(state)
    sign = -1.0 if is_kinetic_energy_scale(energy_scale) else 1.0
    out = {
        "E": float(major_values["E"]) + sign * float(s["split"]),
        "H": float(major_values["H"]) / max(float(s["ratio"]), 1e-12),
    }
    for p in ("L", "G", "A"):
        if s[f"{p}_relation"] == "Same":
            out[p] = float(major_values[p])
    return out



def _doublet_label_base(label: str) -> str:
    """Return the logical base name of a PANDA SO-doublet label.

    PANDA numbers physical doublet siblings as ``<base> #N``.  Legacy releases
    used recursive ``(clone)`` / ``(N)`` suffixes; those are stripped too so
    an old saved setup is migrated cleanly the next time its family is cloned.
    """
    import re
    base = str(label or "").strip() or "Doublet"
    while True:
        newer = re.sub(r"\s+#\d+\s*$", "", base).strip()
        legacy = re.sub(r"\s*(?:\(clone\)|\(\d+\))\s*$", "", newer, flags=re.I).strip()
        if legacy == base:
            return base or "Doublet"
        base = legacy or "Doublet"


def renumber_doublet_family(source_label: str, existing_labels: Sequence[str]) -> tuple[list[str], str]:
    """Normalize one SO-doublet family and return the next numbered label.

    Doublet labels are independent of their constituent peak labels.  A named
    family therefore reads ``S 2p #1``, ``S 2p #2``, ...; an unnamed family
    uses ``Doublet #1``, ``Doublet #2``, ....  The first member is numbered
    immediately, not only after cloning.
    """
    import re
    labels = [str(x or "").strip() for x in existing_labels]
    base = _doublet_label_base(source_label)
    family_indices = [i for i, lab in enumerate(labels) if _doublet_label_base(lab) == base]
    used: set[int] = set()
    assigned: dict[int, int] = {}
    for i in family_indices:
        lab = labels[i]
        m = re.search(r"#(\d+)\s*$", lab) or re.search(r"\((\d+)\)\s*$", lab)
        if m:
            n = int(m.group(1))
        elif lab == base:
            n = 1
        else:
            n = 1
            while n in used:
                n += 1
        while n in used:
            n += 1
        used.add(n)
        assigned[i] = n
    for i, n in assigned.items():
        labels[i] = f"{base} #{n}"
    next_n = max(used, default=0) + 1
    return labels, f"{base} #{next_n}"


def next_doublet_label(source_label: str, existing_labels: Sequence[str]) -> str:
    """Return the next SO-doublet label without changing existing labels."""
    _labels, new_label = renumber_doublet_family(source_label, existing_labels)
    return new_label

def resolve_tied_values(states: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Resolve exact doublet-to-doublet ties for live preview and persistence."""
    out = [normalize_state(s, ordinal=i) for i, s in enumerate(states or [], start=1)]
    by_id = {int(s["id"]): s for s in out}

    def resolve_one(state: dict[str, Any], key: str, stack: set[int]) -> float:
        did = int(state["id"]); mode_key = f"{key}_mode"; target_key = f"{key}_tie_target"
        if str(state.get(mode_key)) != "Tied":
            return float(state[key])
        target = state.get(target_key)
        if target is None or int(target) not in by_id or int(target) == did or did in stack:
            state[mode_key] = "Fixed"
            state[target_key] = None
            return float(state[key])
        target_state = by_id[int(target)]
        value = resolve_one(target_state, key, stack | {did})
        state[key] = float(value)
        return float(value)

    for st in out:
        resolve_one(st, "split", set())
        resolve_one(st, "ratio", set())
    return out



def states_for_batch_peaks(start_fit_state: Mapping[str, Any], peak_states: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Carry Start-anchor SO-doublet topology into one generated batch guess.

    Fixed doublet parameters keep the anchor value. Free parameters use the
    generated constituent peaks as their per-spectrum initial guess, clipped to
    the anchor bounds. Exact doublet-to-doublet ties are resolved afterwards.
    """
    raw = list((start_fit_state or {}).get("so_doublets") or [])
    if not raw:
        return []
    peaks = [dict(p or {}) for p in (peak_states or [])]
    out: list[dict[str, Any]] = []
    for ordinal, item in enumerate(raw, start=1):
        st = normalize_state(item, ordinal=ordinal)
        major = int(st.get("major", 0)); minor = int(st.get("minor", 0))
        if major < 1 or minor < 1 or major > len(peaks) or minor > len(peaks) or major == minor:
            continue
        pmaj = peaks[major - 1]; pmin = peaks[minor - 1]
        if str(st.get("split_mode", "Fixed")) == "Free":
            try:
                value = abs(float(pmin["E"]) - float(pmaj["E"]))
                st["split"] = min(max(value, float(st["split_min"])), float(st["split_max"]))
            except Exception:
                pass
        if str(st.get("ratio_mode", "Fixed")) == "Free":
            try:
                hmaj = max(float(pmaj["H"]), 1e-12)
                hmin = max(float(pmin["H"]), 1e-12)
                value = hmaj / hmin
                st["ratio"] = min(max(value, float(st["ratio_min"])), float(st["ratio_max"]))
            except Exception:
                pass
        out.append(st)
    return resolve_tied_values(out)


def anchor_doublets_by_label(fit_state: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Return explicit SO doublets keyed by the user-visible label.

    The label is the batch identity of a doublet. Numerical values are deliberately
    not part of identity because energies/intensities are expected to evolve across
    a series. Duplicate labels inside one anchor are rejected as ambiguous.
    """
    state = dict(fit_state or {})
    peaks = [dict(p or {}) for p in (state.get("peak_states") or [])]
    out: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for ordinal, raw in enumerate(state.get("so_doublets") or [], start=1):
        d = normalize_state(raw, ordinal=ordinal)
        label = str(d.get("label") or f"Doublet #{ordinal}").strip() or f"Doublet #{ordinal}"
        if label in out:
            errors.append(f"Duplicate SO-doublet label '{label}' in one anchor. Doublet labels must be unique for batch matching.")
            continue
        major = int(d.get("major", 0)); minor = int(d.get("minor", 0))
        major_label = str(peaks[major - 1].get("label") or f"P{major}") if 1 <= major <= len(peaks) else f"P{major}"
        minor_label = str(peaks[minor - 1].get("label") or f"P{minor}") if 1 <= minor <= len(peaks) else f"P{minor}"
        out[label] = {
            "state": d,
            "major_label": major_label,
            "minor_label": minor_label,
            "signature": (
                major_label, minor_label,
                str(d.get("L_relation", "Same")),
                str(d.get("G_relation", "Same")),
                str(d.get("A_relation", "Same")),
            ),
        }
    return out, errors


def anchor_topology_signature(fit_state: Mapping[str, Any]) -> tuple[tuple[Any, ...], ...]:
    """Return the labelled structural SO-doublet topology of one fitted anchor."""
    by_label, _errors = anchor_doublets_by_label(fit_state)
    return tuple((label, *info["signature"]) for label, info in sorted(by_label.items()))


def validate_anchor_topologies(anchor_fit_states: Mapping[str, Mapping[str, Any]], ordered_labels: Sequence[str] = ("Start", "Middle", "End")) -> tuple[str, list[str]]:
    """Classify anchors and validate a union-of-labelled-doublets batch model.

    Peak-only batches remain peak-only. If any explicit SO doublet is present, the
    batch is doublet-aware and the union of doublet labels across fitted anchors is
    used. A labelled doublet may be absent from any anchor (appear/disappear). Where
    the same label is present in more than one anchor, its major/minor peak labels
    and Same/Independent L/G/A relations must be identical. Numerical values and
    Free/Fixed/Tied modes may differ between anchors.
    """
    labels = [str(label) for label in ordered_labels if label in anchor_fit_states]
    if not labels:
        return "peak-only", []
    per_anchor: dict[str, dict[str, dict[str, Any]]] = {}
    errors: list[str] = []
    for anchor in labels:
        mapping, anchor_errors = anchor_doublets_by_label(anchor_fit_states[anchor])
        per_anchor[anchor] = mapping
        errors.extend(f"{anchor}: {msg}" for msg in anchor_errors)
    if not any(per_anchor[a] for a in labels):
        return "peak-only", errors

    union_labels = []
    seen = set()
    for anchor in labels:
        for dlabel in per_anchor[anchor]:
            if dlabel not in seen:
                seen.add(dlabel); union_labels.append(dlabel)
    for dlabel in union_labels:
        present = [(anchor, per_anchor[anchor][dlabel]) for anchor in labels if dlabel in per_anchor[anchor]]
        if not present:
            continue
        ref_anchor, ref_info = present[0]
        major_label, minor_label = ref_info["signature"][:2]
        for anchor in labels:
            if dlabel in per_anchor[anchor]:
                continue
            peak_labels = {str(p.get("label") or f"P{i}") for i, p in enumerate((anchor_fit_states[anchor].get("peak_states") or []), start=1)}
            reused = [lab for lab in (major_label, minor_label) if lab in peak_labels]
            if reused:
                errors.append(
                    f"SO doublet '{dlabel}' is absent in {anchor}, but its constituent peak label(s) "
                    f"{', '.join(reused)} are present there as ordinary peaks. Keep a component either absent or represented "
                    "by the same explicit SO-doublet identity across anchors."
                )
        for anchor, info in present[1:]:
            if info["signature"] != ref_info["signature"]:
                errors.append(
                    f"SO doublet '{dlabel}' has inconsistent structure between {ref_anchor} and {anchor}. "
                    "Keep the same major/minor peak labels and Same/Independent LFWHM, GFWHM and Alpha relations "
                    "when the same labelled doublet is present in more than one anchor."
                )
    return "doublet-aware", errors


def remap_after_doublet_delete(states: Sequence[Mapping[str, Any]], deleted_id: int) -> list[dict[str, Any]]:
    """Remove one doublet and keep exact-tie targets valid after renumbering."""
    result: list[dict[str, Any]] = []
    for raw in states or []:
        st = normalize_state(raw, ordinal=len(result) + 1)
        old_id = int(st["id"])
        if old_id == int(deleted_id):
            continue
        for key in ("split", "ratio"):
            tkey = f"{key}_tie_target"; mkey = f"{key}_mode"
            target = st.get(tkey)
            if str(st.get(mkey)) == "Tied" and target is not None:
                target = int(target)
                if target == int(deleted_id):
                    st[mkey] = "Fixed"; st[tkey] = None
                elif target > int(deleted_id):
                    st[tkey] = target - 1
        st["id"] = old_id - 1 if old_id > int(deleted_id) else old_id
        result.append(st)
    return [normalize_state(st, ordinal=i) for i, st in enumerate(result, start=1)]


def clone_doublet_definition(
    source_state: Mapping[str, Any],
    source_major: Mapping[str, Any],
    source_minor: Mapping[str, Any],
    *,
    new_major_index: int,
    new_minor_index: int,
    ordinal: int,
    energy_scale: str = "",
    label: str | None = None,
    height_scale: float = 0.40,
    min_energy_shift: float = 1.0,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], float]:
    """Clone one SO doublet into two new ordinary peak states plus a new relation state.

    The clone is deliberately made visible: it is shifted away from the source
    and reduced in intensity, while all line-shape values, limits, modes, and
    doublet constraint settings are otherwise inherited from the source.
    """
    src = normalize_state(source_state)
    major = deepcopy(dict(source_major))
    minor = deepcopy(dict(source_minor))
    width = max(abs(float(major.get("L", 0.0))), abs(float(major.get("G", 0.0))))
    shift_mag = max(float(min_energy_shift), 1.5 * width)
    shift = -shift_mag if is_kinetic_energy_scale(energy_scale) else shift_mag
    scale = max(float(height_scale), 1e-6)

    def _shift_energy_state(st: dict[str, Any]) -> None:
        for key in ("E", "E_min", "E_max"):
            if key in st:
                st[key] = float(st[key]) + shift

    def _scale_height_state(st: dict[str, Any]) -> None:
        for key in ("H", "H_min", "H_max"):
            if key in st:
                st[key] = max(0.0, float(st[key]) * scale)

    _shift_energy_state(major); _shift_energy_state(minor)
    _scale_height_state(major); _scale_height_state(minor)
    major["label"] = str(major.get("label") or f"P{new_major_index}")
    minor["label"] = str(minor.get("label") or f"P{new_minor_index}")

    clone = deepcopy(src)
    clone["id"] = int(ordinal)
    clone["major"] = int(new_major_index)
    clone["minor"] = int(new_minor_index)
    if label is not None:
        clone["label"] = str(label)
    clone = normalize_state(clone, ordinal=ordinal)
    return clone, major, minor, shift




def visible_color_map(peak_colors, color_custom, states, *, grouped: bool) -> dict[int, str]:
    """Return 1-based peak->display-color mapping with distinct automatic colors.

    Explicit user colors are preserved. Automatic colors are allocated across the
    *visible* components for the selected representation, so grouping SO pairs
    cannot accidentally make a summed doublet and a standalone peak share a
    default color.
    """
    from . import fit_plotting
    colors = list(peak_colors or [])
    custom = list(color_custom or [])
    normalized = [normalize_state(st, ordinal=i) for i, st in enumerate(states or [], start=1)]
    by_member = {}
    for st in normalized:
        by_member[int(st["major"])] = st
        by_member[int(st["minor"])] = st

    entities = []
    emitted = set()
    n = len(colors)
    for idx in range(1, n + 1):
        st = by_member.get(idx) if grouped else None
        if st is None:
            entities.append(((idx,), idx, bool(custom[idx-1]) if idx-1 < len(custom) else False))
            continue
        did = int(st["id"])
        if did in emitted:
            continue
        emitted.add(did)
        major, minor = int(st["major"]), int(st["minor"])
        is_custom = bool(custom[major-1]) if 0 <= major-1 < len(custom) else False
        entities.append(((major, minor), major, is_custom))

    used = set()
    result = {}
    # Reserve explicit colors first.
    for members, source, is_custom in entities:
        if not is_custom:
            continue
        c = str(colors[source-1] if 0 <= source-1 < len(colors) and colors[source-1] else fit_plotting.default_peak_color(source))
        used.add(c.lower())
        for m in members:
            result[m] = c
    # Assign deterministic distinct colors to automatic entities.
    palette_i = 1
    for members, source, is_custom in entities:
        if is_custom:
            continue
        while True:
            c = fit_plotting.default_peak_color(palette_i)
            palette_i += 1
            if c.lower() not in used:
                break
        used.add(c.lower())
        for m in members:
            result[m] = c
    return result

def grouped_component_specs(components, peak_labels, peak_colors, states, *, grouped: bool, color_custom=None):
    """Return display-only component groups for the fitting plot.

    In ordinary mode every fitted peak is returned separately.  In grouped
    mode each SO-doublet pair is replaced by the sum of its major/minor
    component arrays, while standalone peaks remain individual.  This helper
    deliberately changes presentation only; the underlying fit model stays
    peak-based.
    """
    comps = list(components or [])
    labels = list(peak_labels or [])
    colors = list(peak_colors or [])
    cmap = visible_color_map(colors, color_custom, states, grouped=grouped) if color_custom is not None else {i+1: colors[i] for i in range(len(colors))}
    if not grouped:
        return [
            {"component": comp, "label": labels[i] if i < len(labels) else f"Peak {i+1}",
             "color": cmap.get(i + 1, colors[i] if i < len(colors) else None), "members": (i + 1,)}
            for i, comp in enumerate(comps)
        ]

    normalized = [normalize_state(st, ordinal=i) for i, st in enumerate(states or [], start=1)]
    by_member = {}
    for st in normalized:
        by_member[int(st["major"])] = st
        by_member[int(st["minor"])] = st

    emitted = set()
    out = []
    for idx, comp in enumerate(comps, start=1):
        st = by_member.get(idx)
        if st is None:
            out.append({
                "component": comp,
                "label": labels[idx - 1] if idx - 1 < len(labels) else f"Peak {idx}",
                "color": cmap.get(idx, colors[idx - 1] if idx - 1 < len(colors) else None),
                "members": (idx,),
            })
            continue
        did = int(st["id"])
        if did in emitted:
            continue
        emitted.add(did)
        major = int(st["major"]); minor = int(st["minor"])
        if not (1 <= major <= len(comps) and 1 <= minor <= len(comps)):
            # Invalid/incomplete state: fail safe to the current peak rather than
            # hiding data from the user.
            out.append({
                "component": comp,
                "label": labels[idx - 1] if idx - 1 < len(labels) else f"Peak {idx}",
                "color": cmap.get(idx, colors[idx - 1] if idx - 1 < len(colors) else None),
                "members": (idx,),
            })
            continue
        out.append({
            "component": comps[major - 1] + comps[minor - 1],
            "label": str(st.get("label") or f"Doublet #{did}"),
            "color": cmap.get(major, colors[major - 1] if major - 1 < len(colors) else None),
            "members": (major, minor),
        })
    return out

def remap_after_peak_delete(states: Sequence[Mapping[str, Any]], deleted_index: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in states or []:
        s = normalize_state(raw, ordinal=len(out) + 1)
        if deleted_index in (s["major"], s["minor"]):
            continue
        if s["major"] > deleted_index:
            s["major"] -= 1
        if s["minor"] > deleted_index:
            s["minor"] -= 1
        s["id"] = len(out) + 1
        out.append(s)
    return out


def member_indices(states: Sequence[Mapping[str, Any]]) -> set[int]:
    used: set[int] = set()
    for raw in states or []:
        s = normalize_state(raw)
        used.update((int(s["major"]), int(s["minor"])))
    return used
