from pathlib import Path

from maxiv_panda.source_snapshots import (
    canonical_source_path,
    make_source_snapshot,
    updated_source_label,
)


def test_canonical_path_identifies_same_physical_path(tmp_path: Path):
    p = tmp_path / "data.ibw"
    p.write_bytes(b"abc")
    assert canonical_source_path(p) == canonical_source_path(p.parent / "." / p.name)


def test_snapshot_has_stable_identity_and_file_stat(tmp_path: Path):
    p = tmp_path / "data.ibw"
    p.write_bytes(b"abcdef")
    snap = make_source_snapshot(p)
    assert snap.snapshot_id.startswith("src_")
    assert snap.file_name == "data.ibw"
    assert snap.source_label == "data.ibw"
    assert snap.file_size == 6
    assert snap.canonical_path == canonical_source_path(p)


def test_updated_copy_label_is_explicit_and_unique():
    first = updated_source_label("data.ibw", [])
    second = updated_source_label("data.ibw", [first])
    assert first.startswith("data.ibw [updated ")
    assert second != first


def test_reload_policy_is_centralized_and_context_menu_exposes_reload():
    mixin = Path("src/maxiv_panda/ui_source_reload_mixin.py").read_text(encoding="utf-8")
    actions = Path("src/maxiv_panda/ui_actions_mixin.py").read_text(encoding="utf-8")
    ui = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
    assert "class UiSourceReloadMixin" in mixin
    assert "_source_dependency_summary" in mixin
    assert "Load updated copy" in mixin
    assert "Replace and remove dependent data" in mixin
    assert "_loaded_file_item_for_path(path)" in actions
    assert 'menu.addAction("Reload from disk")' in ui


def test_loaded_curve_payload_and_metadata_carry_snapshot_identity():
    loaded = Path("src/maxiv_panda/loaded_tree.py").read_text(encoding="utf-8")
    ui = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
    assert "snapshot.as_metadata()" in loaded
    assert "source_snapshot_id" in Path("src/maxiv_panda/source_snapshots.py").read_text(encoding="utf-8")
    assert "metadata={**dict(snapshot_meta or {})" in loaded
    assert "metadata: dict[str, Any] | None = None" in ui


def test_provenance_survives_calibration_and_cps_transform():
    calibration = Path("src/maxiv_panda/workflows/calibration/calibrate_logic.py").read_text(encoding="utf-8")
    intensity = Path("src/maxiv_panda/intensity_units.py").read_text(encoding="utf-8")
    assert "metadata=dict(getattr(base_payload, 'metadata', {}) or {})" in calibration
    assert 'result.metadata = dict(getattr(payload, "metadata", {}) or {})' in intensity
    processed = Path("src/maxiv_panda/processed_controller.py").read_text(encoding="utf-8")
    assert processed.count('metadata=dict(getattr(p, "metadata", {}) or {})') >= 2


def test_replacing_one_snapshot_does_not_rebuild_entire_selected_tree():
    mixin = Path("src/maxiv_panda/ui_source_reload_mixin.py").read_text(encoding="utf-8")
    # Reload must surgically remove selected items for the old snapshot rather
    # than call SelectedTreeManager.rebuild_from_loaded(), which would discard
    # processed children from unrelated files.
    assert "_remove_selected_snapshot_items" in mixin
    replace_body = mixin.split("def _replace_loaded_snapshot", 1)[1].split("def _loaded_file_item_for_snapshot_id", 1)[0]
    assert "rebuild_from_loaded" not in replace_body
