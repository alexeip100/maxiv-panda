from __future__ import annotations

from typing import Optional, Sequence, Mapping, Tuple, List
import math
import numpy as np


def gaussian_kernel(x, sigma: float):
    x = np.asarray(x, dtype=float)
    if sigma <= 0:
        return np.array([1.0])
    k = np.exp(-0.5 * (x / sigma) ** 2)
    s = float(np.sum(k))
    return k / s if s != 0 else k


def apply_gaussian_broadening(y, sigma: float, step: float):
    y = np.asarray(y, dtype=float)
    if y.size == 0 or sigma <= 0:
        return y.copy()
    span = int(max(50, min(2000, math.ceil(6.0 * sigma / max(step, 1e-12)))))
    kx = np.arange(-span, span + 1, dtype=float) * float(step)
    k = gaussian_kernel(kx, sigma)
    return np.convolve(y, k, mode="same")


def broadened_doniach_sunjic_profile(
    x, x0: float, gamma: float, alpha: float, sigma: float, energy_scale: str = ""
):
    """Return a Gaussian-broadened Doniach-Sunjic profile without range-edge artifacts.

    The fitting range is only a *view/fit interval* and must not act as a hard
    physical truncation of the line shape.  Convolving a DS profile directly on
    the cropped fit grid implicitly pads it with zeros and therefore depresses
    the profile within roughly one Gaussian kernel width of either boundary.
    That produced the visible kinks at newly selected fit-range limits.

    Evaluate the DS function on a grid padded by the same kernel half-width,
    perform the convolution there, and then crop back to the requested x grid.
    This makes the component inside the fit range independent of where that
    range happens to start and end.
    """
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return np.asarray([], dtype=float)
    if x.size == 1 or sigma <= 0:
        return doniach_sunjic(x, x0, gamma, alpha, energy_scale=energy_scale)

    step = float(np.median(np.diff(x)))
    if not np.isfinite(step) or step <= 0:
        return doniach_sunjic(x, x0, gamma, alpha, energy_scale=energy_scale)

    span = int(max(50, min(2000, math.ceil(6.0 * sigma / max(step, 1e-12)))))
    left = x[0] - step * np.arange(span, 0, -1, dtype=float)
    right = x[-1] + step * np.arange(1, span + 1, dtype=float)
    x_pad = np.concatenate((left, x, right))
    y_pad = doniach_sunjic(x_pad, x0, gamma, alpha, energy_scale=energy_scale)

    kx = np.arange(-span, span + 1, dtype=float) * step
    k = gaussian_kernel(kx, sigma)
    y_conv = np.convolve(y_pad, k, mode="same")
    return y_conv[span:span + x.size]


def voigt_profile(x, x0: float, sigma: float, gamma: float):
    x = np.asarray(x, dtype=float)
    try:
        from scipy.special import wofz
        z = ((x - x0) + 1j * gamma) / (sigma * np.sqrt(2.0))
        y = np.real(wofz(z)) / (sigma * np.sqrt(2.0 * np.pi))
        return y
    except Exception:
        fG = 2.0 * sigma * np.sqrt(2.0 * np.log(2.0))
        fL = 2.0 * gamma
        f = (fL**5 + 2.69269*fL**4*fG + 2.42843*fL**3*fG**2 + 4.47163*fL**2*fG**3 + 0.07842*fL*fG**4 + fG**5) ** (1.0/5.0)
        eta = 1.36603*(fL/f) - 0.47719*(fL/f)**2 + 0.11116*(fL/f)**3
        eta = float(np.clip(eta, 0.0, 1.0))
        L = (gamma**2) / ((x - x0)**2 + gamma**2)
        G = np.exp(-0.5*((x - x0)/sigma)**2)
        return eta*L + (1.0-eta)*G


def is_kinetic_energy_scale(scale: str) -> bool:
    """Return True when a payload energy-scale label denotes kinetic energy."""
    txt = str(scale or "").strip().lower()
    return txt.startswith("kin") or txt in ("ke", "kinetic")


def doniach_sunjic(x, x0: float, gamma: float, alpha: float, energy_scale: str = ""):
    x = np.asarray(x, dtype=float)
    alpha = float(np.clip(alpha, 0.0, 0.2))
    if alpha <= 0.0:
        return (gamma**2) / ((x - x0)**2 + gamma**2)

    # The physical DS tail direction has to follow the energy scale used for
    # fitting/display.  For Binding Energy, the existing convention is kept:
    # the asymmetric tail extends toward higher BE.  For Kinetic Energy, the
    # physically corresponding tail is toward lower KE, therefore the DS sign
    # must be reversed.  Unknown/legacy labels keep the BE convention to avoid
    # changing established behavior.
    if is_kinetic_energy_scale(energy_scale):
        eps = (x - x0) / gamma
    else:
        eps = (x0 - x) / gamma

    theta = np.arctan(eps)
    denom = (1.0 + eps**2) ** ((1.0 - alpha) / 2.0)
    phase = (1.0 - alpha) * theta + (np.pi * alpha / 2.0)
    y = np.cos(phase) / denom
    return np.clip(y, 0.0, None)


def poly_bg_center(x) -> float:
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return 0.0
    return 0.5 * (float(np.nanmin(x)) + float(np.nanmax(x)))


def constant_background(x, b0: float):
    x = np.asarray(x, dtype=float)
    return np.full_like(x, float(b0), dtype=float)


def linear_background_centered(x, b0: float, b1: float, x0: Optional[float] = None):
    x = np.asarray(x, dtype=float)
    if x0 is None:
        x0 = poly_bg_center(x)
    xc = x - float(x0)
    return float(b0) + float(b1) * xc


def poly_background_centered(x, b0: float, b1: float, b2: float = 0.0, x0: Optional[float] = None):
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return np.asarray([], dtype=float)
    if x0 is None:
        x0 = poly_bg_center(x)
    xc = x - float(x0)
    return float(b0) + float(b1) * xc + float(b2) * xc * xc


def raw_to_centered_linear(x, a0: float, a1: float):
    x0 = poly_bg_center(x)
    b1 = float(a1)
    b0 = float(a0) + float(a1) * float(x0)
    return b0, b1


def raw_to_centered_parabolic(x, a0: float, a1: float, a2: float):
    x0 = poly_bg_center(x)
    b2 = float(a2)
    b1 = float(a1) + 2.0 * float(a2) * float(x0)
    b0 = float(a0) + float(a1) * float(x0) + float(a2) * float(x0) * float(x0)
    return b0, b1, b2


def guess_constant_bg(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size == 0 or y.size != x.size:
        return 0.0
    nedge = max(3, min(int(0.1 * x.size), max(3, x.size // 4)))
    return float(np.median(np.r_[y[:nedge], y[-nedge:]]))


def guess_linear_bg_raw(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 2 or y.size != x.size:
        return 0.0, 0.0
    nedge = max(3, min(int(0.12 * x.size), max(3, x.size // 4)))
    xx = np.r_[x[:nedge], x[-nedge:]]
    yy = np.r_[y[:nedge], y[-nedge:]]
    try:
        a1, a0 = np.polyfit(xx, yy, 1)
        return float(a0), float(a1)
    except Exception:
        b0 = guess_constant_bg(x, y)
        return b0, 0.0


def guess_parabolic_bg_raw(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 3 or y.size != x.size:
        return 0.0, 0.0, 0.0
    nedge = max(3, min(int(0.15 * x.size), max(3, x.size // 4)))
    xx = np.r_[x[:nedge], x[-nedge:]]
    yy = np.r_[y[:nedge], y[-nedge:]]
    if xx.size < 3:
        a0, a1 = guess_linear_bg_raw(x, y)
        return a0, a1, 0.0
    try:
        a2, a1, a0 = np.polyfit(xx, yy, 2)
        return float(a0), float(a1), float(a2)
    except Exception:
        a0, a1 = guess_linear_bg_raw(x, y)
        return a0, a1, 0.0


def compute_shirley_background(x, y, scale: str, alpha: float = 1.0):
    x = np.asarray(x, dtype=float)
    alpha = float(np.clip(alpha, 0.0, 1.0))
    y = np.asarray(y, dtype=float)
    n = x.size
    if n < 5 or y.size != n:
        return np.zeros_like(x)
    order = np.argsort(x)
    xs = x[order]
    ys = y[order]
    nwin = max(5, int(round(0.05 * n)))
    scale = (scale or "").lower()
    is_be = scale.startswith("bind") or scale in ("be", "binding")
    if is_be:
        y0 = float(np.median(ys[:nwin]))
        y1 = float(np.median(ys[-nwin:]))
        y_end_pt = float(max(0.0, ys[-1]))
    else:
        y0 = float(np.median(ys[-nwin:]))
        y1 = float(np.median(ys[:nwin]))
        y_end_pt = float(max(0.0, ys[0]))
    y0 = max(0.0, y0)
    y1 = max(0.0, y1)
    y1 = float(np.clip(y1, 0.0, y_end_pt))
    xw, yw = (xs, ys) if is_be else (xs[::-1], ys[::-1])
    b = np.linspace(y0, y1, n, dtype=float)
    tol = 1e-4 * max(1.0, float(np.nanmax(yw) - np.nanmin(yw)))
    for _ in range(80):
        b_old = b.copy()
        diff = np.maximum(yw - b, 0.0)
        cum = np.zeros(n, dtype=float)
        for i in range(n - 2, -1, -1):
            dx = xw[i + 1] - xw[i]
            cum[i] = cum[i + 1] + 0.5 * (diff[i + 1] + diff[i]) * dx
        denom = cum[0]
        if not np.isfinite(denom) or denom <= 0:
            b = np.linspace(y0, y1, n, dtype=float)
            break
        frac = cum / denom
        b = y1 + (y0 - y1) * frac
        b[0] = y0
        b[-1] = y1
        if float(np.nanmax(np.abs(b - b_old))) < tol:
            break
    bs = b if is_be else b[::-1]
    bg_sorted = bs
    bg = np.empty_like(bg_sorted)
    bg[order] = bg_sorted
    try:
        i_end = int(order[-1] if is_be else order[0])
        bg[i_end] = float(np.clip(bg[i_end], 0.0, max(0.0, y[i_end])))
    except Exception:
        pass
    try:
        bg_lin_w = np.linspace(y0, y1, n, dtype=float)
        bg_lin_sorted = bg_lin_w if is_be else bg_lin_w[::-1]
        bg_lin = np.empty_like(bg_lin_sorted)
        bg_lin[order] = bg_lin_sorted
        bg = (1.0 - alpha) * bg_lin + alpha * bg
    except Exception:
        pass
    try:
        # A Shirley background is an integral background and should remain
        # smooth/monotonic between its endpoint levels.  Do *not* clip it
        # point-by-point to the measured spectrum: individual noisy data points
        # may legitimately fall below the background, and such clipping makes
        # the background (and therefore the total model) inherit the raw-data
        # oscillations.  Keep only the physical non-negative/end-level bounds.
        lo = max(0.0, min(y0, y1))
        hi = max(0.0, max(y0, y1))
        bg = np.clip(bg, lo, hi)
    except Exception:
        pass
    try:
        i_pre = int(order[0] if is_be else order[-1])
        bg[i_pre] = float(np.clip(bg[i_pre], 0.0, max(0.0, y[i_pre])))
    except Exception:
        pass
    return bg



def integrated_component_area(x, y) -> float:
    """Return the numerical area of one fitted peak component.

    The integration is performed over the actual fitted energy interval.  This
    gives one consistent, derived intensity measure for both symmetric Voigt
    components and the finite-window DS-Voigt components used by PANDA.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if np.count_nonzero(mask) < 2:
        return float("nan")
    xs = x[mask]
    ys = y[mask]
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    integrate = getattr(np, "trapezoid", None)
    if integrate is None:  # NumPy < 2.0 compatibility
        integrate = np.trapz
    return float(integrate(ys, xs))


def integrated_component_areas(x, components: Sequence[np.ndarray]) -> List[float]:
    """Return fitted-window areas for a sequence of peak components."""
    return [integrated_component_area(x, component) for component in components]

def build_model_from_values(
    xu,
    peaks: Sequence[Mapping[str, float]],
    bg_type: str,
    bg_params: Mapping[str, float],
    measured_y=None,
    energy_scale: str = "",
) -> Tuple[np.ndarray, List[np.ndarray]]:
    xu = np.asarray(xu, dtype=float)
    if xu.size == 0:
        return np.asarray([], dtype=float), []
    step = float(xu[1] - xu[0]) if xu.size > 1 else 1.0
    bg_type = str(bg_type or "constant")
    if bg_type in ("constant", "linear", "parabolic"):
        bg_u = poly_background_centered(
            xu,
            float(bg_params.get("b0", 0.0)),
            float(bg_params.get("b1", 0.0)) if bg_type in ("linear", "parabolic") else 0.0,
            float(bg_params.get("b2", 0.0)) if bg_type == "parabolic" else 0.0,
        )
    elif bg_type == "Shirley":
        if measured_y is None:
            raise ValueError("Shirley background requires measured spectrum data.")
        y_meas = np.asarray(measured_y, dtype=float)
        if y_meas.shape != xu.shape:
            raise ValueError("Measured spectrum for Shirley background has incompatible shape.")
        alpha = float(bg_params.get("bg_alpha", 1.0))
        bg_u = compute_shirley_background(xu, y_meas, str(energy_scale or "").lower(), alpha=alpha)
    else:
        raise ValueError(f"Background type '{bg_type}' is not supported for automated fitting yet.")
    components: List[np.ndarray] = []
    y_sum = bg_u.copy()
    for i, p in enumerate(peaks, start=1):
        E = float(p["E"])
        H = float(p["H"])
        Lf = float(p["L"])
        Gf = float(p["G"])
        A = float(p["A"])
        gamma = max(1e-12, Lf / 2.0)
        sigma = max(1e-12, Gf / (2.0 * np.sqrt(2.0 * np.log(2.0))))
        if A <= 0.0:
            y_u = voigt_profile(xu, E, sigma, gamma)
        else:
            y_u = broadened_doniach_sunjic_profile(
                xu, E, gamma, A, sigma, energy_scale=energy_scale
            )
        mmax = float(np.max(y_u)) if y_u.size else 0.0
        if not np.isfinite(mmax) or mmax <= 0:
            raise ValueError(f"Peak {i} could not produce a valid profile.")
        y_u = (y_u / mmax) * H
        y_sum += y_u
        components.append(y_u)
    return y_sum, components
