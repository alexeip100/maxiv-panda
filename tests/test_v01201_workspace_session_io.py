from pathlib import Path
import numpy as np

from maxiv_panda.session_io import make_manifest, save_session_file, load_session_file, load_array_pair


def test_build5_workspace_and_plotted_state_round_trip(tmp_path: Path):
    member = "plotted/curve_00000.npz"
    manifest = make_manifest(
        panda_version="0.12.1", sources=[],
        plotted_state={"curves": [{"title": "S 2p", "array_member": member}], "reverse_x": True},
        workspace_state={"active_tab_text": "Plotted Data", "fit_windows": [{"signature": "curve_1"}]},
    )
    target = tmp_path / "workspace.panda"
    x = np.array([1.0, 2.0]); y = np.array([3.0, 4.0])
    save_session_file(target, manifest, processed_arrays={member: (x, y)})
    loaded = load_session_file(target)
    assert loaded.plotted_state["curves"][0]["title"] == "S 2p"
    assert loaded.workspace_state["active_tab_text"] == "Plotted Data"
    rx, ry = load_array_pair(target, member)
    np.testing.assert_array_equal(rx, x); np.testing.assert_array_equal(ry, y)


def test_old_session_defaults_new_workspace_fields_empty(tmp_path: Path):
    target = tmp_path / "old.panda"
    save_session_file(target, make_manifest(panda_version="0.12.1", sources=[]))
    loaded = load_session_file(target)
    assert loaded.plotted_state == {}
    assert loaded.workspace_state == {}
