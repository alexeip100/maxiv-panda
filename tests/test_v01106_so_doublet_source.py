from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_so_doublet_invitation_is_explicit():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_dialog.py").read_text(encoding="utf-8")
    assert 'QPushButton("Create SO doublet..."' in src
    assert 'self.btn_create_so_doublet.clicked.connect(self._on_create_so_doublet)' in src


def test_so_doublet_dialog_uses_major_minor_language():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_dialog_doublet_mixin.py").read_text(encoding="utf-8")
    assert 'form.addRow("Major peak:", cb_major)' in src
    assert 'form.addRow("Minor peak:", cb_minor)' in src
    assert 'Splitting and intensity ratio can be fixed or fitted' in src


def test_doublet_state_is_saved_with_fit_setup():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_dialog_state_mixin.py").read_text(encoding="utf-8")
    assert '"so_doublets": self._capture_so_doublet_states()' in src
    assert 'self._restore_so_doublet_states(state.get("so_doublets") or [])' in src


def test_backend_compiles_doublet_into_lmfit_expressions():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_engine.py").read_text(encoding="utf-8")
    assert 'd{ordinal}_split' in src
    assert 'd{ordinal}_ratio' in src
    assert 'p{minor}_E' in src
    assert 'p{minor}_H' in src
