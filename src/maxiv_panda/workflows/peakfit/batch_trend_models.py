from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

try:  # scipy is already a package dependency for fitting workflows.
    from scipy.optimize import curve_fit
except Exception:  # pragma: no cover - defensive fallback
    curve_fit = None


@dataclass(frozen=True)
class TrendModelSpec:
    code: str
    label: str
    n_params: int
    requires_order: bool = False


MODEL_SPECS: tuple[TrendModelSpec, ...] = (
    TrendModelSpec("poly", "Polynomial", 0, True),
    TrendModelSpec("single_exp_plateau", "Single exponential to plateau", 3, False),
    TrendModelSpec("stretched_exp_plateau", "Stretched exponential to plateau", 4, False),
)


def available_models() -> list[tuple[str, str]]:
    return [(m.code, m.label) for m in MODEL_SPECS]


def model_label(code: str, *, order: int | None = None) -> str:
    code = str(code or "")
    if code == "poly":
        return f"Polynomial order {int(order or 0)}"
    for spec in MODEL_SPECS:
        if spec.code == code:
            return spec.label
    return code or "Trend model"



def model_formula(code: str, *, order: int | None = None) -> str:
    """Return a matplotlib-mathtext formula for display in the trend-analysis panel."""
    code = str(code or "")
    if code == "poly":
        n = int(max(0, min(int(order or 0), 5)))
        if n == 0:
            return r"y=c_0"
        terms: list[str] = []
        for power in range(n, -1, -1):
            idx = n - power
            if power == 0:
                terms.append(fr"c_{{{idx}}}")
            elif power == 1:
                terms.append(fr"c_{{{idx}}}x")
            else:
                terms.append(fr"c_{{{idx}}}x^{{{power}}}")
        return r"y=" + "+".join(terms)
    if code == "single_exp_plateau":
        return r"y=y_{\infty}+A\exp\left[-\frac{x-x_0}{\tau}\right]"
    if code == "stretched_exp_plateau":
        return r"y=y_{\infty}+A\exp\left[-\left(\frac{x-x_0}{\tau}\right)^{\beta}\right]"
    return r"y=f(x)"

def _safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        v = float(value)
        return v if np.isfinite(v) else default
    except Exception:
        return default


def _single_exp(x: np.ndarray, y_inf: float, amp: float, tau: float) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    x0 = float(np.nanmin(x)) if x.size else 0.0
    tau = max(float(tau), 1.0e-12)
    return y_inf + amp * np.exp(-(x - x0) / tau)


def _stretched_exp(x: np.ndarray, y_inf: float, amp: float, tau: float, beta: float) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    x0 = float(np.nanmin(x)) if x.size else 0.0
    tau = max(float(tau), 1.0e-12)
    beta = max(float(beta), 1.0e-12)
    dx = np.maximum(x - x0, 0.0)
    return y_inf + amp * np.exp(-np.power(dx / tau, beta))


def _quality_metrics(y: np.ndarray, y_fit: np.ndarray, n_params: int) -> dict[str, float]:
    y = np.asarray(y, dtype=float)
    y_fit = np.asarray(y_fit, dtype=float)
    resid = y - y_fit
    rss = float(np.sum(resid * resid))
    n = int(y.size)
    rmse = float(np.sqrt(rss / max(n, 1)))
    span = float(np.nanmax(y) - np.nanmin(y)) if n else float("nan")
    scale = span if np.isfinite(span) and abs(span) > 1.0e-12 else max(abs(float(np.nanmean(y))) if n else 0.0, 1.0)
    nrmse = float(rmse / scale) if scale else float("nan")
    return {
        "nrmse": nrmse,
        "rmse": rmse,
        "rss": rss,
        "n_points": float(n),
        "n_params": float(n_params),
    }


def _initial_exp_guesses(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    y0 = float(y[0])
    y_last = float(y[-1])
    y_inf = y_last
    amp = y0 - y_inf
    tau = max((float(np.nanmax(x)) - float(np.nanmin(x))) / 3.0, 1.0)
    if not np.isfinite(amp) or abs(amp) < 1.0e-12:
        amp = float(np.nanmax(y) - np.nanmin(y)) or 1.0
    return y_inf, amp, tau


def fit_trend_model(
    x: np.ndarray,
    y: np.ndarray,
    *,
    model: str,
    order: int = 1,
) -> dict[str, Any]:
    """Fit one analytical trend model and return a JSON-compatible result."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if x.size < 2:
        raise ValueError("At least two finite points are required for trend fitting.")
    sort_idx = np.argsort(x)
    x = x[sort_idx]
    y = y[sort_idx]
    model = str(model or "poly")

    if model == "poly":
        order = int(max(0, min(int(order), 5)))
        if x.size <= order:
            raise ValueError(f"Polynomial order {order} needs at least {order + 1} points.")
        coeffs = np.polyfit(x, y, order)
        y_fit = np.polyval(coeffs, x)
        params = {f"c{i}": float(c) for i, c in enumerate(coeffs)}
        metrics = _quality_metrics(y, y_fit, order + 1)
        return {
            "model": "poly",
            "model_label": model_label("poly", order=order),
            "order": order,
            "x": [float(v) for v in x],
            "y_fit": [float(v) for v in y_fit],
            "params": params,
            "coefficients": [float(c) for c in coeffs],
            "metrics": metrics,
        }

    if curve_fit is None:
        raise RuntimeError("SciPy curve_fit is not available for exponential trend fitting.")

    y_inf0, amp0, tau0 = _initial_exp_guesses(x, y)
    x_range = max(float(np.nanmax(x) - np.nanmin(x)), 1.0)
    y_span = max(float(np.nanmax(y) - np.nanmin(y)), 1.0)
    y_pad = 10.0 * y_span
    lower_y = float(np.nanmin(y) - y_pad)
    upper_y = float(np.nanmax(y) + y_pad)

    if model == "single_exp_plateau":
        p0 = [y_inf0, amp0, tau0]
        bounds = ([lower_y, -20.0 * y_span, 1.0e-6], [upper_y, 20.0 * y_span, 1000.0 * x_range])
        popt, _pcov = curve_fit(_single_exp, x, y, p0=p0, bounds=bounds, maxfev=20000)
        y_fit = _single_exp(x, *popt)
        params = {"y_inf": float(popt[0]), "A": float(popt[1]), "tau": float(popt[2])}
        metrics = _quality_metrics(y, y_fit, 3)
        return {
            "model": model,
            "model_label": model_label(model),
            "x": [float(v) for v in x],
            "y_fit": [float(v) for v in y_fit],
            "params": params,
            "metrics": metrics,
        }

    if model == "stretched_exp_plateau":
        p0 = [y_inf0, amp0, tau0, 1.0]
        bounds = ([lower_y, -20.0 * y_span, 1.0e-6, 0.15], [upper_y, 20.0 * y_span, 1000.0 * x_range, 5.0])
        popt, _pcov = curve_fit(_stretched_exp, x, y, p0=p0, bounds=bounds, maxfev=30000)
        y_fit = _stretched_exp(x, *popt)
        params = {"y_inf": float(popt[0]), "A": float(popt[1]), "tau": float(popt[2]), "beta": float(popt[3])}
        metrics = _quality_metrics(y, y_fit, 4)
        return {
            "model": model,
            "model_label": model_label(model),
            "x": [float(v) for v in x],
            "y_fit": [float(v) for v in y_fit],
            "params": params,
            "metrics": metrics,
        }

    raise ValueError(f"Unknown trend model: {model}")


def format_metric(value: Any) -> str:
    v = _safe_float(value)
    if not np.isfinite(v):
        return "n/a"
    if abs(v) < 1.0e-3 or abs(v) >= 1.0e4:
        return f"{v:.3g}"
    return f"{v:.5g}"


def compact_params(params: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in (params or {}).items():
        v = _safe_float(value)
        if np.isfinite(v):
            parts.append(f"{key}={format_metric(v)}")
    return "; ".join(parts)
