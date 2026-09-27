import json
from pathlib import Path

import pytest

from maxiv_panda.workflows.peakfit import fit_io, so_doublets
from maxiv_panda.workflows.peakfit.state_models import (
    DoubletState,
    FitSetupState,
    PeakState,
    StateValidationError,
)


ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "tests/data/reference/peak_fitting/ir111_ir4f_clean_170ev/fit_setup.json"


def _complete_peak():
    return {
        "E": 60.3, "E_min": 57.0, "E_max": 68.0, "E_mode": "Free",
        "H": 71000.0, "H_min": 0.0, "H_max": 180000.0, "H_mode": "Fixed",
        "L": 0.255, "L_min": 0.05, "L_max": 1.0, "L_mode": "Tied to LFWHM_1",
        "G": 0.194, "G_min": 0.05, "G_max": 2.0, "G_mode": "Free",
        "A": 0.144, "A_min": 0.0, "A_max": 0.2, "A_mode": "Tied to Alpha_1",
        "label": "Surf_7/2",
    }


def test_peak_state_round_trips_manual_tie_modes_and_optional_color():
    source = {**_complete_peak(), "color": "#123456", "color_custom": True, "future_key": {"x": 1}}
    restored = PeakState.from_mapping(source, ordinal=2).to_mapping()
    assert restored == source
    assert restored["L_mode"] == "Tied to LFWHM_1"
    assert restored["A_mode"] == "Tied to Alpha_1"


def test_peak_state_has_internal_defaults_but_preserves_sparse_dictionary_shape():
    typed = PeakState.from_mapping({"label": "P3", "E": 61.0}, ordinal=3)
    assert typed.parameters["E"].value == 61.0
    assert typed.parameters["E"].minimum == -1e9
    assert typed.parameters["L"].value == 0.2
    assert typed.parameters["G"].value == 0.3
    assert typed.parameters["A"].value == 0.0
    # A sparse batch/legacy state must stay sparse when converted back, so
    # internal defaults never become accidental fit constraints.
    assert typed.to_mapping() == {"E": 61.0, "label": "P3"}


def test_doublet_state_matches_public_normalizer():
    source = {
        "id": 2, "major": 3, "minor": 4, "label": "S 2p #2", "orbital": "p",
        "split": 1.18, "split_min": 1.0, "split_max": 1.4,
        "split_mode": "Tied", "split_tie_target": 1,
        "ratio": 1.9, "ratio_min": 1.5, "ratio_max": 2.3,
        "ratio_mode": "Free", "ratio_tie_target": None,
        "L_relation": "Same", "G_relation": "Independent", "A_relation": "Same",
        "future_key": "preserved",
    }
    typed = DoubletState.from_mapping(source, ordinal=2).to_mapping()
    assert typed == so_doublets.normalize_state(source, ordinal=2)
    assert typed["future_key"] == "preserved"


def test_fit_setup_round_trip_preserves_existing_v1_reference_shape():
    payload = json.loads(REFERENCE.read_text(encoding="utf-8"))
    original = payload["fit_setup"]
    round_trip = FitSetupState.from_mapping(original).to_mapping()
    assert round_trip == original
    # This historical v1 setup predates SO doublets; Step 1 must not silently
    # add a new on-disk section merely because the internal model knows it.
    assert "so_doublets" not in round_trip


def test_fit_io_load_keeps_v1_format_and_manual_ties_unchanged():
    original_payload = json.loads(REFERENCE.read_text(encoding="utf-8"))
    setup, metadata = fit_io.load_fit_setup_json(REFERENCE)
    assert fit_io.FORMAT_VERSION == 1
    assert setup == original_payload["fit_setup"]
    assert metadata == original_payload["metadata"]
    assert setup["peak_states"][1]["L_mode"] == "Tied to LFWHM_1"


def test_fit_io_save_keeps_external_schema_version_one(tmp_path):
    setup = {
        "peak_states": [_complete_peak()],
        "so_doublets": [],
        "bg_state": {"bg_type": "linear", "b0": 1.0, "b1": 0.0},
    }
    path = tmp_path / "state.fit.json"
    fit_io.save_fit_setup_json(path, setup, metadata={"curve_label": "Trace"})
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format"] == "flexpes_pes_fit_setup"
    assert payload["format_version"] == 1
    assert payload["fit_setup"] == setup



def test_fit_setup_round_trip_preserves_optional_top_level_sections():
    assert FitSetupState.from_mapping({"bg_state": {"bg_type": "linear"}}).to_mapping() == {"bg_state": {"bg_type": "linear"}}
    assert FitSetupState.from_mapping({}).to_mapping() == {}

def test_fit_setup_validation_reports_reversed_peak_bounds():
    bad = {"peak_states": [{**_complete_peak(), "G_min": 2.0, "G_max": 0.05}], "bg_state": {}}
    with pytest.raises(StateValidationError, match="G_max"):
        FitSetupState.from_mapping(bad)
