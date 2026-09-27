from pathlib import Path
import numpy as np


def test_grouped_component_specs_sums_doublet_and_keeps_standalone():
    import sys
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from maxiv_panda.workflows.peakfit import so_doublets

    components = [np.array([1.0, 2.0]), np.array([3.0, 4.0]), np.array([7.0, 8.0])]
    specs = so_doublets.grouped_component_specs(
        components,
        ["major", "minor", "P1"],
        ["#111111", "#222222", "#333333"],
        [{"id": 1, "major": 1, "minor": 2, "label": "S 2p", "orbital": "p", "split": 1.2, "ratio": 2.0}],
        grouped=True,
    )
    assert len(specs) == 2
    assert specs[0]["label"] == "S 2p"
    assert specs[0]["members"] == (1, 2)
    assert specs[0]["color"] == "#111111"
    np.testing.assert_allclose(specs[0]["component"], [4.0, 6.0])
    assert specs[1]["label"] == "P1"
    np.testing.assert_allclose(specs[1]["component"], [7.0, 8.0])


def test_individual_component_specs_are_unchanged():
    import sys
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    from maxiv_panda.workflows.peakfit import so_doublets

    components = [np.array([1.0]), np.array([2.0])]
    specs = so_doublets.grouped_component_specs(
        components, ["A", "B"], ["r", "b"],
        [{"id": 1, "major": 1, "minor": 2, "label": "D", "orbital": "p", "split": 1.0, "ratio": 2.0}],
        grouped=False,
    )
    assert [x["label"] for x in specs] == ["A", "B"]
    assert [x["members"] for x in specs] == [(1,), (2,)]


def test_doublet_view_ui_and_marker_source_contract():
    root = Path(__file__).resolve().parents[1]
    dialog = (root / "src/maxiv_panda/workflows/peakfit/fit_dialog.py").read_text(encoding="utf-8")
    bg = (root / "src/maxiv_panda/workflows/peakfit/fit_dialog_component_display_mixin.py").read_text(encoding="utf-8")
    fit = (root / "src/maxiv_panda/workflows/peakfit/fit_dialog_fit_mixin.py").read_text(encoding="utf-8")

    assert 'QCheckBox("Doublet view"' in dialog
    assert "Show each SO doublet as the sum of its major and minor components" in dialog
    assert "Choose two existing peaks as major and minor components." not in dialog
    assert "status_row = QWidget" in dialog
    assert "_visible_peak_marker_indices" in bg
    assert 'int(st.get("minor", -1)) - 1' in bg
    assert "doublet_view=(self._doublet_view_enabled()" in fit
