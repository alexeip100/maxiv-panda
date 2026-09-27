from __future__ import annotations

import re
from typing import Any

import numpy as np
from matplotlib.ticker import FuncFormatter, MaxNLocator
from PyQt6.QtWidgets import QApplication
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from . import fit_constraints, fit_engine, fit_models

def _request_stop_batch_fit(self, *args, **kwargs) -> None:
    """Ask the batch runner to stop after the current spectrum."""
    self._batch_fit_cancel_requested = True
    try:
        self.lab_batch_run_status.setText("Stopping after the current spectrum...")
    except Exception:
        pass

def _payload_for_batch_spectrum(self, spectrum_key: str, fallback_index: int) -> Any | None:
    """Return the current payload for a generated batch spectrum."""
    entries = self._effective_checked_entries_from_tree()
    if spectrum_key:
        for entry in entries:
            if str(entry.get("key") or "") == str(spectrum_key):
                return entry.get("payload")
    try:
        return entries[int(fallback_index) - 1].get("payload")
    except Exception:
        return None

def _collect_fit_data_from_payload(self, payload: Any, spectrum_key: str = "") -> tuple[dict[str, Any] | None, str | None]:
    """Clean one payload into the same fit-data structure used by the single-curve fitter."""
    if payload is None or getattr(payload, "x", None) is None or getattr(payload, "y", None) is None:
        return None, "Selected spectrum has no data."
    try:
        x_raw = np.asarray(payload.x, dtype=float)
        y_raw = np.asarray(payload.y, dtype=float)
    except Exception:
        return None, "Selected spectrum could not be converted to numeric arrays."
    mask = np.isfinite(x_raw) & np.isfinite(y_raw)
    x_raw = x_raw[mask]
    y_raw = y_raw[mask]
    if x_raw.size < 5 or y_raw.size < 5:
        return None, "Spectrum has too few valid data points for fitting."
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
    return {"payload": payload, "x": x, "y": y, "xu": xu, "yu": yu, "key": spectrum_key}, None

def _batch_human_readable_param_name(self, param_name: str) -> str:
    return fit_engine.human_readable_param_name(str(param_name or ""))

def _resolve_batch_tie_meta(self, peaks: list[dict[str, Any]], peak_index: int, prefix: str, tie_text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse a table tie string and convert it to lmfit tie metadata."""
    text = str(tie_text or "").strip()
    target = fit_constraints.parse_tie_target(prefix, text)
    if target is None:
        m = re.search(r"_(\d+)\b", text)
        if m:
            try:
                target = int(m.group(1))
            except Exception:
                target = None
    if target is None or target < 1 or target > len(peaks) or target == int(peak_index):
        return None, f"Peak {peak_index} {prefix}: could not parse tie target from '{text}'."
    try:
        source_value = float(peaks[int(peak_index) - 1][prefix])
        target_value = float(peaks[int(target) - 1][prefix])
        return fit_constraints.compute_tie_relation(prefix, source_value, target_value, int(target)), None
    except Exception as exc:
        return None, f"Peak {peak_index} {prefix}: invalid tie relation ({exc})."

def _peak_specs_from_batch_fit_state(self, fit_state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Convert generated peak states to fit_engine peak specs."""
    peak_states = list((fit_state or {}).get("peak_states") or [])
    specs: list[dict[str, Any]] = []
    warnings: list[str] = []
    for idx, state in enumerate(peak_states, start=1):
        spec: dict[str, Any] = {"label": str(state.get("label") or f"P{idx}")}
        for prefix in ("E", "H", "L", "G", "A"):
            spec[prefix] = float(state[prefix])
            spec[f"{prefix}_min"] = float(state.get(f"{prefix}_min", spec[prefix]))
            spec[f"{prefix}_max"] = float(state.get(f"{prefix}_max", spec[prefix]))
            mode = str(state.get(f"{prefix}_mode") or "Free")
            if mode not in {"Free", "Fixed", "Tied"}:
                mode = "Free"
            if mode == "Tied":
                existing_tie = state.get(f"{prefix}_tie_meta")
                if isinstance(existing_tie, dict) and existing_tie.get("target"):
                    tie_meta, err = existing_tie, None
                else:
                    tie_meta, err = self._resolve_batch_tie_meta(peak_states, idx, prefix, str(state.get(f"{prefix}_tie_text") or ""))
                if err or tie_meta is None:
                    warnings.append(err or f"Peak {idx} {prefix}: invalid tie; fitted as Fixed.")
                    mode = "Fixed"
                    tie_meta = None
                spec[f"{prefix}_tie"] = tie_meta
            else:
                spec[f"{prefix}_tie"] = None
            spec[f"{prefix}_mode"] = mode
        specs.append(spec)
    return specs, warnings

def _bg_values_from_batch_fit_state(self, fit_state: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    bg_state = dict((fit_state or {}).get("bg_state") or {})
    bg_type = str(bg_state.get("bg_type") or "constant")
    return bg_type, {
        "b0": float(bg_state.get("b0", 0.0)),
        "b1": float(bg_state.get("b1", 0.0)),
        "b2": float(bg_state.get("b2", 0.0)),
        "bg_alpha": float(bg_state.get("bg_alpha", 1.0)),
        "bg_alpha_fixed": bool(bg_state.get("bg_alpha_fixed", False)),
    }

def _build_batch_model_from_values(self, xu: Any, peak_count: int, bg_type: str, values: dict[str, float], measured_y: Any = None, energy_scale: str = "") -> tuple[np.ndarray, list[np.ndarray]]:
    peaks = []
    for i in range(1, int(peak_count) + 1):
        peaks.append({
            "E": float(values[f"p{i}_E"]),
            "H": float(values[f"p{i}_H"]),
            "L": float(values[f"p{i}_L"]),
            "G": float(values[f"p{i}_G"]),
            "A": float(values[f"p{i}_A"]),
        })
    bg_params = {
        "b0": float(values.get("b0", 0.0)),
        "b1": float(values.get("b1", 0.0)),
        "b2": float(values.get("b2", 0.0)),
        "bg_alpha": float(values.get("bg_alpha", 1.0)),
    }
    return fit_models.build_model_from_values(xu, peaks, bg_type, bg_params, measured_y=measured_y, energy_scale=energy_scale)

def _update_batch_monitor_plot(self, result_obj: dict[str, Any] | None = None) -> None:
    """Show the latest fitted spectrum, components and residual in the monitor plot."""
    plot = getattr(self, "plot_batch_monitor", None)
    if plot is None:
        return
    results = list(getattr(self, "_batch_fit_results", []) or [])
    if result_obj is None and results:
        result_obj = results[-1]
    if result_obj is None:
        plot.clear("Batch fit monitor: run a sequence fit to see live results")
        self._style_prepare_plot_area(plot)
        self._compact_plot_margins(plot)
        return
    data = result_obj.get("plot_data") or {}
    try:
        x = np.asarray(data.get("x") or [], dtype=float)
        y = np.asarray(data.get("y") or [], dtype=float)
        model = np.asarray(data.get("model") or [], dtype=float)
        resid = np.asarray(data.get("residual") or [], dtype=float)
        components = [np.asarray(c, dtype=float) for c in (data.get("components") or [])]
    except Exception:
        x = y = model = resid = np.asarray([], dtype=float)
        components = []

    plot.fig.clear()
    if x.size and model.size and resid.size:
        # Use the full canvas height with an 80:20 main/residual split.
        gs = plot.fig.add_gridspec(2, 1, height_ratios=[4, 1], hspace=0.078125)
        ax = plot.fig.add_subplot(gs[0, 0])
        ax2 = plot.fig.add_subplot(gs[1, 0], sharex=ax)
    else:
        ax = plot.fig.add_subplot(111)
        ax2 = None
    plot.ax = ax

    if x.size and y.size:
        ax.plot(x, y, linewidth=1.0, label="data")
    elif not x.size:
        ax.text(0.5, 0.5, "No stored fit curves for this spectrum", transform=ax.transAxes, ha="center", va="center")
    if x.size and components:
        for j, comp in enumerate(components, start=1):
            if comp.size == x.size:
                label = f"P{j}" if j <= 8 else None
                ax.plot(x, comp, linewidth=0.9, linestyle="--", alpha=0.85, label=label)
    if x.size and model.size:
        ax.plot(x, model, linewidth=1.7, label="fit", zorder=10)

    done = len(results)
    try:
        for _pos, _res in enumerate(results, start=1):
            if _res is result_obj or (
                int(_res.get("spectrum_index") or -1) == int(result_obj.get("spectrum_index") or -2)
                and str(_res.get("sequence_key") or "") == str(result_obj.get("sequence_key") or "")
            ):
                done = _pos
                break
    except Exception:
        pass
    total = int(getattr(self, "_batch_run_total", 0) or len(results) or len(getattr(self, "_batch_initial_guesses", []) or []))
    status = str(result_obj.get("status") or "")
    title = str(result_obj.get("display") or result_obj.get("sequence_key") or "Spectrum")
    ax.set_title(f"{done}/{total}: {title} [{status}]", fontsize=9)
    ax.set_ylabel(str(data.get("ylabel") or "Intensity"))
    try:
        if x.size and (model.size or components):
            ax.legend(loc="best", fontsize=8, ncol=2)
    except Exception:
        pass

    xlabel = str(data.get("xlabel") or "x")
    scale = str(data.get("energy_scale") or "").lower()
    should_flip = bool(scale.startswith("bind") or scale in {"be", "binding"} or "binding" in xlabel.lower())
    if x.size:
        xlo = float(np.nanmin(x))
        xhi = float(np.nanmax(x))
        if should_flip:
            ax.set_xlim(xhi, xlo)
        else:
            ax.set_xlim(xlo, xhi)

    if ax2 is not None and x.size and resid.size:
        ax2.axhline(0.0, linewidth=0.8, linestyle="--")
        ax2.plot(x, resid, linewidth=0.9)
        ax2.set_ylabel("Residual")
        ax2.set_xlabel(xlabel)
        try:
            ax.tick_params(axis="x", labelbottom=False)
        except Exception:
            pass
    else:
        ax.set_xlabel(xlabel)

    def _force_scientific_y_axis(_axis):
        """Use scientific scaling with integer mantissa tick labels.

        Matplotlib's standard ScalarFormatter can still produce decimal
        mantissas such as 0.5 or 2.5 depending on the data range.  For the
        batch monitor we prefer the same compact scientific style on both
        stacked axes, but with integer labels only (e.g. 0, 2, 4 and a
        displayed multiplier).
        """
        if _axis is None:
            return
        try:
            ylo, yhi = _axis.get_ylim()
            vals = np.asarray([ylo, yhi], dtype=float)
            finite = vals[np.isfinite(vals)]
            max_abs = float(np.max(np.abs(finite))) if finite.size else 0.0
            if max_abs <= 0.0:
                max_abs = 1.0
            exp = int(np.floor(np.log10(max_abs)))
            # If the largest value would scale to ~1, shift the exponent down
            # so there is enough room for several integer mantissa ticks.
            if max_abs / (10.0 ** exp) < 2.0:
                exp -= 1
            scale = 10.0 ** exp
            scaled_lo = ylo / scale
            scaled_hi = yhi / scale
            locator = MaxNLocator(nbins=5, integer=True, min_n_ticks=3)
            ticks_scaled = locator.tick_values(scaled_lo, scaled_hi)
            lo, hi = sorted((scaled_lo, scaled_hi))
            ticks_scaled = [t for t in ticks_scaled if lo - 1e-9 <= t <= hi + 1e-9]
            if len(ticks_scaled) >= 2:
                _axis.set_yticks([t * scale for t in ticks_scaled])
            _axis.yaxis.set_major_formatter(FuncFormatter(lambda v, pos, _s=scale: f"{v / _s:.0f}"))
            _axis.yaxis.get_offset_text().set_visible(False)
            _axis.tick_params(axis="y", labelsize=9)
            _axis.text(0.0, 1.01, rf"$\times 10^{{{exp}}}$",
                       transform=_axis.transAxes, ha="left", va="bottom", fontsize=9)
        except Exception:
            formatter = FuncFormatter(lambda v, pos: f"{v:.0e}")
            _axis.yaxis.set_major_formatter(formatter)
            _axis.tick_params(axis="y", labelsize=9)

    try:
        # Force scientific Y-axis notation on both stacked monitor axes.
        # Matplotlib's ticklabel_format/scilimits can still switch back to
        # plain labels for values below ~1e3, so use a ScalarFormatter with
        # powerlimits=(0, 0) instead.
        for _axis in (ax, ax2):
            _force_scientific_y_axis(_axis)
    except Exception:
        pass

    try:
        # Avoid tight_layout here: it reserves too much vertical whitespace
        # around two stacked axes. These margins let the plots occupy almost
        # all available canvas height while preserving axis labels.
        plot.fig.subplots_adjust(left=0.10, right=0.985, top=0.93, bottom=0.060, hspace=0.078125)
    except Exception:
        pass
    self._style_prepare_plot_area(plot)
    try:
        # _style_prepare_plot_area() may touch plot.ax (the main axis); reapply
        # forced scientific formatting afterwards to keep both axes consistent.
        for _axis in (ax, ax2):
            _force_scientific_y_axis(_axis)
    except Exception:
        pass
    try:
        plot.canvas.draw_idle()
    except Exception:
        pass

def _result_has_full_plot_data(result_obj: dict[str, Any] | None) -> bool:
    data = dict((result_obj or {}).get("plot_data") or {})
    try:
        return bool(data.get("x") and data.get("y") and data.get("model") and data.get("residual"))
    except Exception:
        return False

def _selected_run_pass(self) -> dict[str, Any] | None:
    strategy = self._current_strategy()
    if strategy is not None:
        # Navigation on the Run tab follows the strategy selected there. If
        # that pass has not been run yet, do not silently browse another pass.
        return self._pass_by_id(str(strategy.get("pass_id") or ""))
    return self._pass_by_id(getattr(self, "_active_analyze_pass_id", None))

def _refresh_batch_fit_navigation_controls(self, *, select_last: bool = False, replot: bool = False) -> None:
    """Enable post-run fit browsing when the selected pass retained full curve data."""
    prev_btn = getattr(self, "btn_batch_fit_prev", None)
    next_btn = getattr(self, "btn_batch_fit_next", None)
    spin = getattr(self, "sb_batch_fit_nav", None)
    total_lab = getattr(self, "lab_batch_fit_nav_total", None)
    detail_lab = getattr(self, "lab_batch_fit_nav_detail", None)
    if spin is None:
        return
    pass_obj = self._selected_run_pass()
    results = list((pass_obj or {}).get("results") or [])
    stored = bool((pass_obj or {}).get("store_all_fit_results", False))
    navigable = bool(results and stored and any(_result_has_full_plot_data(r) for r in results)) and not bool(getattr(self, "_batch_fit_running", False))
    if total_lab is not None:
        total_lab.setText(f"/ {len(results)}" if results else "/ 0")
    try:
        spin.blockSignals(True)
        spin.setRange(1, max(1, len(results)))
        if navigable:
            if select_last or int(getattr(self, "_batch_fit_nav_index", -1)) < 0 or int(getattr(self, "_batch_fit_nav_index", -1)) >= len(results):
                self._batch_fit_nav_index = len(results) - 1
            spin.setValue(int(self._batch_fit_nav_index) + 1)
        else:
            self._batch_fit_nav_index = -1
            spin.setValue(1)
        spin.setEnabled(navigable)
        spin.blockSignals(False)
    except Exception:
        pass
    idx = int(getattr(self, "_batch_fit_nav_index", -1))
    if prev_btn is not None:
        prev_btn.setEnabled(bool(navigable and idx > 0))
    if next_btn is not None:
        next_btn.setEnabled(bool(navigable and idx >= 0 and idx < len(results) - 1))
    if detail_lab is not None:
        if navigable and 0 <= idx < len(results):
            result = results[idx]
            status = str(result.get("status") or "")
            display = str(result.get("display") or result.get("sequence_key") or "")
            detail_lab.setText(f"{display} [{status}]" if display else status)
        elif results and not stored:
            detail_lab.setText("Full fit results were not stored")
        else:
            detail_lab.setText("")
    if replot and navigable and 0 <= idx < len(results):
        self._set_active_batch_results(results, pass_id=str((pass_obj or {}).get("id") or ""))
        self._update_batch_monitor_plot(results[idx])

def _on_batch_fit_navigation_changed(self, value: int) -> None:
    if bool(getattr(self, "_batch_fit_running", False)):
        return
    pass_obj = self._selected_run_pass()
    results = list((pass_obj or {}).get("results") or [])
    idx = int(value) - 1
    if idx < 0 or idx >= len(results):
        return
    self._batch_fit_nav_index = idx
    self._set_active_batch_results(results, pass_id=str((pass_obj or {}).get("id") or ""))
    self._update_batch_monitor_plot(results[idx])
    self._refresh_batch_fit_navigation_controls()

def _step_batch_fit_navigation(self, delta: int) -> None:
    spin = getattr(self, "sb_batch_fit_nav", None)
    if spin is None or not spin.isEnabled():
        return
    target = max(spin.minimum(), min(spin.maximum(), int(spin.value()) + int(delta)))
    spin.setValue(target)

def _confirm_run_strategy(self, strategy: dict[str, Any]) -> bool:
    """Warn before running a non-preferred or already-completed strategy."""
    sid = str(strategy.get("id") or "")
    preferred = str(getattr(self, "_preferred_next_strategy_id", None) or "")
    if preferred and sid != preferred:
        preferred_strategy = self._strategy_by_id(preferred) or {}
        reply = QMessageBox.question(
            self,
            "Run selected strategy?",
            "You are about to run a strategy that is not the currently prepared/default next pass.\n\n"
            f"Selected strategy:\n{strategy.get('label') or sid}\n\n"
            f"Recommended next strategy:\n{preferred_strategy.get('label') or preferred}\n\n"
            "Continue with the selected strategy?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Ok:
            return False
    if bool(strategy.get("has_results")) or self._pass_by_id(str(strategy.get("pass_id") or "")) is not None:
        reply = QMessageBox.question(
            self,
            "Replace existing pass results?",
            f"{strategy.get('label') or sid} already has stored results.\n\n"
            "Rerun this strategy and replace the existing results?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Ok:
            return False
    return True

def _run_selected_batch_strategy(self, *args, **kwargs) -> None:
    """Run the currently selected batch strategy/pass recipe."""
    strategy = self._current_strategy()
    if strategy is None:
        QMessageBox.warning(self, "Run batch fit", "No batch strategy is available.")
        return
    if not self._confirm_run_strategy(strategy):
        return
    kind = str(strategy.get("kind") or "independent")
    if kind == "independent":
        self._run_independent_batch_fit(strategy)
        return
    if kind == "constrained":
        self._run_constrained_batch_fit(strategy)
        return
    QMessageBox.warning(self, "Run batch fit", f"Unsupported batch strategy kind: {kind}")

def _run_independent_batch_fit(self, strategy: dict[str, Any] | None = None) -> None:
    """Run independent fits for all spectra and store results as a completed pass."""
    if getattr(self, "_batch_fit_running", False):
        return
    if strategy is None:
        strategy = self._current_strategy() or self._default_independent_strategy()
    # Make the Validate button redundant: Run always validates, rebuilds the
    # JSON-compatible config and regenerates per-spectrum initial guesses first.
    if not self._validate_and_build_batch_config(show_messages=False):
        QMessageBox.warning(self, "Run batch fit", "The batch setup is not valid. Please correct the table entries shown in the yellow notes box and run again.")
        self._refresh_batch_run_controls()
        return
    guesses = list(getattr(self, "_batch_initial_guesses", []) or [])
    if not guesses:
        QMessageBox.warning(self, "Run batch fit", "No initial guesses are available after validation.")
        return
    self._run_batch_fit_from_guesses(strategy, guesses)

def _constraint_value_map(self, constraint: dict[str, Any]) -> dict[int, float]:
    values: dict[int, float] = {}
    for entry in list(constraint.get("values_by_spectrum") or []):
        try:
            idx = int(entry.get("spectrum_index"))
            val = float(entry.get("value"))
        except Exception:
            continue
        if np.isfinite(val):
            values[idx] = val
    return values

def _apply_constraints_to_fit_state(self, fit_state: dict[str, Any], constraints: list[dict[str, Any]], spectrum_index: int) -> tuple[dict[str, Any], list[str]]:
    """Apply smooth-trend constraints to one source-pass fit_state."""
    state = self._json_clean_value(fit_state or {})
    warnings: list[str] = []
    peaks = list(state.get("peak_states") or [])
    bg_state = dict(state.get("bg_state") or {})
    for constraint in constraints:
        values = self._constraint_value_map(constraint)
        if spectrum_index not in values:
            warnings.append(f"No desired value for {constraint.get('target_label') or constraint.get('target_key')} at spectrum {spectrum_index}; constraint skipped.")
            continue
        desired = float(values[spectrum_index])
        target = constraint.get("target") or {}
        payload = target.get("payload") if isinstance(target, dict) else None
        if payload is None and isinstance(target, dict):
            payload = target
        payload = payload or {}
        kind = str(payload.get("kind") or "")
        if kind == "peak":
            try:
                peak_index = int(payload.get("index"))
            except Exception:
                warnings.append(f"Invalid peak target for {constraint.get('label') or constraint.get('target_key')}; constraint skipped.")
                continue
            prefix = str(payload.get("param") or "")
            if prefix not in {"E", "H", "L", "G", "A"}:
                warnings.append(f"Unsupported peak parameter {prefix} in {constraint.get('label') or constraint.get('target_key')}; constraint skipped.")
                continue
            if peak_index < 1 or peak_index > len(peaks):
                warnings.append(f"Peak P{peak_index} is not available in spectrum {spectrum_index}; constraint skipped.")
                continue
            peak = dict(peaks[peak_index - 1])
            peak[prefix] = desired
            peak[f"{prefix}_mode"] = "Fixed"
            peak[f"{prefix}_constraint"] = self._json_clean_value({
                "source": constraint.get("label") or constraint.get("target_label") or constraint.get("target_key"),
                "value": desired,
                "mode": "fixed",
            })
            peaks[peak_index - 1] = peak
        elif kind == "background" and str(payload.get("param") or "") == "bg_alpha":
            bg_state["bg_alpha"] = desired
            bg_state["bg_alpha_fixed"] = True
        else:
            warnings.append(
                f"Constraint {constraint.get('label') or constraint.get('target_key')} is not executable yet; only peak parameters and Shirley alpha can be fixed in constrained passes."
            )
    state["peak_states"] = peaks
    state["bg_state"] = bg_state
    return self._json_clean_value(state), warnings

def _build_constrained_guesses_from_strategy(self, strategy: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Create per-spectrum guesses from a source pass and smooth constraints."""
    warnings: list[str] = []
    source_pass_id = str(strategy.get("source_pass_id") or "")
    source_pass = self._pass_by_id(source_pass_id)
    if source_pass is None:
        return [], [f"Source pass is not available in memory: {source_pass_id or '(none)'}"]
    constraints = [c for c in list(strategy.get("constraints") or []) if bool(c.get("enabled", True))]
    if not constraints:
        return [], ["The constrained strategy has no enabled constraints."]
    guesses: list[dict[str, Any]] = []
    label = str(strategy.get("label") or "constrained pass")
    for result in list(source_pass.get("results") or []):
        status = str(result.get("status") or "")
        if status == "failed":
            warnings.append(f"Using failed source result for spectrum {result.get('spectrum_index')}; fit may fail again.")
        try:
            spectrum_index = int(result.get("spectrum_index") or 0)
        except Exception:
            spectrum_index = len(guesses) + 1
        fit_state = result.get("fit_state") or {}
        constrained_state, state_warnings = self._apply_constraints_to_fit_state(fit_state, constraints, spectrum_index)
        warnings.extend(state_warnings)
        guesses.append(self._json_clean_value({
            "spectrum_index": spectrum_index,
            "sequence_key": str(result.get("sequence_key") or ""),
            "display": str(result.get("display") or result.get("sequence_key") or f"Spectrum {spectrum_index}"),
            "source_pass_id": source_pass_id,
            "source_status": status,
            "strategy_id": str(strategy.get("id") or ""),
            "strategy_label": label,
            "fit_state": constrained_state,
            "constraint_warnings": list(state_warnings),
        }))
    guesses.sort(key=lambda g: int(g.get("spectrum_index") or 0))
    if not guesses:
        warnings.append("The source pass contains no spectra to refit.")
    return guesses, warnings

def _run_constrained_batch_fit(self, strategy: dict[str, Any]) -> None:
    """Run a constrained pass using selected source-pass results as starting values."""
    if getattr(self, "_batch_fit_running", False):
        return
    guesses, warnings = self._build_constrained_guesses_from_strategy(strategy)
    if warnings:
        # Only block when no runnable guesses exist.  Non-critical per-spectrum
        # warnings are stored and fitting can continue.
        if not guesses:
            QMessageBox.warning(self, "Run constrained pass", "\n".join(warnings[:8]))
            return
        try:
            self.lab_batch_run_status.setText("Constrained-pass warnings: " + "; ".join(warnings[:3]))
        except Exception:
            pass
    if not guesses:
        QMessageBox.warning(self, "Run constrained pass", "No spectra are available for this constrained strategy.")
        return
    self._run_batch_fit_from_guesses(strategy, guesses, preflight_warnings=warnings)

def _run_batch_fit_from_guesses(self, strategy: dict[str, Any], guesses: list[dict[str, Any]], preflight_warnings: list[str] | None = None) -> None:
    """Common execution loop for independent and constrained batch passes."""
    if getattr(self, "_batch_fit_running", False):
        return
    self._set_active_batch_results([], pass_id=str(strategy.get("pass_id") or "pass_1"))
    try:
        self._batch_store_full_results_for_run = bool(self.chk_batch_store_all_results.isChecked())
    except Exception:
        self._batch_store_full_results_for_run = False
    self._batch_fit_running = True
    self._batch_fit_cancel_requested = False
    self._batch_fit_nav_index = -1
    self._batch_run_total = len(guesses)
    self._refresh_batch_run_controls()
    label = str(strategy.get("label") or "Batch pass")
    constraint_text = self._constraint_compact_list(list(strategy.get("constraints") or [])) if str(strategy.get("kind") or "") == "constrained" else "none"
    try:
        self.progress_batch_fit.setRange(0, len(guesses))
        self.progress_batch_fit.setValue(0)
        self.lab_batch_run_status.setText(f"Running {label}: 0/{len(guesses)}")
        if str(strategy.get("kind") or "") == "constrained":
            self._refresh_pass_status_label(
                f"Pass status: running {label}.\nSource: {strategy.get('source_pass_label') or strategy.get('source_pass_id')}.\nConstraints: {constraint_text}.\nSpectrum 0/{len(guesses)}."
            )
        else:
            self._refresh_pass_status_label(f"Pass status: running {label}.\nSpectrum 0/{len(guesses)}.")
    except Exception:
        pass
    try:
        QApplication.processEvents()
    except Exception:
        pass
    completed = 0
    failed = 0
    warnings_count = 0
    run_results: list[dict[str, Any]] = []
    try:
        for i, guess in enumerate(guesses, start=1):
            if getattr(self, "_batch_fit_cancel_requested", False):
                break
            try:
                display = guess.get("display") or guess.get("sequence_key") or ""
                self.lab_batch_run_status.setText(f"{label}: fitting spectrum {i}/{len(guesses)}: {display}")
                if str(strategy.get("kind") or "") == "constrained":
                    self._refresh_pass_status_label(
                        f"Pass status: running {label}.\nSource: {strategy.get('source_pass_label') or strategy.get('source_pass_id')}.\nConstraints: {constraint_text}.\nSpectrum {i}/{len(guesses)}."
                    )
                else:
                    self._refresh_pass_status_label(f"Pass status: running {label}.\nSpectrum {i}/{len(guesses)}.")
            except Exception:
                pass
            result_obj = self._fit_one_batch_spectrum(guess)
            # Preserve non-critical constraint/preflight warnings in the result.
            extra_warnings = list(guess.get("constraint_warnings") or [])
            if extra_warnings:
                msg = str(result_obj.get("message") or "")
                merged = "; ".join([m for m in [msg] + extra_warnings if m])
                result_obj["message"] = merged
                if str(result_obj.get("status") or "") == "success":
                    result_obj["status"] = "warning"
            # Full curve arrays are retained only when explicitly requested.
            # Keep the current full result temporarily for live/final preview even
            # in the lightweight default mode, then store only compact summaries.
            if bool(getattr(self, "_batch_store_full_results_for_run", False)):
                stored_result = result_obj
            else:
                stored_result = dict(result_obj)
                stored_result["plot_data"] = {}
            run_results.append(stored_result)
            self._set_active_batch_results(run_results, pass_id=str(strategy.get("pass_id") or "pass_1"))
            completed += 1
            if result_obj.get("status") == "failed":
                failed += 1
            elif result_obj.get("status") == "warning":
                warnings_count += 1
            try:
                self.progress_batch_fit.setValue(completed)
            except Exception:
                pass
            if bool(self.chk_batch_live_preview.isChecked()) or completed == len(guesses):
                self._update_batch_monitor_plot(result_obj)
            try:
                self.lab_batch_run_status.setText(
                    f"{label}: fitted {completed}/{len(guesses)} spectra; failures: {failed}; warnings: {warnings_count}."
                )
                QApplication.processEvents()
            except Exception:
                pass
    finally:
        self._batch_fit_running = False
        stopped = bool(getattr(self, "_batch_fit_cancel_requested", False)) and completed < len(guesses)
        self._batch_fit_cancel_requested = False
        self._store_completed_batch_pass(strategy, run_results, stopped=stopped, failed=failed, warnings_count=warnings_count)
        if str(strategy.get("id") or "") == str(getattr(self, "_preferred_next_strategy_id", None) or ""):
            self._preferred_next_strategy_id = str(strategy.get("id") or "")
        try:
            if stopped:
                msg = f"Stopped {label} after {completed}/{len(guesses)} spectra; failures: {failed}; warnings: {warnings_count}. Results kept in memory."
                self.lab_batch_run_status.setText(msg)
                self._refresh_pass_status_label(f"Pass status: {msg}")
            else:
                msg = f"Completed {label}: {completed} spectra fitted; failures: {failed}; warnings: {warnings_count}. Results stored in memory."
                self.lab_batch_run_status.setText(msg)
                self._refresh_pass_status_label(f"Pass status: {msg}")
        except Exception:
            pass
        try:
            self._refresh_analyze_results_tab()
        except Exception:
            pass
        self._batch_fit_nav_index = len(run_results) - 1 if run_results else -1
        try:
            self._refresh_batch_fit_navigation_controls(select_last=True, replot=bool(getattr(self, "_batch_store_full_results_for_run", False)))
        except Exception:
            pass
        self._refresh_batch_run_controls()
        try:
            QApplication.processEvents()
        except Exception:
            pass
