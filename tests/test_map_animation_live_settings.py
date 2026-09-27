from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"


def test_safe_animation_settings_do_not_use_definition_changed_handler():
    source = (SRC / "widgets" / "map_animation_dialog.py").read_text(encoding="utf-8")
    assert "self.sb_fps.valueChanged.connect(self._speed_changed)" in source
    assert "self.chk_loop.toggled.connect(self._loop_changed)" in source
    assert "def _loop_changed" in source
    assert "def _speed_changed" in source


def test_speed_change_preserves_running_timer_and_current_position():
    source = (SRC / "widgets" / "map_animation_dialog.py").read_text(encoding="utf-8")
    block = source.split("def _speed_changed", 1)[1].split("def _loop_changed", 1)[0]
    assert "was_running = self._timer.isActive()" in block
    assert "current_position" in block
    assert "self._play_positions = self._build_play_positions()" in block
    assert "self._timer.stop()" not in block


def test_video_controls_are_not_wired_to_live_definition_changes():
    source = (SRC / "widgets" / "map_animation_dialog.py").read_text(encoding="utf-8")
    for widget in ("sb_video_fps", "sb_video_cycles", "cb_video_sequence"):
        assert f"self.{widget}.valueChanged.connect(self._definition_changed)" not in source
        assert f"self.{widget}.currentIndexChanged.connect(self._definition_changed)" not in source
