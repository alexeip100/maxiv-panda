"""Ensure the release Help uses real fitting entry-point controls."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / 'src' / 'maxiv_panda' / 'docs'


def test_single_fit_workflow_names_real_entry_point():
    source = (ROOT / 'src/maxiv_panda/ui_processed_data_mixin.py').read_text(encoding='utf-8')
    workflow = (DOCS / 'usage_workflows.md').read_text(encoding='utf-8')
    assert 'QPushButton("Fit selected"' in source
    assert '**Processed Data**' in workflow
    assert '**Fit selected**' in workflow
    assert 'Open **Fit core-level PE spectra**' not in workflow
    assert 'open **Fit core-level PE spectra**' not in workflow


def test_batch_choice_names_real_control():
    source = (ROOT / 'src/maxiv_panda/workflows/peakfit/fit_dialog.py').read_text(encoding='utf-8')
    workflow = (DOCS / 'usage_workflows.md').read_text(encoding='utf-8')
    assert '"Prepare sequence fit"' in source
    assert '"Fit selected curves individually"' in source
    assert '**Prepare sequence fit**' in workflow


def test_release_notes_are_self_contained():
    for name in ('whats_new.md',):
        note = (DOCS / name).read_text(encoding='utf-8')
        section = note.split('## PANDA 0.12.5', 1)[1].split('## PANDA 0.12.4', 1)[0]
        assert 'EXACT' not in section
        assert all(f'### {heading}' in section for heading in ('Added', 'Changed', 'Fixed'))
