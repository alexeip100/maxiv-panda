from pathlib import Path

from maxiv_panda.session_io import load_session_file, make_manifest, save_session_file


def test_fitting_state_round_trip_is_optional_and_json_safe(tmp_path: Path):
    target = tmp_path / "fit_session.panda"
    fitting = {
        "single": {
            "curve-a||curve-b": {
                "curve_keys": ["curve-a", "curve-b"],
                "active_curve_key": "curve-b",
                "curve_states": {
                    "curve-b": {
                        "fit_range": [160.0, 164.0],
                        "bound_hits": {"p1_E", "p2_H"},
                        "peak_states": [{"label": "S 2p3/2", "E": 161.9}],
                        "so_doublets": [{"major_label": "S 2p3/2", "minor_label": "S 2p1/2"}],
                    }
                },
            }
        },
        "batch": {},
    }
    save_session_file(target, make_manifest(panda_version="0.12.1", sources=[], fitting_state=fitting))
    loaded = load_session_file(target)
    state = loaded.fitting_state["single"]["curve-a||curve-b"]
    assert state["active_curve_key"] == "curve-b"
    assert state["curve_states"]["curve-b"]["fit_range"] == [160.0, 164.0]
    assert sorted(state["curve_states"]["curve-b"]["bound_hits"]) == ["p1_E", "p2_H"]


def test_build3_session_without_fitting_state_still_loads(tmp_path: Path):
    target = tmp_path / "old.panda"
    save_session_file(target, make_manifest(panda_version="0.12.1", sources=[]))
    assert load_session_file(target).fitting_state == {}
