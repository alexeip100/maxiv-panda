from pathlib import Path


def test_platform_icons_are_bundled_as_package_data():
    root = Path(__file__).resolve().parents[2]
    data = root / "src" / "maxiv_panda" / "data"
    for name in ("panda_app_icon.ico", "panda_app_icon.icns", "panda_app_icon.png"):
        icon = data / name
        assert icon.is_file()
        assert icon.stat().st_size > 0


def test_legacy_application_icons_are_removed():
    root = Path(__file__).resolve().parents[2]
    data = root / "src" / "maxiv_panda" / "data"
    assert not (data / "flexpes_xps_icon_light.ico").exists()
    assert not (data / "flexpes_xps_icon_light.png").exists()


def test_pyproject_includes_platform_icon_package_data():
    root = Path(__file__).resolve().parents[2]
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert '"data/*.ico"' in text
    assert '"data/*.icns"' in text
    assert '"data/*.png"' in text
