from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from .core import LiveFileMonitorCore, LiveMapUpdate, MonitorTiming


class LiveFileMonitorWorker(QObject):
    """QObject intended to live in a dedicated QThread.

    The worker owns only a lightweight QTimer and the thread-agnostic monitor
    core.  It never accesses GUI widgets directly.
    """

    update_ready = pyqtSignal(object)      # LiveMapUpdate
    timing_changed = pyqtSignal(object)    # MonitorTiming
    status_changed = pyqtSignal(str)
    stopped = pyqtSignal()

    def __init__(
        self,
        path: str | Path,
        *,
        kind: str | None = None,
        mode: str = LiveFileMonitorCore.AUTO,
        fixed_interval_s: float = 2.0,
        region_index: int = 0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.core = LiveFileMonitorCore(
            path,
            kind=kind,
            mode=mode,
            fixed_interval_s=fixed_interval_s,
            region_index=region_index,
        )
        self._timer: QTimer | None = None
        self._running = False
        self._last_timing: MonitorTiming | None = None

    @pyqtSlot()
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._poll_once)
        self.status_changed.emit("Monitoring")
        self._schedule_next(0.0)

    @pyqtSlot()
    def stop(self) -> None:
        self._running = False
        if self._timer is not None:
            self._timer.stop()
        self.status_changed.emit("Stopped")
        self.stopped.emit()

    @pyqtSlot(str, float)
    def set_timing(self, mode: str, fixed_interval_s: float = 2.0) -> None:
        self.core.set_timing_mode(mode, fixed_interval_s=fixed_interval_s)
        self._emit_timing_if_changed(force=True)
        if self._running:
            self._schedule_next(0.0)

    @pyqtSlot()
    def _poll_once(self) -> None:
        if not self._running:
            return
        try:
            update = self.core.tick()
            if update is not None:
                self.update_ready.emit(update)
                self.status_changed.emit("Monitoring")
            elif self.core.is_idle():
                self.status_changed.emit("Acquisition appears stopped")
        except Exception:
            # Live acquisition is intentionally tolerant: an unexpected read
            # failure must never become a modal warning or stop the monitor.
            self.status_changed.emit("Waiting for readable file")
        self._emit_timing_if_changed()
        self._schedule_next(self.core.next_poll_delay_s())

    def _emit_timing_if_changed(self, *, force: bool = False) -> None:
        timing = self.core.timing()
        if force or timing != self._last_timing:
            self._last_timing = timing
            self.timing_changed.emit(timing)

    def _schedule_next(self, seconds: float) -> None:
        if not self._running or self._timer is None:
            return
        self._timer.start(max(0, int(round(float(seconds) * 1000.0))))
