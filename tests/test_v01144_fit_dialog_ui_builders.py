from pathlib import Path
import ast


def _dialog_class():
    path = Path("src/maxiv_panda/workflows/peakfit/fit_dialog.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FitCoreLevelDialog")


def _methods():
    return {n.name: n for n in _dialog_class().body if isinstance(n, ast.FunctionDef)}


def test_fit_dialog_has_focused_ui_builder_methods():
    methods = _methods()
    expected = {
        "_build_curve_selection_pane",
        "_build_plot_pane",
        "_build_parameters_pane",
        "_build_peak_parameters_tab",
        "_build_fit_results_tab",
        "_configure_main_splitter",
        "_build_dialog_buttons",
        "_initialize_curve_selection",
    }
    assert expected <= set(methods)


def test_constructor_orchestrates_builders_in_established_order():
    methods = _methods()
    init = methods["__init__"]
    calls = []
    for node in ast.walk(init):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                calls.append((node.lineno, node.func.attr))
    ordered = [name for _, name in sorted(calls)]
    expected = [
        "_build_curve_selection_pane",
        "_build_plot_pane",
        "_build_parameters_pane",
        "_configure_main_splitter",
        "_build_dialog_buttons",
        "_initialize_curve_selection",
    ]
    indices = [ordered.index(name) for name in expected]
    assert indices == sorted(indices)


def test_large_widget_construction_no_longer_lives_in_constructor():
    init = _methods()["__init__"]
    constructed = {
        node.func.id
        for node in ast.walk(init)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    # Root containers remain constructor-owned; detailed panes/widgets do not.
    assert "QTreeWidget" not in constructed
    assert "QTabWidget" not in constructed
    assert "QGroupBox" not in constructed
    assert "QTableWidget" not in constructed
    assert "QDoubleSpinBox" not in constructed
    assert "QPushButton" not in constructed
