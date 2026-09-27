from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_cross_section_markers_are_persisted_and_moved_live():
    text = _read("src/maxiv_panda/signal_identification/cross_section_reference.py")
    assert "self._intersection_markers = []" in text
    assert "marker.set_data([photon], [float(value)])" in text
    assert "for selection, marker in list(getattr(self, \"_intersection_markers\", []))" in text


def test_fit_legend_is_draggable_and_uses_peak_label_edits():
    dialog = _read("src/maxiv_panda/workflows/peakfit/fit_dialog.py")
    plotting = _read("src/maxiv_panda/workflows/peakfit/fit_plotting.py")
    component_display = _read("src/maxiv_panda/workflows/peakfit/fit_dialog_component_display_mixin.py")
    assert "legend.set_draggable(True)" in dialog
    assert 'w.get("label_edit").text()' in plotting
    assert 'self._peak_widgets[i - 1].get("label_edit").text()' in component_display


def test_tex_reference_uses_single_backslash_mathtext_commands():
    text = _read("src/maxiv_panda/workflows/plotting/tex_reference_dialog.py")
    assert 'r"$\\alpha$"' in text
    assert 'r"$\\pm$"' in text
    assert 'r"$^\\circ$"' in text
    assert 'r"$\\times$"' in text
    assert 'r"$\\\\alpha$"' not in text
    assert 'r"$\\\\pm$"' not in text


def test_menu_items_have_horizontal_padding():
    text = _read("src/maxiv_panda/ui_style.py")
    assert 'QMenu::item {{ padding: {metrics.menu_v_padding}px 10px; }}' in text
