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

def normalize_respes_rows_at_binding_energy(
    x: np.ndarray,
    z: np.ndarray,
    photon_energy: np.ndarray,
    centre_be: float,
    width_ev: float,
    *,
    work_function: float = 4.5,
    source_axis: str = "be",
) -> tuple[np.ndarray, tuple[float, float]]:
    """Normalize a ResPES map to a fixed binding-energy interval.

    The normalization is evaluated on the original measured rectangular map.
    For a measured kinetic-energy axis, the requested fixed BE interval is
    converted row by row using ``BE = hnu - KE - work_function``.  For a
    measured binding-energy axis, the interval is common to all rows.

    Every row must contain the complete requested BE interval.
    """
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    hv = np.asarray(photon_energy, dtype=float)
    if z.ndim != 2 or x.ndim != 1 or z.shape[1] != x.size or x.size < 2:
        raise ValueError("Map data have incompatible dimensions.")
    if hv.ndim != 1 or hv.size != z.shape[0]:
        raise ValueError("Photon-energy axis is incompatible with the map rows.")
    if not np.all(np.isfinite(hv)):
        raise ValueError("Photon-energy axis contains non-finite values.")
    phi = float(work_function)
    if not np.isfinite(phi):
        raise ValueError("Analyzer work function must be finite.")

    finite_x = np.isfinite(x)
    if np.count_nonzero(finite_x) < 2:
        raise ValueError("Map energy axis is unavailable.")
    x_sorted_all = np.sort(x[finite_x])
    xmin, xmax = float(x_sorted_all[0]), float(x_sorted_all[-1])
    centre_be = float(centre_be)
    width_ev = abs(float(width_ev))
    if not np.isfinite(centre_be) or not np.isfinite(width_ev) or width_ev <= 0.0:
        raise ValueError("The averaging width must be greater than zero and the binding energy must be finite.")
    be_low = centre_be - 0.5 * width_ev
    be_high = centre_be + 0.5 * width_ev

    axis = str(source_axis or "be").strip().lower()
    if axis not in {"be", "ke"}:
        raise ValueError("source_axis must be 'be' or 'ke'.")
    if axis == "be" and (be_low < xmin or be_high > xmax):
        raise ValueError("The binding-energy normalization interval lies outside the map range.")

    out = np.array(z, dtype=float, copy=True)
    for row_idx in range(z.shape[0]):
        y = np.asarray(z[row_idx], dtype=float)
        valid = finite_x & np.isfinite(y)
        if np.count_nonzero(valid) < 2:
            raise ValueError("At least one map row has insufficient finite data.")
        row_order = np.argsort(x[valid])
        xx = x[valid][row_order]
        yy = y[valid][row_order]

        if axis == "be":
            low_src, high_src = be_low, be_high
        else:
            # Fixed BE -> row-dependent KE interval.  Increasing BE
            # corresponds to decreasing KE at fixed photon energy.
            low_src = float(hv[row_idx] - phi - be_high)
            high_src = float(hv[row_idx] - phi - be_low)

        if low_src < float(xx[0]) or high_src > float(xx[-1]):
            raise ValueError(
                "The binding-energy normalization interval is unavailable for at least one row."
            )
        scale = mean_intensity_over_interval(xx, yy, low_src, high_src)
        if not np.isfinite(scale) or abs(scale) < 1.0e-15:
            raise ValueError(
                "The binding-energy normalization interval has a zero mean for at least one row."
            )
        out[row_idx, :] = y / scale
    return out, (be_low, be_high)


def normalize_respes_rows_at_kinetic_energy(
    x: np.ndarray,
    z: np.ndarray,
    photon_energy: np.ndarray,
    centre_ke: float,
    width_ev: float,
    *,
    work_function: float = 4.5,
    source_axis: str = "be",
) -> tuple[np.ndarray, tuple[float, float]]:
    """Normalize a ResPES map to a fixed kinetic-energy interval.

    The normalization is evaluated on the original measured rectangular map,
    never on a BE<->KE resampled display map.  For a measured binding-energy
    axis, the requested fixed KE interval is converted row by row using
    ``KE = hnu - BE - work_function``.  For a measured kinetic-energy axis,
    the interval is common to all rows.

    Every row must contain the *complete* requested KE interval.  This strict
    coverage rule keeps the physical normalization identical for every photon
    energy and prevents silent partial-window normalization at map edges.
    """
    x = np.asarray(x, dtype=float)
    z = np.asarray(z, dtype=float)
    hv = np.asarray(photon_energy, dtype=float)
    if z.ndim != 2 or x.ndim != 1 or z.shape[1] != x.size or x.size < 2:
        raise ValueError("Map data have incompatible dimensions.")
    if hv.ndim != 1 or hv.size != z.shape[0]:
        raise ValueError("Photon-energy axis is incompatible with the map rows.")
    if not np.all(np.isfinite(hv)):
        raise ValueError("Photon-energy axis contains non-finite values.")
    phi = float(work_function)
    if not np.isfinite(phi):
        raise ValueError("Analyzer work function must be finite.")

    finite_x = np.isfinite(x)
    if np.count_nonzero(finite_x) < 2:
        raise ValueError("Map energy axis is unavailable.")
    x_sorted_all = np.sort(x[finite_x])
    xmin, xmax = float(x_sorted_all[0]), float(x_sorted_all[-1])
    centre_ke = float(centre_ke)
    width_ev = abs(float(width_ev))
    if not np.isfinite(centre_ke) or not np.isfinite(width_ev) or width_ev <= 0.0:
        raise ValueError("The averaging width must be greater than zero and the kinetic energy must be finite.")
    ke_low = centre_ke - 0.5 * width_ev
    ke_high = centre_ke + 0.5 * width_ev

    axis = str(source_axis or "be").strip().lower()
    if axis not in {"be", "ke"}:
        raise ValueError("source_axis must be 'be' or 'ke'.")
    if axis == "ke" and (ke_low < xmin or ke_high > xmax):
        raise ValueError("The kinetic-energy normalization interval lies outside the map range.")

    out = np.array(z, dtype=float, copy=True)
    for row_idx in range(z.shape[0]):
        y = np.asarray(z[row_idx], dtype=float)
        valid = finite_x & np.isfinite(y)
        if np.count_nonzero(valid) < 2:
            raise ValueError("At least one map row has insufficient finite data.")
        row_order = np.argsort(x[valid])
        xx = x[valid][row_order]
        yy = y[valid][row_order]

        if axis == "ke":
            low_src, high_src = ke_low, ke_high
        else:
            # Fixed KE -> row-dependent BE interval.  Reversal is intentional:
            # increasing KE corresponds to decreasing BE at fixed photon energy.
            low_src = float(hv[row_idx] - phi - ke_high)
            high_src = float(hv[row_idx] - phi - ke_low)

        if low_src < float(xx[0]) or high_src > float(xx[-1]):
            raise ValueError(
                "The kinetic-energy normalization interval is unavailable for at least one row."
            )
        scale = mean_intensity_over_interval(xx, yy, low_src, high_src)
        if not np.isfinite(scale) or abs(scale) < 1.0e-15:
            raise ValueError(
                "The kinetic-energy normalization interval has a zero mean for at least one row."
            )
        out[row_idx, :] = y / scale
    return out, (ke_low, ke_high)


def normalize_map_to_photon_energy_interval(
    photon_energy: np.ndarray,
    z: np.ndarray,
    centre_hv: float,
    width_ev: float,
) -> tuple[np.ndarray, tuple[float, float], np.ndarray]:
    """Normalize a map point-by-point to an average photon-energy spectrum.

    This implements the ResPES pre-edge normalization discussed for PANDA
    0.12.4.  A reference spectrum is formed as the energy-weighted mean over
    the selected photon-energy interval, including linearly interpolated
    interval boundaries.  Every map row is then divided point-by-point by that
    reference spectrum.

    Returns ``(normalized_map, interval, reference_spectrum)``.
    """
    hv = np.asarray(photon_energy, dtype=float)
    z = np.asarray(z, dtype=float)
    if hv.ndim != 1 or z.ndim != 2 or hv.size != z.shape[0] or hv.size < 2:
        raise ValueError("Photon-energy axis is incompatible with the map rows.")
    finite_hv = np.isfinite(hv)
    if np.count_nonzero(finite_hv) < 2:
        raise ValueError("Photon-energy axis is unavailable.")
    hv_sorted = np.sort(hv[finite_hv])
    hv_min, hv_max = float(hv_sorted[0]), float(hv_sorted[-1])
    interval = normalization_interval_ev(hv_min, hv_max, float(centre_hv), float(width_ev))

    order = np.argsort(hv)
    hv_ordered = hv[order]
    z_ordered = z[order, :]
    reference = np.empty(z.shape[1], dtype=float)
    for col_idx in range(z.shape[1]):
        values = np.asarray(z_ordered[:, col_idx], dtype=float)
        valid = np.isfinite(hv_ordered) & np.isfinite(values)
        if np.count_nonzero(valid) < 2:
            raise ValueError("At least one energy channel has insufficient finite data.")
        hh = hv_ordered[valid]
        vv = values[valid]
        if interval[0] < float(hh[0]) or interval[1] > float(hh[-1]):
            raise ValueError(
                "The photon-energy normalization interval is unavailable for at least one energy channel."
            )
        reference[col_idx] = mean_intensity_over_interval(hh, vv, *interval)

    if np.any(~np.isfinite(reference)) or np.any(np.abs(reference) < 1.0e-15):
        raise ValueError("The photon-energy reference spectrum contains zero or invalid values.")
    out = np.asarray(z, dtype=float) / reference[np.newaxis, :]
    return np.array(out, dtype=float, copy=True), interval, reference


def subtract_map_photon_energy_reference(photon_energy, z, centre_hv, width_ev):
    """Subtract the energy-weighted mean spectrum from every measured map row.

    Unlike division, zero-valued reference channels are valid. This function
    operates on the measured X grid, independently of the displayed BE/KE axis.
    """
    hv = np.asarray(photon_energy, dtype=float)
    z = np.asarray(z, dtype=float)
    if hv.ndim != 1 or z.ndim != 2 or hv.size != z.shape[0] or hv.size < 2:
        raise ValueError("Photon-energy axis is incompatible with the map rows.")
    if not np.all(np.isfinite(hv)) or len(np.unique(hv)) < 2:
        raise ValueError("Photon-energy axis must contain distinct finite values.")
    interval = normalization_interval_ev(float(np.min(hv)), float(np.max(hv)),
                                         float(centre_hv), float(width_ev))
    order = np.argsort(hv)
    hh = hv[order]
    zz = z[order, :]
    reference = np.empty(z.shape[1], dtype=float)
    for col in range(z.shape[1]):
        valid = np.isfinite(zz[:, col])
        if np.count_nonzero(valid) < 2:
            raise ValueError("At least one energy channel has insufficient finite data.")
        xc, yc = hh[valid], zz[valid, col]
        if interval[0] < xc[0] or interval[1] > xc[-1]:
            raise ValueError("Reference interval is unavailable in at least one energy channel.")
        reference[col] = mean_intensity_over_interval(xc, yc, *interval)
    return z - reference[np.newaxis, :], interval, reference
