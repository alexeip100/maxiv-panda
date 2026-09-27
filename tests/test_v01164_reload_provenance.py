from pathlib import Path


def test_processed_to_plotted_copy_preserves_source_metadata():
    source = Path("src/maxiv_panda/ui_processed_data_mixin.py").read_text(encoding="utf-8")
    body = source.split("def _pass_selected_to_plotting", 1)[1].split("def _is_processed_tab_active", 1)[0]
    assert 'metadata=dict(getattr(payload, "metadata", {}) or {})' in body


def test_main_plot_title_rebuild_preserves_source_metadata():
    source = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
    body = source.split("def _update_plot_from_selected", 1)[1].split("def ", 1)[0]
    assert 'metadata=dict(getattr(first, "metadata", {}) or {})' in body


def test_reload_dependency_scanner_counts_plotted_snapshot_metadata():
    source = Path("src/maxiv_panda/ui_source_reload_mixin.py").read_text(encoding="utf-8")
    assert 'meta.get("source_snapshot_id")' in source
    assert "plotted += 1" in source
