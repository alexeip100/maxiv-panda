from pathlib import Path

from test_v01203_real_family_auger_regression import _identify, _accepted

_DATA = Path(__file__).resolve().parents[1] / "data" / "signal_identification"


def _sulfur_assignments(path: Path):
    assignments, _ = _identify(path)
    return [
        a for a in assignments
        if a.best is not None and a.best.kind == "PE" and a.best.confident and a.best.element == "S"
    ]


def test_0003_has_one_sulfur_2p_2s_pair_not_two_chemical_states():
    rows = _sulfur_assignments(_DATA / "family_auger_0003_1200eV.txt")
    labels = [a.best.label for a in rows]
    assert labels.count("S 2p") == 1
    assert labels.count("S 2s") == 1
    s = _accepted(rows, "S")
    assert 167.0 <= s["S 2p"] <= 171.0
    assert 231.0 <= s["S 2s"] <= 235.0


def test_0022_has_one_sulfur_2p_2s_pair_not_two_chemical_states():
    rows = _sulfur_assignments(_DATA / "family_auger_0022_1200eV.txt")
    labels = [a.best.label for a in rows]
    assert labels.count("S 2p") == 1
    assert labels.count("S 2s") == 1
    s = _accepted(rows, "S")
    assert 167.0 <= s["S 2p"] <= 171.0
    assert 231.0 <= s["S 2s"] <= 235.0
