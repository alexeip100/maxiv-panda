from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import os

import numpy as np

from maxiv_panda.live_monitor.core import LiveFileMonitorCore


def _write_count(path: Path, count: int, stamp_ns: int) -> None:
    path.write_text(f"count={count}\n", encoding="ascii")
    os.utime(path, ns=(stamp_ns, stamp_ns))


def _fake_parser(path: Path):
    count = int(path.read_text(encoding="ascii").strip().split("=")[1])
    x = np.linspace(282.0, 290.0, 200)
    cols = [x]
    for i in range(count):
        center = 284.5 + 0.02 * i
        y = np.exp(-0.5 * ((x - center) / 0.18) ** 2) * (1.0 + 0.03 * i)
        cols.append(y)
    mat = np.column_stack(cols)
    meta = {"Dimension 1 name": "Binding Energy [eV]"}
    if count > 1:
        meta["Dimension 2 scale"] = " ".join(str(700 + i) for i in range(count))
    reg = SimpleNamespace(
        data=mat,
        region_meta=meta,
        info_meta={"Energy Scale": "Binding"},
    )
    return SimpleNamespace(regions=[reg])


def test_growing_file_emits_only_new_spectra_and_restart_resets(tmp_path: Path):
    path = tmp_path / "live.ibw"
    _write_count(path, 1, 1_000_000_000)
    core = LiveFileMonitorCore(path, parser=_fake_parser)

    first = core.tick(now=0.0)
    assert first is not None and first.reset is True
    assert first.total_spectra == 1
    assert first.new_spectra.shape == (1, 200)

    _write_count(path, 2, 2_000_000_000)
    assert core.tick(now=1.0) is None
    second = core.tick(now=2.0)
    assert second is not None and second.reset is False
    assert second.total_spectra == 2
    assert second.new_spectra.shape == (1, 200)
    assert second.second_axis is not None
    assert second.second_axis.tolist() == [701.0]

    _write_count(path, 4, 3_000_000_000)
    assert core.tick(now=6.0) is None
    third = core.tick(now=7.0)
    assert third is not None and third.reset is False
    assert third.total_spectra == 4
    assert third.new_spectra.shape == (2, 200)

    # Relaunching the external simulator overwrites the same file with one row.
    _write_count(path, 1, 4_000_000_000)
    assert core.tick(now=10.0) is None
    restarted = core.tick(now=11.0)
    assert restarted is not None and restarted.reset is True
    assert restarted.total_spectra == 1
    assert restarted.new_spectra.shape == (1, 200)


def test_auto_timing_learns_acquisition_cadence(tmp_path: Path):
    path = tmp_path / "live.ibw"
    _write_count(path, 1, 1_000_000_000)
    core = LiveFileMonitorCore(path, parser=_fake_parser)
    assert core.tick(now=0.0) is not None

    for count, changed_at, parsed_at, stamp in [
        (2, 4.0, 5.0, 2_000_000_000),
        (3, 9.0, 10.0, 3_000_000_000),
        (4, 14.0, 15.0, 4_000_000_000),
    ]:
        _write_count(path, count, stamp)
        assert core.tick(now=changed_at) is None
        assert core.tick(now=parsed_at) is not None

    timing = core.timing()
    assert timing.mode == "auto"
    assert timing.learning is False
    assert 4.5 <= timing.learned_cadence_s <= 5.5
    assert 0.5 <= timing.poll_interval_s <= 2.0
    assert timing.settle_interval_s >= 0.5


def test_fixed_timing_is_exposed(tmp_path: Path):
    path = tmp_path / "live.ibw"
    _write_count(path, 1, 1_000_000_000)
    core = LiveFileMonitorCore(path, parser=_fake_parser, mode="fixed", fixed_interval_s=2.0)
    timing = core.timing()
    assert timing.mode == "fixed"
    assert timing.poll_interval_s == 2.0
    assert timing.settle_interval_s == 0.5


def test_windows_snapshot_uses_write_and_delete_share_flags():
    source = Path('src/maxiv_panda/live_monitor/core.py').read_text(encoding='utf-8')
    assert 'FILE_SHARE_WRITE' in source
    assert 'FILE_SHARE_DELETE' in source
    assert 'FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE' in source


def test_snapshot_discards_source_that_changes_while_being_copied():
    source = Path('src/maxiv_panda/live_monitor/core.py').read_text(encoding='utf-8')
    assert 'before = path.stat()' in source
    assert 'after = path.stat()' in source
    assert 'before.st_mtime_ns' in source
    assert 'before.st_size' in source


def test_live_update_carries_main_plot_energy_axis_metadata(tmp_path: Path):
    path = tmp_path / "live.ibw"
    _write_count(path, 1, 1_000_000_000)
    core = LiveFileMonitorCore(path, parser=_fake_parser)
    update = core.tick(now=0.0)
    assert update is not None
    assert update.xlabel == "Binding Energy [eV]"
    assert update.energy_scale.lower().startswith("bind")


def test_restart_relearns_auto_timing_without_cross_run_idle_gap(tmp_path: Path):
    path = tmp_path / "live.ibw"
    _write_count(path, 1, 1_000_000_000)
    core = LiveFileMonitorCore(path, parser=_fake_parser)
    assert core.tick(now=0.0) is not None

    # Learn a stable 5 s acquisition interval.
    for count, changed_at, parsed_at, stamp in [
        (2, 4.0, 5.0, 2_000_000_000),
        (3, 9.0, 10.0, 3_000_000_000),
    ]:
        _write_count(path, count, stamp)
        assert core.tick(now=changed_at) is None
        assert core.tick(now=parsed_at) is not None
    assert core.timing().learned_cadence_s == 5.0

    # Much later, the same filename is reused and starts again at iteration 1.
    _write_count(path, 1, 4_000_000_000)
    assert core.tick(now=100.0) is None
    restarted = core.tick(now=101.0)
    assert restarted is not None and restarted.reset is True
    assert restarted.total_spectra == 1
    timing = core.timing()
    assert timing.learned_cadence_s is None
    assert timing.learning is True
    assert timing.poll_interval_s == 0.5

    # New-run timing is learned only from updates belonging to the new run.
    _write_count(path, 2, 5_000_000_000)
    assert core.tick(now=105.0) is None
    assert core.tick(now=106.0) is not None
    assert core.timing().learned_cadence_s == 5.0


def test_idle_state_uses_learned_cadence_and_auto_relaxes_polling(tmp_path: Path):
    path = tmp_path / "live.ibw"
    _write_count(path, 1, 1_000_000_000)
    core = LiveFileMonitorCore(path, parser=_fake_parser)
    assert core.tick(now=0.0) is not None

    # Learn a stable 5 s spectrum interval from at least two intervals.
    for count, changed_at, parsed_at, stamp in [
        (2, 4.0, 5.0, 2_000_000_000),
        (3, 9.0, 10.0, 3_000_000_000),
    ]:
        _write_count(path, count, stamp)
        assert core.tick(now=changed_at) is None
        assert core.tick(now=parsed_at) is not None

    assert core.idle_timeout_s() == 30.0
    assert core.is_idle(now=39.9) is False
    assert core.is_idle(now=40.0) is True

    # A poll while idle keeps watching but relaxes Auto to 5 s.
    assert core.tick(now=40.0) is None
    assert core.is_idle() is True
    assert core.timing().poll_interval_s == 5.0

    # A new valid spectrum immediately clears the idle condition.
    _write_count(path, 4, 4_000_000_000)
    assert core.tick(now=41.0) is None
    resumed = core.tick(now=42.0)
    assert resumed is not None
    assert core.is_idle() is False


def test_fixed_mode_reports_idle_but_does_not_relax_user_poll_interval(tmp_path: Path):
    path = tmp_path / "live.ibw"
    _write_count(path, 1, 1_000_000_000)
    core = LiveFileMonitorCore(path, parser=_fake_parser, mode="fixed", fixed_interval_s=2.0)
    assert core.tick(now=0.0) is not None
    for count, changed_at, parsed_at, stamp in [
        (2, 4.0, 5.0, 2_000_000_000),
        (3, 9.0, 10.0, 3_000_000_000),
    ]:
        _write_count(path, count, stamp)
        assert core.tick(now=changed_at) is None
        assert core.tick(now=parsed_at) is not None
    assert core.is_idle(now=40.0) is True
    assert core.timing().poll_interval_s == 2.0


def test_idle_file_change_uses_short_settle_recheck_for_fast_restart(tmp_path: Path):
    path = tmp_path / "live.ibw"
    _write_count(path, 1, 1_000_000_000)
    core = LiveFileMonitorCore(path, parser=_fake_parser)
    assert core.tick(now=0.0) is not None

    # Learn a stable 5 s acquisition interval, then become idle.
    for count, changed_at, parsed_at, stamp in [
        (2, 4.0, 5.0, 2_000_000_000),
        (3, 9.0, 10.0, 3_000_000_000),
    ]:
        _write_count(path, count, stamp)
        assert core.tick(now=changed_at) is None
        assert core.tick(now=parsed_at) is not None

    assert core.is_idle(now=40.0) is True
    # A real idle poll also updates the core's current time, which is what the
    # worker does before asking for the next delay.
    assert core.tick(now=40.0) is None
    assert core.timing().poll_interval_s == 5.0

    # A restarted acquisition may write every 3 s.  The first idle poll that
    # notices the restart must schedule a settle/recheck (< 5 s), otherwise
    # every sparse poll can encounter yet another changed stamp forever.
    _write_count(path, 1, 4_000_000_000)
    assert core.tick(now=45.0) is None
    assert core.next_poll_delay_s() == core.timing().settle_interval_s
    assert core.next_poll_delay_s() < 5.0

    restarted = core.tick(now=45.75)
    assert restarted is not None
    assert restarted.reset is True
    assert restarted.total_spectra == 1
    assert core.is_idle() is False
    assert core.timing().learning is True
