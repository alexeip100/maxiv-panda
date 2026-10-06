from pathlib import Path

UI = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
CONTROLS = Path("src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
WORKFLOWS = Path("src/maxiv_panda/docs/usage_workflows.md").read_text(encoding="utf-8")


def test_region_nodes_offer_format_independent_live_monitor_action():
    assert 'elif metadata_scope == "region"' in UI
    assert 'file_path.lower().endswith((".ibw", ".txt"))' in UI
    assert 'parent.indexOfChild(item)' in UI
    assert 'live_region_actions[live_action]' in UI
    assert 'self._open_live_monitor(file_path, region_index=region_index, region_name=region_name)' in UI


def test_help_documents_region_level_live_monitor_for_txt_and_ibw():
    assert 'right-click an individual **region name**' in CONTROLS
    assert 'same region-level workflow for both TXT and IBW' in CONTROLS
    assert 'right-click either the **file-level entry** or an individual **region name**' in WORKFLOWS
    assert 'Region-level right-click works for both TXT and IBW data.' in WORKFLOWS
