from __future__ import annotations

"""Compact non-modal animation and video-export controller for MAP -> Lines."""

from pathlib import Path
import re
from typing import Callable, Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from ..map_animation import (
    playback_positions,
    repeated_cycle_positions,
    smooth_positions,
    stepped_positions,
)


class MapAnimationDialog(QDialog):
    """Non-modal playback controls for the H/V cursors in MAP -> Lines."""

    _LIVE_RENDER_FPS = 60

    def __init__(
        self,
        parent: QWidget | None,
        context_provider: Callable[[str], dict[str, Any] | None],
        move_callback: Callable[[str, float], None],
        video_export_callback: Callable[
            [str, list[dict[str, Any]], int, Callable[[int, str, int, int], bool]], tuple[bool, str]
        ] | None = None,
    ) -> None:
        super().__init__(parent)
        self._context_provider = context_provider
        self._move_callback = move_callback
        self._video_export_callback = video_export_callback
        self._base_positions: list[int] = []
        self._play_positions: list[float] = []
        self._play_index = 0
        self._paused = False
        self._building = False
        self._last_context: dict[str, Any] | None = None
        self._last_video_dir = ""
        self._selected_line = "h"
        self._line_range_settings: dict[str, dict[str, float | int]] = {
            "h": {"mode": 0},
            "v": {"mode": 0},
        }

        self.setWindowTitle("Lines animation")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setMinimumWidth(350)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(7)

        # Line selection -------------------------------------------------
        line_row = QHBoxLayout()
        line_row.addWidget(QLabel("Line"))
        self.btn_h = QPushButton("H")
        self.btn_v = QPushButton("V")
        for btn in (self.btn_h, self.btn_v):
            btn.setCheckable(True)
            btn.setMinimumWidth(48)
        self._line_group = QButtonGroup(self)
        self._line_group.setExclusive(True)
        self._line_group.addButton(self.btn_h)
        self._line_group.addButton(self.btn_v)
        self.btn_h.setChecked(True)
        line_row.addWidget(self.btn_h)
        line_row.addWidget(self.btn_v)
        line_row.addStretch(1)
        self.lab_step = QLabel("Thickness / step: 1")
        line_row.addWidget(self.lab_step)
        root.addLayout(line_row)

        # Range ----------------------------------------------------------
        range_grid = QGridLayout()
        range_grid.setHorizontalSpacing(6)
        range_grid.setVerticalSpacing(4)
        range_grid.addWidget(QLabel("Range"), 0, 0)
        self.cb_range = QComboBox()
        self.cb_range.addItems(["Full range", "Custom"])
        range_grid.addWidget(self.cb_range, 0, 1, 1, 3)

        self.lab_from = QLabel("From")
        self.sb_from = QDoubleSpinBox()
        self.lab_to = QLabel("To")
        self.sb_to = QDoubleSpinBox()
        for spin in (self.sb_from, self.sb_to):
            spin.setDecimals(4)
            spin.setRange(-1.0e12, 1.0e12)
            spin.setKeyboardTracking(False)
        range_grid.addWidget(self.lab_from, 1, 0)
        range_grid.addWidget(self.sb_from, 1, 1)
        range_grid.addWidget(self.lab_to, 1, 2)
        range_grid.addWidget(self.sb_to, 1, 3)
        root.addLayout(range_grid)

        # Motion ---------------------------------------------------------
        motion = QGridLayout()
        motion.setHorizontalSpacing(6)
        motion.setVerticalSpacing(4)
        motion.addWidget(QLabel("Speed"), 0, 0)
        self.sb_fps = QSpinBox()
        self.sb_fps.setRange(1, 30)
        self.sb_fps.setValue(10)
        self.sb_fps.setSuffix(" steps/s")
        self.sb_fps.setToolTip(
            "Physical animation steps per second. One physical step equals the "
            "selected line thickness; intermediate display frames are interpolated."
        )
        motion.addWidget(self.sb_fps, 0, 1)
        motion.addWidget(QLabel("Mode"), 1, 0)
        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["One way", "Back and forth"])
        motion.addWidget(self.cb_mode, 1, 1)
        self.chk_loop = QCheckBox("Loop")
        self.chk_loop.setToolTip("Loop continuously during live preview. Video export uses its own Cycles value.")
        motion.addWidget(self.chk_loop, 1, 2)
        motion.setColumnStretch(3, 1)
        root.addLayout(motion)

        # Live status ----------------------------------------------------
        status = QHBoxLayout()
        self.lab_current = QLabel("Current: —")
        self.lab_frame = QLabel("Frame — / —")
        status.addWidget(self.lab_current)
        status.addStretch(1)
        status.addWidget(self.lab_frame)
        root.addLayout(status)

        # Transport ------------------------------------------------------
        transport = QHBoxLayout()
        self.btn_first = QPushButton("|<")
        self.btn_play = QPushButton("▶")
        self.btn_pause = QPushButton("❚❚")
        self.btn_stop = QPushButton("■")
        self.btn_last = QPushButton(">|")
        tips = {
            self.btn_first: "Jump to first animation position",
            self.btn_play: "Play / resume smooth preview",
            self.btn_pause: "Pause at the current position",
            self.btn_stop: "Stop and return to the first position",
            self.btn_last: "Jump to last animation position",
        }
        for btn, tip in tips.items():
            btn.setToolTip(tip)
            btn.setMinimumWidth(48)
            transport.addWidget(btn)
        root.addLayout(transport)

        # Video export ---------------------------------------------------
        sep = QFrame(self)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        video_title = QLabel("Video")
        f = video_title.font()
        f.setBold(True)
        video_title.setFont(f)
        root.addWidget(video_title)

        video_grid = QGridLayout()
        video_grid.setHorizontalSpacing(6)
        video_grid.setVerticalSpacing(4)
        video_grid.addWidget(QLabel("Frame rate"), 0, 0)
        self.sb_video_fps = QSpinBox()
        self.sb_video_fps.setRange(1, 60)
        self.sb_video_fps.setValue(30)
        self.sb_video_fps.setSuffix(" fps")
        video_grid.addWidget(self.sb_video_fps, 0, 1)
        video_grid.addWidget(QLabel("Cycles"), 0, 2)
        self.sb_video_cycles = QSpinBox()
        self.sb_video_cycles.setRange(1, 100)
        self.sb_video_cycles.setValue(1)
        self.sb_video_cycles.setToolTip(
            "Number of complete finite cycles written to the video. The live Loop checkbox is ignored."
        )
        video_grid.addWidget(self.sb_video_cycles, 0, 3)
        video_grid.addWidget(QLabel("Sequence"), 1, 0)
        self.cb_video_sequence = QComboBox()
        self.cb_video_sequence.addItems(["Current line", "H then V"])
        self.cb_video_sequence.setToolTip(
            "Current line exports the currently selected H or V animation. "
            "H then V exports the configured H sweep followed by the configured V sweep in one MP4."
        )
        video_grid.addWidget(self.cb_video_sequence, 1, 1, 1, 3)
        self.lab_video_output = QLabel("Output: 2D map + H trace + V trace")
        self.lab_video_output.setToolTip(
            "The saved movie contains the same Matplotlib figure area as Save figure: "
            "the 2D map and both side traces, not the Qt controls."
        )
        video_grid.addWidget(self.lab_video_output, 2, 0, 1, 4)
        root.addLayout(video_grid)

        self.btn_save_video = QPushButton("Save video...")
        self.btn_save_video.setToolTip(
            "Choose an MP4 filename, then render the configured animation directly to that file."
        )
        self.btn_save_video.setEnabled(callable(self._video_export_callback))
        root.addWidget(self.btn_save_video)

        # Wiring ---------------------------------------------------------
        self.btn_h.toggled.connect(lambda checked: checked and self._line_changed("h"))
        self.btn_v.toggled.connect(lambda checked: checked and self._line_changed("v"))
        self.cb_range.currentIndexChanged.connect(self._range_mode_changed)
        self.sb_fps.valueChanged.connect(self._speed_changed)
        self.cb_mode.currentIndexChanged.connect(self._definition_changed)
        self.chk_loop.toggled.connect(self._loop_changed)
        self.sb_from.editingFinished.connect(self._definition_changed)
        self.sb_to.editingFinished.connect(self._definition_changed)
        self.btn_first.clicked.connect(self._jump_first)
        self.btn_play.clicked.connect(self._play)
        self.btn_pause.clicked.connect(self._pause)
        self.btn_stop.clicked.connect(self._stop_and_reset)
        self.btn_last.clicked.connect(self._jump_last)
        self.btn_save_video.clicked.connect(self._save_video)

        self._range_mode_changed()
        self.refresh_context(stop=False, preserve_custom=False)

    # ------------------------------------------------------------------
    # Context / position construction
    # ------------------------------------------------------------------
    def _line(self) -> str:
        return str(getattr(self, "_selected_line", "h") or "h")

    def _context_for_line(self, line: str) -> dict[str, Any] | None:
        try:
            ctx = self._context_provider("v" if str(line).lower().startswith("v") else "h")
        except Exception:
            ctx = None
        return dict(ctx) if ctx else None

    def _context(self) -> dict[str, Any] | None:
        return self._context_for_line(self._line())

    def _save_range_settings(self, line: str | None = None) -> None:
        line = "v" if str(line or self._line()).lower().startswith("v") else "h"
        try:
            self._line_range_settings[line] = {
                "mode": int(self.cb_range.currentIndex()),
                "from": float(self.sb_from.value()),
                "to": float(self.sb_to.value()),
            }
        except Exception:
            self._line_range_settings[line] = {"mode": int(self.cb_range.currentIndex())}

    @staticmethod
    def _clamp_spin_value(spin: QDoubleSpinBox, value: float) -> float:
        try:
            return max(float(spin.minimum()), min(float(spin.maximum()), float(value)))
        except Exception:
            return float(value)

    def _restore_range_settings(self, line: str) -> None:
        settings = dict(self._line_range_settings.get(line, {}))
        mode = int(settings.get("mode", 0))
        self._building = True
        try:
            self.cb_range.setCurrentIndex(1 if mode == 1 else 0)
            if mode == 1:
                fval = settings.get("from", self.sb_from.value())
                tval = settings.get("to", self.sb_to.value())
                self.sb_from.setValue(self._clamp_spin_value(self.sb_from, float(fval)))
                self.sb_to.setValue(self._clamp_spin_value(self.sb_to, float(tval)))
        finally:
            self._building = False
        self._range_mode_changed()

    def _range_settings_for(self, line: str) -> dict[str, float | int]:
        line = "v" if str(line).lower().startswith("v") else "h"
        if line == self._line():
            return {
                "mode": int(self.cb_range.currentIndex()),
                "from": float(self.sb_from.value()),
                "to": float(self.sb_to.value()),
            }
        return dict(self._line_range_settings.get(line, {"mode": 0}))

    @staticmethod
    def _decimals(values) -> int:
        try:
            vals = [float(v) for v in values]
            diffs = sorted(abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1))
            diffs = [d for d in diffs if d > 0]
            if not diffs:
                return 3
            spacing = diffs[len(diffs) // 2]
            import math
            return max(0, min(6, int(math.ceil(-math.log10(spacing))) + 1))
        except Exception:
            return 3

    def refresh_context(self, *, stop: bool = True, preserve_custom: bool = True) -> None:
        if stop and self._timer.isActive():
            self._timer.stop()
            self._paused = False
        ctx = self._context()
        self._last_context = ctx
        enabled = bool(ctx and ctx.get("valid_indices"))
        for widget in (
            self.cb_range, self.sb_from, self.sb_to, self.sb_fps, self.cb_mode,
            self.chk_loop, self.btn_first, self.btn_play, self.btn_pause,
            self.btn_stop, self.btn_last, self.sb_video_fps, self.sb_video_cycles,
            self.cb_video_sequence,
        ):
            widget.setEnabled(enabled)
        self.btn_save_video.setEnabled(enabled and callable(self._video_export_callback))
        if not enabled:
            self.lab_step.setText("Thickness / step: —")
            self.lab_current.setText("Current: —")
            self.lab_frame.setText("Frame — / —")
            return

        coords = list(ctx.get("coordinates", []))
        valid = list(ctx.get("valid_indices", []))
        thickness = int(ctx.get("thickness", 1))
        self.lab_step.setText(f"Thickness / step: {thickness}")
        decimals = self._decimals(coords)
        for spin in (self.sb_from, self.sb_to):
            spin.setDecimals(decimals)

        first_value = float(coords[valid[0]])
        last_value = float(coords[valid[-1]])
        all_valid_values = [float(coords[i]) for i in valid]
        lo = min(all_valid_values)
        hi = max(all_valid_values)
        pad = max(abs(hi - lo) * 0.02, 1.0e-9)
        for spin in (self.sb_from, self.sb_to):
            spin.setRange(lo - pad, hi + pad)
        if not preserve_custom or self.cb_range.currentIndex() == 0:
            self._building = True
            try:
                self.sb_from.setValue(first_value)
                self.sb_to.setValue(last_value)
            finally:
                self._building = False
        self._update_status(float(ctx.get("current_index", valid[0])), None, None)
        self._range_mode_changed()

    def external_thickness_changed(self) -> None:
        self.refresh_context(stop=True, preserve_custom=True)
        self._base_positions = []
        self._play_positions = []

    def _line_changed(self, line: str) -> None:
        line = "v" if str(line).lower().startswith("v") else "h"
        previous = self._line()
        self._timer.stop()
        self._paused = False
        self._base_positions = []
        self._play_positions = []
        self._save_range_settings(previous)
        target_settings = dict(self._line_range_settings.get(line, {"mode": 0}))
        self._selected_line = line
        self.refresh_context(stop=False, preserve_custom=False)
        # refresh_context() initializes the newly selected line's widgets; put
        # back its previously configured custom range afterwards.
        self._line_range_settings[line] = target_settings
        self._restore_range_settings(line)

    def _range_mode_changed(self, *_args) -> None:
        custom = self.cb_range.currentIndex() == 1
        for widget in (self.lab_from, self.sb_from, self.lab_to, self.sb_to):
            widget.setEnabled(custom and self.cb_range.isEnabled())
        if not custom and not self._building:
            ctx = self._context()
            if ctx and ctx.get("valid_indices"):
                coords = list(ctx.get("coordinates", []))
                valid = list(ctx.get("valid_indices", []))
                self._building = True
                try:
                    self.sb_from.setValue(float(coords[valid[0]]))
                    self.sb_to.setValue(float(coords[valid[-1]]))
                finally:
                    self._building = False
        self._save_range_settings()
        self._definition_changed()

    def _definition_changed(self, *_args) -> None:
        if self._building:
            return
        if self._timer.isActive():
            self._timer.stop()
        self._paused = False
        self._base_positions = []
        self._play_positions = []

    def _speed_changed(self, *_args) -> None:
        """Apply a new preview speed without interrupting safe live playback."""
        if self._building:
            return
        current_position = None
        if self._play_positions:
            try:
                current_position = float(self._play_positions[self._play_index])
            except Exception:
                current_position = None
        was_running = self._timer.isActive()
        was_paused = bool(self._paused)
        self._base_positions = self._build_base_positions()
        self._play_positions = self._build_play_positions()
        if self._play_positions and current_position is not None:
            self._play_index = min(
                range(len(self._play_positions)),
                key=lambda i: abs(float(self._play_positions[i]) - current_position),
            )
        else:
            self._play_index = 0
        self._paused = was_paused
        if was_running:
            # The timer remains active at the fixed smooth-render rate; changing
            # speed changes interpolation density, not the timer cadence.
            self._timer.setInterval(max(1, int(round(1000.0 / self._LIVE_RENDER_FPS))))
            if not self._timer.isActive():
                self._timer.start()

    def _loop_changed(self, *_args) -> None:
        """Loop is a safe live-playback option and needs no sequence rebuild."""
        return

    def _nearest_valid_index(self, value: float, ctx: dict[str, Any]) -> int:
        coords = list(ctx.get("coordinates", []))
        valid = list(ctx.get("valid_indices", []))
        return min(valid, key=lambda idx: abs(float(coords[idx]) - float(value)))

    def _build_base_positions_for(self, line: str, settings: dict[str, float | int] | None = None) -> list[int]:
        ctx = self._context_for_line(line)
        if not ctx:
            return []
        valid = list(ctx.get("valid_indices", []))
        if not valid:
            return []
        step = max(1, int(ctx.get("thickness", 1)))
        settings = dict(settings or self._range_settings_for(line))
        if int(settings.get("mode", 0)) == 0:
            start, end = int(valid[0]), int(valid[-1])
        else:
            start = self._nearest_valid_index(float(settings.get("from", 0.0)), ctx)
            end = self._nearest_valid_index(float(settings.get("to", 0.0)), ctx)
        return stepped_positions(start, end, step)

    def _build_base_positions(self) -> list[int]:
        return self._build_base_positions_for(self._line())

    def _cycle_key_positions_for(self, line: str, *, for_loop: bool = False) -> list[int]:
        base = self._build_base_positions_for(line)
        if not base:
            return []
        return playback_positions(
            base,
            self.cb_mode.currentText() == "Back and forth",
            bool(for_loop and self.cb_mode.currentText() == "Back and forth"),
        )

    def _cycle_key_positions(self, *, for_loop: bool = False) -> list[int]:
        return self._cycle_key_positions_for(self._line(), for_loop=for_loop)

    def _build_play_positions(self) -> list[float]:
        # For the live preview, use a full finite cycle. The Loop checkbox only
        # controls what happens after that cycle reaches its end.
        keys = self._cycle_key_positions(for_loop=False)
        return smooth_positions(
            keys,
            frame_rate=self._LIVE_RENDER_FPS,
            key_steps_per_second=float(self.sb_fps.value()),
        )

    @staticmethod
    def _cycle_numbers_for_positions(one_cycle: list[float], positions: list[float], cycles: int) -> list[int]:
        cycle_numbers: list[int] = []
        for cycle_no in range(1, cycles + 1):
            if cycle_no == 1:
                part = one_cycle
            elif one_cycle and positions and abs(one_cycle[0] - one_cycle[-1]) < 1.0e-12:
                part = one_cycle[1:]
            else:
                part = one_cycle
            cycle_numbers.extend([cycle_no] * len(part))
        if len(cycle_numbers) != len(positions):
            cycle_numbers = [min(cycles, 1 + (i * cycles // max(len(positions), 1))) for i in range(len(positions))]
        return cycle_numbers

    def _build_video_segments(self) -> tuple[list[dict[str, Any]], int, int]:
        fps = int(self.sb_video_fps.value())
        cycles = int(self.sb_video_cycles.value())
        sequence = str(self.cb_video_sequence.currentText() or "Current line")
        lines = [self._line()] if sequence != "H then V" else ["h", "v"]
        segments: list[dict[str, Any]] = []
        total_frames = 0
        for line in lines:
            keys = self._cycle_key_positions_for(line, for_loop=False)
            if not keys:
                continue
            one_cycle = smooth_positions(
                keys,
                frame_rate=fps,
                key_steps_per_second=float(self.sb_fps.value()),
            )
            positions = repeated_cycle_positions(one_cycle, cycles)
            if not positions:
                continue
            cycle_numbers = self._cycle_numbers_for_positions(one_cycle, positions, cycles)
            segments.append({
                "orientation": line,
                "positions": positions,
                "cycle_numbers": cycle_numbers,
                "cycles": cycles,
                "label": "H" if str(line).lower().startswith("h") else "V",
            })
            total_frames += len(positions)
        return segments, total_frames, fps

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------
    def _apply_play_index(self) -> None:
        if not self._play_positions:
            return
        pos = float(self._play_positions[self._play_index])
        try:
            self._move_callback(self._line(), pos)
        except Exception:
            self._timer.stop()
            return
        self._update_status(pos, self._play_index + 1, len(self._play_positions))

    def _play(self) -> None:
        if self._paused and self._play_positions:
            self._paused = False
        else:
            self._base_positions = self._build_base_positions()
            self._play_positions = self._build_play_positions()
            self._play_index = 0
            if not self._play_positions:
                return
            self._apply_play_index()
        self._timer.setInterval(max(1, int(round(1000.0 / self._LIVE_RENDER_FPS))))
        self._timer.start()

    def _pause(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self._paused = True

    def _stop_and_reset(self) -> None:
        self._timer.stop()
        self._paused = False
        self._base_positions = self._build_base_positions()
        self._play_positions = self._build_play_positions()
        self._play_index = 0
        if self._play_positions:
            self._apply_play_index()

    def _jump_first(self) -> None:
        self._timer.stop()
        self._paused = False
        self._base_positions = self._build_base_positions()
        self._play_positions = self._build_play_positions()
        self._play_index = 0
        if self._play_positions:
            self._apply_play_index()

    def _jump_last(self) -> None:
        self._timer.stop()
        self._paused = False
        self._base_positions = self._build_base_positions()
        if not self._base_positions:
            return
        pos = float(self._base_positions[-1])
        try:
            self._move_callback(self._line(), pos)
        except Exception:
            return
        self._play_positions = self._build_play_positions()
        self._update_status(pos, len(self._play_positions), len(self._play_positions))

    def _advance_frame(self) -> None:
        if not self._play_positions:
            self._timer.stop()
            return
        next_index = self._play_index + 1
        if next_index >= len(self._play_positions):
            if self.chk_loop.isChecked():
                # Back-and-forth ends at its starting position; skip the same
                # first frame on wrap to avoid a visible dwell.
                if (
                    len(self._play_positions) > 1
                    and abs(self._play_positions[-1] - self._play_positions[0]) < 1.0e-12
                ):
                    next_index = 1
                else:
                    next_index = 0
            else:
                self._timer.stop()
                self._paused = False
                return
        self._play_index = next_index
        self._apply_play_index()

    def _update_status(self, sample_position: float, frame: int | None, total: int | None) -> None:
        ctx = self._context()
        if not ctx:
            self.lab_current.setText("Current: —")
            self.lab_frame.setText("Frame — / —")
            return
        coords = list(ctx.get("coordinates", []))
        label = str(ctx.get("coordinate_label") or "Position")
        unit = str(ctx.get("coordinate_unit") or "")
        try:
            pos = float(sample_position)
            lo = max(0, min(len(coords) - 1, int(pos // 1)))
            hi = max(0, min(len(coords) - 1, lo + 1))
            alpha = max(0.0, min(1.0, pos - lo))
            value = float(coords[lo]) * (1.0 - alpha) + float(coords[hi]) * alpha
            decimals = self._decimals(coords)
            value_text = f"{value:.{decimals}f}"
        except Exception:
            value_text = f"{float(sample_position):g}"
        suffix = f" {unit}" if unit else ""
        self.lab_current.setText(f"Current: {label} = {value_text}{suffix}")
        if frame is None or total is None:
            self.lab_frame.setText("Frame — / —")
        else:
            self.lab_frame.setText(f"Frame {int(frame)} / {int(total)}")

    # ------------------------------------------------------------------
    # Video export
    # ------------------------------------------------------------------
    def _default_video_filename(self) -> str:
        ctx = self._context() or {}
        title = str(ctx.get("title") or "MAP")
        title = re.sub(r"[^A-Za-z0-9._-]+", "_", title).strip("._-") or "MAP"
        name = f"{title}_Lines_animation.mp4"
        return str(Path(self._last_video_dir) / name) if self._last_video_dir else name

    def _save_video(self) -> None:
        if not callable(self._video_export_callback):
            return
        self._timer.stop()
        self._paused = False
        self._save_range_settings()
        segments, total, fps = self._build_video_segments()
        if not segments or total <= 0:
            QMessageBox.warning(self, "Save video", "No valid animation frames are available.")
            return
        filename, _selected = QFileDialog.getSaveFileName(
            self,
            "Save animation video",
            self._default_video_filename(),
            "MP4 video (*.mp4)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".mp4"):
            filename += ".mp4"
        self._last_video_dir = str(Path(filename).parent)

        progress = QProgressDialog("Preparing video...", "Cancel", 0, total, self)
        progress.setWindowTitle("Saving video")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()
        QApplication.processEvents()

        def _progress(frame_no: int, segment_label: str = "", cycle_no: int = 1, cycles: int = 1) -> bool:
            frame_no = max(0, min(total, int(frame_no)))
            progress.setValue(frame_no)
            prefix = f"{segment_label} sweep   " if segment_label else ""
            progress.setLabelText(
                f"{prefix}Rendering frame {frame_no} / {total}    Cycle {cycle_no} / {cycles}"
            )
            QApplication.processEvents()
            return not progress.wasCanceled()

        ok = False
        message = ""
        try:
            ok, message = self._video_export_callback(
                filename, segments, fps, _progress
            )
        except Exception as exc:
            ok, message = False, str(exc)
        finally:
            progress.close()

        if ok:
            QMessageBox.information(self, "Video saved", f"Video saved successfully:\n{filename}")
        elif message and message.lower() != "canceled":
            QMessageBox.warning(self, "Video export failed", message)
        self.refresh_context(stop=False, preserve_custom=True)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        self._timer.stop()
        self._paused = False
        super().closeEvent(event)
