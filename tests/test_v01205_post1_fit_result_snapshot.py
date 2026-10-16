"""Persist scientific result information alongside reloadable fitting setup."""
import json
from maxiv_panda.workflows.peakfit import fit_io


def test_optional_completed_fit_result_roundtrip(tmp_path):
    setup = {"peak_states": [], "bg_state": {"bg_type": "parabolic"}, "fit_range": [411, 441]}
    result = {"fit_quality": {"status": "Converged", "rss": 42.5},
              "fit_model": {"peaks": [{"index": 1, "parameters": {"Energy": {"value": 425, "stderr": 0.1}}}]}}
    path = tmp_path / "curve.fit.json"
    fit_io.save_fit_setup_json(path, setup, metadata={"source_file": "example.ibw"}, fit_result=result)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format"] == "flexpes_pes_fit_setup"
    assert payload["fit_result"] == result
    restored, metadata = fit_io.load_fit_setup_json(path)
    assert restored["fit_range"] == [411, 441]
    assert metadata["source_file"] == "example.ibw"


def test_unfitted_configuration_has_no_stale_statistics(tmp_path):
    path = tmp_path / "unfitted.fit.json"
    fit_io.save_fit_setup_json(path, {"peak_states": [], "bg_state": {"bg_type": "constant"}})
    assert "fit_result" not in json.loads(path.read_text(encoding="utf-8"))
