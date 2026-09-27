from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.signal import find_peaks, peak_widths, savgol_filter


@dataclass(frozen=True)
class PeakSuggestion:
    energy: float
    height: float
    prominence: float


def _odd_window_from_energy_step(x: np.ndarray, span_ev: float = 0.20) -> int:
    """Return a modest odd Savitzky-Golay window derived from the energy step."""
    if x.size < 5:
        return 0
    dx = np.abs(np.diff(x))
    dx = dx[np.isfinite(dx) & (dx > 0)]
    if dx.size == 0:
        return 0
    step = float(np.median(dx))
    n = max(5, int(round(span_ev / step)))
    if n % 2 == 0:
        n += 1
    n = min(n, 51)
    max_odd = x.size if x.size % 2 == 1 else x.size - 1
    n = min(n, max_odd)
    return n if n >= 5 else 0


def _smooth_signal(y: np.ndarray, window: int) -> np.ndarray:
    if not window:
        return y.copy()
    try:
        return savgol_filter(y, window_length=window, polyorder=2, mode="interp")
    except Exception:
        return y.copy()


def _robust_sigma(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return 0.0
    med = float(np.median(values))
    mad = float(np.median(np.abs(values - med)))
    return 1.4826 * mad


def suggest_initial_peaks(
    x: Sequence[float],
    y: Sequence[float],
    *,
    max_peaks: int = 5,
    min_separation_ev: float = 0.3,
    edge_guard_ev: float = 0.5,
    smoothing_span_ev: float = 0.20,
    local_height_half_window_ev: float = 0.10,
) -> list[PeakSuggestion]:
    """Conservatively suggest resolved maxima for initial fit components.

    Detection is intentionally biased toward under-detection.  Candidate maxima
    are found after light smoothing, then must either persist on a second,
    stronger smoothing scale or be exceptionally prominent on the fine scale.
    This suppresses noise/ripple maxima that otherwise seed ghost fit peaks.

    Returned ``height`` values are *component amplitudes above the local
    prominence contour*, not absolute spectrum intensities.  This is important
    for XPS spectra with a large background: a tiny ripple on a 2000-count
    background must not initialise a 2000-count peak.

    Shoulders are not inferred.  If no convincing interior maximum survives,
    one conservative fallback suggestion is returned.
    """
    xx = np.asarray(x, dtype=float).reshape(-1)
    yy = np.asarray(y, dtype=float).reshape(-1)
    finite = np.isfinite(xx) & np.isfinite(yy)
    xx = xx[finite]
    yy = yy[finite]
    if xx.size == 0 or yy.size != xx.size:
        return []
    if xx.size < 3:
        i = int(np.nanargmax(yy))
        baseline = float(np.nanmin(yy)) if yy.size else 0.0
        return [PeakSuggestion(float(xx[i]), float(max(0.0, yy[i] - baseline)), 0.0)]

    order = np.argsort(xx)
    xs = xx[order]
    ys = yy[order]

    fine_window = _odd_window_from_energy_step(xs, smoothing_span_ev)
    fine = _smooth_signal(ys, fine_window)

    # A second scale is deliberately much smoother. Real resolved peaks remain
    # represented, while point-to-point noise and small ripple maxima disappear.
    coarse_span_ev = max(0.60, 3.0 * float(smoothing_span_ev))
    coarse_window = _odd_window_from_energy_step(xs, coarse_span_ev)
    coarse = _smooth_signal(ys, coarse_window)

    # High-frequency noise estimate.  Use the more conservative of residuals
    # against the fine and coarse trends, but cap the coarse contribution so a
    # strong narrow real peak does not itself define the noise floor.
    fine_sigma = _robust_sigma(ys - fine)
    coarse_sigma = _robust_sigma(ys - coarse)
    if fine_sigma > 0:
        noise_sigma = max(fine_sigma, min(coarse_sigma, 2.0 * fine_sigma))
    else:
        noise_sigma = coarse_sigma

    yrange = float(np.nanmax(fine) - np.nanmin(fine))
    eps = np.finfo(float).eps
    fine_prom_floor = max(6.0 * noise_sigma, 0.025 * max(yrange, 0.0), eps)
    coarse_prom_floor = max(4.0 * noise_sigma, 0.015 * max(yrange, 0.0), eps)

    dx = np.abs(np.diff(xs))
    dx = dx[np.isfinite(dx) & (dx > 0)]
    step = float(np.median(dx)) if dx.size else 1.0
    distance_points = max(1, int(np.ceil(min_separation_ev / step)))

    peaks, props = find_peaks(fine, prominence=fine_prom_floor, distance=distance_points)
    if peaks.size:
        widths, _, _, _ = peak_widths(fine, peaks, rel_height=0.5)
    else:
        widths = np.asarray([], dtype=float)

    coarse_peaks, coarse_props = find_peaks(
        coarse, prominence=coarse_prom_floor, distance=distance_points
    )
    coarse_proms = np.asarray(coarse_props.get("prominences", np.zeros(coarse_peaks.size)), dtype=float)

    xmin = float(np.nanmin(xs))
    xmax = float(np.nanmax(xs))
    min_width_ev = 0.10
    match_tol_ev = max(0.30, float(min_separation_ev))
    strong_fine_floor = max(10.0 * noise_sigma, 0.06 * max(yrange, 0.0), eps)

    candidates: list[tuple[int, float]] = []
    prominences = np.asarray(props.get("prominences", np.zeros(peaks.size)), dtype=float)
    for p, prom, width_pts in zip(peaks, prominences, widths):
        e = float(xs[int(p)])
        if e - xmin < edge_guard_ev or xmax - e < edge_guard_ev:
            continue
        if float(width_pts) * step < min_width_ev:
            continue

        persistent = False
        if coarse_peaks.size:
            nearby = np.abs(xs[coarse_peaks] - e) <= match_tol_ev
            if np.any(nearby):
                persistent = bool(np.any(coarse_proms[nearby] >= coarse_prom_floor))

        # Exception for a very strong, narrow peak that is attenuated/merged by
        # the coarse smoothing. This keeps clearly resolved sharp components.
        if not persistent and float(prom) < strong_fine_floor:
            continue
        candidates.append((int(p), float(prom)))

    if candidates:
        candidates = sorted(candidates, key=lambda t: t[1], reverse=True)[: max(1, int(max_peaks))]
        candidates.sort(key=lambda t: t[0])

        result: list[PeakSuggestion] = []
        for p, prom in candidates:
            e = float(xs[p])
            mask = np.abs(xs - e) <= float(local_height_half_window_ev)
            if np.any(mask):
                local_idx = np.where(mask)[0]
                j = int(local_idx[np.nanargmax(ys[mask])])
            else:
                j = p

            # Prominence contour approximates the local baseline underlying the
            # peak. Use the original local apex above this contour as the initial
            # component amplitude rather than the absolute measured intensity.
            contour = float(fine[p] - prom)
            amplitude = float(max(0.0, ys[j] - contour))
            if amplitude <= 0:
                amplitude = float(max(0.0, prom))
            result.append(PeakSuggestion(e, amplitude, prom))
        return result

    # Conservative fallback. Estimate amplitude above a robust baseline rather
    # than using the absolute intensity.
    interior = (xs - xmin >= edge_guard_ev) & (xmax - xs >= edge_guard_ev)
    if np.any(interior):
        idxs = np.where(interior)[0]
        j = int(idxs[np.nanargmax(fine[interior])])
        baseline = float(np.nanpercentile(fine[interior], 20.0))
    else:
        j = int(np.nanargmax(fine))
        baseline = float(np.nanmin(fine))
    amplitude = float(max(0.0, ys[j] - baseline))
    return [PeakSuggestion(float(xs[j]), amplitude, 0.0)]
