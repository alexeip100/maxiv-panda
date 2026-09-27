from pathlib import Path

CORE = Path("src/maxiv_panda/live_monitor/core.py").read_text(encoding="utf-8")
CONTROLS = Path("src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
WORKFLOWS = Path("src/maxiv_panda/docs/usage_workflows.md").read_text(encoding="utf-8")
ACTIONS = Path("src/maxiv_panda/ui_actions_mixin.py").read_text(encoding="utf-8")
PYPROJECT = Path("pyproject.toml").read_text(encoding="utf-8")


def test_idle_change_temporarily_uses_settle_recheck_delay():
    assert "if self._change_started is not None" in CORE
    assert "timing.settle_interval_s" in CORE
    assert "return min(timing.poll_interval_s" in CORE


def test_help_explains_idle_change_recheck_transition():
    for doc in (CONTROLS, WORKFLOWS):
        assert "5 s" in doc
        assert "settle/recheck" in doc


def test_panda_expansion_is_photoemission_everywhere_user_facing():
    expected = "Photoemission Analysis, Normalization and Data Assessment"
    assert expected in CONTROLS
    assert expected in ACTIONS
    assert "PANDA" in PYPROJECT
    for path in Path(".").rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".py", ".md", ".toml"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        old = "Photoelectron Analysis" + ", Normalization and Data Assessment"
        assert old not in text, path
