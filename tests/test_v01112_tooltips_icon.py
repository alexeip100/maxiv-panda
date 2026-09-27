from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_doublet_component_tooltip_is_title_only():
    text = (_root() / "src/maxiv_panda/workflows/peakfit/fit_widgets.py").read_text(encoding="utf-8")
    assert "title.setToolTip(component_tip)" in text
    assert "gb.setToolTip(component_tip)" not in text


def test_selective_fit_parameter_tooltips_are_present():
    text = (_root() / "src/maxiv_panda/workflows/peakfit/fit_widgets.py").read_text(encoding="utf-8")
    assert "Spin-orbit energy separation between the major and minor components." in text
    assert "Major/minor peak-height ratio." in text
    assert "Lorentzian FWHM; mainly the lifetime-broadening contribution" in text
    assert "Gaussian FWHM; mainly instrumental and inhomogeneous broadening" in text
    assert "Peak asymmetry parameter." in text
    assert "Free fits this parameter; Fixed holds it constant; Tied links it" in text
    assert "Same constrains major and minor components to the same value" in text


def test_app_icon_has_transparent_outer_canvas():
    from PIL import Image

    icon = Image.open(_root() / "src/maxiv_panda/data/panda_app_icon.png").convert("RGBA")
    w, h = icon.size
    for xy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        assert icon.getpixel(xy)[3] == 0
    assert icon.getpixel((w // 2, h // 2))[3] > 250
