import numpy as np

from maxiv_panda.workflows.normalization.logic import (
    mean_intensity_over_interval,
    normalization_interval_if_reachable,
)


def test_centre_rounded_just_below_edge_is_accepted_and_shifted_inward():
    low, high = normalization_interval_if_reachable(158.0640428457901, 168.06404284578102, 158.064, 1.0)
    assert low == 158.0640428457901
    assert high > low
    assert abs((high-low)-0.1) < 1e-9


def test_slight_ecal_shift_beyond_edge_still_normalizes():
    x=np.linspace(158.10,168.10,201)
    y=np.linspace(2.0,3.0,201)
    interval=normalization_interval_if_reachable(x[0],x[-1],158.06,1.0)
    assert interval is not None
    scale=mean_intensity_over_interval(x,y,*interval)
    assert np.isfinite(scale) and scale > 0


def test_distant_centre_remains_invalid():
    assert normalization_interval_if_reachable(158.1,168.1,157.0,1.0) is None
