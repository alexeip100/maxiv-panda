from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src/maxiv_panda/workflows/peakfit"


def _read(name: str) -> str:
    return (PEAKFIT / name).read_text(encoding="utf-8")


def test_dialog_inherits_doublet_mixin():
    dialog = _read("fit_dialog.py")
    assert "from .fit_dialog_doublet_mixin import FitDialogDoubletMixin" in dialog
    assert "FitDialogDoubletMixin," in dialog


def test_doublet_mixin_owns_so_doublet_management():
    text = _read("fit_dialog_doublet_mixin.py")
    expected = [
        "_capture_so_doublet_states",
        "_doublet_view_enabled",
        "_on_doublet_view_toggled",
        "_current_energy_scale_for_doublet",
        "_apply_so_doublet_relations",
        "_refresh_so_doublet_widgets",
        "_restore_so_doublet_states",
        "_on_create_so_doublet",
        "_clone_so_doublet",
        "_ungroup_so_doublet",
    ]
    for name in expected:
        assert f"def {name}" in text


def test_state_mixin_no_longer_owns_doublet_management():
    text = _read("fit_dialog_state_mixin.py")
    for name in (
        "_capture_so_doublet_states",
        "_apply_so_doublet_relations",
        "_refresh_so_doublet_widgets",
        "_on_create_so_doublet",
        "_clone_so_doublet",
        "_ungroup_so_doublet",
    ):
        assert f"def {name}" not in text


def test_peak_rebuild_and_delete_remain_in_state_mixin_for_now():
    text = _read("fit_dialog_state_mixin.py")
    assert "def _delete_peak_by_index" in text
    assert "def _rebuild_peak_widgets" in text
