from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from maxiv_panda.ibw_parser import parse_ibw
from maxiv_panda.workflows.peakfit import fit_engine, fit_models


DATASET = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "reference"
    / "peak_fitting"
    / "ir111_ir4f_clean_170ev"
)


def _load_json(name: str) -> dict:
    return json.loads((DATASET / name).read_text(encoding="utf-8"))


def _peak_specs_from_export(fit_setup: dict) -> list[dict]:
    specs: list[dict] = []
    for state in fit_setup["fit_setup"]["peak_states"]:
        spec = {"label": state["label"]}
        for prefix in ("E", "H", "L", "G", "A"):
            spec[prefix] = float(state[prefix])
            spec[f"{prefix}_min"] = float(state[f"{prefix}_min"])
            spec[f"{prefix}_max"] = float(state[f"{prefix}_max"])
            exported_mode = str(state[f"{prefix}_mode"])
            if exported_mode in {"Free", "Fixed"}:
                spec[f"{prefix}_mode"] = exported_mode
                spec[f"{prefix}_tie"] = None
            elif exported_mode.startswith("Tied to "):
                target = int(exported_mode.rsplit("_", 1)[1])
                spec[f"{prefix}_mode"] = "Tied"
                spec[f"{prefix}_tie"] = {
                    "target": target,
                    "kind": "ratio",
                    "value": 1.0,
                }
            else:
                raise AssertionError(f"Unsupported exported mode: {exported_mode}")
        specs.append(spec)
    return specs


def _model_from_values(
    x: np.ndarray,
    values: dict[str, float],
    peak_count: int,
    bg_type: str,
) -> np.ndarray:
    peaks = [
        {prefix: float(values[f"p{i}_{prefix}"]) for prefix in ("E", "H", "L", "G", "A")}
        for i in range(1, peak_count + 1)
    ]
    model, _ = fit_models.build_model_from_values(
        x,
        peaks,
        bg_type,
        values,
        energy_scale="Binding",
    )
    return model


@pytest.fixture(scope="module")
def ir_reference() -> dict:
    parsed = parse_ibw(DATASET / "spectrum.ibw")
    region = parsed.regions[0]
    data = np.asarray(region.data, dtype=float)
    order = np.argsort(data[:, 0])
    x = data[order, 0]
    y = data[order, 1]

    setup = _load_json("fit_setup.json")
    expected = _load_json("expected.json")
    peak_specs = _peak_specs_from_export(setup)
    bg_state = dict(setup["fit_setup"]["bg_state"])
    fit_data = {"xu": x, "yu": y}
    params = fit_engine.build_lmfit_parameters(
        peak_specs,
        bg_state["bg_type"],
        bg_state,
        fit_data,
    )

    def residual(params_obj):
        values = params_obj.valuesdict()
        return _model_from_values(x, values, len(peak_specs), bg_state["bg_type"]) - y

    initial_values = params.valuesdict()
    initial_model = _model_from_values(x, initial_values, len(peak_specs), bg_state["bg_type"])
    result = fit_engine.run_lmfit_fit(params, residual, max_nfev=3000)
    fitted_values = {str(k): float(v) for k, v in result.params.valuesdict().items()}
    fitted_model = _model_from_values(x, fitted_values, len(peak_specs), bg_state["bg_type"])

    return {
        "parsed": parsed,
        "region": region,
        "x": x,
        "y": y,
        "setup": setup,
        "expected": expected,
        "peak_specs": peak_specs,
        "bg_state": bg_state,
        "params": params,
        "result": result,
        "values": fitted_values,
        "initial_model": initial_model,
        "fitted_model": fitted_model,
    }


def test_ir111_ibw_import_and_energy_axis(ir_reference):
    region = ir_reference["region"]
    x = ir_reference["x"]
    y = ir_reference["y"]
    assert region.info_meta["Spectrum Name"] == "Ir4f_170eV"
    assert region.info_meta["Energy Scale"] == "Binding"
    assert region.region_meta["Dimension 1 name"] == "Binding Energy [eV]"
    assert x.size == y.size == 551
    assert np.all(np.isfinite(x)) and np.all(np.isfinite(y))
    assert np.all(np.diff(x) > 0)
    assert x[0] == pytest.approx(57.0, abs=1e-8)
    assert x[-1] == pytest.approx(68.0, abs=1e-8)
    assert np.median(np.diff(x)) == pytest.approx(0.02, abs=1e-8)


def test_ir111_fit_setup_restores_four_components_and_background(ir_reference):
    specs = ir_reference["peak_specs"]
    bg = ir_reference["bg_state"]
    assert [spec["label"] for spec in specs] == [
        "Bulk_7/2",
        "Surf_7/2",
        "Bulk_5/2",
        "Surf_5/2",
    ]
    assert bg["bg_type"] == "parabolic"
    assert all(np.isfinite(float(bg[name])) for name in ("b0", "b1", "b2"))


def test_ir111_exported_constraints_are_restored(ir_reference):
    specs = ir_reference["peak_specs"]
    assert specs[1]["L_mode"] == "Tied"
    assert specs[1]["L_tie"] == {"target": 1, "kind": "ratio", "value": 1.0}
    assert specs[3]["L_mode"] == "Tied"
    assert specs[3]["L_tie"] == {"target": 3, "kind": "ratio", "value": 1.0}
    for index in (1, 2, 3):
        assert specs[index]["A_mode"] == "Tied"
        assert specs[index]["A_tie"] == {"target": 1, "kind": "ratio", "value": 1.0}


def test_ir111_real_spectrum_fit_converges(ir_reference):
    result = ir_reference["result"]
    assert result.success, result.message
    assert int(result.nfev) < 3000
    assert np.all(np.isfinite(result.residual))
    assert ir_reference["fitted_model"].shape == ir_reference["y"].shape
    assert all(np.isfinite(v) for v in ir_reference["values"].values())


def test_ir111_fitted_peak_positions_match_reference(ir_reference):
    expected = ir_reference["expected"]
    values = ir_reference["values"]
    tolerance = float(expected["position_tolerance_eV"])
    for i, label in enumerate(["Bulk_7/2", "Surf_7/2", "Bulk_5/2", "Surf_5/2"], start=1):
        assert values[f"p{i}_E"] == pytest.approx(expected["positions_eV"][label], abs=tolerance)


def test_ir111_spin_orbit_and_surface_shift_relations(ir_reference):
    values = ir_reference["values"]
    expected = ir_reference["expected"]
    tol = float(expected["relation_tolerance_eV"])
    bulk_split = values["p3_E"] - values["p1_E"]
    surface_split = values["p4_E"] - values["p2_E"]
    surface_shift_7_2 = values["p2_E"] - values["p1_E"]
    surface_shift_5_2 = values["p4_E"] - values["p3_E"]
    assert bulk_split == pytest.approx(expected["bulk_spin_orbit_splitting_eV"], abs=tol)
    assert surface_split == pytest.approx(expected["surface_spin_orbit_splitting_eV"], abs=tol)
    assert surface_shift_7_2 == pytest.approx(expected["surface_shift_7_2_eV"], abs=tol)
    assert surface_shift_5_2 == pytest.approx(expected["surface_shift_5_2_eV"], abs=tol)


def test_ir111_fit_quality_and_parameters_remain_physical(ir_reference):
    y = ir_reference["y"]
    model = ir_reference["fitted_model"]
    values = ir_reference["values"]
    expected = ir_reference["expected"]
    rms = float(np.sqrt(np.mean((model - y) ** 2)))
    background_only = fit_models.poly_background_centered(
        ir_reference["x"],
        values["b0"],
        values["b1"],
        values["b2"],
    )
    background_rms = float(np.sqrt(np.mean((background_only - y) ** 2)))
    assert rms < float(expected["max_rms_residual"])
    assert rms < 0.1 * background_rms
    for i in range(1, 5):
        assert values[f"p{i}_H"] > 0
        assert 0.05 <= values[f"p{i}_L"] <= 1.0
        assert 0.05 <= values[f"p{i}_G"] <= 2.0
        assert 0.0 <= values[f"p{i}_A"] <= 0.2
    assert values["p2_L"] == pytest.approx(values["p1_L"], abs=1e-12)
    assert values["p4_L"] == pytest.approx(values["p3_L"], abs=1e-12)
    assert values["p2_A"] == pytest.approx(values["p1_A"], abs=1e-12)
    assert values["p3_A"] == pytest.approx(values["p1_A"], abs=1e-12)
    assert values["p4_A"] == pytest.approx(values["p1_A"], abs=1e-12)
