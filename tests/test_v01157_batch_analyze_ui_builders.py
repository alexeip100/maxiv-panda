from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIXIN = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit" / "batch_analyze_mixin.py"


def _class_methods():
    tree = ast.parse(MIXIN.read_text(encoding="utf-8"))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "BatchAnalyzeMixin")
    return {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}


def test_analyze_tab_has_focused_ui_builder_methods():
    methods = _class_methods()
    expected = {
        "_build_analyze_main_panel",
        "_build_analyze_top_bar",
        "_build_analyze_parameter_panel",
        "_build_next_pass_controls",
        "_build_analyze_trend_panel",
    }
    assert expected <= set(methods)


def test_analyze_tab_constructor_is_orchestration_only():
    method = _class_methods()["_build_analyze_tab"]
    calls = {
        node.func.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "self"
    }
    assert "_build_analyze_main_panel" in calls
    assert "_build_analyze_trend_panel" in calls

    constructed = {
        node.func.id
        for node in ast.walk(method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "QTreeWidget" not in constructed
    assert "QTableWidget" not in constructed
    assert "QComboBox" not in constructed
    assert "QPushButton" not in constructed
    assert "QTextEdit" not in constructed


def test_established_analyze_signal_connections_are_preserved():
    source = MIXIN.read_text(encoding="utf-8")
    expected = {
        "self.cb_analyze_result_pass.currentIndexChanged.connect(self._on_analyze_result_pass_changed)",
        "self.cb_analyze_parameter_type.currentIndexChanged.connect(self._on_analyze_parameter_type_changed)",
        "self.tree_analyze_parameters.itemChanged.connect(self._on_analyze_parameter_item_changed)",
        "self.btn_fit_smooth_trend.clicked.connect(self._fit_selected_smooth_trend)",
        "self.btn_add_next_constraint.clicked.connect(self._add_update_next_pass_constraint)",
        "self.btn_prepare_next_pass.clicked.connect(self._prepare_next_constrained_pass)",
        "self.cb_trend_fit_target.currentIndexChanged.connect(self._on_trend_fit_target_changed)",
        "self.cb_trend_fit_model.currentIndexChanged.connect(self._on_trend_fit_model_changed)",
        "self.cb_trend_fit_poly_order.currentIndexChanged.connect(self._on_trend_fit_model_changed)",
        "self.btn_fit_analysis_trend.clicked.connect(self._fit_selected_analysis_trend)",
        "self.btn_accept_analysis_trend.clicked.connect(self._accept_trend_analysis_fit)",
        "self.btn_clear_selected_analysis_trend.clicked.connect(self._clear_selected_trend_analysis_fit)",
        "self.btn_clear_all_analysis_trends.clicked.connect(self._clear_all_trend_analysis_fits)",
        "self.btn_export_analyze_trends.clicked.connect(self._export_analyze_trends_csv)",
        "self.btn_export_all_batch_fits.clicked.connect(self._export_all_batch_fits_zip)",
    }
    for connection in expected:
        assert connection in source
