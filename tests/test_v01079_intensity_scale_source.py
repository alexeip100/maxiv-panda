from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src/maxiv_panda/ui.py").read_text(encoding="utf-8")
PROC = (ROOT / "src/maxiv_panda/processed_controller.py").read_text(encoding="utf-8")
PLOT = (ROOT / "src/maxiv_panda/ui_processed_data_mixin.py").read_text(encoding="utf-8")
FIT = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_dialog_curve_mixin.py").read_text(encoding="utf-8")


def test_raw_and_processed_keep_independent_intensity_modes():
    assert "_raw_intensity_mode = COUNTS" in UI
    assert "_processed_intensity_mode = COUNTS" in UI
    assert "def _current_intensity_mode" in UI


def test_y_axis_double_click_opens_counts_cps_selector():
    assert "_on_intensity_axis_double_click" in UI
    assert 'menu.addAction("Counts")' in UI
    assert 'menu.addAction("CPS")' in UI


def test_maps_are_deliberately_excluded_from_cps_transform():
    assert "if not images and payloads:" in UI
    assert "Maps always use the" in UI


def test_processed_children_inherit_cps():
    assert "_processed_intensity_mode" in PROC
    assert "scale_payload" in PROC
    assert "inherit CPS when it is selected upstream" in PLOT
    assert "normalize_payload_for_workflow(pl, it)" in FIT
