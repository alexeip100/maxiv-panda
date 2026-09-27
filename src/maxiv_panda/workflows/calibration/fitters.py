def _voigt_profile(x, amp, cen, sigma, gamma):
    # Normalized-ish Voigt using scipy.special.wofz
    import numpy as _np
    from scipy.special import wofz

    z = ((x - cen) + 1j * gamma) / (sigma * _np.sqrt(2.0))
    return amp * _np.real(wofz(z)) / (sigma * _np.sqrt(2.0 * _np.pi))

def _smooth(y: "Any", win: int = 11) -> "Any":
    import numpy as _np
    yy = _np.asarray(y, dtype=float)
    if win < 5:
        return yy
    try:
        from scipy.signal import savgol_filter
        w = min(win, len(yy) - (len(yy) + 1) % 2)
        w = max(5, w)
        if w % 2 == 0:
            w += 1
        return savgol_filter(yy, window_length=w, polyorder=2, mode="interp")
    except Exception:
        # Fallback: simple moving average
        w = min(win, len(yy))
        if w <= 1:
            return yy
        k = _np.ones(w) / float(w)
        return _np.convolve(yy, k, mode="same")

def _fit_fermi_edge(
    x,
    y,
    expected_ef: float | None = None,
    energy_scale: str = "Unknown",
    x_min: float | None = None,
    x_max: float | None = None,
):
    """Simplified automated Fermi-edge fit.

    Notes
    -----
    * We always fit in *data coordinates* (x sorted increasing) and apply any axis flipping
      only for plotting.
    * Optionally, we can fit only within a user-specified [x_min, x_max] window.
    * The model direction is locked for Binding Energy: step UP with increasing BE.
    """
    import numpy as _np
    from scipy.optimize import least_squares

    x = _np.asarray(x, dtype=float)
    y = _np.asarray(y, dtype=float)

    # Sort by x increasing for robust derivative + fitting (independent of display flipping)
    order = _np.argsort(x)
    x = x[order]
    y = y[order]

    ys = _smooth(y, 21)

    # Robust mid-level guess
    ylo = float(_np.nanmedian(ys[: max(3, len(ys)//10)]))
    yhi = float(_np.nanmedian(ys[-max(3, len(ys)//10):]))
    ymid = 0.5 * (ylo + yhi)
    i_mid = int(_np.nanargmin(_np.abs(ys - ymid)))
    x_mid = float(x[i_mid])

    # Derivative guess (smoothed)
    dy = _np.gradient(ys, x)
    i_der = int(_np.nanargmax(_np.abs(dy)))
    x_der = float(x[i_der])

    # Decide if edge is rising or falling.
    # For Binding Energy (sorted x increasing BE), the user convention here is that
    # the Fermi edge is a step UP with increasing BE.
    if str(energy_scale).lower().startswith("bind"):
        rising = True
    else:
        slope_at_edge = float(dy[i_der]) if _np.isfinite(dy[i_der]) else 0.0
        rising = slope_at_edge > 0

    # Hybrid initial guess
    x0_guess = 0.6 * x_mid + 0.4 * x_der
    if expected_ef is not None:
        # Nudge guess towards expected if wildly off
        if abs(x0_guess - expected_ef) > 1.0:
            x0_guess = expected_ef

    # Fit range: default full range, optionally restrict to [x_min, x_max].
    xx = x
    yy = y
    if x_min is not None and x_max is not None and _np.isfinite(x_min) and _np.isfinite(x_max):
        _xmin = float(x_min)
        _xmax = float(x_max)
        if _xmin > _xmax:
            _xmin, _xmax = _xmax, _xmin
        m = (xx >= _xmin) & (xx <= _xmax)
        if int(_np.count_nonzero(m)) >= 10:
            xx = xx[m]
            yy = yy[m]
    full_span = float(_np.nanmax(xx)) - float(_np.nanmin(xx))
    ylo_w = float(_np.nanmedian(yy[: max(3, len(yy)//10)]))
    yhi_w = float(_np.nanmedian(yy[-max(3, len(yy)//10):]))

    # Fermi-step model (simplified): step + constant baseline (no slope term).
    # This enforces the physically expected flat pre/post-edge behavior.
    if rising:
        a_guess = yhi_w - ylo_w
        b_guess = ylo_w

        def model(xv, a, x0, w, b):
            t = (xv - x0) / w
            t = _np.clip(t, -60.0, 60.0)
            return a / (1.0 + _np.exp(-t)) + b

    else:
        a_guess = ylo_w - yhi_w
        b_guess = yhi_w

        def model(xv, a, x0, w, b):
            t = (xv - x0) / w
            t = _np.clip(t, -60.0, 60.0)
            return a / (1.0 + _np.exp(t)) + b

    p0 = _np.array([a_guess, x0_guess, 0.08, b_guess], dtype=float)

    # Parameter bounds: keep x0 within range; keep width <= 0.5 eV
    lb = _np.array([-_np.inf, float(_np.nanmin(xx)), 1e-4, -_np.inf], dtype=float)
    ub = _np.array([_np.inf, float(_np.nanmax(xx)), 0.5, _np.inf], dtype=float)

    def _fit_with_p0(p0_local: _np.ndarray):
        def resid(params: _np.ndarray) -> _np.ndarray:
            return model(xx, *params) - yy

        res = least_squares(
            resid,
            x0=_np.clip(p0_local, lb, ub),
            bounds=(lb, ub),
            max_nfev=60000,
            loss="soft_l1",
            f_scale=0.1 * (_np.nanstd(yy) if _np.nanstd(yy) > 0 else 1.0),
        )
        popt_local = _np.asarray(res.x, dtype=float)
        yfit_local = model(xx, *popt_local)
        # Quality metrics
        residv = yy - yfit_local
        ss_res = float(_np.nansum(residv * residv))
        ss_tot = float(_np.nansum((yy - float(_np.nanmean(yy))) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        rmse = float(_np.sqrt(_np.nanmean(residv * residv)))
        return popt_local, yfit_local, r2, rmse

    # First fit
    popt, yfit, r2, rmse = _fit_with_p0(p0)
    x0 = float(popt[1])
    w = float(popt[2])

    # Fallback re-fit if suspicious
    suspicious = False
    if not _np.isfinite(r2) or r2 < 0.90:
        suspicious = True
    if w >= 0.49:
        suspicious = True
    if expected_ef is not None and abs(x0 - expected_ef) > 0.5:
        suspicious = True
    # Sanity vs expected range when expected_ef not provided
    if expected_ef is None and abs(x0) > 1.0:
        suspicious = True

    if suspicious:
        # Alternative guess: mid-level only
        p0b = _np.array([a_guess, x_mid if expected_ef is None else expected_ef, 0.08, b_guess], dtype=float)
        try:
            popt2, yfit2, r2_2, rmse2 = _fit_with_p0(p0b)
            if _np.isfinite(r2_2) and (not _np.isfinite(r2) or r2_2 > r2):
                popt, yfit, r2, rmse = popt2, yfit2, r2_2, rmse2
                x0 = float(popt[1])
                w = float(popt[2])
        except Exception:
            pass

    # Status
    status = "OK"
    reasons = []
    # R2 thresholds tuned for noisy single-sweep references: avoid hard-failing
    # otherwise visually good fits.
    if not _np.isfinite(r2) or r2 < 0.90:
        status = "FAIL"
        reasons.append("low R2")
    elif r2 < 0.95:
        status = "WARN"
        reasons.append("R2")
    elif r2 < 0.985 and status == "OK":
        status = "WARN"
        reasons.append("R2")
    if w >= 0.5:
        status = "FAIL"
        reasons.append("width")
    elif w >= 0.35 and status == "OK":
        status = "WARN"
        reasons.append("width")
    if expected_ef is not None:
        if abs(x0 - expected_ef) > 0.5:
            status = "FAIL"
            reasons.append("|EF-expected|")
        elif abs(x0 - expected_ef) > 0.2 and status == "OK":
            status = "WARN"
            reasons.append("|EF-expected|")
    else:
        # Generic sanity check (only meaningful for Binding Energy workflows)
        if str(energy_scale).lower().startswith("bind"):
            if abs(x0) > 0.7:
                status = "FAIL"
                reasons.append("|EF|")
            elif abs(x0) > 0.5 and status == "OK":
                status = "WARN"
                reasons.append("|EF|")

    return {
        "kind": "fermi_edge",
        "marker": "EF",
        "E_meas": x0,
        "params": {"a": float(popt[0]), "x0": x0, "w": w, "b": float(popt[3])},
        "quality": {"r2": float(r2), "rmse": float(rmse), "status": status, "reasons": reasons},
        "fit_window": (float(_np.nanmin(xx)), float(_np.nanmax(xx))),
        "fit_x": xx,
        "fit_y": yfit,
    }

def _fit_core_level(
    x,
    y,
    expected_peak: float | None = None,
    x_min: float | None = None,
    x_max: float | None = None,
    model: str = "single",
    delta_e: float | None = None,
    ratio: float | None = None,
    tie_widths: bool = True,
):
    import numpy as _np
    from scipy.optimize import curve_fit
    from scipy.signal import find_peaks

    x = _np.asarray(x, dtype=float)
    y = _np.asarray(y, dtype=float)

    # Work in ascending-x order for more stable peak finding and fitting.
    try:
        _ord = _np.argsort(x)
        x = x[_ord]
        y = y[_ord]
    except Exception:
        pass

    ys = _smooth(y, 11)

    # Peak guess:
    # - if user provided expected peak, prefer it
    # - otherwise peak-find with a sane fallback
    cen_guess = None
    if expected_peak is not None:
        try:
            if _np.isfinite(float(expected_peak)):
                cen_guess = float(expected_peak)
        except Exception:
            cen_guess = None
    if cen_guess is None:
        try:
            peaks, props = find_peaks(
                ys,
                prominence=max(
                    1e-12,
                    0.02 * _np.nanmax(ys) if _np.isfinite(_np.nanmax(ys)) else 1.0,
                ),
            )
        except Exception:
            peaks = _np.array([], dtype=int)
            props = {}
        if len(peaks) == 0:
            i0 = int(_np.nanargmax(ys))
        else:
            prom = props.get("prominences")
            if prom is None:
                i0 = int(peaks[int(_np.argmax(ys[peaks]))])
            else:
                i0 = int(peaks[int(_np.argmax(prom))])
        cen_guess = float(x[i0])

    # Fit window
    if x_min is not None and x_max is not None:
        try:
            _xmin = float(x_min)
            _xmax = float(x_max)
        except Exception:
            _xmin, _xmax = None, None
        if _xmin is not None and _xmax is not None:
            if _xmin > _xmax:
                _xmin, _xmax = _xmax, _xmin
            m = (x >= _xmin) & (x <= _xmax)
        else:
            m = None
    else:
        # Default: if user provided an expected peak, use ±1 eV; otherwise use a broader automatic span.
        if expected_peak is not None:
            span = 1.0
        else:
            span = max(0.6, 0.10 * (float(_np.nanmax(x)) - float(_np.nanmin(x))))
        m = (x >= cen_guess - span) & (x <= cen_guess + span)

    if m is None:
        xx = x
        yy = y
    else:
        xx = x[m]
        yy = y[m]
        if len(xx) < 10:
            xx = x
            yy = y

    # Background estimate
    b_guess = float(_np.nanmin(yy))
    amp_guess = float(_np.nanmax(yy) - b_guess)

    # Helper: determine measured energy as maximum of summed fit curve.
    def _meas_from_model(xmin: float, xmax: float, f) -> float:
        try:
            x_dense = _np.linspace(float(xmin), float(xmax), 3000)
            y_dense = _np.asarray(f(x_dense), dtype=float)
            i = int(_np.nanargmax(y_dense))
            # local quadratic refinement
            if 1 <= i < len(x_dense) - 1:
                x0, x1, x2 = x_dense[i - 1], x_dense[i], x_dense[i + 1]
                y0, y1, y2 = y_dense[i - 1], y_dense[i], y_dense[i + 1]
                denom = (y0 - 2.0 * y1 + y2)
                if _np.isfinite(denom) and abs(float(denom)) > 0:
                    dx = 0.5 * (y0 - y2) / denom
                    if _np.isfinite(dx) and abs(float(dx)) <= 1.0:
                        return float(x1 + dx * (x2 - x1))
            return float(x_dense[i])
        except Exception:
            return float("nan")

    model = (model or "single").strip().lower()
    if model.startswith("double"):
        # Doublet model: two Voigt peaks + linear background.
        # Optional constraints:
        #   - delta_e: fix splitting mu2 = mu1 + delta_e
        #   - ratio: fix amplitude ratio A2 = ratio * A1
        try:
            _ratio = float(ratio) if ratio is not None else None
            if _ratio is not None and (not _np.isfinite(_ratio) or _ratio < 0):
                _ratio = None
        except Exception:
            _ratio = None

        try:
            _delta = float(delta_e) if delta_e is not None else None
            if _delta is not None and (not _np.isfinite(_delta) or _delta <= 0):
                _delta = None
        except Exception:
            _delta = None

        # Estimate delta if needed (coarse): find a second peak in the smoothed signal inside the window.
        if _delta is None:
            _delta_guess = None
            try:
                peaks, props = find_peaks(
                    _smooth(yy, 9),
                    prominence=max(1e-12, 0.02 * _np.nanmax(yy)),
                )
                if len(peaks) >= 2:
                    prom = props.get("prominences")
                    if prom is None:
                        order = _np.argsort(_np.asarray(yy[peaks], dtype=float))[::-1]
                    else:
                        order = _np.argsort(_np.asarray(prom, dtype=float))[::-1]
                    p1 = int(peaks[int(order[0])])
                    for oi in order[1:]:
                        p2 = int(peaks[int(oi)])
                        if abs(float(xx[p2] - xx[p1])) > 1e-6:
                            _delta_guess = abs(float(xx[p2] - xx[p1]))
                            break
            except Exception:
                _delta_guess = None
            if _delta_guess is None or not _np.isfinite(_delta_guess) or _delta_guess <= 0:
                _span = max(1e-6, float(_np.nanmax(xx)) - float(_np.nanmin(xx)))
                # Conservative fallback: keep the trial splitting small compared with
                # the fit window so the optimizer does not immediately drift into a
                # broad quasi-single-peak solution.
                _delta_guess = max(0.05, min(0.30, 0.10 * _span))
            delta_guess = float(_delta_guess)
        else:
            delta_guess = float(_delta)

        _delta_for_guess = float(_delta) if _delta is not None else delta_guess

        # The observed maximum of a doublet usually lies between the two components,
        # not on the first component itself. Shifting the initial centre accordingly
        # makes the fit much less sensitive to tiny ΔE changes.
        ratio_guess = float(_ratio) if _ratio is not None else 1.0
        ratio_guess = max(1e-6, ratio_guess)
        cen1_guess = float(cen_guess - _delta_for_guess * (ratio_guess / (1.0 + ratio_guess)))
        cen2_guess = float(cen1_guess + _delta_for_guess)

        # Amplitude guesses
        try:
            y1 = float(_np.interp(cen1_guess, xx, yy))
            y2 = float(_np.interp(cen2_guess, xx, yy))
        except Exception:
            y1 = float(_np.nanmax(yy))
            y2 = float(_np.nanmax(yy))
        a1_guess = max(1e-12, y1 - b_guess)
        if _ratio is not None:
            a2_guess = max(1e-12, _ratio * a1_guess)
        else:
            a2_guess = max(1e-12, y2 - b_guess)
            if not _np.isfinite(a2_guess) or a2_guess <= 0:
                a2_guess = max(1e-12, 0.7 * a1_guess)

        def model_free(xv, a1, cen1, a2, delt, sigma, gamma, b, c):
            cen2 = cen1 + abs(float(delt))
            yv = _voigt_profile(xv, a1, cen1, sigma, gamma)
            if _ratio is not None:
                yv = yv + _voigt_profile(xv, a1 * _ratio, cen2, sigma, gamma)
            else:
                yv = yv + _voigt_profile(xv, a2, cen2, sigma, gamma)
            return yv + b + c * xv

        def model_fixed_delta(xv, a1, cen1, a2, sigma, gamma, b, c):
            cen2 = cen1 + float(_delta)
            yv = _voigt_profile(xv, a1, cen1, sigma, gamma)
            if _ratio is not None:
                yv = yv + _voigt_profile(xv, a1 * _ratio, cen2, sigma, gamma)
            else:
                yv = yv + _voigt_profile(xv, a2, cen2, sigma, gamma)
            return yv + b + c * xv

        _span = max(1e-6, float(_np.nanmax(xx)) - float(_np.nanmin(xx)))
        _width_ub = max(0.05, min(1.0, 0.50 * _span))

        def _rss(y_obs, y_calc):
            _m = _np.isfinite(y_obs) & _np.isfinite(y_calc)
            if not _np.any(_m):
                return float("inf")
            _r = _np.asarray(y_obs[_m] - y_calc[_m], dtype=float)
            return float(_np.sum(_r * _r))

        if _delta is None:
            bounds = (
                [0.0, float(_np.nanmin(xx)), 0.0, 1e-6, 1e-3, 1e-3, -_np.inf, -_np.inf],
                [_np.inf, float(_np.nanmax(xx)), _np.inf, float(_span), _width_ub, _width_ub, _np.inf, _np.inf],
            )
            seeds = []
            for _frac in (0.20, ratio_guess / (1.0 + ratio_guess), 0.80):
                _cen1_seed = float(cen_guess - delta_guess * _frac)
                for _w0 in (0.08, 0.15, min(0.25, _width_ub)):
                    seeds.append([a1_guess, _cen1_seed, a2_guess, delta_guess, _w0, _w0, b_guess, 0.0])
            best = None
            best_rss = float("inf")
            for p0 in seeds:
                try:
                    popt_try, pcov = curve_fit(model_free, xx, yy, p0=p0, bounds=bounds, maxfev=50000)
                    yfit_try = model_free(xx, *popt_try)
                    rss_try = _rss(yy, yfit_try)
                    if rss_try < best_rss:
                        best_rss = rss_try
                        best = popt_try
                except Exception:
                    continue
            if best is None:
                raise RuntimeError("doublet fit failed")
            popt = _np.asarray(best, dtype=float)
            a1, cen1, a2, delt, sigma, gamma, b, c = popt
            cen2 = float(cen1 + abs(float(delt)))
            f_model = lambda xv: model_free(xv, *popt)
        else:
            bounds = (
                [0.0, float(_np.nanmin(xx)), 0.0, 1e-3, 1e-3, -_np.inf, -_np.inf],
                [_np.inf, float(_np.nanmax(xx)), _np.inf, _width_ub, _width_ub, _np.inf, _np.inf],
            )
            seeds = []
            for _frac in (0.20, ratio_guess / (1.0 + ratio_guess), 0.80):
                _cen1_seed = float(cen_guess - float(_delta) * _frac)
                for _w0 in (0.08, 0.15, min(0.25, _width_ub)):
                    seeds.append([a1_guess, _cen1_seed, a2_guess, _w0, _w0, b_guess, 0.0])
            best = None
            best_rss = float("inf")
            for p0 in seeds:
                try:
                    popt_try, pcov = curve_fit(model_fixed_delta, xx, yy, p0=p0, bounds=bounds, maxfev=50000)
                    yfit_try = model_fixed_delta(xx, *popt_try)
                    rss_try = _rss(yy, yfit_try)
                    if rss_try < best_rss:
                        best_rss = rss_try
                        best = popt_try
                except Exception:
                    continue
            if best is None:
                raise RuntimeError("doublet fit failed")
            popt = _np.asarray(best, dtype=float)
            a1, cen1, a2, sigma, gamma, b, c = popt
            cen2 = float(cen1 + float(_delta))
            delt = float(_delta)
            f_model = lambda xv: model_fixed_delta(xv, *popt)

        yfit = _np.asarray(f_model(xx), dtype=float)
        e_meas = _meas_from_model(float(_np.nanmin(xx)), float(_np.nanmax(xx)), f_model)

        # Quality metrics
        try:
            _m = _np.isfinite(yy) & _np.isfinite(yfit)
            _yy = yy[_m]
            _yf = yfit[_m]
            if _yy.size >= 3:
                ss_res = float(_np.sum((_yy - _yf) ** 2))
                ss_tot = float(_np.sum((_yy - float(_np.mean(_yy))) ** 2))
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                rmse = float(_np.sqrt(ss_res / _yy.size))
            else:
                r2 = 0.0
                rmse = float("nan")
        except Exception:
            r2 = 0.0
            rmse = float("nan")

        return {
            "kind": "core_level",
            "marker": "peak",
            "model": "doublet",
            "E_meas": float(e_meas) if _np.isfinite(e_meas) else float(cen1),
            "params": {
                "a1": float(a1),
                "a2": float(a1 * _ratio) if _ratio is not None else float(a2),
                "cen1": float(cen1),
                "cen2": float(cen2),
                "delta": float(abs(float(delt))),
                "ratio": float(_ratio) if _ratio is not None else None,
                "sigma": float(sigma),
                "gamma": float(gamma),
                "b": float(b),
                "c": float(c),
            },
            "quality": {"r2": float(r2), "rmse": float(rmse), "status": "OK", "reasons": []},
            "fit_window": (float(_np.nanmin(xx)), float(_np.nanmax(xx))),
            "fit_x": xx,
            "fit_y": yfit,
        }

    # Single-peak model (Voigt + linear background)
    def model1(xv, amp, cen, sigma, gamma, b, c):
        return _voigt_profile(xv, amp, cen, sigma, gamma) + b + c * xv

    p0 = [amp_guess, cen_guess, 0.15, 0.15, b_guess, 0.0]
    bounds = (
        [0.0, float(_np.nanmin(xx)), 1e-3, 1e-3, -_np.inf, -_np.inf],
        [_np.inf, float(_np.nanmax(xx)), 5.0, 5.0, _np.inf, _np.inf],
    )
    popt, pcov = curve_fit(model1, xx, yy, p0=p0, bounds=bounds, maxfev=20000)
    yfit = model1(xx, *popt)
    cen = float(popt[1])

    f_model = lambda xv: model1(xv, *popt)
    e_meas = _meas_from_model(float(_np.nanmin(xx)), float(_np.nanmax(xx)), f_model)

    # Quality metrics (R2 / RMSE) on the fit window.
    try:
        _m = _np.isfinite(yy) & _np.isfinite(yfit)
        _yy = yy[_m]
        _yf = yfit[_m]
        if _yy.size >= 3:
            ss_res = float(_np.sum((_yy - _yf) ** 2))
            ss_tot = float(_np.sum((_yy - float(_np.mean(_yy))) ** 2))
            r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
            rmse = float(_np.sqrt(ss_res / _yy.size))
        else:
            r2 = 0.0
            rmse = float("nan")
    except Exception:
        r2 = 0.0
        rmse = float("nan")

    return {
        "kind": "core_level",
        "marker": "peak",
        "model": "single",
        "E_meas": float(e_meas) if _np.isfinite(e_meas) else cen,
        "params": {
            "amp": float(popt[0]),
            "cen": cen,
            "sigma": float(popt[2]),
            "gamma": float(popt[3]),
            "b": float(popt[4]),
            "c": float(popt[5]),
        },
        "quality": {"r2": float(r2), "rmse": float(rmse), "status": "OK", "reasons": []},
        "fit_window": (float(_np.nanmin(xx)), float(_np.nanmax(xx))),
        "fit_x": xx,
        "fit_y": yfit,
    }
