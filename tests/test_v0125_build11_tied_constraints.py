"""Regression: the tied GFWHM from the six-peak Sn MNN case is not clipped.

Qt-free functional tests extract the range-binding function because the CI
container does not include Qt. They exercise the actual source function.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'src/maxiv_panda/workflows/peakfit'

class Signal:
    def __init__(self): self.callbacks = []
    def connect(self, f): self.callbacks.append(f)
    def fire(self, v=0):
        for f in list(self.callbacks): f(v)

class Spinner:
    def __init__(self, value, minimum, maximum, hard_min=None, hard_max=None):
        self._value, self._min, self._max = value, minimum, maximum
        self.props = {'hard_min': hard_min, 'hard_max': hard_max}
        self.valueChanged = Signal()
        self.blocked = False
    def value(self): return self._value
    def minimum(self): return self._min
    def maximum(self): return self._max
    def property(self, n): return self.props.get(n)
    def blockSignals(self, b): self.blocked = b
    def setRange(self, lo, hi):
        self._min, self._max = lo, hi
        self.setValue(self._value)
    def setValue(self, v):
        value = max(self._min, min(self._max, v))
        if value != self._value:
            self._value = value
            if not self.blocked: self.valueChanged.fire(value)

class Mode:
    def __init__(self, text='Free'):
        self.text = text
        self.currentTextChanged = Signal()
    def currentText(self): return self.text
    def setText(self, text):
        self.text = text
        self.currentTextChanged.fire(text)


def _source_function(file, name):
    module = ast.parse((ROOT / file).read_text())
    fn = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name)
    # annotations aren't needed for this isolated executable-source test
    fn.returns = None
    for arg in fn.args.args: arg.annotation = None
    namespace = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(ROOT / file), 'exec'), namespace)
    return namespace[name]


def test_tied_gfwhm_not_clipped_by_legacy_max_and_fixed_to_free_does_not_change_value():
    bind = _source_function('fit_widgets.py', '_wire_limits')
    lo, val, hi = Spinner(.05, .05, 3., .05, 3.), Spinner(2., .05, 2.), Spinner(2., .05, 3., .05, 3.)
    mode = Mode('Free')
    bind(lo, val, hi, mode)
    mode.setText('Tied to GFWHM_1')
    val.setValue(2.393)  # original optimized source from user's saved Sn MNN fit
    assert val.value() == 2.393
    assert hi.value() == 2.0  # original independent bounds preserved when tied
    mode.setText('Free')
    assert val.value() == 2.393
    assert hi.value() == 2.393  # expanded to preserve shape on detach
    mode.setText('Fixed')
    assert val.value() == 2.393


def test_independent_bound_edit_still_clamps_value():
    bind = _source_function('fit_widgets.py', '_wire_limits')
    lo, val, hi = Spinner(.05, .05, 3., .05, 3.), Spinner(2.5, .05, 3.), Spinner(3., .05, 3., .05, 3.)
    bind(lo, val, hi, Mode())
    hi.setValue(2.)
    assert val.value() == 2.


def test_result_application_preserves_tied_parameter_above_its_old_bound():
    apply = _source_function('fit_engine.py', 'apply_fit_result_to_widgets')
    w = {'G': Spinner(2., .05, 2.), 'G_min': Spinner(.05, .05, 3., .05, 3.),
         'G_max': Spinner(2., .05, 3., .05, 3.), 'G_mode': Mode('Tied to GFWHM_1')}
    apply({'p1_G': 2.393}, [w], 'constant', {})
    assert w['G'].value() == 2.393
    assert w['G_max'].value() == 2.0
