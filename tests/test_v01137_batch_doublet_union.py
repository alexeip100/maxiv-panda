from pathlib import Path

from maxiv_panda.workflows.peakfit import so_doublets

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src/maxiv_panda/workflows/peakfit"


def _peak(label, e=1.0, h=1.0):
    return {"label": label, "E": e, "H": h, "L": 0.2, "G": 0.3, "A": 0.0}


def _state(doublets, peaks=None):
    return {"peak_states": list(peaks or [_peak("P1"), _peak("P2"), _peak("P3"), _peak("P4")]), "so_doublets": list(doublets)}


def _doublet(label, major, minor, *, split=1.2, relations=("Same", "Same", "Same"), did=1):
    return {
        "id": did, "major": major, "minor": minor, "label": label, "orbital": "p",
        "split": split, "split_min": 1.0, "split_max": 1.4, "split_mode": "Free", "split_tie_target": None,
        "ratio": 2.0, "ratio_min": 1.5, "ratio_max": 2.5, "ratio_mode": "Free", "ratio_tie_target": None,
        "L_relation": relations[0], "G_relation": relations[1], "A_relation": relations[2],
    }


def test_doublet_label_is_identity_not_energy():
    start = _state([_doublet("S 2p #1", 1, 2, split=1.15)], [_peak("P1", 162.0), _peak("P2", 163.15)])
    end = _state([_doublet("S 2p #1", 1, 2, split=1.22)], [_peak("P1", 162.8), _peak("P2", 164.02)])
    mode, errors = so_doublets.validate_anchor_topologies({"Start": start, "End": end})
    assert mode == "doublet-aware"
    assert errors == []


def test_doublet_may_appear_or_disappear_across_anchors():
    start = _state([_doublet("A #1", 1, 2)], [_peak("P1"), _peak("P2")])
    end = _state([_doublet("A #1", 1, 2), _doublet("B #1", 3, 4, did=2)], [_peak("P1"), _peak("P2"), _peak("P3"), _peak("P4")])
    mode, errors = so_doublets.validate_anchor_topologies({"Start": start, "End": end})
    assert mode == "doublet-aware"
    assert errors == []


def test_peak_only_anchor_can_coexist_when_doublet_components_are_absent():
    start = _state([], [_peak("Other")])
    end = _state([_doublet("S 2p #1", 1, 2)], [_peak("P1"), _peak("P2")])
    mode, errors = so_doublets.validate_anchor_topologies({"Start": start, "End": end})
    assert mode == "doublet-aware"
    assert errors == []


def test_absent_doublet_cannot_reappear_as_same_constituent_labels_standalone():
    start = _state([], [_peak("P1"), _peak("P2")])
    end = _state([_doublet("S 2p #1", 1, 2)], [_peak("P1"), _peak("P2")])
    mode, errors = so_doublets.validate_anchor_topologies({"Start": start, "End": end})
    assert mode == "doublet-aware"
    assert errors and "ordinary peaks" in errors[0]


def test_same_label_requires_same_pairing_and_shape_relations():
    start = _state([_doublet("S 2p #1", 1, 2)])
    changed_pair = _state([_doublet("S 2p #1", 2, 3)])
    _, errors = so_doublets.validate_anchor_topologies({"Start": start, "End": changed_pair})
    assert errors
    changed_shape = _state([_doublet("S 2p #1", 1, 2, relations=("Independent", "Same", "Same"))])
    _, errors = so_doublets.validate_anchor_topologies({"Start": start, "End": changed_shape})
    assert errors


def test_duplicate_doublet_label_in_one_anchor_is_rejected():
    state = _state([_doublet("S 2p #1", 1, 2, did=1), _doublet("S 2p #1", 3, 4, did=2)])
    _, errors = so_doublets.validate_anchor_topologies({"Start": state})
    assert errors and "Duplicate SO-doublet label" in errors[0]


def test_doublet_batch_builder_is_union_and_not_start_template_source_contract():
    src = (PEAKFIT / "batch_table_builder.py").read_text(encoding="utf-8")
    assert "def _doublet_union_model" in src
    assert "for anchor in fitted_labels" in src
    assert "ordered_labels" in src
    assert "start_doublets" not in src
    assert '"presence": self._presence_pattern(present, fitted_labels)' in src


def test_batch_config_builds_doublets_from_union_model_not_start_anchor_source_contract():
    src = (PEAKFIT / "batch_config.py").read_text(encoding="utf-8")
    assert '"doublet_models": doublet_models' in src
    assert 'label_to_peak_index' in src
    assert 'for model in list(config.get("doublet_models") or [])' in src
    assert 'states_for_batch_peaks' not in src


def test_component_identity_note_and_doublet_label_tooltip_are_present():
    anchor = (PEAKFIT / "batch_anchor_mixin.py").read_text(encoding="utf-8")
    widgets = (PEAKFIT / "fit_widgets.py").read_text(encoding="utf-8")
    assert "A peak or doublet label identifies the same component across the series" in anchor
    assert "Components may be absent from some anchors" in anchor
    assert "This label identifies the same SO-doublet component across batch anchors" in widgets
