from pathlib import Path

from maxiv_panda.workflows.peakfit import so_doublets

ROOT = Path(__file__).resolve().parents[1]


def _peak(label):
    return {"label": label, "E": 1.0, "H": 1.0, "L": 0.2, "G": 0.3, "A": 0.0}


def _state(*, pair=(1, 2), relations=("Same", "Same", "Same"), doublets=True):
    out = {"peak_states": [_peak("P1"), _peak("P2"), _peak("P3")]}
    if doublets:
        out["so_doublets"] = [{
            "id": 1, "major": pair[0], "minor": pair[1], "label": "S 2p #1", "orbital": "p",
            "split": 1.2, "split_min": 1.0, "split_max": 1.4, "split_mode": "Free", "split_tie_target": None,
            "ratio": 2.0, "ratio_min": 1.5, "ratio_max": 2.5, "ratio_mode": "Free", "ratio_tie_target": None,
            "L_relation": relations[0], "G_relation": relations[1], "A_relation": relations[2],
        }]
    else:
        out["so_doublets"] = []
    return out


def test_topology_classifier_keeps_peak_only_mode_unchanged():
    mode, errors = so_doublets.validate_anchor_topologies({"Start": _state(doublets=False), "End": _state(doublets=False)})
    assert mode == "peak-only"
    assert errors == []


def test_topology_classifier_accepts_same_doublet_structure_despite_numeric_modes():
    start = _state()
    end = _state()
    end["so_doublets"][0]["split"] = 1.31
    end["so_doublets"][0]["split_mode"] = "Fixed"
    end["so_doublets"][0]["ratio_mode"] = "Tied"
    mode, errors = so_doublets.validate_anchor_topologies({"Start": start, "End": end})
    assert mode == "doublet-aware"
    assert errors == []


def test_topology_classifier_allows_doublet_absent_from_an_anchor_when_members_are_absent():
    peak_only = {"peak_states": [_peak("Other")], "so_doublets": []}
    mode, errors = so_doublets.validate_anchor_topologies({"Start": _state(), "Middle": peak_only})
    assert mode == "doublet-aware"
    assert errors == []


def test_topology_classifier_rejects_changed_pairing_or_shape_relation():
    _, pairing_errors = so_doublets.validate_anchor_topologies({"Start": _state(), "End": _state(pair=(2, 3))})
    assert pairing_errors
    _, relation_errors = so_doublets.validate_anchor_topologies({"Start": _state(), "End": _state(relations=("Independent", "Same", "Same"))})
    assert relation_errors


def test_batch_table_has_two_modes_and_disabled_derived_rows_source_contract():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/batch_table_builder.py").read_text(encoding="utf-8")
    assert '"Peak / Doublet / BG" if doublet_aware else "Peak / BG"' in src
    assert '"parameter": "Splitting"' not in src  # rows are generated from the shared tuple below
    assert '(("split", "Splitting"), ("ratio", "Ratio"))' in src
    assert '"kind": "derived" if derived else "peak"' in src
    assert 'table.setItem(row_idx, 10, self._make_batch_table_item("Derived", enabled=False))' in src
    assert 'editable=not derived, enabled=not derived' in src


def test_batch_config_applies_doublet_rows_to_generated_states_source_contract():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/batch_config.py").read_text(encoding="utf-8")
    assert 'kind == "doublet"' in src
    assert 'st[f"{key}_mode"] = str(row.get("mode") or "Free")' in src
    assert 'st[f"{key}_tie_target"] = int(row.get("tie_target_id"))' in src
    assert 'generated_doublets = so_doublets.resolve_tied_values(generated_doublets)' in src
    assert '"Fixed" if kind == "derived" else mode' in src


def test_anchor_model_note_and_early_validation_are_present():
    anchor = (ROOT / "src/maxiv_panda/workflows/peakfit/batch_anchor_mixin.py").read_text(encoding="utf-8")
    setup = (ROOT / "src/maxiv_panda/workflows/peakfit/batch_prepare_setup_mixin.py").read_text(encoding="utf-8")
    assert '"Batch anchor model structure"' in anchor
    assert "A peak or doublet label identifies the same component across the series" in anchor
    assert "_batch_anchor_model_mode_and_errors" in anchor
    assert '"Anchor model structure differs"' in anchor
    assert "validate_anchor_topologies" in setup
    assert '"The batch setup cannot be created until the fitted anchors use a consistent model structure.' in setup
