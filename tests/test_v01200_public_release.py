from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_version_and_metadata():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = (ROOT / "src/maxiv_panda/version.py").read_text(encoding="utf-8")
    assert 'version = "0.12.2"' in pyproject
    assert '__version__ = "0.12.2"' in version
    assert 'name = "Alexei Preobrajenski"' in pyproject
    assert 'Repository = "https://github.com/alexeip100/maxiv-panda"' in pyproject


def test_public_identity_files_are_consistent():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    cff = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    actions = (ROOT / "src/maxiv_panda/ui_actions_mixin.py").read_text(encoding="utf-8")
    phrase = "Alexei Preobrajenski (MAX IV Laboratory)"
    assert phrase in readme
    assert phrase in actions
    assert "Alexei Preobrajenski, MAX IV Laboratory" in license_text
    assert 'version: 0.12.2' in cff
    assert 'affiliation: "MAX IV Laboratory"' in cff
    assert "Photoemission Analysis, Normalization and Data Assessment" in cff


def test_public_description_is_present_in_readme_and_about():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    actions = (ROOT / "src/maxiv_panda/ui_actions_mixin.py").read_text(encoding="utf-8")
    first = "PANDA is a Python software package with an interactive graphical interface for"
    assert first in readme
    assert first in actions
    assert "It was developed at the FlexPES beamline at MAX IV Laboratory." in readme


def test_whats_new_is_real_help_page():
    ui = (ROOT / "src/maxiv_panda/ui.py").read_text(encoding="utf-8")
    doc = ROOT / "src/maxiv_panda/docs/whats_new.md"
    assert doc.is_file()
    assert 'md_filename="whats_new.md"' in ui
    assert '_show_not_implemented_dialog("What\'s new?")' not in ui
    text = doc.read_text(encoding="utf-8")
    assert text.startswith("# What’s new in PANDA\n")
    assert "## PANDA 0.12.1" in text
    assert "### Added" in text
    assert "### Fixed" in text
    assert "### Changed" in text
    assert "## PANDA 0.12.0" in text
    assert "### First public release" in text
    assert "Unified loading and analysis of **Scienta/SES TXT**, **Igor IBW**, and **SPECS/SpecsLab Prodigy XY** data." in text
    assert "Version 0.12.0 establishes the first public PANDA baseline." in text
    release_sections = [line for line in text.splitlines() if line.startswith("## PANDA ")]
    assert release_sections[:3] == ["## PANDA 0.12.2", "## PANDA 0.12.1", "## PANDA 0.12.0"]
    assert len(release_sections) <= 5
    assert release_sections[-1] == "## PANDA 0.12.0"
    assert len(release_sections) <= 5


def test_legacy_namespace_removed_but_saved_format_ids_retained():
    assert not (ROOT / "src/flexpes_pes").exists()
    fit_schema = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_schema.py").read_text(encoding="utf-8")
    fit_export = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_export.py").read_text(encoding="utf-8")
    batch = (ROOT / "src/maxiv_panda/workflows/peakfit/batch_config.py").read_text(encoding="utf-8")
    assert 'FORMAT_NAME = "flexpes_pes_fit_setup"' in fit_schema
    assert 'FORMAT_NAME = "flexpes_pes_single_fit_result"' in fit_export
    assert '"format": "flexpes_pes_batch_setup"' in batch
