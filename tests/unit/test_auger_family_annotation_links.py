from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from maxiv_panda.signal_identification.annotation_plotting import draw_signal_annotations
from maxiv_panda.signal_identification.matcher import (
    AugerDisplayRegion,
    PeakAssignment,
    SignalCandidate,
)
from maxiv_panda.signal_identification.peak_detection import DetectedPeak


class _Checked:
    def isChecked(self):
        return True


def _assignment(element, family, regions):
    peak_energy = regions[0].peak_energy
    candidate = SignalCandidate(
        element=element,
        line=family,
        kind="Auger",
        expected_energy=peak_energy,
        delta_e=0.0,
        score=10.0,
        confident=True,
        auger_subregions=tuple(regions),
    )
    return PeakAssignment(
        peak=DetectedPeak(index=0, energy=peak_energy, intensity=1.0, prominence=1.0),
        candidates=[candidate],
    )


def test_auger_families_use_distinct_colours_and_component_connectors():
    fig, ax = plt.subplots()
    x = np.linspace(900.0, 600.0, 601)
    y = 1.0 + 0.02 * np.sin(x / 10.0)
    ax.plot(x, y)

    assignments = [
        _assignment("O", "KLL", [
            AugerDisplayRegion(710.0, 695.0, 702.0, 717.0, 725.0, 2.0),
            AugerDisplayRegion(755.0, 740.0, 747.0, 763.0, 772.0, 1.5),
        ]),
        _assignment("Cr", "LMM", [
            AugerDisplayRegion(728.0, 712.0, 720.0, 736.0, 744.0, 2.0),
        ]),
    ]
    payload = SimpleNamespace(x=x, y=y, energy_scale="Binding")
    controller = SimpleNamespace(
        window=SimpleNamespace(
            cb_identify_signals=_Checked(),
            plot_area=SimpleNamespace(ax=ax, canvas=fig.canvas),
        ),
        assignments=assignments,
        _active_key="curve",
        settings=SimpleNamespace(valence_band_cutoff_eV=0.0, photon_energy=1215.0),
        current_single_curve=lambda: (payload, {}, "curve"),
        identify=lambda show_messages=False: None,
    )

    draw_signal_annotations(controller)

    labels = {text.get_text(): text for text in ax.texts}
    assert labels["O KLL"].get_color() != labels["Cr LMM"].get_color()
    assert labels["O KLL"].get_position()[1] != labels["Cr LMM"].get_position()[1]

    # Each measured Auger subregion now gets its own local underline and tick;
    # no connector spans the empty gap between distant clusters.
    connector_lines = ax.lines[1:]
    assert len(connector_lines) == 6

    oxygen_colour = labels["O KLL"].get_color()
    oxygen_lines = [line for line in connector_lines if line.get_color() == oxygen_colour]
    assert len(oxygen_lines) == 4
    horizontals = [line for line in oxygen_lines if np.ptp(line.get_xdata()) > 0]
    assert len(horizontals) == 2
    centers = sorted(float(np.mean(line.get_xdata())) for line in horizontals)
    assert np.allclose(centers, [710.0, 755.0])
    assert all(np.ptp(line.get_xdata()) < 15.0 for line in horizontals)

    plt.close(fig)
