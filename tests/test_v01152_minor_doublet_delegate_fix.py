from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
ANALYZE = ROOT / 'src' / 'maxiv_panda' / 'workflows' / 'peakfit' / 'batch_analysis.py'
CONSTRAINTS = ROOT / 'src' / 'maxiv_panda' / 'workflows' / 'peakfit' / 'batch_analysis_constraints.py'
MIXIN = ROOT / 'src' / 'maxiv_panda' / 'workflows' / 'peakfit' / 'batch_analyze_mixin.py'


def _methods(path: Path, class_name: str | None = None) -> set[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    if class_name is None:
        return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    raise AssertionError(f'{class_name} not found')


def test_minor_doublet_helpers_are_exposed_by_batch_analyze_mixin():
    module_methods = _methods(CONSTRAINTS)
    mixin_methods = _methods(MIXIN, 'BatchAnalyzeMixin')
    required = {'_derived_so_minor_peak_indices', '_is_derived_so_minor_target'}
    assert required <= module_methods
    assert required <= mixin_methods


def test_smoothing_combo_can_call_minor_filter_through_self():
    source = CONSTRAINTS.read_text(encoding='utf-8')
    assert 'minor_peak_indices = self._derived_so_minor_peak_indices()' in source
    mixin_source = MIXIN.read_text(encoding='utf-8')
    assert 'return batch_analysis_constraints._derived_so_minor_peak_indices(self, *args, **kwargs)' in mixin_source
