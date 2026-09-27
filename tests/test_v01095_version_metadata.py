from pathlib import Path
import importlib.util
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "maxiv_panda"


def _load_version_module():
    spec = importlib.util.spec_from_file_location("maxiv_panda_version_test", SRC / "version.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_version_metadata_has_single_dedicated_source():
    version = _load_version_module()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version.__version__)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", version.__date__)


def test_gui_imports_version_metadata_directly():
    for rel in ["ui.py", "ui_actions_mixin.py"]:
        text = (SRC / rel).read_text(encoding="utf-8")
        assert "from .version import __date__, __version__" in text
        assert "from . import __date__, __version__" not in text


def test_package_initializer_reexports_metadata():
    text = (SRC / "__init__.py").read_text(encoding="utf-8")
    assert "from .version import __date__, __version__" in text


def test_pyproject_version_matches_runtime_version():
    version = _load_version_module()
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["version"] == version.__version__
