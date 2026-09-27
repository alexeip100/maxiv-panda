from pathlib import Path

from maxiv_panda.utils.help_text import get_usage_html


DOCS = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda" / "docs"


def _h1_titles(filename: str) -> list[str]:
    return [
        line[2:].strip()
        for line in (DOCS / filename).read_text(encoding="utf-8").splitlines()
        if line.startswith("# ")
    ]


def test_what_is_what_major_sections_are_ordered_and_limited():
    assert _h1_titles("usage_controls.md") == [
        "Application overview",
        "Data loading and selection",
        "Data tabs and plot area",
        "Signal identification",
        "Processing and energy calibration",
        "Cross-section reference",
        "Binding-energy reference",
        "Spectrum fitting",
        "Sequence fitting and analysis",
        "Output and conventions",
    ]


def test_how_to_major_sections_follow_user_workflow():
    assert _h1_titles("usage_workflows.md") == [
        "Load and organize data",
        "Inspect spectra and use references",
        "Identify signals",
        "Process and calibrate spectra",
        "Fit one spectrum",
        "Fit a sequence",
        "Analyze and export results",
        "Troubleshooting and fitting workflow",
    ]


def test_help_html_has_semantic_visual_hierarchy_and_cross_links():
    html = get_usage_html("usage_controls.md")
    assert 'data-help-level="1"' in html
    assert 'font-size:23px' in html
    assert 'background-color:' in html
    assert 'font-size:20px' in html
    assert 'font-size:19px' in html
    assert 'font-size:18px' in html
    assert 'margin-top:3.20em' in html
    assert '<h1' not in html
    assert "See also:" in html
    assert 'href="#signal-identification"' in html
    assert "<blockquote>" in html


def test_help_dialog_source_has_clear_titles_and_wide_resizable_toc():
    source = (DOCS.parent / "ui_actions_mixin.py").read_text(encoding="utf-8")
    assert 'QLabel("Table of Contents")' in source
    assert 'dlg.resize(1240, 800)' in source
    assert 'splitter.setSizes([390, 830])' in source
    assert 'toc.setMaximumWidth' not in source
    assert 'help_name = "What is what?"' in source
    assert "GUI elements and analysis methods" in source
    assert "Practical workflows and troubleshooting" in source
    assert 'header.setMaximumHeight(44)' in source
    assert 'layout.addWidget(splitter, 1)' in source
    assert 'toc_title.setFont(toc_title_font)' in source
    assert 'pane_title.setFont(pane_title_font)' in source
    assert 'font-style: italic' in source
    assert 'color: palette(link)' in source


def test_help_sources_do_not_use_raw_horizontal_rules_or_long_dashes():
    for filename in ("usage_controls.md", "usage_workflows.md"):
        text = (DOCS / filename).read_text(encoding="utf-8")
        assert "\n---\n" not in text
        assert "—" not in text
        assert "–" not in text


def test_fallback_renderer_handles_fourth_level_headings():
    from maxiv_panda.utils.help_text import _basic_md_to_html
    html = _basic_md_to_html("#### Control name\n\nText")
    assert "<h4" in html
    assert "####" not in html


def test_plotted_data_help_covers_controls_and_workflow():
    controls = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")
    for label in (
        "Pass to plotting", "Legend style...", "Reverse X", "Annotation...",
        "Plotted curves list", "Waterfall", "Export / Import", "Clear plotted",
    ):
        assert label in controls
    assert "## Compose and export curves in Plotted Data" in workflows
    assert "<select curve name>" in controls


def test_reference_help_uses_core_level_terminology_and_top_level_binding_reference():
    controls = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")
    assert "# Binding-energy reference" in controls
    assert "## Reference sources and scope" in controls
    assert "Available core levels" in controls
    assert "Available core levels" in workflows
    assert "Available core shells" not in controls
    assert "Available core shells" not in workflows


def test_map_help_covers_respes_and_generic_trace_comparison():
    controls = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")
    for label in (
        "ResPES analysis", "Constant BE", "Constant KE", "Plot trace",
        "Plot H-trace", "Plot V-trace", "Animation...", "Trace comparison", "Rename...",
    ):
        assert label in controls
        assert label in workflows
    assert "## Compare ResPES excitation profiles" in workflows
    assert "Export CSV in the ResPES panel" not in controls
    assert "Export CSV → Horizontal trace" not in workflows


def test_batch_help_covers_full_fit_storage_navigation_and_export():
    controls = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")
    for label in ("Store all fit results", "Export all fits...", "Fit navigation"):
        assert label in controls or label in workflows
    assert "left/right arrows" in controls
    assert "batch_manifest.csv" in controls
    assert "one CSV per spectrum" in workflows


def test_post_0944_help_is_consistent_with_current_controls():
    controls = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")
    assert "A **MAP** button is shown only for a genuine multi-iteration dataset" in controls
    assert "gradient preview for each available palette" in controls
    assert "All 2D maps use **terrain** by default" in controls
    assert "Right-click directly inside the 2D image" in controls
    assert "Lines cursor positions are remembered for each map" in controls
    assert "PhE = 585.00 eV" in controls
    assert "Iteration = N" in controls
    assert "Leave it at 1 for no binning" in workflows
    assert "Decide whether to enable **binning**" not in workflows
    assert "drag horizontally for **Energy** and vertically for **Height**" in workflows
    assert "marker size for marker-only curves" in controls


def test_help_uses_current_flip_x_axis_label():
    for filename in ("usage_controls.md", "usage_workflows.md"):
        text = (DOCS / filename).read_text(encoding="utf-8")
        assert "Flip X axis" in text
        assert "Flip BE" not in text
