from __future__ import annotations

from datetime import datetime
from typing import Any

def _default_independent_strategy(self) -> dict[str, Any]:
    """Return the default independent-fit strategy/pass recipe."""
    return {
        "id": "strategy_pass_1",
        "pass_id": "pass_1",
        "label": "Pass 1: independent",
        "kind": "independent",
        "source_pass_id": None,
        "constraints": [],
        "start_from": "table_initial_guesses",
        "has_results": bool(self._pass_by_id("pass_1")),
        "description": "Independent fits from Start/Middle/End anchor-derived initial guesses.",
    }

def _reset_batch_pass_workflow(self, *, clear_results: bool = False) -> None:
    """Reset pass/strategy bookkeeping while preserving the editable setup table."""
    if clear_results:
        self._batch_passes = []
        self._active_analyze_pass_id = None
    self._batch_strategies = [self._default_independent_strategy()]
    self._preferred_next_strategy_id = self._batch_strategies[0]["id"]
    self._refresh_strategy_combo()
    self._refresh_pass_status_label()
    try:
        self._refresh_batch_fit_navigation_controls()
    except Exception:
        pass
    try:
        self._refresh_analyze_results_tab()
    except Exception:
        pass

def _pass_by_id(self, pass_id: str | None) -> dict[str, Any] | None:
    if not pass_id:
        return None
    for entry in getattr(self, "_batch_passes", []) or []:
        if str(entry.get("id") or "") == str(pass_id):
            return entry
    return None

def _strategy_by_id(self, strategy_id: str | None) -> dict[str, Any] | None:
    if not strategy_id:
        return None
    for entry in getattr(self, "_batch_strategies", []) or []:
        if str(entry.get("id") or "") == str(strategy_id):
            return entry
    return None

def _current_strategy(self) -> dict[str, Any] | None:
    combo = getattr(self, "cb_batch_strategy", None)
    if combo is not None:
        try:
            strategy_id = combo.currentData()
            strategy = self._strategy_by_id(str(strategy_id))
            if strategy is not None:
                return strategy
        except Exception:
            pass
    strategies = list(getattr(self, "_batch_strategies", []) or [])
    return strategies[0] if strategies else None

def _refresh_strategy_combo(self) -> None:
    combo = getattr(self, "cb_batch_strategy", None)
    if combo is None:
        return
    old_id = None
    try:
        old_id = combo.currentData()
    except Exception:
        pass
    preferred = getattr(self, "_preferred_next_strategy_id", None)
    self._populating_strategy_combo = True
    try:
        combo.blockSignals(True)
        combo.clear()
        for strategy in getattr(self, "_batch_strategies", []) or []:
            sid = str(strategy.get("id") or "")
            label = str(strategy.get("label") or sid or "Unnamed strategy")
            if bool(strategy.get("has_results")):
                label = f"{label}  ✓"
            combo.addItem(label, sid)
        target = preferred or old_id
        if target is not None:
            for i in range(combo.count()):
                if str(combo.itemData(i)) == str(target):
                    combo.setCurrentIndex(i)
                    break
        combo.blockSignals(False)
    finally:
        self._populating_strategy_combo = False

def _on_batch_strategy_changed(self, *_args) -> None:
    if bool(getattr(self, "_populating_strategy_combo", False)):
        return
    self._refresh_pass_status_label()
    self._refresh_batch_run_controls()
    try:
        self._refresh_batch_fit_navigation_controls(select_last=True, replot=True)
    except Exception:
        pass

def _refresh_pass_status_label(self, message: str | None = None) -> None:
    label = getattr(self, "lab_batch_pass_status", None)
    if label is None:
        return
    if message:
        try:
            label.setText(message)
        except Exception:
            pass
        return
    strategy = self._current_strategy()
    if not strategy:
        text = "Pass status: no batch strategy is available."
    else:
        desc = str(strategy.get("description") or "")
        pass_id = str(strategy.get("pass_id") or "")
        existing = self._pass_by_id(pass_id)
        if existing:
            results = list(existing.get("results") or [])
            ok = sum(1 for r in results if str(r.get("status") or "") in {"success", "warning"})
            failed = sum(1 for r in results if str(r.get("status") or "") == "failed")
            text = f"Pass status: {strategy.get('label')} has stored results: {len(results)} spectra ({ok} success/warning, {failed} failed)."
        else:
            text = f"Pass status: ready to run {strategy.get('label')}."
        if desc:
            text += f"\n{desc}"
    try:
        label.setText(text)
    except Exception:
        pass

def _set_active_batch_results(self, results: list[dict[str, Any]], pass_id: str | None = None) -> None:
    """Update backward-compatible result aliases used by existing plotting code."""
    self._batch_fit_results = list(results or [])
    by_key: dict[str, dict[str, Any]] = {}
    for result in self._batch_fit_results:
        key = str(result.get("sequence_key") or "")
        if key:
            by_key[key] = result
    self._batch_fit_results_by_key = by_key
    if pass_id:
        self._active_analyze_pass_id = str(pass_id)

def _current_binning_metadata_for_pass(self, results: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return JSON-compatible binning metadata for a just-completed batch pass."""
    results = list(results or [])
    enabled = False
    bin_size = 1
    discarded = 0
    original_checked = None
    try:
        enabled = bool(self._binned_mode_active())
        bin_size = int(self.sb_bin_size.value()) if hasattr(self, "sb_bin_size") else 1
    except Exception:
        enabled = False
        bin_size = 1
    if enabled and bin_size > 1:
        try:
            _entries, discarded = self._build_binned_entries()
        except Exception:
            discarded = 0
        try:
            original_checked = len(self._checked_sequence_entries_for_mode("original"))
        except Exception:
            original_checked = None
        return self._json_clean_value({
            "enabled": True,
            "bin_size": int(bin_size),
            "original_checked": original_checked,
            "effective_count": len(results),
            "discarded": int(discarded or 0),
        })
    return {
        "enabled": False,
        "bin_size": 1,
        "original_checked": len(results),
        "effective_count": len(results),
        "discarded": 0,
    }

def _store_completed_batch_pass(self, strategy: dict[str, Any], results: list[dict[str, Any]], *, stopped: bool, failed: int, warnings_count: int) -> dict[str, Any]:
    """Store or replace the completed pass object for the executed strategy."""
    pass_id = str(strategy.get("pass_id") or "pass_1")
    pass_obj = {
        "id": pass_id,
        "label": str(strategy.get("label") or pass_id),
        "kind": str(strategy.get("kind") or "independent"),
        "source_pass_id": strategy.get("source_pass_id"),
        "strategy_id": str(strategy.get("id") or ""),
        "constraints": self._json_clean_value(strategy.get("constraints") or []),
        "start_from": str(strategy.get("start_from") or "table_initial_guesses"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "stopped": bool(stopped),
        "store_all_fit_results": bool(getattr(self, "_batch_store_full_results_for_run", False)),
        "summary": {
            "n_results": len(results or []),
            "failed": int(failed),
            "warnings": int(warnings_count),
        },
        "binning": self._current_binning_metadata_for_pass(list(results or [])),
        "results": list(results or []),
    }
    passes = [p for p in (getattr(self, "_batch_passes", []) or []) if str(p.get("id") or "") != pass_id]
    passes.append(pass_obj)
    passes.sort(key=lambda p: str(p.get("id") or ""))
    self._batch_passes = passes
    for strat in getattr(self, "_batch_strategies", []) or []:
        if str(strat.get("id") or "") == str(strategy.get("id") or ""):
            strat["has_results"] = True
    self._set_active_batch_results(list(results or []), pass_id=pass_id)
    self._refresh_strategy_combo()
    self._refresh_pass_status_label()
    return pass_obj

def _selected_analyze_pass(self) -> dict[str, Any] | None:
    combo = getattr(self, "cb_analyze_result_pass", None)
    if combo is not None:
        try:
            pass_id = str(combo.currentData() or "")
            found = self._pass_by_id(pass_id)
            if found is not None:
                return found
        except Exception:
            pass
    active = self._pass_by_id(getattr(self, "_active_analyze_pass_id", None))
    if active is not None:
        return active
    passes = list(getattr(self, "_batch_passes", []) or [])
    return passes[-1] if passes else None

def _selected_analyze_results(self) -> list[dict[str, Any]]:
    selected = self._selected_analyze_pass()
    if selected is not None:
        return list(selected.get("results") or [])
    return list(getattr(self, "_batch_fit_results", []) or [])

def _on_analyze_result_pass_changed(self, *_args) -> None:
    if bool(getattr(self, "_populating_analyze_pass_combo", False)):
        return
    selected = self._selected_analyze_pass()
    if selected is not None:
        self._set_active_batch_results(list(selected.get("results") or []), pass_id=str(selected.get("id") or ""))
    self._refresh_analyze_results_tab()
