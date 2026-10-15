"""Guard the editable peak-width limits and automatic fit bounds."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "src" / "maxiv_panda" / "workflows" / "peakfit"


def test_peak_width_hard_limits():
    tree = ast.parse((ROOT / "fit_widgets.py").read_text(encoding="utf-8"))
    limits = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple):
            names = [elt.id for elt in node.targets[0].elts if isinstance(elt, ast.Name)]
            if names == ["l_hard_min", "l_hard_max"] or names == ["g_hard_min", "g_hard_max"]:
                limits[tuple(names)] = ast.literal_eval(node.value)
    assert limits[("l_hard_min", "l_hard_max")] == (0.05, 1.5)
    assert limits[("g_hard_min", "g_hard_max")] == (0.05, 3.0)


def test_auto_initial_peak_width_bounds():
    tree = ast.parse((ROOT / "fit_dialog_curve_mixin.py").read_text(encoding="utf-8"))
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value if isinstance(k, ast.Constant) else None for k in node.keys]
            if "L_max" in keys and "G_max" in keys and "peak_states" not in keys:
                values = {k: ast.literal_eval(v) for k, v in zip(keys, node.values) if k in ("L_max", "G_max")}
                matches.append(values)
    assert matches == [{"L_max": 1.5, "G_max": 3.0}]
