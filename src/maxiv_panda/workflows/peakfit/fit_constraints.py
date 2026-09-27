from __future__ import annotations

from typing import Optional, Dict, Tuple, Mapping, Any, List

PARAM_LABELS = {"E": "Energy", "H": "Height", "L": "LFWHM", "G": "GFWHM", "A": "Alpha"}


def constraint_label(prefix: str) -> str:
    return PARAM_LABELS.get(prefix, str(prefix))


def constraint_combo_text(prefix: str, peak_index: int) -> str:
    return f"Tied to {constraint_label(prefix)}_{peak_index}"


def build_constraint_options(prefix: str, peak_index: int, n_peaks: int) -> List[str]:
    items = ["Free", "Fixed"]
    for j in range(1, int(n_peaks) + 1):
        if j == int(peak_index):
            continue
        items.append(constraint_combo_text(prefix, j))
    return items


def parse_tie_target(prefix: str, text: str):
    text = str(text or "")
    prefix_text = f"Tied to {constraint_label(prefix)}_"
    if not text.startswith(prefix_text):
        return None
    try:
        return int(text[len(prefix_text):])
    except Exception:
        return None


def tie_kind_for_prefix(prefix: str) -> str:
    return "offset" if prefix == "E" else "factor"


def compute_tie_relation(prefix: str, source_value: float, target_value: float, target_index: int) -> Dict[str, Any]:
    kind = tie_kind_for_prefix(prefix)
    if kind == "offset":
        return {"target": int(target_index), "kind": kind, "value": float(source_value - target_value)}
    src = float(source_value)
    tgt = float(target_value)
    if abs(tgt) < 1e-12:
        if abs(src) < 1e-12:
            return {"target": int(target_index), "kind": kind, "value": 1.0}
        raise ValueError(f"Cannot tie {constraint_label(prefix)} because the target value is zero while the source value is non-zero.")
    return {"target": int(target_index), "kind": kind, "value": float(src / tgt)}


def constraint_tooltip(prefix: str, tie_meta: Optional[dict]) -> str:
    if tie_meta is None:
        return ""
    target = tie_meta.get("target")
    kind = tie_meta.get("kind")
    value = tie_meta.get("value")
    if kind == "offset":
        return f"Keeps a fixed shift relative to {constraint_label(prefix)}_{target} (Δ = {value:.6g})."
    return f"Keeps a fixed factor relative to {constraint_label(prefix)}_{target} (factor = {value:.6g})."


def render_constraint_display(prefix: str, mode: str, tie_meta: Optional[dict], combo_text: str = "") -> str:
    if mode == "Fixed":
        return "Fixed"
    if mode == "Tied":
        target = (tie_meta or {}).get("target")
        if target:
            return constraint_combo_text(prefix, int(target))
        return combo_text or "Tied"
    return "Free"


def resolve_tie_root(prefix: str, peak_index: int, state_map: Mapping[int, Mapping[str, Any]]) -> Tuple[int, List[int]]:
    visited = set()
    current = int(peak_index)
    chain: List[int] = []
    while True:
        if current in visited:
            raise ValueError(f"Circular tie detected for {constraint_label(prefix)}_{peak_index}.")
        visited.add(current)
        node = state_map.get(current)
        if node is None:
            raise ValueError(f"Invalid tie target for {constraint_label(prefix)}_{peak_index}.")
        mode = node.get("mode", "Free")
        if mode != "Tied":
            return current, chain
        target = node.get("target")
        if target is None:
            return current, chain
        chain.append(current)
        current = int(target)
