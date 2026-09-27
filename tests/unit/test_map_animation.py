from maxiv_panda.map_animation import (
    valid_full_width_indices,
    stepped_positions,
    playback_positions,
)


def test_valid_indices_keep_full_thickness_inside_map():
    assert valid_full_width_indices(10, 1) == list(range(10))
    assert valid_full_width_indices(10, 5) == [2, 3, 4, 5, 6, 7]


def test_step_is_exactly_selected_thickness():
    assert stepped_positions(2, 17, 5) == [2, 7, 12, 17]
    assert stepped_positions(17, 2, 5) == [17, 12, 7, 2]
    assert stepped_positions(2, 16, 5) == [2, 7, 12]


def test_back_and_forth_sequences():
    base = [2, 7, 12, 17]
    assert playback_positions(base, True, False) == [2, 7, 12, 17, 12, 7, 2]
    assert playback_positions(base, True, True) == [2, 7, 12, 17, 12, 7]
    assert playback_positions(base, False, True) == base


def test_smooth_positions_preserve_key_endpoints_and_insert_frames():
    from maxiv_panda.map_animation import smooth_positions
    out = smooth_positions([2, 7, 12], frame_rate=30, key_steps_per_second=10)
    assert out[0] == 2.0
    assert out[-1] == 12.0
    assert len(out) == 7  # 3 rendered frames per physical key step
    assert out[3] == 7.0


def test_repeated_back_and_forth_cycle_has_no_duplicate_dwell():
    from maxiv_panda.map_animation import repeated_cycle_positions
    cycle = [2.0, 7.0, 2.0]
    assert repeated_cycle_positions(cycle, 2) == [2.0, 7.0, 2.0, 7.0, 2.0]
