import sys
import types

from maxiv_panda.workflows.peakfit import fit_engine


class Param:
    def __init__(self, value=None, min=None, max=None, vary=None, expr=None):
        self.value, self.min, self.max, self.vary, self.expr = value, min, max, vary, expr


class Parameters(dict):
    def add(self, name, **kwargs):
        self[name] = Param(**kwargs)


def _spec(E, H):
    out = {}
    for p, v, lo, hi in (("E",E,0,1000),("H",H,0,1e6),("L",0.2,0.05,1),("G",0.3,0.05,2),("A",0,0,0.2)):
        out[p]=v; out[p+"_min"]=lo; out[p+"_max"]=hi; out[p+"_mode"]="Free"; out[p+"_tie"]=None
    return out


def test_doublet_is_compiled_to_physical_lmfit_expressions(monkeypatch):
    monkeypatch.setitem(sys.modules, "lmfit", types.SimpleNamespace(Parameters=Parameters))
    d = {"major":1,"minor":2,"orbital":"p","split":1.2,"split_min":1.0,"split_max":1.4,"split_mode":"Free",
         "ratio":2.0,"ratio_min":1.5,"ratio_max":2.5,"ratio_mode":"Free","L_relation":"Same","G_relation":"Same","A_relation":"Same"}
    params = fit_engine.build_lmfit_parameters([_spec(100,200),_spec(101.2,100)], "constant", {"b0":0}, {"xu":[0,1],"yu":[0,1]}, [d], "Binding")
    assert params["d1_split"].vary is True
    assert params["d1_ratio"].vary is True
    assert "d1_split" in params["p2_E"].expr and "+ (1.0)" in params["p2_E"].expr
    assert params["p2_H"].expr == "(p1_H / d1_ratio)"
    assert params["p2_L"].expr == "p1_L"
    assert params["p2_G"].expr == "p1_G"
    assert params["p2_A"].expr == "p1_A"


def test_kinetic_energy_reverses_minor_energy_direction(monkeypatch):
    monkeypatch.setitem(sys.modules, "lmfit", types.SimpleNamespace(Parameters=Parameters))
    d = {"major":1,"minor":2,"orbital":"p","split":1.2,"split_mode":"Fixed","ratio":2,"ratio_mode":"Fixed"}
    params = fit_engine.build_lmfit_parameters([_spec(100,200),_spec(98.8,100)], "constant", {"b0":0}, {"xu":[0,1],"yu":[0,1]}, [d], "Kinetic")
    assert "(-1.0)" in params["p2_E"].expr


def test_doublet_split_and_ratio_can_be_tied_to_another_doublet(monkeypatch):
    monkeypatch.setitem(sys.modules, "lmfit", types.SimpleNamespace(Parameters=Parameters))
    d1 = {"major":1,"minor":2,"orbital":"p","split":1.2,"split_min":1.0,"split_max":1.4,"split_mode":"Free",
          "ratio":2.0,"ratio_min":1.5,"ratio_max":2.5,"ratio_mode":"Free","L_relation":"Same","G_relation":"Same","A_relation":"Same"}
    d2 = {"major":3,"minor":4,"orbital":"p","split":1.1,"split_mode":"Tied","split_tie_target":1,
          "ratio":1.9,"ratio_mode":"Tied","ratio_tie_target":1,"L_relation":"Same","G_relation":"Same","A_relation":"Same"}
    specs = [_spec(100,200),_spec(101.2,100),_spec(103,80),_spec(104.2,40)]
    params = fit_engine.build_lmfit_parameters(specs, "constant", {"b0":0}, {"xu":[0,1],"yu":[0,1]}, [d1,d2], "Binding")
    assert params["d2_split"].expr == "d1_split"
    assert params["d2_ratio"].expr == "d1_ratio"
    assert "d2_split" in params["p4_E"].expr
    assert params["p4_H"].expr == "(p3_H / d2_ratio)"
