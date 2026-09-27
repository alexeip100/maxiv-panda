from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _method_calls(path: Path, class_name: str, method_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == method_name:
                    calls = []
                    for call in ast.walk(item):
                        if not isinstance(call, ast.Call):
                            continue
                        func = call.func
                        if isinstance(func, ast.Attribute):
                            parts = [func.attr]
                            value = func.value
                            while isinstance(value, ast.Attribute):
                                parts.append(value.attr)
                                value = value.value
                            if isinstance(value, ast.Name):
                                parts.append(value.id)
                            calls.append(".".join(reversed(parts)))
                        elif isinstance(func, ast.Name):
                            calls.append(func.id)
                    return calls
    raise AssertionError(f"{class_name}.{method_name} not found in {path}")


def test_apply_identifies_without_accepting_dialog() -> None:
    path = ROOT / "src/maxiv_panda/signal_identification/dialogs.py"
    calls = _method_calls(path, "SignalIdentificationDialog", "_apply")
    assert "self.apply_requested.emit" in calls
    assert "self.accept" not in calls
    assert "self.close" not in calls


def test_controller_refreshes_open_dialog_after_apply() -> None:
    path = ROOT / "src/maxiv_panda/signal_identification/controller.py"
    source = path.read_text(encoding="utf-8")
    assert "dialog.apply_requested.connect(apply_and_identify)" in source
    assert "dialog.set_assignments(self.assignments)" in source
    assert "dialog.exec()" in source


def test_charging_summary_is_compact_and_refreshed() -> None:
    path = ROOT / "src/maxiv_panda/signal_identification/dialogs.py"
    source = path.read_text(encoding="utf-8")
    assert 'self.charging_summary = QLabel(left_pane)' in source
    assert 'left_layout.addWidget(self.charging_summary, 0)' in source
    assert 'self._update_charging_summary()' in source
    calls = _method_calls(path, "SignalIdentificationDialog", "set_assignments")
    assert "self._update_charging_summary" in calls


def test_charging_summary_hides_when_option_is_disabled() -> None:
    path = ROOT / "src/maxiv_panda/signal_identification/dialogs.py"
    source = path.read_text(encoding="utf-8")
    assert 'if not self.cb_small_charging.isChecked()' in source
    assert 'self.charging_summary.setVisible(False)' in source
    assert 'Charging: no reliable shift inferred.' in source
