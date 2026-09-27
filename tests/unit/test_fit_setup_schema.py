import json
from pathlib import Path

import pytest

from maxiv_panda.workflows.peakfit import fit_io, fit_schema


ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/data/reference/peak_fitting/ir111_ir4f_clean_170ev/fit_setup.json"


def test_current_schema_contract_remains_v1_until_real_schema_change():
    assert fit_schema.FORMAT_NAME == "flexpes_pes_fit_setup"
    assert fit_schema.CURRENT_FORMAT_VERSION == 1
    assert fit_io.FORMAT_VERSION == fit_schema.CURRENT_FORMAT_VERSION


def test_historical_v1_envelope_canonicalizes_without_semantic_change():
    original = json.loads(REFERENCE.read_text(encoding="utf-8"))
    canonical = fit_schema.canonicalize_fit_setup_payload(original)
    assert canonical["format"] == original["format"]
    assert canonical["format_version"] == 1
    assert canonical["metadata"] == original["metadata"]
    assert canonical["fit_setup"] == original["fit_setup"]


def test_raw_legacy_dictionary_is_wrapped_as_implicit_v1():
    raw = {"peak_states": [{"E": 61.0, "label": "P1"}], "bg_state": {"bg_type": "linear"}}
    canonical = fit_schema.canonicalize_fit_setup_payload(raw)
    assert canonical == {
        "format": "flexpes_pes_fit_setup",
        "format_version": 1,
        "metadata": {},
        "fit_setup": raw,
    }


def test_future_format_version_is_rejected_with_clear_message(tmp_path):
    payload = {
        "format": fit_schema.FORMAT_NAME,
        "format_version": 999,
        "metadata": {},
        "fit_setup": {"peak_states": [], "bg_state": {}},
    }
    path = tmp_path / "future.fit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="newer PANDA release"):
        fit_io.load_fit_setup_json(path)


def test_missing_or_invalid_version_in_wrapped_file_is_rejected():
    base = {"format": fit_schema.FORMAT_NAME, "metadata": {}, "fit_setup": {}}
    with pytest.raises(fit_schema.FitSetupSchemaError, match="format_version"):
        fit_schema.canonicalize_fit_setup_payload(base)
    with pytest.raises(fit_schema.FitSetupSchemaError, match="format_version"):
        fit_schema.canonicalize_fit_setup_payload({**base, "format_version": "nope"})


def test_wrong_envelope_is_not_treated_as_raw_fit_setup():
    with pytest.raises(fit_schema.FitSetupSchemaError, match="does not look like"):
        fit_schema.canonicalize_fit_setup_payload({"format": "something_else", "format_version": 1})
