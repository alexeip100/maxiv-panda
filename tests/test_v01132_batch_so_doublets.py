from pathlib import Path

from maxiv_panda.workflows.peakfit import so_doublets

ROOT = Path(__file__).resolve().parents[1]


def _peak(e, h):
    return {"E": e, "H": h, "L": 0.4, "G": 0.5, "A": 0.02}


def test_batch_doublet_free_values_follow_generated_peaks_and_bounds():
    start = {"so_doublets": [{
        "id": 1, "major": 1, "minor": 2, "label": "S 2p #1", "orbital": "p",
        "split": 1.2, "split_min": 1.0, "split_max": 1.5, "split_mode": "Free",
        "ratio": 2.0, "ratio_min": 1.5, "ratio_max": 2.5, "ratio_mode": "Free",
        "L_relation": "Same", "G_relation": "Same", "A_relation": "Independent",
    }]}
    states = so_doublets.states_for_batch_peaks(start, [_peak(100.0, 90.0), _peak(101.4, 30.0)])
    assert len(states) == 1
    assert abs(states[0]["split"] - 1.4) < 1e-12
    # 90/30=3, clipped to configured upper bound.
    assert states[0]["ratio"] == 2.5
    assert states[0]["L_relation"] == "Same"
    assert states[0]["A_relation"] == "Independent"


def test_batch_doublet_fixed_values_keep_anchor_definition():
    start = {"so_doublets": [{
        "id": 1, "major": 1, "minor": 2, "label": "S 2p #1", "orbital": "p",
        "split": 1.18, "split_min": 1.0, "split_max": 1.4, "split_mode": "Fixed",
        "ratio": 2.0, "ratio_min": 1.5, "ratio_max": 2.5, "ratio_mode": "Fixed",
        "L_relation": "Same", "G_relation": "Same", "A_relation": "Same",
    }]}
    states = so_doublets.states_for_batch_peaks(start, [_peak(100.0, 100.0), _peak(101.35, 20.0)])
    assert states[0]["split"] == 1.18
    assert states[0]["ratio"] == 2.0


def test_batch_doublet_exact_ties_survive_and_resolve():
    d1 = {
        "id": 1, "major": 1, "minor": 2, "label": "A #1", "orbital": "p",
        "split": 1.1, "split_min": 0.8, "split_max": 1.4, "split_mode": "Fixed",
        "ratio": 2.0, "ratio_min": 1.5, "ratio_max": 2.5, "ratio_mode": "Fixed",
        "L_relation": "Same", "G_relation": "Same", "A_relation": "Same",
    }
    d2 = dict(d1)
    d2.update({"id": 2, "major": 3, "minor": 4, "label": "A #2", "split": 1.3,
               "split_mode": "Tied", "split_tie_target": 1,
               "ratio": 1.8, "ratio_mode": "Tied", "ratio_tie_target": 1})
    states = so_doublets.states_for_batch_peaks(
        {"so_doublets": [d1, d2]},
        [_peak(100, 100), _peak(101.1, 50), _peak(103, 80), _peak(104.3, 40)],
    )
    assert states[1]["split_mode"] == "Tied"
    assert states[1]["split_tie_target"] == 1
    assert states[1]["split"] == states[0]["split"] == 1.1
    assert states[1]["ratio"] == states[0]["ratio"] == 2.0


def test_batch_config_and_runner_route_structured_doublets_to_fit_engine():
    config_src = (ROOT / "src/maxiv_panda/workflows/peakfit/batch_config.py").read_text(encoding="utf-8")
    runner_src = (ROOT / "src/maxiv_panda/workflows/peakfit/batch_runner.py").read_text(encoding="utf-8")
    assert '"so_doublets": generated_doublets' in config_src
    assert 'doublets = list(fit_state.get("so_doublets") or [])' in runner_src
    assert 'doublets=doublets' in runner_src
    assert '"so_doublets": result_doublets' in runner_src


def test_help_no_longer_claims_batch_flattens_doublets():
    controls = (ROOT / "src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
    workflows = (ROOT / "src/maxiv_panda/docs/usage_workflows.md").read_text(encoding="utf-8")
    text = controls + workflows
    assert "flattens the grouped doublets" not in text
    assert "preserved" in text
    assert "peak-oriented" in text
