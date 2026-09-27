from matplotlib.figure import Figure

from maxiv_panda.workflows.peakfit import fit_plotting


class _ValueBox:
    def __init__(self, value):
        self._value = float(value)

    def value(self):
        return self._value


class _Canvas:
    def __init__(self):
        self.draw_calls = 0

    def draw_idle(self):
        self.draw_calls += 1


def test_peak_markers_remain_visible_when_calculated_spectrum_is_active():
    fig = Figure()
    ax = fig.add_subplot(111)
    canvas = _Canvas()
    widgets = [{"E": _ValueBox(5.0), "H": _ValueBox(12.0), "color": "#123456"}]

    artists = fit_plotting.refresh_peak_markers(
        ax, canvas, widgets, calc_checked=True, existing_artists=[]
    )

    assert len(artists) == 1
    segments = artists[0].get_segments()
    assert len(segments) == 1
    assert segments[0][0][0] == 5.0
    assert segments[0][1][0] == 5.0
    assert segments[0][0][1] == 0.0
    assert segments[0][1][1] == 12.0
    assert canvas.draw_calls == 1


def test_peak_marker_existing_artist_color_updates_in_place():
    fig = Figure()
    ax = fig.add_subplot(111)
    canvas = _Canvas()
    widget = {"E": _ValueBox(5.0), "H": _ValueBox(12.0), "color": "#123456"}

    artists = fit_plotting.refresh_peak_markers(
        ax, canvas, [widget], calc_checked=True, existing_artists=[]
    )
    artist = artists[0]
    first_rgba = tuple(artist.get_colors()[0])

    widget["color"] = "#ff0000"
    artists2 = fit_plotting.refresh_peak_markers(
        ax, canvas, [widget], calc_checked=True, existing_artists=artists
    )

    assert artists2[0] is artist
    second_rgba = tuple(artist.get_colors()[0])
    assert second_rgba != first_rgba
    assert second_rgba[:3] == (1.0, 0.0, 0.0)
