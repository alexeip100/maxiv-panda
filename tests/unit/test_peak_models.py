import numpy as np

from maxiv_panda.workflows.peakfit.fit_models import (
    apply_gaussian_broadening,
    broadened_doniach_sunjic_profile,
    constant_background,
    doniach_sunjic,
    gaussian_kernel,
    linear_background_centered,
    poly_background_centered,
    raw_to_centered_linear,
    raw_to_centered_parabolic,
    voigt_profile,
)


def test_gaussian_kernel_is_normalized_and_symmetric():
    x = np.linspace(-3.0, 3.0, 121)
    k = gaussian_kernel(x, 0.7)
    assert np.isclose(k.sum(), 1.0)
    assert np.allclose(k, k[::-1])


def test_gaussian_broadening_preserves_constant_signal():
    y = np.ones(1001)
    broadened = apply_gaussian_broadening(y, sigma=0.2, step=0.01)
    assert broadened.shape == y.shape
    assert np.allclose(broadened[100:-100], 1.0, atol=1e-10)


def test_voigt_profile_is_centered_and_nonnegative():
    x = np.linspace(-2.0, 2.0, 2001)
    y = voigt_profile(x, x0=0.25, sigma=0.15, gamma=0.08)
    assert np.all(y >= 0)
    assert abs(x[int(np.argmax(y))] - 0.25) < 0.005


def test_doniach_sunjic_tail_reverses_with_energy_scale():
    x = np.linspace(-2.0, 2.0, 2001)
    be = doniach_sunjic(x, 0.0, 0.15, 0.08, "Binding")
    ke = doniach_sunjic(x, 0.0, 0.15, 0.08, "Kinetic")
    assert np.allclose(be, ke[::-1], atol=1e-12)


def test_centered_backgrounds_and_parameter_conversion():
    x = np.linspace(10.0, 20.0, 101)
    assert np.allclose(constant_background(x, 2.5), 2.5)
    b0, b1 = raw_to_centered_linear(x, 1.0, 0.2)
    assert np.allclose(linear_background_centered(x, b0, b1), 1.0 + 0.2 * x)
    c0, c1, c2 = raw_to_centered_parabolic(x, 1.0, 0.2, 0.03)
    assert np.allclose(poly_background_centered(x, c0, c1, c2), 1.0 + 0.2 * x + 0.03 * x**2)


def test_broadened_ds_is_independent_of_fit_range_edges():
    step = 0.01
    x_wide = np.arange(60.0, 70.0 + step / 2.0, step)
    x_crop = x_wide[(x_wide >= 62.7) & (x_wide <= 66.2)]

    params = dict(x0=63.35, gamma=0.22, alpha=0.08, sigma=0.18, energy_scale="Binding")
    y_wide = broadened_doniach_sunjic_profile(x_wide, **params)
    y_crop = broadened_doniach_sunjic_profile(x_crop, **params)

    mask = (x_wide >= x_crop[0] - 1e-12) & (x_wide <= x_crop[-1] + 1e-12)
    y_ref = y_wide[mask]
    assert y_ref.shape == y_crop.shape
    # Cropping the fitting interval must not create a zero-padding kink at either edge.
    assert np.allclose(y_crop, y_ref, rtol=2e-5, atol=2e-8)


def test_broadened_ds_has_no_boundary_collapse():
    x = np.linspace(62.7, 66.2, 351)
    y = broadened_doniach_sunjic_profile(
        x, x0=63.35, gamma=0.22, alpha=0.08, sigma=0.18, energy_scale="Binding"
    )
    # A convolution boundary must not artificially depress the first/last point
    # relative to its immediate neighbours.
    assert y[0] > 0.8 * y[1]
    assert y[-1] > 0.8 * y[-2]
