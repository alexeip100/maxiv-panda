from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "src" / "maxiv_panda" / "ui.py").read_text(encoding="utf-8")


def test_large_xy_average_has_targeted_incremental_selection_path():
    start = UI.index("def _on_loaded_tree_item_changed")
    end = UI.index("def _schedule_update_plot_from_selected", start)
    block = UI[start:end]
    assert 'str(meta.get("kind") or "").lower() == "average"' in block
    assert "XY_LAZY_ITERATION_THRESHOLD" in block
    assert 'str(source_meta.get("Format") or "") == "SPECS Prodigy XY"' in block
    assert "self._selected_tree_manager.sync_loaded_leaf(" in block
    assert "self._update_plot_from_selected()" in block


def test_large_xy_average_fast_path_returns_before_full_rebuild():
    start = UI.index("def _on_loaded_tree_item_changed")
    end = UI.index("def _schedule_update_plot_from_selected", start)
    block = UI[start:end]
    sync_pos = block.index("self._selected_tree_manager.sync_loaded_leaf(")
    return_pos = block.index("return", sync_pos)
    rebuild_pos = block.rindex("self._schedule_rebuild_selected_from_loaded()")
    assert sync_pos < return_pos < rebuild_pos


def test_large_xy_average_fast_path_does_not_materialize_iterations():
    start = UI.index("def _on_loaded_tree_item_changed")
    end = UI.index("def _schedule_update_plot_from_selected", start)
    block = UI[start:end]
    assert "_materialize_lazy_iterations" not in block
