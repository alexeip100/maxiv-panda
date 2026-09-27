from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "src" / "maxiv_panda" / "ui_raw_data_mixin.py"
HELP = ROOT / "src" / "maxiv_panda" / "docs" / "usage_controls.md"


def _source() -> str:
    return RAW.read_text(encoding="utf-8")


def test_region_combo_has_reversible_preview_popup_contract():
    src = _source()
    assert "class RegionPreviewComboBox(QComboBox)" in src
    assert "popupOpened = pyqtSignal(int)" in src
    assert "popupClosed = pyqtSignal(bool)" in src
    assert "self._popup_open_index = int(self.currentIndex())" in src
    assert "committed = bool(self._popup_activated)" in src
    assert "self.setCurrentIndex(self._popup_open_index)" in src


def test_region_preview_is_wired_to_highlight_and_activation_separately():
    src = _source()
    assert "highlighted.connect(self._on_all_region_preview_highlighted)" in src
    assert "activated.connect(self._on_all_region_activated)" in src
    assert "popupOpened.connect(self._on_all_region_preview_opened)" in src
    assert "popupClosed.connect(self._on_all_region_preview_closed)" in src
    # Popup browsing must not let currentIndexChanged commit every arrow-key highlight.
    changed_body = src.split("def _on_all_in_region_changed", 1)[1].split("def _on_all_region_activated", 1)[0]
    assert "if self._all_region_preview_popup_open:" in changed_body
    assert "return" in changed_body


def test_preview_is_plot_only_and_cancel_restores_committed_plot():
    src = _source()
    preview = src.split("def _preview_all_in_region", 1)[1].split("def _on_all_in_region_toggled", 1)[0]
    assert "self.plot_area.plot_many(" in preview
    assert "self._iter_curve_leaves()" in preview
    assert "setCheckState" not in preview
    assert "_rebuild_selected_from_loaded" not in preview
    assert "_apply_all_in_region_selection" not in preview

    closed = src.split("def _on_all_region_preview_closed", 1)[1].split("def _preview_all_in_region", 1)[0]
    assert "if not committed:" in closed
    assert "self._update_plot_from_selected()" in closed


def test_help_documents_region_preview_browsing():
    text = HELP.read_text(encoding="utf-8")
    assert "All in region" in text
    assert "temporarily previews the highlighted region" in text
    assert "Click / Enter" in text
    assert "Esc" in text
    assert "does not change the checked curves" in text


def test_release_version_metadata_agrees():
    import re

    version_py = (ROOT / "src" / "maxiv_panda" / "version.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version_match = re.search(r'__version__\s*=\s*"([^"]+)"', version_py)
    project_match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert version_match is not None
    assert project_match is not None
    assert version_match.group(1) == project_match.group(1)
