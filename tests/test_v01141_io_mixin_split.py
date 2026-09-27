from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src/maxiv_panda/workflows/peakfit"


def _read(name: str) -> str:
    return (PEAKFIT / name).read_text(encoding="utf-8")


def test_dialog_inherits_io_mixin():
    dialog = _read("fit_dialog.py")
    assert "from .fit_dialog_io_mixin import FitDialogIOMixin" in dialog
    assert "FitDialogIOMixin," in dialog


def test_io_mixin_owns_fit_setup_actions_and_export():
    text = _read("fit_dialog_io_mixin.py")
    expected = [
        "_update_saved_setup_status",
        "_on_save_fit_setup",
        "_on_apply_fit_setup",
        "_current_fit_io_metadata",
        "_fit_io_default_dir",
        "_remember_fit_io_dir",
        "_on_export_fit_results",
        "_on_save_fit_setup_file",
        "_on_load_fit_setup_file",
    ]
    for name in expected:
        assert f"def {name}" in text


def test_state_mixin_no_longer_owns_fit_io_actions():
    text = _read("fit_dialog_state_mixin.py")
    for name in (
        "_on_save_fit_setup",
        "_on_apply_fit_setup",
        "_current_fit_io_metadata",
        "_fit_io_default_dir",
        "_on_export_fit_results",
        "_on_save_fit_setup_file",
        "_on_load_fit_setup_file",
    ):
        assert f"def {name}" not in text


def test_setup_capture_and_apply_remain_in_state_mixin():
    text = _read("fit_dialog_state_mixin.py")
    assert "def _capture_fit_setup_template" in text
    assert "def _apply_fit_setup_template" in text
