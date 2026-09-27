import numpy as np

from maxiv_panda.ui_map_plot_mixin import MapPlotMixin


def test_constant_be_cut_tracks_fixed_binding_energy():
    x = np.array([3.0, 2.0, 1.0, 0.0])
    hv = np.array([570.0, 571.0, 572.0])
    Z = np.array([[30.,20.,10.,0.],[31.,21.,11.,1.],[32.,22.,12.,2.]])
    out = MapPlotMixin._respes_trace_values(x, hv, Z, "constant_be", 2.0, 0.1)
    assert np.allclose(out, [20.,21.,22.])


def test_constant_ke_cut_follows_unit_slope_trajectory():
    x = np.array([3.0, 2.0, 1.0, 0.0])
    hv = np.array([570.0, 571.0, 572.0])
    # KE = hnu-BE-Phi = 564.5 eV (Phi=4.5) -> targets 1,2,3 eV.
    Z = np.array([[30.,20.,10.,0.],[31.,21.,11.,1.],[32.,22.,12.,2.]])
    out = MapPlotMixin._respes_trace_values(x, hv, Z, "constant_ke", 564.5, 0.1)
    assert np.allclose(out, [10.,21.,32.])


def test_constant_ke_cut_returns_nan_outside_measured_be_range():
    x = np.array([2.0, 1.0, 0.0])
    hv = np.array([570.0, 571.0, 572.0])
    Z = np.ones((3, 3))
    out = MapPlotMixin._respes_trace_values(x, hv, Z, "constant_ke", 563.5, 0.1)
    assert np.isfinite(out[0])
    assert np.isnan(out[1])
    assert np.isnan(out[2])


def test_respes_ke_map_uses_work_function_and_preserves_rows():
    x_be = np.array([2.0, 1.0, 0.0])
    hv = np.array([570.0, 571.0])
    Z = np.array([[20.0, 10.0, 0.0], [21.0, 11.0, 1.0]])
    ke, out = MapPlotMixin._respes_map_to_ke(x_be, hv, Z, work_function=4.5)
    assert ke[0] == 563.5
    assert ke[-1] == 566.5
    # Row 1 spans 563.5..565.5; row 2 spans 564.5..566.5.
    assert np.isnan(out[0, -1])
    assert np.isnan(out[1, 0])
    # Same measured points are retained at their transformed KE coordinates.
    i5655 = int(np.argmin(np.abs(ke - 565.5)))
    i5665 = int(np.argmin(np.abs(ke - 566.5)))
    assert np.isclose(out[0, i5655], 0.0)
    assert np.isclose(out[1, i5665], 1.0)


def test_constant_photon_energy_cut_returns_spectrum():
    x = np.array([3.0, 2.0, 1.0, 0.0])
    hv = np.array([570.0, 571.0, 572.0])
    Z = np.array([[30.,20.,10.,0.],[31.,21.,11.,1.],[32.,22.,12.,2.]])
    out = MapPlotMixin._respes_constant_hv_trace(x, hv, Z, 571.0, 0.1)
    assert np.allclose(out, [31.,21.,11.,1.])


def test_constant_photon_energy_cut_interpolates_between_rows():
    x = np.array([2.0, 1.0, 0.0])
    hv = np.array([570.0, 572.0])
    Z = np.array([[20.,10.,0.],[24.,14.,4.]])
    out = MapPlotMixin._respes_constant_hv_trace(x, hv, Z, 571.0, 0.1)
    assert np.allclose(out, [22.,12.,2.])


def test_constant_ke_cut_on_measured_ke_map_is_vertical_in_source_coordinates():
    x_ke = np.array([564.5, 565.5, 566.5])
    hv = np.array([570.0, 571.0, 572.0])
    Z = np.array([[0., 10., 20.], [1., 11., 21.], [2., 12., 22.]])
    out = MapPlotMixin._respes_trace_values(
        x_ke, hv, Z, "constant_ke", 565.5, 0.1, source_axis="ke"
    )
    assert np.allclose(out, [10., 11., 12.])


def test_constant_be_cut_on_measured_ke_map_follows_diagonal():
    x_ke = np.array([564.5, 565.5, 566.5])
    hv = np.array([570.0, 571.0, 572.0])
    # BE = hnu - KE - Phi = 1 eV selects KE 564.5, 565.5, 566.5 row by row.
    Z = np.array([[0., 10., 20.], [1., 11., 21.], [2., 12., 22.]])
    out = MapPlotMixin._respes_trace_values(
        x_ke, hv, Z, "constant_be", 1.0, 0.1, source_axis="ke"
    )
    assert np.allclose(out, [0., 11., 22.])


def test_respes_be_map_from_measured_ke_uses_work_function_and_preserves_rows():
    x_ke = np.array([564.5, 565.5, 566.5])
    hv = np.array([570.0, 571.0])
    Z = np.array([[0.0, 10.0, 20.0], [1.0, 11.0, 21.0]])
    be, out = MapPlotMixin._respes_map_to_be(x_ke, hv, Z, work_function=4.5)
    assert be[0] == -1.0
    assert be[-1] == 2.0
    # Row 1 spans -1..1 BE; row 2 spans 0..2 BE.
    assert np.isnan(out[0, -1])
    assert np.isnan(out[1, 0])
    i1 = int(np.argmin(np.abs(be - 1.0)))
    i2 = int(np.argmin(np.abs(be - 2.0)))
    assert np.isclose(out[0, i1], 0.0)
    assert np.isclose(out[1, i2], 1.0)


def test_respes_source_energy_axis_detects_measured_scale():
    assert MapPlotMixin._respes_source_energy_axis("Kinetic Energy [eV]") == "ke"
    assert MapPlotMixin._respes_source_energy_axis("Binding Energy [eV]") == "be"
