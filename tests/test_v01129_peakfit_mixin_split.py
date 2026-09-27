from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src/maxiv_panda/workflows/peakfit"


def _read(name: str) -> str:
    return (PEAKFIT / name).read_text(encoding="utf-8")


def test_dialog_inherits_new_responsibility_mixins():
    dialog = _read("fit_dialog.py")
    assert "from .fit_dialog_component_display_mixin import FitDialogComponentDisplayMixin" in dialog
    assert "from .fit_dialog_peak_interaction_mixin import FitDialogPeakInteractionMixin" in dialog
    assert "FitDialogBackgroundMixin," in dialog
    assert "FitDialogComponentDisplayMixin," in dialog
    assert "FitDialogPeakInteractionMixin," in dialog


def test_background_mixin_contains_only_background_responsibility():
    text = _read("fit_dialog_background_mixin.py")
    assert "def _compute_shirley_background" in text
    assert "def _refresh_bg_artist" in text
    assert "def _on_peak_marker_press" not in text
    assert "def _on_calculate_spectrum" not in text


def test_component_display_mixin_owns_rendering_and_colors():
    text = _read("fit_dialog_component_display_mixin.py")
    assert "def _on_calculate_spectrum" in text
    assert "def _sync_peak_display_colors" in text
    assert "def _refresh_peak_markers" in text
    assert "def _on_peak_marker_motion" not in text


def test_peak_interaction_mixin_owns_dragging_and_initialization():
    text = _read("fit_dialog_peak_interaction_mixin.py")
    assert "def _on_peak_marker_press" in text
    assert "def _on_peak_marker_motion" in text
    assert "def _on_peak_marker_release" in text
    assert "def _apply_peak_defaults_from_ranges" in text
    assert "def _on_calculate_spectrum" not in text
