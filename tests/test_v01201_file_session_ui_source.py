from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src/maxiv_panda/ui.py").read_text(encoding="utf-8")
ACTIONS = (ROOT / "src/maxiv_panda/ui_actions_mixin.py").read_text(encoding="utf-8")


def test_file_button_replaces_load_button_and_groups_session_actions():
    assert 'QPushButton("File", controls)' in UI
    assert 'addMenu("Load data...")' in UI
    assert 'addAction("Open session...")' in UI
    assert 'addAction("Save session...")' in UI
    assert 'addAction("Exit")' in UI


def test_session_open_restores_preserved_snapshot_identity():
    assert "_source_snapshot_from_session" in ACTIONS
    assert "snapshot_id=source.snapshot_id" in ACTIONS
    assert "self._add_txt_to_tree(parsed, snapshot=snapshot)" in ACTIONS


def test_session_open_restores_processed_workspace_for_build_3():
    assert "_restore_processed_workspace" in ACTIONS
    assert "processed_curves" in ACTIONS
    assert "self.close_all()" in ACTIONS


def test_session_restore_reinstates_loaded_tree_selection_before_processed_curves():
    # The Loaded-files tree is the canonical source of raw selection state.
    # Session restore must put its checkboxes back before rebuilding Selected,
    # otherwise a later tab/UI refresh can erase the apparent restored workspace.
    start = ACTIONS.index("def _restore_processed_workspace")
    body = ACTIONS[start:ACTIONS.index("def _open_session", start)]
    assert "loaded.setCheckState(" in body
    assert "tree.blockSignals(True)" in body
    assert "self._rebuild_selected_from_loaded()" in body
    assert body.index("loaded.setCheckState(") < body.index("self._rebuild_selected_from_loaded()")
    assert body.index("self._rebuild_selected_from_loaded()") < body.index("arrays = load_processed_arrays")


def test_session_saves_and_restores_ecal_toggle_state():
    assert '"ecal_enabled"' in ACTIONS
    restore = ACTIONS[ACTIONS.index('def _restore_processed_workspace'):ACTIONS.index('def _open_session')]
    assert 'view.get("ecal_enabled", has_processed)' in restore
    assert 'btn.blockSignals(True)' in restore
    assert 'show_processed=bool(ecal_enabled and on_processed_tab)' in restore


def test_session_guarantees_raw_source_for_restored_ecal_curve():
    restore = ACTIONS[ACTIONS.index('def _restore_processed_workspace'):ACTIONS.index('def _open_session')]
    assert 'required_source_keys' in restore
    assert 'source_key = meta.get("source_key")' in restore
    assert 'self._selected_tree_manager.add_from_loaded_item' in restore


def test_session_save_preserves_semantic_selected_parent_group_key():
    save = ACTIONS[ACTIONS.index('def _session_processed_state'):ACTIONS.index('def _save_session')]
    assert '_region_key_for_parent(parent)' in save
    assert 'parent_file = str(region_key[0])' in save


def test_session_restore_attaches_ecal_child_to_restored_raw_parent():
    restore = ACTIONS[ACTIONS.index('def _restore_processed_workspace'):ACTIONS.index('def _open_session')]
    assert 'raw_item = getattr(self, "_selected_by_key", {}).get(source_key)' in restore
    assert '_region_key_for_parent(raw_parent)' in restore
    assert 'parent_file = str(region_key[0])' in restore


def test_session_round_trip_preserves_all_in_region_grouping_state():
    save = ACTIONS[ACTIONS.index('def _session_processed_state'):ACTIONS.index('def _save_session')]
    restore = ACTIONS[ACTIONS.index('def _restore_processed_workspace'):ACTIONS.index('def _open_session')]
    assert '"all_in_region_enabled"' in save
    assert '"all_in_region_target"' in save
    assert 'view.get("all_in_region_enabled", False)' in restore
    assert 'view.get("all_in_region_target")' in restore


def test_session_round_trip_preserves_processed_map_view_mode_and_state():
    save = ACTIONS[ACTIONS.index('def _session_processed_state'):ACTIONS.index('def _save_session')]
    restore = ACTIONS[ACTIONS.index('def _restore_processed_workspace'):ACTIONS.index('def _open_session')]
    for token in ('"map_view_mode"', '"map_h_thickness"', '"map_v_thickness"', '"map_roi_spec"', '"map_right_y_mode"', '"map_lines_positions"'):
        assert token in save
    assert 'saved_map_mode = str(view.get("map_view_mode") or "simple").lower()' in restore
    assert 'self._session_restoring_map_view = True' in restore
    assert 'self._map_roi_spec = dict(view.get("map_roi_spec") or {}) or None' in restore
    assert 'self._map_lines_position_memory = memory' in restore
    assert 'combo.findData(saved_map_mode)' in restore


def test_fresh_map_simple_reset_is_bypassed_during_session_restore():
    processed = (ROOT / "src/maxiv_panda/ui_processed_data_mixin.py").read_text(encoding="utf-8")
    assert 'restoring_session_view = bool(getattr(self, "_session_restoring_map_view", False))' in processed
    assert 'if map_active and not was_active and not restoring_session_view:' in processed


def test_session_round_trip_preserves_map_normalization_and_bin_size():
    source = Path("src/maxiv_panda/ui_actions_mixin.py").read_text(encoding="utf-8")
    for token in (
        '"map_bin_size"', '"map_norm_mode"', '"map_norm_be"',
        '"map_norm_width_ev"', '"map_norm_area_low"', '"map_norm_area_high"',
        '"map_norm_show_region"'
    ):
        assert token in source
    assert '("sb_map_bin_size", view.get("map_bin_size", 1))' in source
    assert 'norm_combo.setCurrentIndex' in source


def test_binned_physical_y_axis_uses_nice_physical_ticks():
    source = Path("src/maxiv_panda/ui_map_plot_mixin.py").read_text(encoding="utf-8")
    assert 'MaxNLocator' in source
    assert 'physical_ticks = _np.asarray(locator.tick_values(lo, hi)' in source
    assert '_np.interp(physical_ticks, values, row_centers)' in source
