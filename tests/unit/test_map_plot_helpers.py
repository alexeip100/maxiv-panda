import numpy as np

from maxiv_panda.ui_map_plot_mixin import MapPlotMixin


class _YAxis:
    def __init__(self):
        self.ticks_position = None
        self.label_position = None
        self.label_coords = None

    def tick_right(self):
        self.ticks_position = "right"

    def set_label_position(self, value):
        self.label_position = value

    def set_label_coords(self, x, y, transform=None):
        self.label_coords = (x, y, transform)


class _Axis:
    def __init__(self):
        self.ylim = None
        self.yticks = None
        self.yticklabels = None
        self.ylabel = None
        self.tick_kwargs = None
        self.yaxis = _YAxis()
        self.transAxes = object()

    def set_ylim(self, *args):
        self.ylim = args

    def set_yticks(self, values):
        self.yticks = np.asarray(values, dtype=float)

    def set_yticklabels(self, values):
        self.yticklabels = list(values)

    def set_ylabel(self, value):
        self.ylabel = value

    def tick_params(self, **kwargs):
        self.tick_kwargs = kwargs


class _Plot(MapPlotMixin):
    pass


def test_physical_left_and_iteration_right_use_same_row_positions():
    plot = _Plot()
    left, right = _Axis(), _Axis()
    secondary = np.linspace(700.0, 728.2, 283)
    iterations = np.arange(1, 284)

    centers, idx = plot._configure_map_y_axes(
        left, right, 283, iterations, secondary, "Photon Energy [eV]"
    )

    np.testing.assert_allclose(left.yticks, right.yticks)
    np.testing.assert_allclose(left.yticks, centers[idx])
    assert left.ylabel == "Photon Energy [eV]"
    assert right.ylabel == "Iteration"
    assert left.yticklabels[0] == "700"
    assert right.yticklabels[0] == "1"
    assert float(left.yticklabels[-1]) > 720
    assert int(right.yticklabels[-1]) > 250


def test_missing_physical_axis_hides_left_labels_but_keeps_iteration():
    plot = _Plot()
    left, right = _Axis(), _Axis()
    plot._configure_map_y_axes(left, right, 10, list(range(1, 11)))

    assert left.ylabel == "Iteration"
    assert right.ylabel == "Iteration"
    assert right.yticklabels == [str(i) for i in range(1, 11)]


def test_secondary_axis_metadata_is_extracted_from_map_payload():
    x = np.arange(3.0)
    z = np.zeros((4, 3))
    payload = (x, [1, 2, 3, 4], z, "map", "BE", "viridis", [700, 701, 702, 703], "Photon Energy [eV]")

    values, label = _Plot._map_secondary_axis(payload, 4)

    np.testing.assert_allclose(values, [700, 701, 702, 703])
    assert label == "Photon Energy [eV]"


def test_map_coordinate_formatter_reports_intensity_for_photon_energy_map():
    plot = _Plot()
    axis = _Axis()
    z = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])

    plot._set_map_coordinate_formatter(
        axis,
        [10.0, 9.0, 8.0],
        2,
        "Binding Energy [eV]",
        [1, 2],
        [585.0, 586.0],
        "Photon Energy [eV]",
        z,
    )

    assert axis.format_coord(9.11, 1.2) == (
        "BE = 9.1 eV     PhE = 586.0 eV    Intensity = 5.0000e+00"
    )


def test_map_coordinate_formatter_reports_intensity_with_iteration_fallback():
    plot = _Plot()
    axis = _Axis()
    z = np.array([[10.0, 20.0], [30.0, 40.0]])

    plot._set_map_coordinate_formatter(
        axis, [0.0, 1.0], 2, "Kinetic Energy [eV]", [7, 8], z_values=z
    )

    assert axis.format_coord(0.9, 0.4) == (
        "KE = 0.9 eV     Iteration = 7     Intensity = 2.0000e+01"
    )
