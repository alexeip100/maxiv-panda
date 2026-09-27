from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Callable, Any
import os
import tempfile
import time

import numpy as np

from ..energy_utils import infer_energy_scale, normalize_energy_xlabel


@dataclass(frozen=True)
class MonitorTiming:
    """Timing information suitable for display by a future live-monitor UI."""

    mode: str
    poll_interval_s: float
    settle_interval_s: float
    learned_cadence_s: float | None = None
    learning: bool = True


@dataclass(frozen=True)
class LiveMapUpdate:
    """A validated update emitted by the live monitor core.

    ``new_spectra`` contains only rows not already held by the consumer unless
    ``reset`` is true.  For a reset, it contains the complete currently valid
    map so the consumer can replace its state atomically.
    """

    path: Path
    x: np.ndarray
    new_spectra: np.ndarray
    total_spectra: int
    reset: bool
    second_axis: np.ndarray | None = None
    second_axis_label: str = ""
    xlabel: str = "Energy [eV]"
    energy_scale: str = "Unknown"


@dataclass(frozen=True)
class _FileStamp:
    mtime_ns: int
    size: int


class LiveFileMonitorCore:
    """Thread-agnostic state machine for a growing 1D/2D analyzer file.

    The class performs no Qt work.  A QThread worker can call :meth:`tick` and
    forward returned updates as signals.  The live acquisition file is copied
    through a non-locking shared-read handle on Windows and the parser sees only
    the temporary snapshot, never the writer-owned file itself.
    """

    AUTO = "auto"

    def __init__(
        self,
        path: str | Path,
        *,
        kind: str | None = None,
        mode: str = AUTO,
        fixed_interval_s: float = 2.0,
        region_index: int = 0,
        parser: Callable[[Path], Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.path = Path(path)
        self.kind = (kind or self._kind_from_path(self.path)).upper()
        self.mode = str(mode).lower()
        self.fixed_interval_s = max(0.25, float(fixed_interval_s))
        self.region_index = max(0, int(region_index))
        self._parser = parser or self._default_parser
        self._clock = clock

        self._last_seen_stamp: _FileStamp | None = None
        self._stable_since: float | None = None
        self._change_started: float | None = None
        self._last_parse_attempt: float = float("-inf")
        self._last_success_time: float | None = None
        self._last_tick_time: float | None = None
        self._cadences: deque[float] = deque(maxlen=8)
        self._write_durations: deque[float] = deque(maxlen=8)

        self._x: np.ndarray | None = None
        self._spectra: np.ndarray | None = None
        self._second_axis: np.ndarray | None = None
        self._second_axis_label = ""
        self._xlabel = "Energy [eV]"
        self._energy_scale = "Unknown"

    def _default_parser(self, path: Path) -> Any:
        if self.kind == "IBW":
            from ..ibw_parser import parse_ibw
            return parse_ibw(path)
        if self.kind == "TXT":
            from ..txt_parser import parse_structured_txt
            return parse_structured_txt(path)
        raise ValueError(f"Unsupported live-monitor kind: {self.kind}")

    @staticmethod
    def _kind_from_path(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".ibw":
            return "IBW"
        if suffix in {".txt", ".dat", ".csv"}:
            return "TXT"
        raise ValueError(f"Unsupported live-monitor file type: {suffix or '(none)'}")

    @property
    def total_spectra(self) -> int:
        return 0 if self._spectra is None else int(self._spectra.shape[0])

    def reset_state(self) -> None:
        self._last_seen_stamp = None
        self._stable_since = None
        self._change_started = None
        self._last_parse_attempt = float("-inf")
        self._last_success_time = None
        self._last_tick_time = None
        self._cadences.clear()
        self._write_durations.clear()
        self._x = None
        self._spectra = None
        self._second_axis = None
        self._second_axis_label = ""
        self._xlabel = "Energy [eV]"
        self._energy_scale = "Unknown"

    def set_timing_mode(self, mode: str, *, fixed_interval_s: float | None = None) -> None:
        mode = str(mode).lower()
        if mode != self.AUTO and mode != "fixed":
            raise ValueError("mode must be 'auto' or 'fixed'")
        self.mode = mode
        if fixed_interval_s is not None:
            self.fixed_interval_s = max(0.25, float(fixed_interval_s))

    def idle_timeout_s(self) -> float | None:
        """Return the no-update interval that marks a learned acquisition idle.

        The idle state is intentionally conservative: Auto timing must have at
        least two observed update intervals before PANDA can infer that the
        acquisition has probably stopped.
        """

        if len(self._cadences) < 2:
            return None
        learned = float(median(self._cadences))
        return max(30.0, 5.0 * learned)

    def is_idle(self, now: float | None = None) -> bool:
        """Whether a previously learned acquisition appears to have stopped."""

        timeout = self.idle_timeout_s()
        if timeout is None or self._last_success_time is None:
            return False
        if now is None:
            now = self._last_tick_time
            if now is None:
                now = self._clock()
        return float(now) - self._last_success_time >= timeout

    def timing(self) -> MonitorTiming:
        if self.mode == self.AUTO:
            learned = float(median(self._cadences)) if self._cadences else None
            if self.is_idle():
                # Keep watching for a same-file restart, but stop probing a
                # finished/paused acquisition several times per second.
                poll = 5.0
            elif learned is None:
                poll = 0.5
            else:
                # Probe often enough to discover a write burst without turning
                # metadata polling into busy waiting.  5 probes/cadence is a
                # practical compromise for slow synchrotron acquisitions.
                poll = min(5.0, max(0.5, learned / 5.0))
            # A short quiet period after the last observed metadata change is
            # enough to avoid parsing most in-progress rewrites.  Failed or
            # partial snapshots are harmless and retried on a later cycle.
            settle = 0.75
            return MonitorTiming(
                mode=self.AUTO,
                poll_interval_s=poll,
                settle_interval_s=settle,
                learned_cadence_s=learned,
                learning=len(self._cadences) < 2,
            )
        return MonitorTiming(
            mode="fixed",
            poll_interval_s=self.fixed_interval_s,
            settle_interval_s=0.5,
            learned_cadence_s=(float(median(self._cadences)) if self._cadences else None),
            learning=False,
        )

    def next_poll_delay_s(self) -> float:
        timing = self.timing()
        if self._change_started is not None:
            # A file change has already been observed.  Even if Auto is in the
            # relaxed idle state (5 s checks), recheck promptly after the settle
            # period so a restarted fast acquisition cannot keep moving the file
            # before PANDA ever gets a stable snapshot.
            return min(timing.poll_interval_s, max(0.25, timing.settle_interval_s))
        return timing.poll_interval_s

    def tick(self, now: float | None = None) -> LiveMapUpdate | None:
        """Inspect the file once and return a validated update, if any.

        Expected transient conditions (file busy, half-written snapshot, parse
        failure) are intentionally silent and simply return ``None``.
        """

        now = self._clock() if now is None else float(now)
        self._last_tick_time = now
        try:
            stat = self.path.stat()
        except OSError:
            return None
        stamp = _FileStamp(int(stat.st_mtime_ns), int(stat.st_size))

        if self._last_seen_stamp is None:
            self._last_seen_stamp = stamp
            self._stable_since = now
            self._change_started = now
            return self._attempt_parse(now, force=True)

        if stamp != self._last_seen_stamp:
            if self._change_started is None:
                self._change_started = now
            self._last_seen_stamp = stamp
            self._stable_since = now
            return None

        if self._stable_since is None:
            self._stable_since = now
            return None

        settle = self.timing().settle_interval_s
        if now - self._stable_since < settle:
            return None
        if now - self._last_parse_attempt < min(0.25, settle):
            return None
        return self._attempt_parse(now)

    def _attempt_parse(self, now: float, *, force: bool = False) -> LiveMapUpdate | None:
        self._last_parse_attempt = now
        try:
            snapshot = _snapshot_to_temp(self.path)
        except OSError:
            return None
        if snapshot is None:
            return None
        try:
            try:
                parsed = self._parser(snapshot)
            except Exception:
                return None
        finally:
            try:
                snapshot.unlink(missing_ok=True)
            except Exception:
                pass

        try:
            x, spectra, second_axis, second_axis_label, xlabel, energy_scale = _extract_map(
                parsed, region_index=self.region_index
            )
        except Exception:
            return None
        if spectra.shape[0] < 1 or spectra.shape[1] < 1:
            return None

        had_state = self._spectra is not None and self._x is not None
        update = self._classify_update(x, spectra, second_axis, second_axis_label, xlabel, energy_scale)
        if update is None and not force:
            return None
        if update is None:
            # ``force`` is only relevant for the initial parse; a valid initial
            # dataset always becomes a reset event.
            update = self._replace_state(x, spectra, second_axis, second_axis_label, xlabel, energy_scale)

        # A reset after an already-valid map means the acquisition file has
        # started a new epoch in place (for example, iteration count returned
        # to 1 under the same filename).  Do not let the idle gap between runs
        # contaminate Auto timing; relearn from the new acquisition instead.
        restarted_in_place = bool(had_state and update.reset)
        if restarted_in_place:
            self._cadences.clear()
            self._write_durations.clear()
            self._last_success_time = None

        if self._change_started is not None:
            self._change_started = None
        if self._last_success_time is not None:
            cadence = now - self._last_success_time
            if cadence > 0:
                self._cadences.append(cadence)
        self._last_success_time = now
        return update

    def _classify_update(
        self,
        x: np.ndarray,
        spectra: np.ndarray,
        second_axis: np.ndarray | None,
        second_axis_label: str,
        xlabel: str,
        energy_scale: str,
    ) -> LiveMapUpdate | None:
        if self._spectra is None or self._x is None:
            return self._replace_state(x, spectra, second_axis, second_axis_label, xlabel, energy_scale)

        old = self._spectra
        same_x = self._x.shape == x.shape and np.allclose(self._x, x, rtol=1e-9, atol=1e-10, equal_nan=True)
        if not same_x or spectra.shape[1] != old.shape[1] or spectra.shape[0] < old.shape[0]:
            return self._replace_state(x, spectra, second_axis, second_axis_label, xlabel, energy_scale)

        n_old = old.shape[0]
        if spectra.shape[0] == n_old:
            # Same number of spectra.  A changed prefix means the file was
            # replaced/restarted in place, so reset rather than silently drift.
            if not np.allclose(old, spectra, rtol=1e-8, atol=1e-10, equal_nan=True):
                return self._replace_state(x, spectra, second_axis, second_axis_label, xlabel, energy_scale)
            return None

        prefix = spectra[:n_old]
        if not np.allclose(old, prefix, rtol=1e-8, atol=1e-10, equal_nan=True):
            return self._replace_state(x, spectra, second_axis, second_axis_label, xlabel, energy_scale)

        new_rows = np.array(spectra[n_old:], dtype=float, copy=True)
        self._x = np.array(x, dtype=float, copy=True)
        self._spectra = np.array(spectra, dtype=float, copy=True)
        self._second_axis = None if second_axis is None else np.array(second_axis, dtype=float, copy=True)
        self._second_axis_label = str(second_axis_label or "")
        self._xlabel = str(xlabel or "Energy [eV]")
        self._energy_scale = str(energy_scale or "Unknown")
        return LiveMapUpdate(
            path=self.path,
            x=self._x.copy(),
            new_spectra=new_rows,
            total_spectra=int(spectra.shape[0]),
            reset=False,
            second_axis=(None if second_axis is None else np.array(second_axis[n_old:], dtype=float, copy=True)),
            second_axis_label=self._second_axis_label,
            xlabel=self._xlabel,
            energy_scale=self._energy_scale,
        )

    def _replace_state(
        self,
        x: np.ndarray,
        spectra: np.ndarray,
        second_axis: np.ndarray | None,
        second_axis_label: str,
        xlabel: str,
        energy_scale: str,
    ) -> LiveMapUpdate:
        self._x = np.array(x, dtype=float, copy=True)
        self._spectra = np.array(spectra, dtype=float, copy=True)
        self._second_axis = None if second_axis is None else np.array(second_axis, dtype=float, copy=True)
        self._second_axis_label = str(second_axis_label or "")
        self._xlabel = str(xlabel or "Energy [eV]")
        self._energy_scale = str(energy_scale or "Unknown")
        return LiveMapUpdate(
            path=self.path,
            x=self._x.copy(),
            new_spectra=self._spectra.copy(),
            total_spectra=int(self._spectra.shape[0]),
            reset=True,
            second_axis=(None if self._second_axis is None else self._second_axis.copy()),
            second_axis_label=self._second_axis_label,
            xlabel=self._xlabel,
            energy_scale=self._energy_scale,
        )


def discover_live_regions(path: str | Path) -> list[tuple[int, str]]:
    """Return monitorable regions as ``(zero_based_index, display_name)``.

    TXT exports can contain several analyzer regions in one physical file, while
    normal IBW acquisition writes one region per file.  Discovery is deliberately
    lightweight and side-effect free so the file context menu can expose each TXT
    region as an independent Live Monitor target.
    """

    source = Path(path)
    if source.suffix.lower() != ".txt":
        return [(0, source.stem)]
    from ..txt_parser import parse_structured_txt

    parsed = parse_structured_txt(source)
    out: list[tuple[int, str]] = []
    for idx, region in enumerate(getattr(parsed, "regions", ()) or ()):
        name = str(getattr(region, "region_name", "") or f"Region {idx + 1}").strip()
        out.append((idx, name or f"Region {idx + 1}"))
    return out


def _extract_map(
    parsed: Any, *, region_index: int = 0
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, str, str, str]:
    regions = getattr(parsed, "regions", None)
    if not regions:
        raise ValueError("Parsed file has no regions")
    idx = int(region_index)
    if idx < 0 or idx >= len(regions):
        raise ValueError(f"Live-monitor region index {idx} is out of range")
    reg = regions[idx]
    mat = np.asarray(getattr(reg, "data", None), dtype=float)
    if mat.ndim != 2 or mat.shape[1] < 2:
        raise ValueError("Live-monitor region is not a plottable spectrum/map")
    x = np.asarray(mat[:, 0], dtype=float)
    spectra = np.asarray(mat[:, 1:], dtype=float).T

    second_axis = None
    meta = getattr(reg, "region_meta", {}) or {}
    info = getattr(reg, "info_meta", {}) or {}
    second_axis_label = str(meta.get("Dimension 2 name") or "").strip()
    raw_axis = meta.get("Dimension 2 scale")
    if raw_axis:
        try:
            values = np.asarray([float(v) for v in str(raw_axis).split()], dtype=float)
            if values.size == spectra.shape[0]:
                second_axis = values
        except Exception:
            second_axis = None
    raw_xlabel = str(meta.get("Dimension 1 name") or "Energy [eV]")
    energy_scale = infer_energy_scale(
        info.get("Energy Scale") or meta.get("Energy Scale") or "",
        hints=[raw_xlabel, info.get("Spectrum Name") or "", meta.get("Region Name") or ""],
    )
    xlabel = normalize_energy_xlabel(raw_xlabel, energy_scale)
    return x, spectra, second_axis, second_axis_label, xlabel, energy_scale


def _snapshot_to_temp(path: Path) -> Path | None:
    """Copy ``path`` to a temporary snapshot without ever locking the writer."""

    try:
        before = path.stat()
    except OSError:
        return None
    data = _read_shared_bytes(path)
    if data is None:
        return None
    try:
        after = path.stat()
    except OSError:
        return None
    if int(before.st_mtime_ns) != int(after.st_mtime_ns) or int(before.st_size) != int(after.st_size):
        # The analyzer changed the file while PANDA was copying it.  Discard
        # this snapshot and try again later; the writer always has priority.
        return None
    suffix = path.suffix or ".dat"
    fd, name = tempfile.mkstemp(prefix="panda_live_", suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
    except Exception:
        try:
            os.close(fd)
        except Exception:
            pass
        try:
            Path(name).unlink(missing_ok=True)
        except Exception:
            pass
        raise
    return Path(name)


def _read_shared_bytes(path: Path) -> bytes | None:
    if os.name != "nt":
        try:
            return path.read_bytes()
        except OSError:
            return None
    return _read_shared_bytes_windows(path)


def _read_shared_bytes_windows(path: Path) -> bytes | None:
    """Read with Windows share flags that never deny analyzer writes/deletes."""

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    FILE_SHARE_DELETE = 0x00000004
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x00000080
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    CreateFileW = kernel32.CreateFileW
    CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    CreateFileW.restype = wintypes.HANDLE
    ReadFile = kernel32.ReadFile
    ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    ReadFile.restype = wintypes.BOOL
    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL

    handle = CreateFileW(
        str(path),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle == INVALID_HANDLE_VALUE:
        return None

    chunks: list[bytes] = []
    try:
        chunk_size = 1024 * 1024
        while True:
            buf = ctypes.create_string_buffer(chunk_size)
            read = wintypes.DWORD(0)
            ok = ReadFile(handle, buf, chunk_size, ctypes.byref(read), None)
            if not ok:
                return None
            if read.value == 0:
                break
            chunks.append(buf.raw[: read.value])
    finally:
        CloseHandle(handle)
    return b"".join(chunks)
