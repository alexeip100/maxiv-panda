from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
APP = (ROOT / "src" / "maxiv_panda" / "app.py").read_text(encoding="utf-8")


def test_distribution_name_is_maxiv_panda():
    assert 'name = "maxiv-panda"' in PYPROJECT


def test_only_new_public_launchers_are_exposed():
    assert 'panda = "maxiv_panda.app:main"' in PYPROJECT
    assert 'maxiv-panda = "maxiv_panda.app:main"' in PYPROJECT
    assert 'flexpes-pes = ' not in PYPROJECT


def test_readme_uses_new_launchers():
    assert "\npanda\n" in README
    assert "maxiv-panda" in README
    assert "flexpes-pes" not in README


def test_entrypoint_docstrings_use_panda_names():
    assert "`panda` and `maxiv-panda`" in APP
    assert "`flexpes-pes`" not in APP
