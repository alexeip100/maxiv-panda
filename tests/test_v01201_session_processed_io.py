from pathlib import Path
import zipfile
import numpy as np

from maxiv_panda.session_io import (
    SessionProcessedCurve, SessionSelection, make_manifest,
    save_session_file, load_session_file, load_processed_arrays,
)


def test_processed_curve_round_trip(tmp_path: Path):
    member = "processed/curve_00001.npz"
    curve = SessionProcessedCurve(
        key="curve_00001", display="0070: C1s (E-cal)", parent_file="XPS_0070.ibw",
        source_file="XPS_0070.ibw", region_name="C1s", array_member=member,
        title="C1s (E-cal)", xlabel="Binding Energy (eV)", ylabel="Intensity",
        energy_scale="Binding", metadata={"origin": "test"},
        item_meta={"processed": True, "energy_shift": 0.25}, checked=False,
    )
    manifest = make_manifest(
        panda_version="0.12.1", sources=[],
        selected_raw=[SessionSelection("raw-key", True)],
        processed_curves=[curve],
        processed_view={"norm_enabled": True, "norm_energy": 285.0, "region_cmap": [{"file":"f","region":"r","cmap":"terrain"}]},
    )
    target = tmp_path / "work.panda"
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    save_session_file(target, manifest, processed_arrays={member: (x, y)})

    loaded = load_session_file(target)
    assert loaded.selected_raw[0].key == "raw-key"
    assert loaded.processed_curves[0].item_meta["energy_shift"] == 0.25
    assert loaded.processed_curves[0].checked is False
    assert loaded.processed_view["norm_enabled"] is True
    arrays = load_processed_arrays(target, loaded)
    np.testing.assert_array_equal(arrays["curve_00001"][0], x)
    np.testing.assert_array_equal(arrays["curve_00001"][1], y)

    with zipfile.ZipFile(target) as zf:
        assert "session.json" in zf.namelist()
        assert member in zf.namelist()


def test_build2_manifest_without_processed_fields_still_loads(tmp_path: Path):
    # Use the normal writer with no build-3 state: optional fields must remain empty.
    target = tmp_path / "oldstyle.panda"
    save_session_file(target, make_manifest(panda_version="0.12.1", sources=[]))
    loaded = load_session_file(target)
    assert loaded.selected_raw == ()
    assert loaded.processed_curves == ()
    assert loaded.processed_view == {}
