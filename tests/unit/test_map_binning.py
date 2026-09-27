import numpy as np

from maxiv_panda.map_binning import bin_map_image


def test_map_binning_matches_batch_style_complete_consecutive_bins():
    x = np.array([3.0, 2.0, 1.0])
    y = [1, 2, 3, 4, 5]
    Z = np.array([
        [1.0, 2.0, 3.0],
        [3.0, 4.0, 5.0],
        [10.0, 20.0, 30.0],
        [14.0, 24.0, 34.0],
        [99.0, 99.0, 99.0],
    ])
    secondary = [100.0, 102.0, 110.0, 114.0, 999.0]
    image = (x, y, Z, "region (map)", "Binding Energy [eV]", "viridis", secondary, "Photon Energy [eV]")

    binned, original, effective, discarded = bin_map_image(image, 2)

    assert original == 5
    assert effective == 2
    assert discarded == 1
    np.testing.assert_allclose(binned[2], [[2.0, 3.0, 4.0], [12.0, 22.0, 32.0]])
    np.testing.assert_allclose(binned[1], [1.5, 3.5])
    np.testing.assert_allclose(binned[6], [101.0, 112.0])
    assert binned[3].endswith("— binned by 2")
    assert binned[7] == "Photon Energy [eV]"


def test_map_binning_size_one_is_noop():
    image = (np.array([1.0, 2.0]), [1, 2], np.array([[1.0, 2.0], [3.0, 4.0]]), "map", "E")
    out, original, effective, discarded = bin_map_image(image, 1)
    assert out[0] is image[0]
    assert out[1] == image[1]
    assert out[2] is image[2]
    assert out[3:] == image[3:]
    assert (original, effective, discarded) == (2, 2, 0)
