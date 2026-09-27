from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_MIXIN = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit" / "batch_run_mixin.py"
PEAK_ONLY = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit" / "batch_peak_only_table.py"
DOUBLET = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit" / "batch_table_builder.py"


def test_shared_batch_table_explicitly_enables_editing_triggers():
    text = RUN_MIXIN.read_text(encoding="utf-8")
    assert "setEditTriggers(" in text
    for trigger in (
        "EditTrigger.SelectedClicked",
        "EditTrigger.DoubleClicked",
        "EditTrigger.EditKeyPressed",
        "EditTrigger.AnyKeyPressed",
    ):
        assert trigger in text


def test_both_paths_expose_same_user_editable_parameter_columns():
    peak = PEAK_ONLY.read_text(encoding="utf-8")
    doublet = DOUBLET.read_text(encoding="utf-8")
    for col in (6, 8, 9, 11):
        assert f"table.setItem(row_idx, {col}," in peak
        assert f"table.setItem(row_idx, {col}," in doublet
    # Peak-only rows are editable; doublet-aware rows use the same rule for
    # every independent row and only suppress edits for genuinely derived rows.
    assert 'row.get("initial"), editable=True' in peak
    assert 'row.get("initial"), editable=not derived' in doublet
    assert 'row.get("min"), editable=True' in peak
    assert 'row.get("min"), editable=not derived' in doublet
    assert 'row.get("max"), editable=True' in peak
    assert 'row.get("max"), editable=not derived' in doublet
    assert 'row.get("tie", ""), editable=True' in peak
    assert 'row.get("tie", ""), editable=not derived' in doublet
