from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _load_selection_tree_without_qt(monkeypatch):
    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.Qt = types.SimpleNamespace(CheckState=types.SimpleNamespace(Checked=2, Unchecked=0))
    qtcore.QSize = lambda width, height: (width, height)
    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtwidgets.QPushButton = type("QPushButton", (), {})
    qtwidgets.QTreeWidgetItem = type("QTreeWidgetItem", (), {})
    pyqt6 = types.ModuleType("PyQt6")
    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)

    path = Path(__file__).parents[2] / "src" / "maxiv_panda" / "selection_tree.py"
    spec = importlib.util.spec_from_file_location("maxiv_panda._selection_tree_state_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _SelectedItem:
    def __init__(self, state):
        self.state = state

    def checkState(self, _column):
        return self.state

    def setCheckState(self, _column, state):
        self.state = state


class _LoadedItem:
    def __init__(self, key, role_key):
        self.key = key
        self.role_key = role_key

    def data(self, _column, role):
        if role == self.role_key:
            return (self.key, self.key)
        return None


def test_rebuild_preserves_existing_visibility_and_checks_only_new_curves(monkeypatch):
    module = _load_selection_tree_without_qt(monkeypatch)
    manager = module.SelectedTreeManager.__new__(module.SelectedTreeManager)
    manager.role_key = 17
    manager.selected_by_key = {
        "a": _SelectedItem(module.Qt.CheckState.Unchecked),
        "b": _SelectedItem(module.Qt.CheckState.Checked),
    }

    def clear():
        manager.selected_by_key.clear()

    def add_from_loaded_item(*, loaded_item, all_in_region_enabled, target_region):
        key = loaded_item.data(0, manager.role_key)[0]
        manager.selected_by_key[str(key)] = _SelectedItem(module.Qt.CheckState.Checked)
        return True

    manager.clear = clear
    manager.add_from_loaded_item = add_from_loaded_item

    manager.rebuild_from_loaded(
        loaded_items=[
            _LoadedItem("a", manager.role_key),
            _LoadedItem("b", manager.role_key),
            _LoadedItem("c", manager.role_key),
        ],
        all_in_region_enabled=False,
        target_region="",
    )

    assert manager.selected_by_key["a"].state == module.Qt.CheckState.Unchecked
    assert manager.selected_by_key["b"].state == module.Qt.CheckState.Checked
    assert manager.selected_by_key["c"].state == module.Qt.CheckState.Checked


class _MapChild:
    def __init__(self, meta, role_meta):
        self.meta = meta
        self.role_meta = role_meta

    def data(self, _column, role):
        if role == self.role_meta:
            return self.meta
        return None


class _ParentForMapButton:
    def __init__(self, children):
        self.children = list(children)
        self.size_hint = None

    def childCount(self):
        return len(self.children)

    def child(self, index):
        return self.children[index]

    def setSizeHint(self, column, hint):
        self.size_hint = (column, hint)


class _ExistingMapButton:
    def __init__(self, checked=False):
        self.checked = checked
        self.set_checked_calls = []

    def isChecked(self):
        return self.checked

    def setChecked(self, checked):
        self.checked = checked
        self.set_checked_calls.append(checked)


class _SelectedTreeForMapButton:
    def __init__(self):
        self.removed = []

    def removeItemWidget(self, parent, column):
        self.removed.append((parent, column))


def test_map_button_requires_two_iterations_from_a_real_source_group(monkeypatch):
    module = _load_selection_tree_without_qt(monkeypatch)
    manager = module.SelectedTreeManager.__new__(module.SelectedTreeManager)
    manager.role_meta = 18
    manager.region_map_buttons = {}
    manager.selected_tree = _SelectedTreeForMapButton()
    created = []

    def create(key, parent):
        button = _ExistingMapButton()
        manager.region_map_buttons[key] = button
        created.append((key, parent))
        return button

    manager._create_map_button = create
    key = ("XPS_0022.ibw", "S2p_700eV")
    one_iteration = _MapChild({"kind": "iteration", "iteration": 1}, manager.role_meta)
    ordinary = _MapChild({"kind": "trace"}, manager.role_meta)
    parent = _ParentForMapButton([one_iteration, ordinary])

    manager._sync_map_button(key, parent)
    assert created == []
    assert key not in manager.region_map_buttons

    second_iteration = _MapChild({"kind": "iteration", "iteration": 2}, manager.role_meta)
    parent.children.append(second_iteration)
    manager._sync_map_button(key, parent)
    assert created == [(key, parent)]
    assert key in manager.region_map_buttons


def test_map_button_is_hidden_for_all_in_group_even_with_many_curves(monkeypatch):
    module = _load_selection_tree_without_qt(monkeypatch)
    manager = module.SelectedTreeManager.__new__(module.SelectedTreeManager)
    manager.role_meta = 18
    manager.region_map_buttons = {}
    manager.selected_tree = _SelectedTreeForMapButton()
    created = []
    manager._create_map_button = lambda key, parent: created.append((key, parent))
    children = [
        _MapChild({"kind": "iteration", "iteration": 1}, manager.role_meta),
        _MapChild({"kind": "iteration", "iteration": 2}, manager.role_meta),
    ]
    parent = _ParentForMapButton(children)
    key = ("__GROUP__", "Survey_700eV")

    manager._sync_map_button(key, parent)

    assert created == []
    assert key not in manager.region_map_buttons


def test_map_button_is_removed_if_group_shrinks_back_to_one_curve(monkeypatch):
    module = _load_selection_tree_without_qt(monkeypatch)
    manager = module.SelectedTreeManager.__new__(module.SelectedTreeManager)
    manager.selected_tree = _SelectedTreeForMapButton()
    manager.role_meta = 18
    key = ("XPS_0022.ibw", "S2p_700eV")
    button = _ExistingMapButton(checked=True)
    manager.region_map_buttons = {key: button}
    parent = _ParentForMapButton([_MapChild({"kind": "iteration", "iteration": 1}, manager.role_meta)])

    manager._sync_map_button(key, parent)

    assert button.set_checked_calls == [False]
    assert key not in manager.region_map_buttons
    assert manager.selected_tree.removed == [(parent, 1)]
