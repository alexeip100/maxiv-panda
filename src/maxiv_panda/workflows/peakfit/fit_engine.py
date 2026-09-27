from __future__ import annotations

from typing import Optional, Dict, Any, Mapping, Sequence, Callable, Tuple, Set
import warnings
import re

import numpy as np


def collect_bound_hit_params(result, tol: float = 1e-8) -> Set[str]:
    hits: Set[str] = set()
    if result is None:
        return hits
    try:
        for name, par in result.params.items():
            if getattr(par, "expr", None):
                continue
            if not getattr(par, "vary", False):
                continue
            try:
                value = float(par.value)
                pmin = par.min
                pmax = par.max
            except Exception:
                continue
            try:
                if pmin is not None and abs(value - float(pmin)) < tol:
                    hits.add(str(name))
                elif pmax is not None and abs(value - float(pmax)) < tol:
                    hits.add(str(name))
            except Exception:
                pass
    except Exception:
        pass
    return hits


def human_readable_param_name(param_name: str) -> str:
    name = str(param_name or "")
    if name == "bg_alpha":
        return "Shirley α"
    if name in ("b0", "b1", "b2"):
        return name
    m = re.fullmatch(r"p(\d+)_([EHLGA])", name)
    if not m:
        return name
    idx = m.group(1)
    prefix = m.group(2)
    mapping = {"E": "Energy", "H": "Height", "L": "LFWHM", "G": "GFWHM", "A": "Alpha"}
    return f"{mapping.get(prefix, prefix)}_{idx}"




def collect_fit_curve_data(payload_by_key: Mapping[str, Any], checked_key: Optional[str], fit_range: Optional[Tuple[float, float]] = None):
    if checked_key is None:
        return None, "No curve selected for fitting."
    pl = payload_by_key.get(checked_key)
    if pl is None or getattr(pl, "x", None) is None or getattr(pl, "y", None) is None:
        return None, "Selected curve has no data."

    x_raw = np.asarray(pl.x, dtype=float)
    y_raw = np.asarray(pl.y, dtype=float)
    mask = np.isfinite(x_raw) & np.isfinite(y_raw)
    x_raw = x_raw[mask]
    y_raw = y_raw[mask]
    if x_raw.size < 5 or y_raw.size < 5:
        return None, "Selected curve has too few valid data points for fitting."

    if fit_range is not None:
        try:
            lo = float(min(fit_range))
            hi = float(max(fit_range))
        except Exception:
            return None, "Fit range is invalid."
        range_mask = (x_raw >= lo) & (x_raw <= hi)
        x_raw = x_raw[range_mask]
        y_raw = y_raw[range_mask]
        if x_raw.size < 5 or y_raw.size < 5:
            return None, "Selected fit range contains too few data points for fitting."

    order = np.argsort(x_raw)
    x = x_raw[order]
    y = y_raw[order]
    if np.any(np.diff(x) <= 0):
        keep = np.concatenate(([True], np.diff(x) > 0))
        x = x[keep]
        y = y[keep]
    if x.size < 5:
        return None, "Energy axis is degenerate after cleaning."

    dx = np.diff(x)
    dx_med = float(np.median(dx)) if dx.size else 0.0
    if dx_med <= 0:
        return None, "Energy step is invalid."
    rel = float(np.max(np.abs(dx - dx_med)) / dx_med) if dx.size else 0.0
    xu = np.linspace(float(x.min()), float(x.max()), x.size) if rel > 0.01 else x.copy()
    yu = np.interp(xu, x, y) if xu.size != x.size or not np.allclose(xu, x) else y.copy()
    return {
        "payload": pl, "x": x, "y": y, "xu": xu, "yu": yu, "key": checked_key,
        "fit_range": (float(x.min()), float(x.max())) if fit_range is not None else None,
    }, None


def collect_peak_specs(peak_widgets: Sequence[Mapping[str, Any]], param_mode_fn: Callable[[Mapping[str, Any], str], str]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for i, w in enumerate(peak_widgets, start=1):
        spec: dict[str, Any] = {}
        try:
            label_edit = w.get("label_edit")
            label = str(label_edit.text()).strip() if label_edit is not None else ""
        except Exception:
            label = ""
        spec["label"] = label or f"P{i}"
        for prefix in ("E", "H", "L", "G", "A"):
            spec[prefix] = float(w[prefix].value())
            spec[f"{prefix}_min"] = float(w[f"{prefix}_min"].value())
            spec[f"{prefix}_max"] = float(w[f"{prefix}_max"].value())
            spec[f"{prefix}_mode"] = param_mode_fn(w, prefix)
            spec[f"{prefix}_tie"] = w.get(f"{prefix}_tie")
        specs.append(spec)
    return specs


def apply_fit_result_to_widgets(result_values: Mapping[str, float], peak_widgets: Sequence[Mapping[str, Any]], bg_type: str, bg_widgets: Mapping[str, Any]) -> None:
    for i, w in enumerate(peak_widgets, start=1):
        for pkey, widget_key in (("E", "E"), ("H", "H"), ("L", "L"), ("G", "G"), ("A", "A")):
            name = f"p{i}_{pkey}"
            if name in result_values:
                w[widget_key].setValue(float(result_values[name]))
    if "b0" in result_values:
        bg_widgets["b0"].setValue(float(result_values["b0"]))
    if bg_type in ("linear", "parabolic") and "b1" in result_values:
        bg_widgets["b1"].setValue(float(result_values["b1"]))
    if bg_type == "parabolic" and "b2" in result_values:
        bg_widgets["b2"].setValue(float(result_values["b2"]))
    if bg_type == "Shirley" and "bg_alpha" in result_values:
        bg_widgets["bg_alpha"].setValue(float(result_values["bg_alpha"]))


def build_model_from_dialog_state(
    xu,
    peak_widgets: Sequence[Mapping[str, Any]],
    bg_widgets: Mapping[str, Any],
    bg_type: Optional[str] = None,
    values: Optional[Mapping[str, float]] = None,
    measured_y=None,
    energy_scale: str = "",
):
    from . import fit_models

    xu = np.asarray(xu, dtype=float)
    if xu.size == 0:
        return np.asarray([], dtype=float), []

    bg_type = str(bg_type or "constant")
    values = dict(values or {})
    peaks = []
    if values:
        for i in range(1, len(peak_widgets) + 1):
            peaks.append({
                "E": float(values[f"p{i}_E"]),
                "H": float(values[f"p{i}_H"]),
                "L": float(values[f"p{i}_L"]),
                "G": float(values[f"p{i}_G"]),
                "A": float(values[f"p{i}_A"]),
            })
    else:
        for w in peak_widgets:
            peaks.append({
                "E": float(w["E"].value()),
                "H": float(w["H"].value()),
                "L": float(w["L"].value()),
                "G": float(w["G"].value()),
                "A": float(w["A"].value()),
            })

    def _bg_value(name: str, fallback: float = 0.0) -> float:
        widget = bg_widgets.get(name)
        if widget is None:
            return float(fallback)
        return float(widget.value())

    bg_params = {
        "b0": float(values.get("b0", _bg_value("b0", 0.0))),
        "b1": float(values.get("b1", _bg_value("b1", 0.0))),
        "b2": float(values.get("b2", _bg_value("b2", 0.0))),
        "bg_alpha": float(values.get("bg_alpha", _bg_value("bg_alpha", 1.0))),
    }
    return fit_models.build_model_from_values(xu, peaks, bg_type, bg_params, measured_y=measured_y, energy_scale=energy_scale)


def validate_fit_ready(fit_data: Optional[dict], peak_specs: Sequence[Mapping[str, Any]], bg_type: str, shirley_alpha_fixed: bool, doublets: Optional[Sequence[Mapping[str, Any]]] = None) -> Optional[str]:
    if fit_data is None:
        return "No fit curve selected."
    if bg_type not in ("constant", "linear", "parabolic", "Shirley"):
        return "Automated fitting currently supports only constant, linear, parabolic, or Shirley background."
    if not peak_specs:
        return "No peaks are defined."
    from . import so_doublets
    ds = [so_doublets.normalize_state(d, ordinal=i) for i, d in enumerate(doublets or [], start=1)]
    derived = set()
    for d in ds:
        mi = int(d["minor"]); derived.update({(mi, "E"), (mi, "H")})
        for p in ("L", "G", "A"):
            if d.get(f"{p}_relation", "Same") == "Same": derived.add((mi, p))
    free_params = 0
    name_map = {"E": "Energy", "H": "Height", "L": "LFWHM", "G": "GFWHM", "A": "Alpha"}
    for i, spec in enumerate(peak_specs, start=1):
        for prefix in ("E", "H", "L", "G", "A"):
            if (i, prefix) in derived:
                continue
            v = float(spec[prefix])
            vmin = float(spec[f"{prefix}_min"])
            vmax = float(spec[f"{prefix}_max"])
            mode = str(spec[f"{prefix}_mode"])
            if vmin > vmax:
                return f"Peak {i} {name_map[prefix]}: min is larger than max."
            if mode == "Free" and (v < vmin or v > vmax):
                return f"Peak {i} {name_map[prefix]}: initial value is outside its bounds."
            if prefix in ("H", "L", "G") and v <= 0:
                return f"Peak {i} {name_map[prefix]} must be > 0."
            if mode == "Tied":
                tie = spec.get(f"{prefix}_tie")
                if not tie or not tie.get("target"):
                    return f"Peak {i} {name_map[prefix]} has an invalid tie target."
            if mode == "Free":
                free_params += 1
    for d in ds:
        for key in ("split", "ratio"):
            mode = str(d.get(f"{key}_mode", "Fixed"))
            if mode == "Free":
                free_params += 1
            elif mode == "Tied":
                target = d.get(f"{key}_tie_target")
                if target is None or int(target) == int(d["id"]) or not any(int(other["id"]) == int(target) for other in ds):
                    return f"SO doublet {d['id']}: {key} has an invalid tie target."
    free_params += {"constant": 1, "linear": 2, "parabolic": 3}.get(bg_type, 0)
    if bg_type == "Shirley" and not shirley_alpha_fixed:
        free_params += 1
    if free_params <= 0:
        return "No free parameters remain. Nothing can be fitted."
    return None


def build_lmfit_parameters(peak_specs: Sequence[Mapping[str, Any]], bg_type: str, bg_values: Mapping[str, float], fit_data: Optional[dict], doublets: Optional[Sequence[Mapping[str, Any]]] = None, energy_scale: str = ""):
    from lmfit import Parameters
    from . import so_doublets, fit_models
    params = Parameters()
    ds = [so_doublets.normalize_state(d, ordinal=i) for i, d in enumerate(doublets or [], start=1)]
    derived: dict[tuple[int, str], tuple[dict[str, Any], str]] = {}
    for d in ds:
        mi = int(d["minor"])
        derived[(mi, "E")] = (d, "E")
        derived[(mi, "H")] = (d, "H")
        for p in ("L", "G", "A"):
            if str(d.get(f"{p}_relation", "Same")) == "Same":
                derived[(mi, p)] = (d, p)

    tied_specs = []
    for i, spec in enumerate(peak_specs, start=1):
        for prefix in ("E", "H", "L", "G", "A"):
            if (i, prefix) in derived:
                continue
            name = f"p{i}_{prefix}"
            mode = str(spec[f"{prefix}_mode"])
            value = float(spec[prefix])
            if mode == "Free":
                params.add(name, value=value, min=float(spec[f"{prefix}_min"]), max=float(spec[f"{prefix}_max"]), vary=True)
            elif mode == "Fixed":
                params.add(name, value=value, vary=False)
            else:
                tied_specs.append((i, prefix, spec))
    pending = list(tied_specs)
    progress = True
    while pending and progress:
        progress = False
        remaining = []
        for i, prefix, spec in pending:
            tie = spec.get(f"{prefix}_tie") or {}
            try:
                target = int(tie.get("target")); kind = str(tie.get("kind")); rel = float(tie.get("value"))
            except Exception as exc:
                raise ValueError(f"Invalid tie specification for p{i}_{prefix}") from exc
            src_name = f"p{target}_{prefix}"
            if src_name not in params:
                remaining.append((i, prefix, spec)); continue
            name = f"p{i}_{prefix}"
            expr = f"({src_name} + ({rel:.16g}))" if kind == "offset" else f"(({rel:.16g})*{src_name})"
            params.add(name, expr=expr); progress = True
        pending = remaining
    if pending:
        unresolved = ", ".join(f"p{i}_{prefix}" for i, prefix, _ in pending)
        raise ValueError(f"Could not resolve tied parameter source(s): {unresolved}")

    # Add doublet-level physical parameters.  Fixed/Free parameters are added
    # first; exact Tied-to relationships are resolved in a second pass using
    # the same expression mechanism as ordinary tied peak parameters.
    sign = -1.0 if fit_models.is_kinetic_energy_scale(energy_scale) else 1.0
    pending_doublet_ties = []
    for ordinal, d in enumerate(ds, start=1):
        major, minor = int(d["major"]), int(d["minor"])
        if major < 1 or minor < 1 or major > len(peak_specs) or minor > len(peak_specs) or major == minor:
            raise ValueError(f"Invalid peak indices for SO doublet {ordinal}.")
        for key in ("split", "ratio"):
            name = f"d{ordinal}_{key}"
            mode = str(d.get(f"{key}_mode", "Fixed"))
            if mode == "Free":
                params.add(name, value=float(d[key]), min=float(d[f"{key}_min"]), max=float(d[f"{key}_max"]), vary=True)
            elif mode == "Fixed":
                params.add(name, value=float(d[key]), vary=False)
            elif mode == "Tied":
                pending_doublet_ties.append((ordinal, key, d))
            else:
                raise ValueError(f"Invalid {key} mode for SO doublet {ordinal}: {mode}")

    pending = list(pending_doublet_ties)
    progress = True
    while pending and progress:
        progress = False
        remaining = []
        for ordinal, key, d in pending:
            target = d.get(f"{key}_tie_target")
            if target is None or int(target) == int(ordinal):
                raise ValueError(f"Invalid {key} tie target for SO doublet {ordinal}.")
            src_name = f"d{int(target)}_{key}"
            if src_name not in params:
                remaining.append((ordinal, key, d)); continue
            params.add(f"d{ordinal}_{key}", expr=src_name)
            progress = True
        pending = remaining
    if pending:
        unresolved = ", ".join(f"d{ordinal}_{key}" for ordinal, key, _ in pending)
        raise ValueError(f"Could not resolve tied SO-doublet parameter source(s): {unresolved}")

    # Compile every doublet into ordinary peak parameters via expressions.
    for ordinal, d in enumerate(ds, start=1):
        major, minor = int(d["major"]), int(d["minor"])
        split_name = f"d{ordinal}_split"
        ratio_name = f"d{ordinal}_ratio"
        if f"p{major}_E" not in params or f"p{major}_H" not in params:
            raise ValueError(f"Major peak parameters for SO doublet {ordinal} are not available.")
        params.add(f"p{minor}_E", expr=f"(p{major}_E + ({sign:.1f})*{split_name})")
        params.add(f"p{minor}_H", expr=f"(p{major}_H / {ratio_name})")
        for p in ("L", "G", "A"):
            if str(d.get(f"{p}_relation", "Same")) == "Same":
                if f"p{major}_{p}" not in params:
                    raise ValueError(f"Major peak {p} parameter for SO doublet {ordinal} is not available.")
                params.add(f"p{minor}_{p}", expr=f"p{major}_{p}")

    xr = yr = 1.0
    if fit_data is not None:
        xu = np.asarray(fit_data.get("xu", []), dtype=float)
        yu = np.asarray(fit_data.get("yu", []), dtype=float)
        if xu.size >= 2:
            xr = max(float(np.max(xu) - np.min(xu)), 1e-12)
        if yu.size >= 2:
            yr = max(float(np.max(yu) - np.min(yu)), 1.0)
    slope_lim = 5.0 * (yr / xr) if xr > 0 else 5.0
    curv_lim = 5.0 * (yr / (xr * xr)) if xr > 0 else 5.0
    y_min = float(np.min(fit_data.get("yu", [0.0]))) if fit_data is not None else 0.0
    y_max = float(np.max(fit_data.get("yu", [1.0]))) if fit_data is not None else 1.0
    b0_margin = max(0.5 * yr, 1.0)
    b0_min = y_min - b0_margin
    b0_max = y_max + b0_margin
    if bg_type in ("constant", "linear", "parabolic"):
        params.add("b0", value=float(bg_values.get("b0", 0.0)), min=b0_min, max=b0_max, vary=True)
    if bg_type in ("linear", "parabolic"):
        params.add("b1", value=float(bg_values.get("b1", 0.0)), min=-slope_lim, max=slope_lim, vary=True)
    if bg_type == "parabolic":
        params.add("b2", value=float(bg_values.get("b2", 0.0)), min=-curv_lim, max=curv_lim, vary=True)
    if bg_type == "Shirley":
        params.add(
            "bg_alpha",
            value=float(bg_values.get("bg_alpha", 1.0)),
            min=0.0,
            max=1.0,
            vary=not bool(bg_values.get("bg_alpha_fixed", False)),
        )
    return params


def classify_fit_outcome(result, peak_count: int, fit_data: Optional[dict] = None, human_name_fn: Callable[[str], str] = human_readable_param_name) -> Tuple[str, str, Set[str]]:
    if result is None:
        return "failed", "Fit did not return a result.", set()
    vals = result.params.valuesdict()
    if any((not np.isfinite(float(v))) for v in vals.values()):
        return "failed", "Fit returned non-finite parameter values.", set()
    warnings_list = []
    success = bool(getattr(result, "success", False))
    message = str(getattr(result, "message", "") or "").strip()
    if not success:
        warnings_list.append(message or "optimizer did not report full convergence")
    try:
        nfev = int(getattr(result, "nfev", 0) or 0)
    except Exception:
        nfev = 0
    if nfev >= 3000:
        warnings_list.append("maximum number of function evaluations reached")
    exact_bound_hits = collect_bound_hit_params(result)
    near_bound_hits: Set[str] = set()
    for name, par in result.params.items():
        if not getattr(par, "vary", False):
            continue
        if str(name) in exact_bound_hits:
            continue
        try:
            value = float(par.value)
            pmin = par.min
            pmax = par.max
        except Exception:
            continue
        try:
            if pmin is not None and pmax is not None and float(pmax) > float(pmin):
                frac = min(abs(value - float(pmin)), abs(float(pmax) - value)) / abs(float(pmax) - float(pmin))
                if frac < 0.02:
                    near_bound_hits.add(str(name))
        except Exception:
            pass
    if exact_bound_hits:
        hit_names = ", ".join(human_name_fn(name) for name in sorted(exact_bound_hits))
        warnings_list.append(f"{len(exact_bound_hits)} parameter(s) reached a bound: {hit_names}")
    elif near_bound_hits:
        hit_names = ", ".join(human_name_fn(name) for name in sorted(near_bound_hits))
        warnings_list.append(f"{len(near_bound_hits)} parameter(s) ended very close to a bound: {hit_names}")
    try:
        x = np.asarray((fit_data or {}).get("xu", []), dtype=float)
        xmin = float(np.nanmin(x)) if x.size else None
        xmax = float(np.nanmax(x)) if x.size else None
        span = abs(xmax - xmin) if xmin is not None and xmax is not None else None
    except Exception:
        xmin = xmax = span = None
    suspicious_widths = 0
    suspicious_centers = 0
    suspicious_heights = 0
    for i in range(1, peak_count + 1):
        try:
            E = float(vals.get(f"p{i}_E"))
            H = float(vals.get(f"p{i}_H"))
            L = float(vals.get(f"p{i}_L"))
            G = float(vals.get(f"p{i}_G"))
        except Exception:
            continue
        if not np.isfinite(E) or not np.isfinite(H) or not np.isfinite(L) or not np.isfinite(G):
            return "failed", f"Peak {i} returned non-finite values.", exact_bound_hits
        if H <= 0.0:
            suspicious_heights += 1
        if L <= 1e-9 or G <= 1e-9:
            suspicious_widths += 1
        if span is not None and span > 0:
            if L > 0.7 * span or G > 0.7 * span:
                suspicious_widths += 1
            if xmin is not None and xmax is not None and (E < xmin or E > xmax):
                suspicious_centers += 1
    if suspicious_centers:
        warnings_list.append(f"{suspicious_centers} peak center(s) moved outside the data range")
    if suspicious_widths:
        warnings_list.append(f"{suspicious_widths} peak width(s) look suspicious")
    if suspicious_heights:
        warnings_list.append(f"{suspicious_heights} peak height(s) became non-positive")
    try:
        residual = np.asarray(getattr(result, "residual", []), dtype=float)
        if residual.size:
            rss = float(np.nansum(residual ** 2))
            if not np.isfinite(rss):
                return "failed", "Fit returned an invalid residual.", exact_bound_hits
        redchi = float(getattr(result, "redchi", np.nan))
        if np.isfinite(redchi) and redchi <= 0:
            warnings_list.append("reduced chi-square is not positive")
    except Exception:
        pass
    if warnings_list:
        return "warning", "; ".join(dict.fromkeys(warnings_list)), exact_bound_hits
    return "success", (message if message and not success else ""), exact_bound_hits


def compute_fit_quality_metrics(result, fit_data: Optional[dict], bg_type: str, build_model_fn: Callable[..., Tuple[np.ndarray, Sequence[np.ndarray]]]) -> Dict[str, float]:
    metrics: Dict[str, float] = {"rss": float("nan"), "rms": float("nan"), "redchi_poisson": float("nan")}
    if result is None or fit_data is None:
        return metrics
    xu = np.asarray(fit_data.get("xu", []), dtype=float)
    yu = np.asarray(fit_data.get("yu", []), dtype=float)
    if xu.size == 0 or yu.size == 0 or xu.size != yu.size:
        return metrics
    try:
        energy_scale = str(getattr(fit_data.get("payload"), "energy_scale", "") or "")
    except Exception:
        energy_scale = ""
    vals = result.params.valuesdict()
    model_u, _ = build_model_fn(xu, bg_type=bg_type, values=vals, measured_y=yu if bg_type == "Shirley" else None, energy_scale=energy_scale)
    resid = np.asarray(yu - model_u, dtype=float)
    finite = np.isfinite(resid) & np.isfinite(yu)
    if not np.any(finite):
        return metrics
    resid = resid[finite]
    yfit = np.asarray(yu, dtype=float)[finite]
    rss = float(np.sum(resid ** 2))
    rms = float(np.sqrt(np.mean(resid ** 2))) if resid.size else float("nan")
    sigma = np.sqrt(np.maximum(yfit, 1.0))
    chi2 = float(np.sum((resid / sigma) ** 2)) if resid.size else float("nan")
    npts = int(resid.size)
    nfree = 0
    try:
        for par in result.params.values():
            if getattr(par, "expr", None):
                continue
            if bool(getattr(par, "vary", False)):
                nfree += 1
    except Exception:
        nfree = 0
    dof = max(npts - nfree, 1)
    redchi = float(chi2 / dof) if np.isfinite(chi2) else float("nan")
    metrics.update({"rss": rss, "rms": rms, "redchi_poisson": redchi})
    return metrics


def run_lmfit_fit(params, residual_func: Callable, iter_cb: Optional[Callable] = None, max_nfev: int = 3000):
    from lmfit import minimize
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning, module=r"uncertainties\.core")
        warnings.filterwarnings("ignore", message=r".*AffineScalarFunc\.error_components\(\).*", category=FutureWarning)
        warnings.filterwarnings("ignore", message=r".*AffineScalarFunc\.derivatives\(\).*|.*AffineScalarFunc\.derivatives.*deprecated.*", category=FutureWarning)
        return minimize(residual_func, params, method="least_squares", max_nfev=max_nfev, iter_cb=iter_cb)
