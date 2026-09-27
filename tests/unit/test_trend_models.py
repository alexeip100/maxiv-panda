import numpy as np
import pytest

from maxiv_panda.workflows.peakfit.batch_trend_models import (
    fit_trend_model,
    model_formula,
    model_label,
)


def test_polynomial_trend_recovers_quadratic():
    x = np.arange(10.0)
    y = 2.0 * x**2 - 3.0 * x + 4.0
    result = fit_trend_model(x, y, model="poly", order=2)
    assert result["model_label"] == "Polynomial order 2"
    assert result["metrics"]["rmse"] < 1e-10
    assert np.allclose(result["coefficients"], [2.0, -3.0, 4.0], atol=1e-10)


def test_single_exponential_trend_recovers_synthetic_curve():
    x = np.linspace(0.0, 12.0, 60)
    y = 1.5 + 4.0 * np.exp(-x / 2.5)
    result = fit_trend_model(x, y, model="single_exp_plateau")
    assert result["metrics"]["nrmse"] < 1e-6
    assert result["params"]["tau"] == pytest.approx(2.5, rel=1e-3)


def test_trend_model_rejects_insufficient_data_and_unknown_model():
    with pytest.raises(ValueError, match="At least two"):
        fit_trend_model(np.array([1.0]), np.array([2.0]), model="poly")
    with pytest.raises(ValueError, match="Unknown trend model"):
        fit_trend_model(np.arange(4.0), np.arange(4.0), model="mystery")


def test_trend_labels_and_formulas_are_stable():
    assert model_label("poly", order=3) == "Polynomial order 3"
    assert "x^{3}" in model_formula("poly", order=3)
    assert "tau" in model_formula("single_exp_plateau")
