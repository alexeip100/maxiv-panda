"""Physical normalization must remain visible when ResPES mode is off."""
import numpy as np
import matplotlib
matplotlib.use('Agg')
from matplotlib.figure import Figure
from maxiv_panda.ui_map_plot_mixin import MapPlotMixin

class Dummy(MapPlotMixin):
    pass

def test_generic_map_photon_energy_interval_remains_horizontal():
    obj = Dummy(); ax = Figure().subplots()
    ax.set_xlim(410, 450); ax.set_ylim(0, 4)
    image = (np.linspace(410,450,41), np.arange(1,5), np.ones((4,41)), 'Map', 'Kinetic Energy [eV]')
    obj._draw_physical_map_normalization_region(
        ax, (484.0, 486.0), 'at_hv', lambda *_: None,
        image=image, x_values=image[0], rows=4,
        photon_energy=np.array([484.,486.,488.,490.]), photon_label='Photon Energy [eV]')
    state = obj._map_norm_band_state
    assert state is not None
    x, y = state['boundary_xy'][0]
    assert np.allclose(y, y[0])

def test_generic_ke_map_be_interval_is_diagonal():
    obj = Dummy(); ax = Figure().subplots()
    ax.set_xlim(410,450); ax.set_ylim(0,4)
    image = (np.linspace(410,450,41), np.arange(1,5), np.ones((4,41)), 'Map', 'Kinetic Energy [eV]')
    obj._draw_physical_map_normalization_region(
        ax, (51.0, 52.0), 'at_be', lambda *_: None,
        image=image, x_values=image[0], rows=4,
        photon_energy=np.array([484.,486.,488.,490.]), photon_label='Photon Energy [eV]')
    x, y = obj._map_norm_band_state['boundary_xy'][0]
    assert len(x) == len(y) == 4
    assert not np.allclose(x, x[0])

def test_generic_non_photon_map_has_no_false_photon_overlay():
    obj = Dummy(); ax = Figure().subplots()
    image=(np.array([1.,2.]), np.arange(1,5), np.ones((4,2)), 'Map', 'Kinetic Energy [eV]')
    obj._draw_physical_map_normalization_region(
        ax, (484.,486.), 'at_hv', lambda *_: None,
        image=image, x_values=image[0], rows=4,
        photon_energy=None, photon_label='')
    assert obj._map_norm_band_state is None
