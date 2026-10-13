"""Dataset-dependent normalization options, independent of selected map view."""
import ast
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[2] / 'src/maxiv_panda/ui_map_controls_mixin.py'

class Combo:
    def __init__(self, items, selected='none'):
        self.items=list(items); self.selected=selected; self.blocked=False
    def currentData(self): return self.selected
    def count(self): return len(self.items)
    def itemText(self, i): return self.items[i][0]
    def itemData(self, i): return self.items[i][1]
    def blockSignals(self, enabled): self.blocked=enabled
    def clear(self): self.items=[]; self.selected=None
    def addItem(self, text, data): self.items.append((text,data))
    def findData(self, value): return next((i for i, (_,d) in enumerate(self.items) if d==value),-1)
    def setCurrentIndex(self, index): self.selected=self.items[index][1]

# Exercise the real method without requiring a graphical Qt runtime.
tree=ast.parse(SOURCE.read_text(encoding='utf-8'))
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='UiMapControlsMixin')
method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_sync_map_normalization_options')
namespace={}
exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(SOURCE),'exec'),namespace)
sync=namespace[method.name]

def host(physical, combo):
    obj=SimpleNamespace(cb_map_normalization=combo,_map_norm_mode=combo.selected,
        _map_norm_active_interval=(2,3),_map_norm_dialog=None,
        _respes_normalization_context=lambda: ('data',) if physical else None)
    return obj

def test_ordinary_map_three_modes():
    h=host(False,Combo([('None','none'),('at BE','at_be'),('Area','area')]))
    sync(h)
    assert h.cb_map_normalization.items==[('None','none'),('at BE','at_be'),('Area','area')]

def test_photon_map_five_modes():
    h=host(True,Combo([('None','none'),('at BE','at_be'),('Area','area')],'at_be'))
    sync(h)
    assert h.cb_map_normalization.items==[('None','none'),('at BE','at_be'),('at KE','at_ke'),('at PhE','at_hv'),('Area','area')]
    assert h.cb_map_normalization.selected=='at_be'

def test_switch_to_non_photon_map_removes_unsupported_mode():
    h=host(False,Combo([('None','none'),('at BE','at_be'),('at KE','at_ke'),('at PhE','at_hv'),('Area','area')],'at_hv'))
    sync(h)
    assert h.cb_map_normalization.selected=='none'
    assert h._map_norm_mode=='none'
    assert h._map_norm_active_interval is None

def test_switch_back_keeps_area():
    h=host(False,Combo([('None','none'),('at BE','at_be'),('at KE','at_ke'),('at PhE','at_hv'),('Area','area')],'area'))
    sync(h)
    assert h.cb_map_normalization.selected=='area'
