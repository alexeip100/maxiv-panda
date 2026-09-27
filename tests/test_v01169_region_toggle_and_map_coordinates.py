from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "src" / "maxiv_panda" / "ui_raw_data_mixin.py"
LOADED = ROOT / "src" / "maxiv_panda" / "loaded_tree.py"
MAP = ROOT / "src" / "maxiv_panda" / "ui_map_plot_mixin.py"
UI = ROOT / "src" / "maxiv_panda" / "ui.py"
HELP = ROOT / "src" / "maxiv_panda" / "docs" / "usage_controls.md"


def test_all_in_region_off_clears_group_selection_and_rebuilds():
    src = RAW.read_text(encoding="utf-8")
    body = src.split("def _on_all_in_region_toggled", 1)[1].split("def _iter_curve_leaves", 1)[0]
    assert "if self.cb_all_in_region.isChecked():" in body
    assert "else:" in body
    assert "clear_curve_selection(leaves=leaves)" in body
    assert "self._rebuild_selected_from_loaded()" in body


def test_loaded_tree_clear_selection_unchecks_every_leaf_with_signals_blocked():
    src = LOADED.read_text(encoding="utf-8")
    body = src.split("def clear_curve_selection", 1)[1].split("def _cache_region_iteration_stack", 1)[0]
    assert "self.tree.blockSignals(True)" in body
    assert "for leaf in leaves:" in body
    assert "leaf.setCheckState(0, Qt.CheckState.Unchecked)" in body
    assert "self.tree.blockSignals(False)" in body


def test_map_toolbar_uses_fixed_width_font_and_ordinary_plots_restore_it():
    map_src = MAP.read_text(encoding="utf-8")
    ui_src = UI.read_text(encoding="utf-8")
    assert "def _stabilize_map_toolbar_coordinate_font" in map_src
    assert "QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)" in map_src
    assert "self._stabilize_map_toolbar_coordinate_font()" in map_src
    assert "def _restore_toolbar_coordinate_font" in map_src
    assert "if not images:" in ui_src
    assert "self._restore_toolbar_coordinate_font()" in ui_src


def test_help_documents_toggle_off_and_cross_platform_stationary_coordinates():
    text = HELP.read_text(encoding="utf-8")
    assert "Unchecking **All in region** clears that group selection" in text
    assert "fixed-width font" in text
    assert "Windows and macOS" in text


def test_release_version_metadata_stays_synchronized():
    import re

    version_py = (ROOT / "src" / "maxiv_panda" / "version.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    version = re.search(r'__version__ = "([^"]+)"', version_py).group(1)
    project_version = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1)
    assert version == project_version
    assert any(line.startswith(f"## {version}") for line in changelog.splitlines()[:5])
