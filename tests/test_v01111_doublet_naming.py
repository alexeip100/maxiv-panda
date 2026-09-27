from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_create_doublet_always_assigns_numbered_family_label():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_dialog_doublet_mixin.py").read_text(encoding="utf-8")
    assert 'requested_base = str(le_label.text()).strip() or "Doublet"' in src
    assert 'renumber_doublet_family(requested_base, existing_labels)' in src
    assert 'st["label"] = new_label' in src


def test_doublet_card_tooltip_lists_major_and_minor_peak_ids():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_widgets.py").read_text(encoding="utf-8")
    assert 'Major component: P' in src
    assert 'minor component: P' in src
    assert 'title.setToolTip(component_tip)' in src
