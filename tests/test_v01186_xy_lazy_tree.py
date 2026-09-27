from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem

from maxiv_panda.loaded_tree import LoadedTreeController
from maxiv_panda.specs_xy_adapter import AdaptedSpecsXY, SpecsXYRegionData
from maxiv_panda.txt_parser import ParsedTXT, RegionData


@dataclass
class _Payload:
    title: str
    x: object
    y: object
    xlabel: str
    ylabel: str
    energy_scale: str
    metadata: dict


def _qapp():
    app = QApplication.instance()
    return app or QApplication([])


def _controller():
    _qapp()
    tree = QTreeWidget()
    tree.setColumnCount(2)
    root = QTreeWidgetItem(["Loaded files"])
    tree.addTopLevelItem(root)
    stack = {}
    ctl = LoadedTreeController(
        tree=tree,
        files_root=root,
        role_payload=0x101,
        role_key=0x102,
        role_region=0x103,
        role_file=0x104,
        role_meta=0x105,
        payload_factory=_Payload,
        region_iteration_stack=stack,
    )
    return tree, root, stack, ctl


def _xy_parsed(n_iter: int) -> AdaptedSpecsXY:
    x = np.linspace(290.0, 280.0, 5)
    rows = [np.arange(5, dtype=float) + i for i in range(n_iter)]
    region = SpecsXYRegionData(index=1, original_region_name="C1s", spectrum_id=7, group_name="XPS")
    region.region_meta = {
        "Region Name": "C1s",
        "Dimension 1 name": "Binding Energy [eV]",
        "Dimension 1 size": "5",
        "Dimension 2 name": "Iteration",
        "Dimension 2 size": str(n_iter),
        "Dimension 2 scale": " ".join(str(i) for i in range(1, n_iter + 1)),
    }
    region.info_meta = {"Energy Scale": "Binding", "Spectrum Name": "C1s"}
    region.data = np.column_stack([x, np.asarray(rows).T])
    return AdaptedSpecsXY(path=Path("large.xy"), regions=[region])


def _txt_parsed(n_iter: int) -> ParsedTXT:
    x = np.linspace(10.0, 0.0, 5)
    rows = [np.arange(5, dtype=float) + i for i in range(n_iter)]
    region = RegionData(index=1)
    region.region_meta = {
        "Region Name": "TXT",
        "Dimension 1 name": "Binding Energy [eV]",
        "Dimension 1 size": "5",
        "Dimension 2 name": "Iteration",
        "Dimension 2 size": str(n_iter),
        "Dimension 2 scale": " ".join(str(i) for i in range(1, n_iter + 1)),
    }
    region.info_meta = {"Energy Scale": "Binding", "Spectrum Name": "TXT"}
    region.data = np.column_stack([x, np.asarray(rows).T])
    return ParsedTXT(path=Path("large.txt"), regions=[region])


def test_large_xy_iterations_are_lazy_until_expanded():
    tree, root, stack, ctl = _controller()
    parsed = _xy_parsed(300)
    ctl.add_parsed_to_tree(parsed)

    file_item = root.child(0)
    region_item = file_item.child(0)
    assert region_item.childCount() == 2  # Average + Iterations
    it_root = region_item.child(1)
    assert it_root.text(0) == "Iterations"
    assert bool(it_root.flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert it_root.checkState(0) == Qt.CheckState.Unchecked
    assert it_root.childCount() == 1
    assert "300 spectra" in it_root.child(0).text(0)
    assert ("large.xy", "C1s") in stack
    assert len(stack[("large.xy", "C1s")][1]) == 300

    it_root.setExpanded(True)
    QApplication.processEvents()
    assert it_root.childCount() == 300
    assert it_root.child(0).text(0) == "Iteration 1"
    assert it_root.child(299).text(0) == "Iteration 300"


def test_small_xy_keeps_existing_eager_tree_shape():
    _tree, root, _stack, ctl = _controller()
    ctl.add_parsed_to_tree(_xy_parsed(50))
    it_root = root.child(0).child(0).child(1)
    assert it_root.childCount() == 50
    assert it_root.child(0).text(0) == "Iteration 1"


def test_txt_with_same_large_iteration_count_remains_eager():
    _tree, root, _stack, ctl = _controller()
    ctl.add_parsed_to_tree(_txt_parsed(300))
    it_root = root.child(0).child(0).child(1)
    assert it_root.childCount() == 300
    assert it_root.child(0).text(0) == "Iteration 1"


def test_checking_lazy_iterations_before_expansion_materializes_and_checks_children():
    tree, root, _stack, ctl = _controller()
    ctl.add_parsed_to_tree(_xy_parsed(300))
    it_root = root.child(0).child(0).child(1)

    assert it_root.childCount() == 1  # placeholder only
    it_root.setCheckState(0, Qt.CheckState.Checked)
    QApplication.processEvents()

    assert it_root.childCount() == 300
    assert it_root.checkState(0) == Qt.CheckState.Checked
    assert all(it_root.child(i).checkState(0) == Qt.CheckState.Checked for i in range(300))
