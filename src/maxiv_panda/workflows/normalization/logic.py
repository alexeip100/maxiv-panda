from __future__ import annotations

import numpy as np


def normalization_interval(
    xmin: float,
    xmax: float,
    centre: float,
    span_percent: float,
) -> tuple[float, float]:
    """Return a fixed-width interval, shifted inward at spectrum edges."""
    total = max(0.0, float(xmax) - float(xmin))
    width = min(total, max(0.0, float(span_percent)) * total / 100.0)
    if width <= 0.0:
        return float(centre), float(centre)
    low = float(centre) - width / 2.0
    high = float(centre) + width / 2.0
    if low < xmin:
        high += xmin - low
        low = xmin
    if high > xmax:
        low -= high - xmax
        high = xmax
    return max(float(xmin), low), min(float(xmax), high)




def normalization_interval_if_reachable(
    xmin: float,
    xmax: float,
    centre: float,
    span_percent: float,
) -> tuple[float, float] | None:
    """Return an edge-shifted interval when the requested band reaches the curve.

    A normalization centre may lie slightly beyond a spectrum edge after
    per-curve energy calibration or GUI rounding.  If at least half of the
    requested full-width band can still reach the spectrum, use the established
    inward-shifting rule.  Centres farther away remain invalid.
    """
    xmin, xmax = sorted((float(xmin), float(xmax)))
    total = max(0.0, xmax - xmin)
    width = min(total, max(0.0, float(span_percent)) * total / 100.0)
    half_width = 0.5 * width
    centre = float(centre)
    if centre < xmin - half_width or centre > xmax + half_width:
        return None
    return normalization_interval(xmin, xmax, centre, span_percent)


def mean_intensity_over_interval(
    x: np.ndarray,
    y: np.ndarray,
    low: float,
    high: float,
) -> float:
    """Return the energy-weighted mean, including interpolated boundaries."""
    if high <= low:
        return float(np.interp(low, x, y))
    inside = (x > low) & (x < high)
    x_seg = np.concatenate(([low], x[inside], [high]))
    y_seg = np.concatenate((
        [float(np.interp(low, x, y))],
        y[inside],
        [float(np.interp(high, x, y))],
    ))
    return float(np.trapezoid(y_seg, x_seg) / (high - low))


def integrated_intensity_over_interval(
    x: np.ndarray,
    y: np.ndarray,
    low: float,
    high: float,
) -> float:
    """Return the signed area over [low, high], interpolating both boundaries.

    ``x`` is expected to be finite and monotonically increasing.  The helper
    mirrors :func:`mean_intensity_over_interval` so map-area normalization and
    the established point-normalization workflow use the same boundary rules.
    """
    low = float(low)
    high = float(high)
    if high < low:
        low, high = high, low
    if high <= low:
        return 0.0
    if x.size < 2 or y.size < 2:
        return float("nan")
    if low < float(x[0]) or high > float(x[-1]):
        return float("nan")
    inside = (x > low) & (x < high)
    x_seg = np.concatenate(([low], x[inside], [high]))
    y_seg = np.concatenate((
        [float(np.interp(low, x, y))],
        y[inside],
        [float(np.interp(high, x, y))],
    ))
    return float(np.trapezoid(y_seg, x_seg))


def normalization_interval_ev(
    xmin: float,
    xmax: float,
    centre: float,
    width_ev: float,
) -> tuple[float, float]:
    """Return an absolute-width interval centred on ``centre``.

    Unlike the established 1D percentage-span helper, the 2D map workflow
    does not shift the interval at an edge.  Both requested boundaries must
    actually exist on the spectral energy axis so the shaded map band and
    the numerical normalization operation always mean exactly the same thing.
    """
    xmin, xmax = sorted((float(xmin), float(xmax)))
    centre = float(centre)
    width = abs(float(width_ev))
    if not np.isfinite(centre) or not np.isfinite(width) or width <= 0.0:
        raise ValueError("The averaging width must be greater than zero.")
    low = centre - 0.5 * width
    high = centre + 0.5 * width
    if low < xmin or high > xmax:
        raise ValueError("The normalization interval lies outside the map energy range.")
    return low, high


def normalize_map_rows_at_energy(
    x: np.ndarray,
    z: np.ndarray,
    centre: float,
    width_ev: float,
) -> tuple[np.ndarray, tuple[float, float]]:
    """Normalize every map row to its mean intensity around ``centre``.

    ``width_ev`` is the absolute averaging width in eV used by the 2D-map
    workflow.  Returns a copy of ``z`` and the exact common energy interval.
    A ``ValueError`` is raised if that interval or any row denominator is not
    usable.
    """
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    if z.ndim != 2 or x.ndim != 1 or z.shape[1] != x.size or x.size < 2:
        raise ValueError("Map data have incompatible dimensions.")
    finite_x = np.isfinite(x)
    if np.count_nonzero(finite_x) < 2:
        raise ValueError("Map energy axis is unavailable.")
    order = np.argsort(x[finite_x])
    x_sorted = x[finite_x][order]
    xmin, xmax = float(x_sorted[0]), float(x_sorted[-1])
    centre = float(centre)
    if not (xmin <= centre <= xmax):
        raise ValueError("Normalization energy lies outside the map range.")
    interval = normalization_interval_ev(xmin, xmax, centre, float(width_ev))

    out = np.array(z, dtype=float, copy=True)
    for row_idx in range(z.shape[0]):
        y = np.asarray(z[row_idx], dtype=float)
        valid = finite_x & np.isfinite(y)
        if np.count_nonzero(valid) < 2:
            raise ValueError("At least one map row has insufficient finite data.")
        row_order = np.argsort(x[valid])
        xx = x[valid][row_order]
        yy = y[valid][row_order]
        if interval[0] < float(xx[0]) or interval[1] > float(xx[-1]):
            raise ValueError("The normalization interval is unavailable for at least one row.")
        scale = mean_intensity_over_interval(xx, yy, *interval)
        if not np.isfinite(scale) or abs(scale) < 1.0e-15:
            raise ValueError("The normalization interval has a zero mean for at least one row.")
        out[row_idx, :] = y / scale
    return out, interval


def normalize_map_rows_by_area(
    x: np.ndarray,
    z: np.ndarray,
    low: float,
    high: float,
) -> np.ndarray:
    """Normalize each map row to the area within the requested energy range."""
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    if z.ndim != 2 or x.ndim != 1 or z.shape[1] != x.size or x.size < 2:
        raise ValueError("Map data have incompatible dimensions.")
    lo, hi = sorted((float(low), float(high)))
    finite_x = np.isfinite(x)
    if np.count_nonzero(finite_x) < 2:
        raise ValueError("Map energy axis is unavailable.")
    x_finite = x[finite_x]
    xmin, xmax = float(np.nanmin(x_finite)), float(np.nanmax(x_finite))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        raise ValueError("Area-normalization range has zero width.")
    if lo < xmin or hi > xmax:
        raise ValueError("Area-normalization limits lie outside the map energy range.")

    out = np.array(z, dtype=float, copy=True)
    for row_idx in range(z.shape[0]):
        y = np.asarray(z[row_idx], dtype=float)
        valid = finite_x & np.isfinite(y)
        if np.count_nonzero(valid) < 2:
            raise ValueError("At least one map row has insufficient finite data.")
        row_order = np.argsort(x[valid])
        xx = x[valid][row_order]
        yy = y[valid][row_order]
        if lo < float(xx[0]) or hi > float(xx[-1]):
            raise ValueError("The area-normalization range is unavailable for at least one row.")
        area = integrated_intensity_over_interval(xx, yy, lo, hi)
        if not np.isfinite(area) or abs(area) < 1.0e-15:
            raise ValueError("The selected range has zero area for at least one row.")
        out[row_idx, :] = y / area
    return out
