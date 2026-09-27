from pathlib import Path
import importlib.util


def _load_source_snapshots_module():
    path = Path("src/maxiv_panda/source_snapshots.py")
    spec = importlib.util.spec_from_file_location("source_snapshots_v01165", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_workflow_use_counts_as_reload_dependency():
    mod = _load_source_snapshots_module()
    summary = mod.SourceDependencySummary(workflow_uses=("normalization",))
    assert summary.has_dependencies
    assert "normalization" in summary.describe()


def test_normalization_records_snapshot_usage():
    source = Path("src/maxiv_panda/processed_controller.py").read_text(encoding="utf-8")
    assert '_mark_source_usage_from_items' in source
    assert '"normalization"' in source


def test_peak_fit_records_snapshot_usage():
    source = Path("src/maxiv_panda/workflows/peakfit/fit_dialog.py").read_text(encoding="utf-8")
    assert '_mark_source_usage_from_payloads' in source
    assert '"peak fitting"' in source


def test_reload_scanner_reads_persisted_workflow_uses():
    source = Path("src/maxiv_panda/ui_source_reload_mixin.py").read_text(encoding="utf-8")
    assert 'source_workflow_uses' in source
    assert 'workflow_uses=workflow_uses' in source


def test_help_describes_processing_aware_reload_policy():
    controls = Path("src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
    assert "normalization, fitting, energy calibration, or Plotted Data" in controls
