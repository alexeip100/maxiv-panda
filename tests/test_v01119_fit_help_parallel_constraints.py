from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda" / "docs"


def test_howto_presents_manual_ties_and_so_doublets_as_parallel_options():
    text = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")
    assert "## Link ordinary peaks manually with Tied" in text
    assert "The original peak-level **Tied** mechanism remains fully supported" in text
    assert "Both mechanisms remain available" in text
    assert "additional structured option" in text
    assert "does not replace the manual peak-level **Tied** mechanism" in text
    assert "instead of manually constructing peak-to-peak ties" not in text
    assert "preferred" not in text.lower()


def test_howto_explains_manual_tie_semantics():
    text = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")
    assert "Energy tie preserves the current energy **offset**" in text
    assert "Height, LFWHM, GFWHM, and Alpha ties preserve the current **multiplicative factor**" in text
    assert "not combined by **Doublet view**" in text


def test_controls_help_distinguishes_peak_ties_from_doublet_level_ties():
    text = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    assert "**Tied** is the general peak-level linking mechanism" in text
    assert "independently of SO-doublet grouping" in text
    assert "**Create SO doublet...** is an additional structured option" in text
    assert "It does not replace the general peak-level **Tied** mechanism" in text
    assert "editable **Splitting** and **Ratio** rows" in text
    assert "General per-peak Free/Fixed/Tied relationships remain available" in text


def test_batch_help_preserves_doublet_constraints_and_manual_peak_ties():
    controls = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")
    assert "General per-peak Free/Fixed/Tied relationships remain available" in controls
    assert "Ordinary per-peak Free/Fixed/Tied relationships remain available" in workflows
    assert "Splitting and Ratio are exposed as editable batch parameters" in workflows
    assert "minor-component parameters controlled by the doublet are shown as greyed-out **Derived** entries" in workflows
