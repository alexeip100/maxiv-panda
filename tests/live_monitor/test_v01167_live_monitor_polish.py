from pathlib import Path


WINDOW = Path("src/maxiv_panda/live_monitor/window.py").read_text(encoding="utf-8")
UI = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
CORE = Path("src/maxiv_panda/live_monitor/core.py").read_text(encoding="utf-8")
CONTROLS = Path("src/maxiv_panda/docs/usage_controls.md").read_text(encoding="utf-8")
WORKFLOWS = Path("src/maxiv_panda/docs/usage_workflows.md").read_text(encoding="utf-8")


def test_timing_labels_match_requested_user_language():
    assert "Checked every" in WINDOW
    assert "Settle for" in WINDOW
    assert "New spectrum every" in WINDOW
    assert "Auto: check" not in WINDOW
    assert "Fixed: check" not in WINDOW
    assert "stable wait" not in WINDOW


def test_live_x_axis_uses_parser_label_and_main_flip_control():
    assert "xlabel: str" in CORE
    assert "normalize_energy_xlabel" in CORE
    assert "self.ax.set_xlabel(self._xlabel)" in WINDOW
    assert "def set_flip_x" in WINDOW
    assert "flip_x=bool(self.cb_flip_be.isChecked())" in UI
    assert "self.cb_flip_be.toggled.connect(window.set_flip_x)" in UI


def test_restart_resets_only_auto_timing_learning_epoch():
    assert "restarted_in_place = bool(had_state and update.reset)" in CORE
    assert "self._cadences.clear()" in CORE
    assert "self._last_success_time = None" in CORE


def test_help_explains_all_three_timing_concepts_and_values():
    for doc in (CONTROLS, WORKFLOWS):
        assert "Checked every" in doc
        assert "Settle for" in doc
        assert "New spectrum every" in doc
        assert "0.75 s" in doc
        assert "size" in doc.lower()
        assert "modification" in doc.lower()
