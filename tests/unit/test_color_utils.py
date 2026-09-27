from maxiv_panda.utils.colors import mpl_color_to_hex, mpl_color_to_rgba8


def test_matplotlib_cycle_color_converts_to_qt_rgba():
    assert mpl_color_to_rgba8("C0") == (31, 119, 180, 255)


def test_matplotlib_tab_color_converts_to_qt_rgba():
    assert mpl_color_to_rgba8("tab:orange") == (255, 127, 14, 255)


def test_hex_and_tuple_colors_are_supported():
    assert mpl_color_to_rgba8("#336699") == (51, 102, 153, 255)
    assert mpl_color_to_rgba8((1.0, 0.5, 0.0, 0.25)) == (255, 128, 0, 64)


def test_matplotlib_color_converts_to_css_safe_hex():
    assert mpl_color_to_hex("tab:blue") == "#1f77b4"


def test_stringified_rgba_tuple_from_matplotlib_is_recovered():
    color = "(0.12156862745098039, 0.4666666666666667, 0.7058823529411765, 1.0)"
    assert mpl_color_to_hex(color) == "#1f77b4"
