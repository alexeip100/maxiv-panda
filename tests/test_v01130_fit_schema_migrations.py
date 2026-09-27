from pathlib import Path

from maxiv_panda.workflows.peakfit import fit_io, fit_schema


ROOT = Path(__file__).resolve().parents[1]


def test_fit_setup_schema_contract_is_centralized_without_version_bump():
    assert fit_schema.FORMAT_NAME == "flexpes_pes_fit_setup"
    assert fit_schema.CURRENT_FORMAT_VERSION == 1
    assert fit_schema.MIN_SUPPORTED_FORMAT_VERSION == 1
    assert fit_io.FORMAT_NAME == fit_schema.FORMAT_NAME
    assert fit_io.FORMAT_VERSION == fit_schema.CURRENT_FORMAT_VERSION


def test_fit_io_routes_loading_through_schema_layer():
    source = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_io.py").read_text(encoding="utf-8")
    assert "fit_schema.canonicalize_fit_setup_payload(data)" in source
    assert "fit_schema.FitSetupSchemaError" in source


def test_schema_layer_has_controlled_future_migration_registry():
    source = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_schema.py").read_text(encoding="utf-8")
    assert "_MIGRATIONS" in source
    assert "while version < CURRENT_FORMAT_VERSION" in source
    assert "migrations must advance one version" in source
