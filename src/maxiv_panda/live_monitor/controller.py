from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QMetaObject, QThread, Qt, pyqtSignal, pyqtSlot

from .worker import LiveFileMonitorWorker


class LiveFileMonitorController(QObject):
    """Own a live-file worker and guarantee that it runs in its own QThread."""

    update_ready = pyqtSignal(object)
    timing_changed = pyqtSignal(object)
    status_changed = pyqtSignal(str)

    _start_requested = pyqtSignal()
    _stop_requested = pyqtSignal()
    _timing_requested = pyqtSignal(str, float)

    def __init__(
        self,
        path: str | Path,
        *,
        kind: str | None = None,
        mode: str = "auto",
        fixed_interval_s: float = 2.0,
        region_index: int = 0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker = LiveFileMonitorWorker(
            path,
            kind=kind,
            mode=mode,
            fixed_interval_s=fixed_interval_s,
            region_index=region_index,
        )
        self._worker.moveToThread(self._thread)

        self._worker.update_ready.connect(self.update_ready)
        self._worker.timing_changed.connect(self.timing_changed)
        self._worker.status_changed.connect(self.status_changed)
        self._start_requested.connect(self._worker.start)
        self._stop_requested.connect(self._worker.stop)
        self._timing_requested.connect(self._worker.set_timing)
        self._thread.start()

    @property
    def is_thread_running(self) -> bool:
        return self._thread.isRunning()

    @pyqtSlot()
    def start(self) -> None:
        if self._thread.isRunning():
            self._start_requested.emit()

    @pyqtSlot()
    def stop(self) -> None:
        if self._thread.isRunning():
            self._stop_requested.emit()

    def set_auto(self) -> None:
        self._timing_requested.emit("auto", 2.0)

    def set_fixed_interval(self, seconds: float) -> None:
        self._timing_requested.emit("fixed", max(0.25, float(seconds)))

    def shutdown(self, timeout_ms: int = 3000) -> None:
        """Stop the worker and terminate its event-loop thread cleanly."""
        if not self._thread.isRunning():
            return
        QMetaObject.invokeMethod(
            self._worker,
            "stop",
            Qt.ConnectionType.BlockingQueuedConnection,
        )
        self._thread.quit()
        self._thread.wait(max(0, int(timeout_ms)))
