from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_batch_config_imports_so_doublets_before_using_it():
    src = (ROOT / "src/maxiv_panda/workflows/peakfit/batch_config.py").read_text(encoding="utf-8")
    assert "from . import so_doublets" in src
    assert "so_doublets.normalize_state" in src
    assert "so_doublets.resolve_tied_values" in src
    assert src.index("from . import so_doublets") < src.index("so_doublets.normalize_state")


def test_version_is_01133():
    version_src = (ROOT / "src/maxiv_panda/version.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    import re
    v1 = re.search(r'__version__ = "([^"]+)"', version_src).group(1)
    v2 = re.search(r'^version = "([^"]+)"', pyproject, re.M).group(1)
    assert v1 == v2
