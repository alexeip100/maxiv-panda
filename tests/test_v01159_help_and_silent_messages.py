from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "maxiv_panda"
DOCS = SRC / "docs"


def test_help_covers_major_current_workflows_and_two_batch_paths():
    controls = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")

    for phrase in (
        "Show metadata",
        "Signal identification",
        "Normalization",
        "2D Map workflow",
        "ResPES analysis",
        "Trace comparison",
        "Plotted Data controls",
        "Energy calibration",
        "Cross-section reference",
        "Binding-energy reference",
        "SO doublets",
        "Save config to file...",
        "Prepare sequence fit tab",
        "Analyze fit results tab",
        "Export all fits...",
    ):
        assert phrase in controls

    for phrase in (
        "## Inspect file and acquisition metadata",
        "## Identify signals in a survey spectrum",
        "## Apply simple processing before fitting",
        "## Inspect a sequence as a 2D map",
        "## Compare ResPES excitation profiles",
        "## Compose and export curves in Plotted Data",
        "## Calibrate an energy scale",
        "## Save and reuse a fit configuration",
        "## Build and fit SO doublets",
        "## Choose the peak-only or SO-doublet batch path",
        "## Smooth a scattered parameter and prepare a constrained pass",
        "## Fit analytical trend curves for analysis and export",
        "## Export batch trend data",
    ):
        assert phrase in workflows


def test_help_explains_independent_vs_derived_so_batch_constraints():
    controls = (DOCS / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (DOCS / "usage_workflows.md").read_text(encoding="utf-8")

    for text in (controls, workflows):
        assert "Derived" in text
        assert "minor" in text.lower()
        assert "next-pass" in text.lower()

    assert "derived minor-member parameters" in controls
    assert "not offered as next-pass constraint targets" in controls
    assert "derived minor-member parameters are intentionally absent from the next-pass target list" in workflows
    assert "minor Energy can retain a small amount of wobble" in workflows
    assert "analytical trend fits there are descriptive only" in workflows


def test_all_panda_message_boxes_use_silent_wrapper_directly():
    offenders = []
    for path in SRC.rglob("*.py"):
        if path.name == "silent_message_box.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "PyQt6.QtWidgets":
                if any(alias.name == "QMessageBox" for alias in node.names):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
    assert offenders == []

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in SRC.rglob("*.py")
        if path.name != "silent_message_box.py"
    )
    assert "QApplication.beep(" not in source


def test_silent_wrapper_is_used_by_message_box_call_sites():
    for path in SRC.rglob("*.py"):
        if path.name == "silent_message_box.py":
            continue
        text = path.read_text(encoding="utf-8")
        if "QMessageBox." not in text and "QMessageBox(" not in text:
            continue
        assert "SilentMessageBox as QMessageBox" in text, path.relative_to(ROOT)


def test_release_version_is_at_least_01159():
    version_py = (ROOT / "src" / "maxiv_panda" / "version.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    import re
    version = re.search(r'__version__ = "([0-9]+)\.([0-9]+)\.([0-9]+)"', version_py)
    assert version and tuple(map(int, version.groups())) >= (0, 11, 59)
    v = ".".join(version.groups())
    assert f'version = "{v}"' in pyproject
