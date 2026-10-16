"""Convert PANDA's exported single-curve fit results into editable fit setups.

A fit-result report and a reusable fit setup have distinct on-disk formats.
This adapter intentionally does not alter either format, and rejects constraints
that cannot be represented faithfully in the setup editor.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

RESULT_FORMAT = "flexpes_pes_single_fit_result"
PARAMETERS = {"Energy": ("E", "Energy"), "Height": ("H", "Height"),
              "LFWHM": ("L", "LFWHM"), "GFWHM": ("G", "GFWHM"),
              "Alpha": ("A", "Alpha")}


def _number(value: Any, where: str) -> float:
    try:
        number = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid fitted value for {where}.") from exc
    if not math.isfinite(number):
        raise ValueError(f"Non-finite fitted value for {where}.")
    return number


def convert_result_to_setup(data: Mapping[str, Any]) -> tuple[dict, dict]:
    if data.get("format") != RESULT_FORMAT:
        raise ValueError("Not a PANDA single-fit result.")
    if type(data.get("format_version")) is not int or data["format_version"] != 1:
        raise ValueError("Unsupported PANDA single-fit result format version.")
    model = data.get("fit_model")
    if not isinstance(model, Mapping):
        raise ValueError("Fit result is missing its fit_model section.")
    raw_peaks = model.get("peaks")
    if not isinstance(raw_peaks, list) or not raw_peaks:
        raise ValueError("Fit result does not contain a list of peaks.")
    states = []
    for expected, peak in enumerate(raw_peaks, start=1):
        if not isinstance(peak, Mapping) or peak.get("index") != expected:
            raise ValueError("Fit-result peak indices must be consecutive, starting at 1.")
        if peak.get("model") != "Voigt/DS-Voigt":
            raise ValueError(f"Unsupported peak model at peak {expected}.")
        params = peak.get("parameters")
        if not isinstance(params, Mapping):
            raise ValueError(f"Missing parameters for peak {expected}.")
        state = {"label": str(peak.get("label") or f"P{expected}")}
        for human, (prefix, title) in PARAMETERS.items():
            param = params.get(human)
            if not isinstance(param, Mapping):
                raise ValueError(f"Missing {human} for peak {expected}.")
            val = _number(param.get("value"), f"peak {expected} {human}")
            mode = str(param.get("mode", "Free"))
            expr = param.get("expr")
            constraint = str(param.get("constraint") or "")
            if mode == "Tied":
                match = re.fullmatch(r"Tied to ([A-Za-z]+)_(\d+)", constraint)
                if not match or match.group(1) != title:
                    raise ValueError(f"Unrecognized tie for peak {expected} {human}: {constraint}")
                target = int(match.group(2))
                if target >= expected or target < 1:
                    raise ValueError(f"Invalid tie target for peak {expected} {human}.")
                # The setup editor expresses equality ties; do not silently
                # discard non-unit factors or offsets from fitted expressions.
                if expr is not None:
                    ref = f"p{target}_{prefix}"
                    normalized = re.sub(r"[\s()]", "", str(expr))
                    if normalized not in (ref, f"1*{ref}", f"1.0*{ref}"):
                        raise ValueError(f"Unsupported fitted tie expression for peak {expected} {human}: {expr}")
                mode_text = constraint
            elif mode in ("Free", "Fixed"):
                if expr:
                    raise ValueError(f"Unsupported expression for peak {expected} {human}: {expr}")
                mode_text = mode
            else:
                raise ValueError(f"Unsupported mode for peak {expected} {human}: {mode}")
            # lmfit expressions have null bounds, which are not usable in the
            # editor. For tied values, preserve the value and provide a safe
            # editable range; the tie itself remains authoritative.
            lo = param.get("min")
            hi = param.get("max")
            if lo is None or hi is None:
                if mode != "Tied":
                    raise ValueError(f"Missing bounds for peak {expected} {human}.")
                lo, hi = (min(0.0, val), max(val, 1.0))
            else:
                lo = _number(lo, f"peak {expected} {human} minimum")
                hi = _number(hi, f"peak {expected} {human} maximum")
            if lo > hi:
                raise ValueError(f"Reversed bounds for peak {expected} {human}.")
            state.update({prefix: val, f"{prefix}_min": lo,
                          f"{prefix}_max": hi, f"{prefix}_mode": mode_text})
        states.append(state)

    bg = model.get("background")
    if not isinstance(bg, Mapping):
        raise ValueError("Fit result is missing its background.")
    bg_type = str(bg.get("type"))
    if bg_type not in ("constant", "linear", "parabolic", "Shirley"):
        raise ValueError(f"Unsupported background: {bg_type}")
    bg_params = bg.get("parameters")
    if not isinstance(bg_params, Mapping):
        raise ValueError("Fit result has invalid background parameters.")
    bg_state = {"bg_type": bg_type, "bg_touched": True}
    for key in ("b0", "b1", "b2"):
        entry = bg_params.get(key)
        if isinstance(entry, Mapping):
            bg_state[key] = _number(entry.get("value"), f"background {key}")
    if bg_type == "Shirley":
        entry = bg_params.get("alpha")
        if not isinstance(entry, Mapping):
            raise ValueError("Shirley background is missing alpha.")
        bg_state["bg_alpha"] = _number(entry.get("value"), "background alpha")
        bg_state["bg_alpha_fixed"] = entry.get("mode") == "Fixed"
    fit_range = model.get("fit_range_eV")
    if fit_range is not None:
        if not isinstance(fit_range, list) or len(fit_range) != 2:
            raise ValueError("Invalid fit range in fit result.")
        fit_range = [_number(value, "fit range") for value in fit_range]
        if fit_range[0] >= fit_range[1]:
            raise ValueError("Invalid fit range order in fit result.")
    source = data.get("source")
    metadata = dict(source) if isinstance(source, Mapping) else {}
    return {"peak_states": states, "so_doublets": [], "bg_state": bg_state,
            "fit_range": fit_range}, metadata
