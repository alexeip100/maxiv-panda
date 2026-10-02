from pathlib import Path

from maxiv_panda.workflows.peakfit import fit_io
from maxiv_panda.workflows.peakfit.state_models import FitSetupState

ROOT = Path(__file__).resolve().parents[1]


def _setup_with_range():
    return {
        "peak_states": [],
        "so_doublets": [],
        "bg_state": {"bg_type": "linear"},
        "fit_range": [81.25, 86.75],
    }


def test_fit_setup_state_preserves_optional_fit_range():
    setup = _setup_with_range()
    assert FitSetupState.from_mapping(setup).to_mapping()["fit_range"] == [81.25, 86.75]


def test_fit_setup_json_round_trip_preserves_fit_range(tmp_path):
    path = tmp_path / "range.fit.json"
    fit_io.save_fit_setup_json(path, _setup_with_range(), metadata={"curve_label": "test"})
    loaded, metadata = fit_io.load_fit_setup_json(path)
    assert loaded["fit_range"] == [81.25, 86.75]
    assert metadata["curve_label"] == "test"


def test_fit_setup_dialog_capture_and_apply_include_fit_range():
    source = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_dialog_state_mixin.py").read_text(encoding="utf-8")
    capture = source[source.index("def _capture_fit_setup_template"):source.index("def _apply_fit_setup_template")]
    apply = source[source.index("def _apply_fit_setup_template"):source.index("def _delete_peak_by_index")]
    assert '"fit_range": list(fit_range) if fit_range is not None else None' in capture
    assert 'raw_range = state.get("fit_range")' in apply
    assert 'self._fit_range = restored_range' in apply
    assert 'self._refresh_fit_range_artists()' in apply


def test_legacy_setup_without_fit_range_still_normalizes():
    legacy = {"peak_states": [], "so_doublets": [], "bg_state": {}}
    normalized = FitSetupState.from_mapping(legacy).to_mapping()
    assert "fit_range" not in normalized


def test_exported_parameter_json_includes_current_fit_range_source():
    source = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_export.py").read_text(encoding="utf-8")
    assert 'fit_range = dialog._current_fit_range()' in source
    assert '"fit_range_eV": _clean_for_json(list(fit_range) if fit_range is not None else None)' in source
