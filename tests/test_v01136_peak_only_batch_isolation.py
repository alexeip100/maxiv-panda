from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"

# The peak-only path remains isolated from SO-doublet policy even as
# path-neutral config/table/runner helpers move into shared cores.


def test_peak_only_runner_contains_only_peak_only_policy():
    src = (PEAKFIT / "batch_peak_only_runner.py").read_text(encoding="utf-8")
    assert "batch_runner_core" not in src
    assert "from . import fit_engine, fit_models" in src
    assert "so_doublets" not in src
    assert "def _fit_one_batch_spectrum" in src


def test_peak_only_config_contains_only_peak_only_policy():
    src = (PEAKFIT / "batch_peak_only_config.py").read_text(encoding="utf-8")
    assert "batch_config_core" not in src
    assert "from . import so_doublets" not in src
    assert "def _build_batch_config_from_table" in src
    assert "def _build_initial_guess_sequence" in src
    assert "model_mode" not in src
    assert "doublet_models" not in src


def test_prepare_mixin_routes_peak_only_and_doublet_tables_to_separate_modules():
    src = (PEAKFIT / "batch_prepare_setup_mixin.py").read_text(encoding="utf-8")
    assert "from . import batch_peak_only_table" in src
    assert "return batch_table_builder if self._use_doublet_batch_path() else batch_peak_only_table" in src
    assert "module = self._batch_table_module()" in src


def test_run_mixin_routes_peak_only_config_to_preserved_legacy_module():
    src = (PEAKFIT / "batch_run_mixin.py").read_text(encoding="utf-8")
    assert "from . import batch_peak_only_config, batch_peak_only_runner" in src
    assert "batch_config if self._use_doublet_batch_path() else batch_peak_only_config" in src
    assert "module = self._batch_config_module()" in src


def test_peak_only_runner_is_selected_when_generated_guess_has_no_doublets():
    src = (PEAKFIT / "batch_run_mixin.py").read_text(encoding="utf-8")
    assert 'has_doublets = bool((((guess or {}).get("fit_state") or {}).get("so_doublets") or []))' in src
    assert "module = batch_runner if has_doublets else batch_peak_only_runner" in src


def test_legacy_peak_only_builder_preserves_manual_tie_text():
    src = (PEAKFIT / "batch_peak_only_table.py").read_text(encoding="utf-8")
    assert '"tie": "; ".join(dict.fromkeys(tie_texts)) if suggested_mode == "Tied" else ""' in src
    assert '"kind": "derived"' not in src
    assert "so_doublets" not in src
