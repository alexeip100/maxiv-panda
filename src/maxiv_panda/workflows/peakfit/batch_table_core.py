from __future__ import annotations

from typing import Any

import numpy as np

def _fmt_batch_value(self, value: Any) -> str:
    """Compact formatting for values in the batch setup table."""
    if value is None:
        return "—"
    try:
        v = float(value)
        if not np.isfinite(v):
            return "—"
        if abs(v) >= 1e4 or (abs(v) < 1e-3 and v != 0.0):
            return f"{v:.4g}"
        return f"{v:.5g}"
    except Exception:
        text = str(value)
        return text if text else "—"

def _mode_from_anchor_modes(self, modes: list[str]) -> str:
    """Inherit the batch mode from the anchor fit setups.

    The batch table should not infer Fixed merely because anchor values are
    numerically similar.  It should preserve explicit anchor constraints
    when they are consistent; mixed anchor modes fall back to Free and are
    explained in the Notes column.
    """
    clean = [str(m or "Free").strip() for m in modes if str(m or "").strip()]
    if not clean:
        return "Free"
    normalized: list[str] = []
    for mode in clean:
        low = mode.lower()
        if "tied" in low:
            normalized.append("Tied")
        elif low.startswith("fixed"):
            normalized.append("Fixed")
        else:
            normalized.append("Free")
    unique = set(normalized)
    if len(unique) == 1:
        return normalized[0]
    return "Free"

def _presence_pattern(self, present: set[str], fitted_labels: list[str]) -> str:
    """Compact Start/Middle/End presence pattern for a fitted component."""
    ordered = [a for a in self._anchor_labels if a in fitted_labels and a in present]
    return "+".join(ordered) if ordered else "—"

def _presence_note(self, present: set[str], fitted_labels: list[str]) -> str:
    """Human-readable interpretation of where a component appears in the fitted anchors."""
    if not present:
        return "not present"
    if len(present) == len(fitted_labels):
        return "common component"
    if present == {"Start"}:
        return "Start only / likely disappearing"
    if present == {"Middle"}:
        return "Middle only / transient optional component"
    if present == {"End"}:
        return "End only / appearing optional component"
    if "Start" in present and "End" not in present:
        return "disappearing / absent in later anchor(s)"
    if "Start" not in present and ("Middle" in present or "End" in present):
        return "appearing / optional component"
    return "present in " + ", ".join([a for a in fitted_labels if a in present])

def _finite_floats(self, values: list[Any]) -> list[float]:
    out: list[float] = []
    for value in values:
        try:
            fv = float(value)
            if np.isfinite(fv):
                out.append(fv)
        except Exception:
            pass
    return out

def _suggest_peak_bounds(self, prefix: str, numeric_vals: list[float], mins: list[float], maxs: list[float]) -> tuple[Any, Any]:
    """Suggest conservative batch bounds from fitted anchor values.

    The suggestions are deliberately based mainly on the fitted anchor values,
    while still respecting finite user bounds where those bounds are tighter.
    This prevents the batch table from simply inheriting very broad single-fit
    ranges when the anchors already define a much narrower plausible window.
    """
    user_min = max(mins) if mins else None
    user_max = min(maxs) if maxs else None

    if not numeric_vals:
        if prefix == "H":
            return 0.0, 1.0
        if prefix == "A":
            return 0.0, max(maxs) if maxs else 0.2
        if prefix in ("L", "G"):
            return 0.05, max(maxs) if maxs else 1.0
        return (min(mins) if mins else None, max(maxs) if maxs else None)

    lo = min(numeric_vals)
    hi = max(numeric_vals)
    span = hi - lo

    if prefix == "E":
        margin = max(0.10, 0.25 * span)
        suggested_min = lo - margin
        suggested_max = hi + margin
    elif prefix == "H":
        suggested_min = 0.0
        suggested_max = max(hi * 1.5, hi + max(abs(hi - lo), 1e-9))
    elif prefix in ("L", "G"):
        suggested_min = max(0.01, lo * 0.5)
        suggested_max = max(hi * 1.5, hi + 0.05)
    elif prefix == "A":
        suggested_min = 0.0
        suggested_max = max(0.2, hi * 1.5 if hi > 0 else 0.2)
    else:
        margin = max(abs(hi) * 0.2, abs(lo) * 0.2, span * 0.5, 1e-9)
        suggested_min = lo - margin
        suggested_max = hi + margin

    if user_min is not None:
        try:
            suggested_min = max(float(user_min), float(suggested_min))
        except Exception:
            pass
    if user_max is not None:
        try:
            suggested_max = min(float(user_max), float(suggested_max))
        except Exception:
            pass
    # Never return an invalid interval. If user bounds were inconsistent/tighter
    # than the anchor-derived suggestion, fall back to a minimal safe interval.
    try:
        if suggested_min is not None and suggested_max is not None and float(suggested_min) >= float(suggested_max):
            if prefix == "H":
                suggested_min = 0.0
                suggested_max = max(hi * 1.5, 1.0)
            elif prefix == "A":
                suggested_min = 0.0
                suggested_max = max(0.2, hi * 1.5)
            else:
                c = float(np.nanmean(numeric_vals))
                pad = max(abs(c) * 0.01, 0.05)
                suggested_min = c - pad
                suggested_max = c + pad
    except Exception:
        pass
    return suggested_min, suggested_max

def _suggest_peak_mode(self, prefix: str, numeric_vals: list[float], modes: list[str]) -> str:
    """Suggest the first batch mode by inheriting anchor constraints only."""
    return self._mode_from_anchor_modes(modes)

def _anchor_presence_kind(self, present: set[str], fitted_labels: list[str]) -> str:
    """Classify a component presence pattern for suggestions and notes."""
    if not present:
        return "absent"
    if len(present) == len(fitted_labels):
        return "common"
    if present == {"Start"}:
        return "start_only"
    if present == {"Middle"}:
        return "middle_only"
    if present == {"End"}:
        return "end_only"
    if "Start" not in present and ("Middle" in present or "End" in present):
        return "appearing"
    if "Start" in present and "End" not in present:
        return "disappearing"
    return "partial"

def _initial_strategy_for_peak_param(
    self,
    prefix: str,
    present: set[str],
    fitted_labels: list[str],
    numeric_vals: list[float],
    suggested_mode: str,
) -> str:
    """Describe how future per-spectrum initial guesses should be generated.

    This is only metadata for the editable batch table at this stage; actual
    sequence fitting will use it later.
    """
    kind = self._anchor_presence_kind(present, fitted_labels)
    mode = str(suggested_mode or "Free")
    n = len(numeric_vals)
    if prefix == "H":
        if kind == "common" and n >= 2:
            return "interpolate anchor heights"
        if kind in {"appearing", "end_only"}:
            return "ramp up from small nonzero height"
        if kind in {"disappearing", "start_only"}:
            return "ramp down toward zero"
        if kind == "middle_only":
            return "transient triangular height guess"
        return "use available anchor height"
    if prefix == "E":
        if mode == "Fixed":
            return "fixed to initial/template energy"
        if n >= 2:
            return "interpolate anchor energies"
        return "use available anchor energy"
    if prefix in ("L", "G"):
        if mode == "Fixed":
            return "fixed to mean anchor width"
        if n >= 2:
            return "interpolate anchor widths"
        return "use available anchor width"
    if prefix == "A":
        if mode == "Fixed":
            return "fixed to mean anchor alpha"
        if n >= 2:
            return "interpolate anchor alpha"
        return "use available anchor alpha"
    return "use anchor-derived value"

def _initial_strategy_for_background(self, key: str, numeric_vals: list[float], mode: str) -> str:
    if str(mode or "Free") == "Fixed":
        return "fixed to template background value"
    if len(numeric_vals) >= 2:
        return "interpolate anchor background values"
    return "use available background value"

def _mean_if_fixed(self, initial: Any, numeric_vals: list[float], mode: str) -> Any:
    """Use a mean anchor value for parameters suggested as Fixed."""
    if str(mode or "") == "Fixed" and numeric_vals:
        try:
            return float(np.nanmean(numeric_vals))
        except Exception:
            return initial
    return initial

def _component_sort_key(self, label: str, component: dict[str, Any]) -> tuple[float, str]:
    vals = []
    for state in (component.get("anchors") or {}).values():
        try:
            vals.append(float(state.get("E")))
        except Exception:
            pass
    if vals:
        return (float(np.nanmean(vals)), str(label))
    return (1e99, str(label))
