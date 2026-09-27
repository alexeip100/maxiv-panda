from maxiv_panda.workflows.peakfit import so_doublets


def test_automatic_colors_are_distinct_in_peak_view():
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b"]
    cmap = so_doublets.visible_color_map(colors, [False]*5, [], grouped=False)
    visible = [cmap[i] for i in range(1, 6)]
    assert len(set(visible)) == len(visible)


def test_automatic_colors_are_distinct_in_doublet_view():
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b"]
    states = [
        {"id": 1, "major": 1, "minor": 2, "label": "D1 #1"},
        {"id": 2, "major": 4, "minor": 5, "label": "D2 #1"},
    ]
    cmap = so_doublets.visible_color_map(colors, [False]*5, states, grouped=True)
    # Visible entities are doublet(1,2), standalone 3, doublet(4,5).
    visible = [cmap[1], cmap[3], cmap[4]]
    assert len(set(visible)) == 3
    assert cmap[1] == cmap[2]
    assert cmap[4] == cmap[5]


def test_user_color_is_preserved_and_automatic_colors_avoid_it():
    custom = "#2ca02c"
    colors = [custom, "#ff7f0e", "#2ca02c"]
    cmap = so_doublets.visible_color_map(colors, [True, False, False], [], grouped=False)
    assert cmap[1] == custom
    assert cmap[2].lower() != custom.lower()
    assert cmap[3].lower() != custom.lower()
    assert len({cmap[1].lower(), cmap[2].lower(), cmap[3].lower()}) == 3
