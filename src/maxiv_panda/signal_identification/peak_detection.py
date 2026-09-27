from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from scipy.signal import find_peaks, savgol_filter


@dataclass(frozen=True)
class DetectedPeak:
    index: int
    energy: float
    intensity: float
    prominence: float


def detect_peaks(x, y, *, prominence_fraction: float = 0.005, min_distance_fraction: float = 0.012) -> list[DetectedPeak]:
    x_arr = np.asarray(x, dtype=float).ravel()
    y_arr = np.asarray(y, dtype=float).ravel()
    finite = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr, y_arr = x_arr[finite], y_arr[finite]
    if x_arr.size < 7:
        return []

    # Peak detection is performed on a lightly smoothed copy only; displayed data stay untouched.
    window = max(5, int(round(x_arr.size * 0.015)) | 1)
    window = min(window, x_arr.size - (1 - x_arr.size % 2))
    if window < 5:
        smooth = y_arr
    else:
        try:
            smooth = savgol_filter(y_arr, window_length=window, polyorder=min(3, window - 2))
        except Exception:
            smooth = y_arr

    span = float(np.nanmax(smooth) - np.nanmin(smooth))
    if not np.isfinite(span) or span <= 0:
        return []
    prominence = max(float(prominence_fraction) * span, np.finfo(float).eps)
    distance = max(1, int(round(x_arr.size * float(min_distance_fraction))))
    indices, props = find_peaks(smooth, prominence=prominence, distance=distance)
    prominences = props.get("prominences", np.zeros(indices.size))
    peaks = [
        DetectedPeak(int(i), float(x_arr[i]), float(y_arr[i]), float(p))
        for i, p in zip(indices, prominences)
    ]
    return sorted(peaks, key=lambda peak: peak.energy)



def _clean_xy(x, y):
    x_arr = np.asarray(x, dtype=float).ravel()
    y_arr = np.asarray(y, dtype=float).ravel()
    finite = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr, y_arr = x_arr[finite], y_arr[finite]
    order = np.argsort(x_arr)
    return x_arr[order], y_arr[order]


def _local_smooth(y_local: np.ndarray) -> np.ndarray:
    # Very short survey windows (typically 5--7 points) must not be
    # smoothed with a polynomial spanning the entire window.  That can shift
    # a narrow spin-orbit partner into the valley between the two components.
    if y_local.size <= 7:
        return y_local
    window = min(y_local.size if y_local.size % 2 == 1 else y_local.size - 1, 11)
    window = max(5, window)
    if window >= y_local.size:
        window = y_local.size - (1 - y_local.size % 2)
    if window < 5:
        return y_local
    try:
        return savgol_filter(y_local, window_length=window, polyorder=min(3, window - 2))
    except Exception:
        return y_local


def refine_peak_near_reference(x, y, *, target_energy: float, search_half_width: float = 5.0,
                               min_feature_height: float | None = None,
                               detrend_background_noise: bool = False) -> DetectedPeak | None:
    x_arr, y_arr = _clean_xy(x, y)
    if x_arr.size < 7:
        return None
    lo = float(target_energy) - float(search_half_width)
    hi = float(target_energy) + float(search_half_width)
    mask = (x_arr >= lo) & (x_arr <= hi)
    # A coarse survey may provide only 3--4 samples across a narrow,
    # reference-guided spin-orbit window.  That is still sufficient for a
    # targeted local-maximum check; requiring five points can leave the true
    # partner undetected while a smoothing artefact in the valley is retained.
    if np.count_nonzero(mask) < 3:
        return None
    x_local = x_arr[mask]
    y_local = y_arr[mask]
    smooth = _local_smooth(y_local)
    baseline = np.linspace(float(smooth[0]), float(smooth[-1]), smooth.size)
    # Use sample order rather than np.interp on the energy axis. Survey spectra
    # are commonly stored with descending binding energy, while np.interp
    # requires an increasing x grid and otherwise produces a false baseline.
    residual = smooth - baseline
    if min_feature_height is None:
        span = float(np.nanmax(y_arr) - np.nanmin(y_arr)) if x_arr.size else 0.0
        min_feature_height = max(0.0015 * span, np.finfo(float).eps)
    # Ordinary refinement keeps the historical first-difference noise gate.
    # Reference-guided discovery can opt into a two-pass, peak-excluded local
    # background estimate.  Keeping the improved estimator scoped to discovery
    # avoids changing downstream family-recovery behaviour for already assigned
    # peaks (for example overlapping Ir 4f/5p families).
    differences = np.diff(y_local)
    noise = 0.0
    detection_residual = residual
    if detrend_background_noise and y_local.size >= 9:
        provisional_idx = int(np.nanargmax(residual))
        local_step = float(np.nanmedian(np.abs(np.diff(x_local)))) if x_local.size > 1 else 0.0
        exclusion_half_width = max(1.0, 2.0 * local_step) if np.isfinite(local_step) and local_step > 0 else 1.0
        background_mask = np.abs(x_local - float(x_local[provisional_idx])) > exclusion_half_width
        if np.count_nonzero(background_mask) >= 4:
            xb = x_local[background_mask]
            yb = y_local[background_mask]
            x0 = float(np.nanmedian(xb))
            degree = 2 if xb.size >= 8 else 1
            try:
                coeff = np.polyfit(xb - x0, yb, degree)
                fitted_background = np.polyval(coeff, x_local - x0)
                background_residual = yb - np.polyval(coeff, xb - x0)
                median_residual = float(np.nanmedian(background_residual))
                noise = 1.4826 * float(np.nanmedian(np.abs(background_residual - median_residual)))
                if np.isfinite(noise) and noise > 0 and xb.size >= 6:
                    keep = np.abs(background_residual - median_residual) <= 3.0 * noise
                    if max(degree + 2, 4) <= np.count_nonzero(keep) < xb.size:
                        coeff = np.polyfit(xb[keep] - x0, yb[keep], degree)
                        fitted_background = np.polyval(coeff, x_local - x0)
                        background_residual = yb[keep] - np.polyval(coeff, xb[keep] - x0)
                        median_residual = float(np.nanmedian(background_residual))
                        noise = 1.4826 * float(np.nanmedian(np.abs(background_residual - median_residual)))
                detection_residual = smooth - fitted_background
            except Exception:
                noise = 0.0
    elif differences.size and y_local.size >= 9:
        median_difference = float(np.nanmedian(differences))
        noise = 1.4826 * float(np.nanmedian(np.abs(differences - median_difference))) / np.sqrt(2.0)
    if not np.isfinite(noise):
        noise = 0.0

    required_height = max(float(min_feature_height), 3.0 * noise, np.finfo(float).eps)
    required_prominence = max(0.30 * float(min_feature_height), 2.0 * noise, np.finfo(float).eps)
    peaks, props = find_peaks(detection_residual, prominence=required_prominence)
    if peaks.size == 0:
        # Do not accept a window-edge maximum: it is normally a baseline slope
        # or the tail of a neighbouring peak rather than independent evidence.
        idx_local = int(np.nanargmax(detection_residual))
        if idx_local in (0, detection_residual.size - 1) or float(detection_residual[idx_local]) < required_height:
            return None
    else:
        # Prefer a real local feature close to the target, but allow moderate
        # distance if it is much more pronounced.
        prominences = props.get('prominences', np.zeros(peaks.size))
        scores = []
        for position, i in enumerate(peaks):
            prominence = float(prominences[position])
            if float(detection_residual[i]) < required_height:
                continue
            dist_penalty = abs(float(x_local[i]) - float(target_energy)) / max(float(search_half_width), 1e-9)
            scores.append((prominence - 0.55 * dist_penalty * required_prominence, int(i)))
        if not scores:
            return None
        idx_local = max(scores, key=lambda item: item[0])[1]
    global_indices = np.nonzero(mask)[0]
    idx_global = int(global_indices[idx_local])

    # Snap the reported position to the actual displayed-data maximum in the
    # immediate neighbourhood of the stable, smoothed maximum.  This keeps the
    # noise resistance of the smoothed detector while ensuring that PE guide
    # lines visibly pass through the measured peak apex.
    if x_arr.size > 1:
        step = float(np.nanmedian(np.abs(np.diff(x_arr))))
    else:
        step = 0.0
    if np.isfinite(step) and step > 0:
        raw_neighbourhood = np.abs(x_arr - float(x_arr[idx_global])) <= 1.05 * step
        neighbour_indices = np.nonzero(raw_neighbourhood)[0]
        if neighbour_indices.size:
            idx_global = int(neighbour_indices[int(np.nanargmax(y_arr[neighbour_indices]))])

    return DetectedPeak(idx_global, float(x_arr[idx_global]), float(y_arr[idx_global]), float(max(residual[idx_local], 0.0)))


def detect_reference_guided_peaks(x, y, *, expected_windows: list[tuple[float, float]], existing_peaks: list[DetectedPeak],
                                  min_feature_fraction: float = 0.005) -> list[DetectedPeak]:
    x_arr, y_arr = _clean_xy(x, y)
    if x_arr.size < 7:
        return []
    span = float(np.nanmax(y_arr) - np.nanmin(y_arr))
    min_feature_height = max(float(min_feature_fraction) * span * 0.22, 0.00035 * span, np.finfo(float).eps)
    found: list[DetectedPeak] = []
    existing_positions = [float(p.energy) for p in existing_peaks]
    for center, half_width in expected_windows:
        # Reference-guided detection is a recovery path for genuinely missed
        # features.  If the ordinary detector has already found a measured
        # peak anywhere inside this reference-search window, reuse that peak
        # during matching rather than creating a second, reference-nearer
        # pseudo-duplicate.  The latter can otherwise win early de-duplication
        # and then fail the stricter local-feature check, hiding the real peak.
        if any(abs(pos - float(center)) <= max(0.6, float(half_width)) for pos in existing_positions):
            continue
        peak = refine_peak_near_reference(
            x_arr, y_arr, target_energy=float(center), search_half_width=float(half_width),
            min_feature_height=min_feature_height, detrend_background_noise=True,
        )
        if peak is None:
            continue
        if any(abs(float(peak.energy) - float(p.energy)) <= max(0.6, 0.2 * half_width) for p in found):
            continue
        found.append(peak)
    return sorted(found, key=lambda peak: peak.energy)
