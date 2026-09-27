from pathlib import Path

from maxiv_panda.workflows.peakfit import fit_io
from maxiv_panda.workflows.peakfit.state_models import DoubletState, FitSetupState, PeakState


ROOT = Path(__file__).resolve().parents[1]


def test_typed_fit_state_models_are_present_without_schema_bump():
    assert PeakState is not None
    assert DoubletState is not None
    assert FitSetupState is not None
    assert fit_io.FORMAT_VERSION == 1


def test_fit_dialog_uses_typed_models_at_capture_and_apply_boundaries():
    source = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_dialog_state_mixin.py").read_text(encoding="utf-8")
    assert "PeakState.from_mapping(state" in source
    assert "FitSetupState.from_mapping(setup).to_mapping()" in source
    assert "FitSetupState.from_mapping(state).to_mapping()" in source


def test_so_doublet_normalization_delegates_to_shared_state_model():
    source = (ROOT / "src/maxiv_panda/workflows/peakfit/so_doublets.py").read_text(encoding="utf-8")
    assert "DoubletState.from_mapping(state, ordinal=ordinal).to_mapping()" in source
