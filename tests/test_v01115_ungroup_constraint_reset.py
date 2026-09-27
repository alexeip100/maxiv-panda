from pathlib import Path


def test_constraint_state_refresh_reenables_mode_selector_after_ungroup():
    src = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_constraints_mixin.py").read_text(encoding="utf-8")
    assert "combo.setEnabled(True)" in src


def test_doublet_ungroup_reapplies_ordinary_constraint_state():
    src = Path("src/maxiv_panda/workflows/peakfit/fit_dialog_doublet_mixin.py").read_text(encoding="utf-8")
    assert "def _ungroup_so_doublet" in src
    assert "self._apply_so_doublet_relations(refresh=True)" in src
    assert "First return all peak editors to ordinary enabled/title state." in src
