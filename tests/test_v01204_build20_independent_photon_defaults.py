"""Regression for narrow-window resonant PES scans (e.g. FeO Fe 2p IBW)."""
import ast
from pathlib import Path
import numpy as np

SOURCE = Path(__file__).resolve().parents[1] / 'src/maxiv_panda/ui_map_controls_mixin.py'


def _methods():
    cls = next(n for n in ast.parse(SOURCE.read_text()).body
               if isinstance(n, ast.ClassDef) and n.name == 'UiMapControlsMixin')
    ns = {}
    for name in ('_respes_physical_energy_range', '_respes_normalization_defaults'):
        f = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[f], type_ignores=[])), str(SOURCE), 'exec'), ns)
    return ns


def test_photon_energy_defaults_do_not_require_common_kinetic_energy_window():
    methods = _methods()

    class Map:
        _respes_physical_energy_range = methods['_respes_physical_energy_range']
        _respes_normalization_defaults = methods['_respes_normalization_defaults']

        def _respes_normalization_context(self):
            x = np.linspace(13.8, 0, 140)
            hv = np.arange(700, 728.201, 0.1)
            return ((x, None, np.ones((len(hv), len(x))), None, 'Binding Energy [eV]'), hv, 'be', 4.5)

    m = Map()
    assert m._respes_physical_energy_range('ke') is None
    assert m._respes_physical_energy_range('be') is not None
    be, bw, ke, kw, hv, hw = m._respes_normalization_defaults()
    assert 0 <= be <= 13.8 and bw > 0
    assert ke is None and kw is None
    assert 700 <= hv <= 728.2 and hw > 0


def test_unavailable_kinetic_energy_is_not_displayed_as_nan_range():
    code = SOURCE.read_text()
    assert 'No common KE interval across all photon energies' in code
    assert 'if target == "at_ke" and not ke_available:' in code
