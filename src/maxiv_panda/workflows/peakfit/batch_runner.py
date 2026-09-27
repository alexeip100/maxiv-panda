from __future__ import annotations

from typing import Any

import numpy as np

from . import fit_engine, fit_models, so_doublets


def _fit_one_batch_spectrum(self, guess: dict[str, Any]) -> dict[str, Any]:
    """Fit one spectrum independently and return a compact in-memory result object."""
    spectrum_index = int(guess.get("spectrum_index") or 0)
    sequence_key = str(guess.get("sequence_key") or "")
    display = str(guess.get("display") or sequence_key or f"Spectrum {spectrum_index}")
    payload = self._payload_for_batch_spectrum(sequence_key, spectrum_index)
    fit_data, err = self._collect_fit_data_from_payload(payload, sequence_key)
    base = {
        "spectrum_index": spectrum_index,
        "sequence_key": sequence_key,
        "display": display,
        "status": "failed",
        "message": "",
        "fit_state": guess.get("fit_state") or {},
        "fit_quality": {},
        "parameters": {},
        "peaks": [],
        "background": {},
        "bound_hits": [],
        "plot_data": {},
    }
    if fit_data is None:
        base["message"] = err or "No fit data."
        return self._json_clean_value(base)

    fit_state = dict(guess.get("fit_state") or {})
    peak_specs, tie_warnings = self._peak_specs_from_batch_fit_state(fit_state)
    doublets = list(fit_state.get("so_doublets") or [])
    bg_type, bg_values = self._bg_values_from_batch_fit_state(fit_state)
    try:
        energy_scale = str(getattr(fit_data.get("payload"), "energy_scale", "") or "")
    except Exception:
        energy_scale = ""
    err = fit_engine.validate_fit_ready(
        fit_data, peak_specs, bg_type, bool(bg_values.get("bg_alpha_fixed", False)), doublets=doublets
    )
    if err:
        base["message"] = err
        return self._json_clean_value(base)
    try:
        params = fit_engine.build_lmfit_parameters(
            peak_specs, bg_type, bg_values, fit_data, doublets=doublets, energy_scale=energy_scale
        )
        xu = np.asarray(fit_data["xu"], dtype=float)
        yu = np.asarray(fit_data["yu"], dtype=float)

        def residual(params_obj):
            vals = params_obj.valuesdict()
            model_u, _components = self._build_batch_model_from_values(
                xu,
                len(peak_specs),
                bg_type,
                vals,
                measured_y=yu if bg_type == "Shirley" else None,
                energy_scale=energy_scale,
            )
            return model_u - yu

        result = fit_engine.run_lmfit_fit(params, residual, iter_cb=None, max_nfev=3000)
        outcome, detail, bound_hits = fit_engine.classify_fit_outcome(
            result,
            len(peak_specs),
            fit_data=fit_data,
            human_name_fn=self._batch_human_readable_param_name,
        )
        vals = {str(k): float(v) for k, v in result.params.valuesdict().items()}
        model_u, components = self._build_batch_model_from_values(
            xu,
            len(peak_specs),
            bg_type,
            vals,
            measured_y=yu if bg_type == "Shirley" else None,
            energy_scale=energy_scale,
        )
        metrics = fit_engine.compute_fit_quality_metrics(
            result,
            fit_data,
            bg_type,
            lambda x, bg_type, values, measured_y=None, energy_scale="": self._build_batch_model_from_values(
                x,
                len(peak_specs),
                bg_type,
                values,
                measured_y=measured_y,
                energy_scale=energy_scale,
            ),
        )
        # Add user-facing fit-quality diagnostics for the Analyze tab.
        # These are deliberately separated from optimizer diagnostics such as nfev.
        try:
            residual_arr = np.asarray(yu - model_u, dtype=float)
            y_arr = np.asarray(yu, dtype=float)
            finite = np.isfinite(residual_arr) & np.isfinite(y_arr)
            if np.any(finite):
                r = residual_arr[finite]
                yy = y_arr[finite]
                rms_resid = float(np.sqrt(np.mean(r ** 2))) if r.size else float("nan")
                max_abs_resid = float(np.max(np.abs(r))) if r.size else float("nan")
                y_span = float(np.nanmax(yy) - np.nanmin(yy)) if yy.size else float("nan")
                y_scale = y_span if np.isfinite(y_span) and abs(y_span) > 1e-15 else float(np.nanmax(np.abs(yy))) if yy.size else float("nan")
                norm_rms = float(rms_resid / y_scale) if np.isfinite(y_scale) and abs(y_scale) > 1e-15 else float("nan")
                metrics.update({
                    "rms_residual": rms_resid,
                    "norm_rms_residual": norm_rms,
                    "max_abs_residual": max_abs_resid,
                })
        except Exception:
            pass
        result_state_peaks: list[dict[str, Any]] = []
        peak_summary: list[dict[str, Any]] = []
        peak_areas = fit_models.integrated_component_areas(xu, components)
        for i, spec in enumerate(peak_specs, start=1):
            peak_state = {"label": str(spec.get("label") or f"P{i}")}
            peak_row = {"index": i, "label": peak_state["label"]}
            for prefix in ("E", "H", "L", "G", "A"):
                name = f"p{i}_{prefix}"
                value = float(vals.get(name, spec[prefix]))
                peak_state[prefix] = value
                peak_state[f"{prefix}_min"] = float(spec.get(f"{prefix}_min", value))
                peak_state[f"{prefix}_max"] = float(spec.get(f"{prefix}_max", value))
                peak_state[f"{prefix}_mode"] = str(spec.get(f"{prefix}_mode", "Free"))
                if peak_state[f"{prefix}_mode"] == "Tied" and spec.get(f"{prefix}_tie"):
                    peak_state[f"{prefix}_tie_meta"] = self._json_clean_value(spec.get(f"{prefix}_tie"))
                peak_row[prefix] = value
            if i - 1 < len(peak_areas):
                peak_row["Area"] = float(peak_areas[i - 1])
            result_state_peaks.append(peak_state)
            peak_summary.append(peak_row)
        result_doublets: list[dict[str, Any]] = []
        for ordinal, item in enumerate(doublets, start=1):
            st = so_doublets.normalize_state(item, ordinal=ordinal)
            if f"d{ordinal}_split" in vals:
                st["split"] = float(vals[f"d{ordinal}_split"])
            if f"d{ordinal}_ratio" in vals:
                st["ratio"] = float(vals[f"d{ordinal}_ratio"])
            result_doublets.append(st)

        bg_result_state = {
            "bg_type": bg_type,
            "b0": float(vals.get("b0", bg_values.get("b0", 0.0))),
            "b1": float(vals.get("b1", bg_values.get("b1", 0.0))),
            "b2": float(vals.get("b2", bg_values.get("b2", 0.0))),
            "bg_alpha": float(vals.get("bg_alpha", bg_values.get("bg_alpha", 1.0))),
            "bg_alpha_fixed": bool(bg_values.get("bg_alpha_fixed", False)),
            "bg_touched": True,
            "calc_on": True,
        }
        param_summary: dict[str, Any] = {}
        for name, par in result.params.items():
            try:
                param_summary[str(name)] = {
                    "value": float(par.value),
                    "stderr": None if getattr(par, "stderr", None) is None else float(par.stderr),
                    "min": self._json_clean_value(getattr(par, "min", None)),
                    "max": self._json_clean_value(getattr(par, "max", None)),
                    "vary": bool(getattr(par, "vary", False)),
                    "expr": self._json_clean_value(getattr(par, "expr", None)),
                }
            except Exception:
                continue
        messages = []
        if detail:
            messages.append(str(detail))
        messages.extend(tie_warnings)
        status = "failed" if outcome == "failed" else ("warning" if outcome == "warning" or tie_warnings else "success")
        return self._json_clean_value({
            **base,
            "status": status,
            "message": "; ".join(dict.fromkeys(messages)),
            "fit_state": {
                "peak_states": result_state_peaks,
                "so_doublets": result_doublets,
                "bg_state": bg_result_state,
                "fit_table": {},
                "bg_table": {},
                "fit_quality": {**metrics, "n_bound_hits": int(len(bound_hits))},
                "bound_hits": sorted(str(x) for x in bound_hits),
            },
            "fit_quality": {**metrics, "n_bound_hits": int(len(bound_hits))},
            "parameters": param_summary,
            "peaks": peak_summary,
            "background": bg_result_state,
            "bound_hits": sorted(str(x) for x in bound_hits),
            "nfev": int(getattr(result, "nfev", 0) or 0),
            "chisqr": float(getattr(result, "chisqr", np.nan)),
            "redchi": float(getattr(result, "redchi", np.nan)),
            "plot_data": {
                "x": xu.tolist(),
                "y": yu.tolist(),
                "model": np.asarray(model_u, dtype=float).tolist(),
                "residual": np.asarray(yu - model_u, dtype=float).tolist(),
                "components": [np.asarray(c, dtype=float).tolist() for c in components],
                "xlabel": str(getattr(payload, "xlabel", "x") or "x"),
                "ylabel": str(getattr(payload, "ylabel", "Intensity") or "Intensity"),
                "energy_scale": energy_scale,
            },
        })
    except Exception as exc:
        base["message"] = str(exc)
        return self._json_clean_value(base)
