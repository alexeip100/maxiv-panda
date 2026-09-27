from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda" / "docs"


def test_controls_help_covers_current_so_doublet_controls_and_naming():
    text = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    for phrase in (
        "### SO doublets",
        "Create SO doublet...",
        "Major peak",
        "Minor peak",
        "Doublet #1",
        "S 2p #1",
        "Splitting",
        "Ratio",
        "Tied to",
        "Same",
        "Independent",
        "Clone",
        "Ungroup",
        "Doublet view",
        "major marker",
    ):
        assert phrase in text
    assert "PANDA does not guess doublets automatically" in text
    assert "Constituent peaks keep their simple `P1`, `P2`, ... labels" in text


def test_workflow_help_documents_dedicated_so_doublet_workflow_alongside_manual_peak_ties():
    text = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")
    assert "## Build and fit SO doublets" in text
    assert "Press **Create SO doublet...**" in text
    assert "statistical major/minor height ratio only as an initial value" in text
    assert "Any clone can itself be cloned" in text
    assert "Doublet view stays active during fitting" in text
    assert "## Link ordinary peaks manually with Tied" in text
    assert "Both mechanisms remain available" in text
    assert "instead of manually constructing peak-to-peak ties" not in text


def test_help_states_current_batch_doublet_support_and_two_mode_table():
    controls = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")
    assert "Ordinary peak-only anchors keep the existing batch parameter table unchanged" in controls
    assert "Splitting and Ratio are exposed as editable batch parameters" in workflows
    assert "greyed-out **Derived** entries" in workflows
    assert "same major/minor pairings" in controls
