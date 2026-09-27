from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_doublet_card_has_compact_clone_action_and_tooltip():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_widgets.py").read_text(encoding="utf-8")
    assert 'QPushButton("Clone", gb)' in src
    assert 'setToolTip("Clone this doublet")' in src
    assert 'on_clone(int(did))' in src


def test_create_doublet_invitation_has_tooltip():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_dialog.py").read_text(encoding="utf-8")
    assert 'self.btn_create_so_doublet.setToolTip("Create a spin-orbit doublet from two existing standalone peaks.")' in src


def test_clone_handler_adds_two_peaks_and_can_clone_any_doublet():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_dialog_doublet_mixin.py").read_text(encoding="utf-8")
    assert 'def _clone_so_doublet(self, doublet_id: int)' in src
    assert 'doublets + [clone]' in src
    assert 'len(peak_states) + 2 > 10' in src
