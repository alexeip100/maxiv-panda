from pathlib import Path


CORE = Path("src/maxiv_panda/live_monitor/core.py").read_text(encoding="utf-8")
WORKER = Path("src/maxiv_panda/live_monitor/worker.py").read_text(encoding="utf-8")
WINDOW = Path("src/maxiv_panda/live_monitor/window.py").read_text(encoding="utf-8")
CONTROLS = Path("src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
WORKFLOWS = Path("src/maxiv_panda/docs/usage_workflows.md").read_text(encoding="utf-8")


def test_idle_threshold_and_auto_relaxed_polling_are_explicit():
    assert "max(30.0, 5.0 * learned)" in CORE
    assert "if self.is_idle()" in CORE
    assert "poll = 5.0" in CORE
    assert 'status_changed.emit("Acquisition appears stopped")' in WORKER


def test_status_descriptors_are_bold_and_colored():
    assert '"Monitoring": "#2e8b57"' in WINDOW
    assert '"Stopped": "#c62828"' in WINDOW
    assert '"Acquisition appears stopped": "#cc7000"' in WINDOW
    assert '<b><span style=' in WINDOW


def test_help_documents_idle_status_and_continued_watching():
    for doc in (CONTROLS, WORKFLOWS):
        assert "Acquisition appears stopped" in doc
        assert "max(30 s, 5 × the learned interval)" in doc
        assert "5 s" in doc
        assert "Stopped" in doc
