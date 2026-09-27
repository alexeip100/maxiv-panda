from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from maxiv_panda.live_monitor.core import LiveFileMonitorCore, discover_live_regions


UI = Path("src/maxiv_panda/ui.py").read_text(encoding="utf-8")
WINDOW = Path("src/maxiv_panda/live_monitor/window.py").read_text(encoding="utf-8")
CONTROLLER = Path("src/maxiv_panda/live_monitor/controller.py").read_text(encoding="utf-8")
WORKER = Path("src/maxiv_panda/live_monitor/worker.py").read_text(encoding="utf-8")


def _write_two_region_txt(path: Path) -> None:
    path.write_text(
        "[Info]\n"
        "Number of Regions=0002\n\n"
        "[Region 1]\n"
        "Region Name=S2p_700eV\n"
        "Dimension 1 name=Binding Energy [eV]\n"
        "Dimension 1 size=2\n"
        "Dimension 2 size=2\n"
        "Dimension 2 scale=1 2\n"
        "[Info 1]\n"
        "Energy Scale=Binding\n"
        "[Data 1]\n"
        "166 10 11\n"
        "165 20 21\n\n"
        "[Region 2]\n"
        "Region Name=P2p_700eV\n"
        "Dimension 1 name=Binding Energy [eV]\n"
        "Dimension 1 size=2\n"
        "Dimension 2 size=3\n"
        "Dimension 2 scale=1 2 3\n"
        "[Info 2]\n"
        "Energy Scale=Binding\n"
        "[Data 2]\n"
        "136 30 31 32\n"
        "135 40 41 42\n",
        encoding="utf-8",
    )


def test_txt_region_discovery_returns_independent_monitor_targets(tmp_path: Path):
    path = tmp_path / "multi.txt"
    _write_two_region_txt(path)
    assert discover_live_regions(path) == [(0, "S2p_700eV"), (1, "P2p_700eV")]


def test_core_extracts_selected_txt_region_not_always_first(tmp_path: Path):
    path = tmp_path / "multi.txt"
    _write_two_region_txt(path)

    first = LiveFileMonitorCore(path, region_index=0).tick(now=0.0)
    second = LiveFileMonitorCore(path, region_index=1).tick(now=0.0)

    assert first is not None and second is not None
    assert first.total_spectra == 2
    assert second.total_spectra == 3
    assert np.allclose(first.x, [166.0, 165.0])
    assert np.allclose(second.x, [136.0, 135.0])
    assert np.allclose(second.new_spectra[-1], [32.0, 42.0])


def test_region_index_propagates_through_threaded_live_monitor_stack():
    assert "region_index=region_index" in CONTROLLER
    assert "region_index=region_index" in WORKER
    assert "region_index=self.region_index" in WINDOW


def test_txt_context_menu_exposes_regions_and_window_registry_is_region_scoped():
    assert 'live_menu = menu.addMenu("Open live monitor")' in UI
    assert 'label = f"{region_name} (Region {region_index + 1})"' in UI
    assert "monitor_key = (path, max(0, int(region_index)))" in UI
    assert "self._live_monitor_windows[monitor_key] = window" in UI
    assert 'title += f" — {self.region_name}"' in WINDOW
