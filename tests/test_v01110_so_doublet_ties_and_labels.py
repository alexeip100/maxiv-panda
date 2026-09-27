from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_doublet_editor_exposes_tied_modes():
    src = (ROOT / 'src/maxiv_panda/workflows/peakfit/fit_widgets.py').read_text(encoding='utf-8')
    assert 'cb.addItem("Fixed", ("Fixed", None))' in src
    assert 'cb.addItem("Free", ("Free", None))' in src
    assert 'f"Tied to {label}"' in src


def test_clone_path_keeps_peak_labels_simple_and_numbers_doublets_only():
    src = (ROOT / 'src/maxiv_panda/workflows/peakfit/fit_dialog_doublet_mixin.py').read_text(encoding='utf-8')
    assert 'renumber_doublet_family' in src
    assert 'major_state["label"] = f"P{new_major_i}"' in src
    assert 'minor_state["label"] = f"P{new_minor_i}"' in src
