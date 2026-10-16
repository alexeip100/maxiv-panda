"""PANDA's exported fit report must be loadable as an editable fit setup."""
import json
from pathlib import Path
import pytest
from maxiv_panda.workflows.peakfit import fit_io

FIXTURE = Path(__file__).parent / "data" / "single_fit_result_sn_mnn.json"


def test_real_export_converts_to_fit_setup():
    setup, metadata = fit_io.load_fit_setup_json(FIXTURE)
    assert metadata["region"] == "Sn_MNN_AES_520eV#1"
    assert len(setup["peak_states"]) == 6
    assert setup["fit_range"] == pytest.approx([411.79168749279137, 440.6432388788566])
    assert setup["bg_state"]["bg_type"] == "parabolic"
    assert setup["bg_state"]["b2"] == pytest.approx(-7.639362756336584)
    assert setup["peak_states"][0]["E"] == pytest.approx(419.57995742057665)
    for peak in setup["peak_states"][1:]:
        for key, label in (("L", "LFWHM"), ("G", "GFWHM"), ("A", "Alpha")):
            assert peak[f"{key}_mode"] == f"Tied to {label}_1"


def test_reject_unknown_result_version(tmp_path):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["format_version"] = 99
    path = tmp_path / "future.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported PANDA single-fit result format version"):
        fit_io.load_fit_setup_json(path)


def test_setup_format_stays_distinct(tmp_path):
    setup, md = fit_io.load_fit_setup_json(FIXTURE)
    path = tmp_path / "converted.fit.json"
    fit_io.save_fit_setup_json(path, setup, md)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format"] == "flexpes_pes_fit_setup"
    restored, _ = fit_io.load_fit_setup_json(path)
    assert restored == setup
