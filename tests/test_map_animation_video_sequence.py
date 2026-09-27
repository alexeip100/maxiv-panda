from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"


def test_animation_dialog_offers_combined_h_then_v_video_sequence():
    source = (SRC / "widgets" / "map_animation_dialog.py").read_text(encoding="utf-8")
    assert 'self.cb_video_sequence.addItems(["Current line", "H then V"])' in source
    assert 'lines = [self._line()] if sequence != "H then V" else ["h", "v"]' in source
    assert '"orientation": line' in source
    assert '"label": "H" if str(line).lower().startswith("h") else "V"' in source


def test_combined_video_export_writes_all_segments_to_one_ffmpeg_stream():
    source = (SRC / "ui_map_controls_mixin.py").read_text(encoding="utf-8")
    assert "for seg in segments:" in source
    assert 'orientation = str(seg.get("orientation") or "h")' in source
    assert "for local_frame, position in enumerate(positions, start=1):" in source
    assert 'plot_area.set_map_lines_cursor_position(orientation, position, redraw=False)' in source
    assert 'progress_callback(global_frame, label, cycle_no, cycles)' in source


def test_help_documents_h_then_v_sequence():
    controls = (SRC / "docs" / "usage_controls.md").read_text(encoding="utf-8")
    workflows = (SRC / "docs" / "usage_workflows.md").read_text(encoding="utf-8")
    assert "**H then V**" in controls
    assert "**H then V**" in workflows
