from dataclasses import dataclass

import numpy as np

from maxiv_panda.intensity_units import CPS, time_per_spectrum_channel, scale_payload


@dataclass
class Payload:
    title: str
    x: object
    y: object
    xlabel: str = "Binding Energy [eV]"
    ylabel: str = "Intensity"
    energy_scale: str = "Binding"


def test_time_per_spectrum_channel_from_source_metadata():
    meta = {"source_metadata": {"Time per Spectrum Channel": "29.11"}}
    assert time_per_spectrum_channel(meta) == 29.11


def test_invalid_time_per_spectrum_channel_is_rejected():
    assert time_per_spectrum_channel({"source_metadata": {"Time per Spectrum Channel": "0"}}) is None
    assert time_per_spectrum_channel({"source_metadata": {"Time per Spectrum Channel": "bad"}}) is None


def test_cps_scaling_returns_copy_and_updates_ylabel():
    p = Payload("Sn3d", np.array([1.0, 2.0]), np.array([29.11, 58.22]))
    q = scale_payload(p, seconds=29.11, mode=CPS)
    assert q is not p
    np.testing.assert_allclose(q.y, [1.0, 2.0])
    assert q.ylabel == "Intensity [counts/s]"
    np.testing.assert_allclose(p.y, [29.11, 58.22])
