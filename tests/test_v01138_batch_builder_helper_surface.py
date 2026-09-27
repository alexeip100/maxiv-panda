import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src/maxiv_panda/workflows/peakfit"


def _module_function_names(tree):
    return {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _self_helper_calls(tree):
    out = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "self"
            and fn.attr.startswith("_")
        ):
            out.add(fn.attr)
    return out


def test_batch_table_builder_internal_helpers_are_exposed_by_prepare_mixin():
    builder_tree = ast.parse((PEAKFIT / "batch_table_builder.py").read_text(encoding="utf-8"))
    mixin_tree = ast.parse((PEAKFIT / "batch_prepare_setup_mixin.py").read_text(encoding="utf-8"))

    builder_helpers = _module_function_names(builder_tree)
    internally_dispatched = _self_helper_calls(builder_tree) & builder_helpers
    mixin_methods = _module_function_names(next(
        node for node in mixin_tree.body if isinstance(node, ast.ClassDef) and node.name == "BatchPrepareSetupMixin"
    ))

    missing = internally_dispatched - mixin_methods
    assert missing == set(), f"BatchPrepareSetupMixin is missing builder helper delegations: {sorted(missing)}"


def test_doublet_builder_delegations_are_present_explicitly():
    src = (PEAKFIT / "batch_prepare_setup_mixin.py").read_text(encoding="utf-8")
    assert "def _doublet_union_model" in src
    assert "batch_table_builder._doublet_union_model" in src
    assert "def _build_doublet_parameter_rows" in src
    assert "batch_table_builder._build_doublet_parameter_rows" in src
