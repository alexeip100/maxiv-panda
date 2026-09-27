from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PEAKFIT = ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit"


def _imports_datetime(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "datetime":
            if any(alias.name == "datetime" for alias in node.names):
                return True
    return False


def test_path_specific_batch_configs_import_datetime_locally():
    for name in ("batch_peak_only_config.py", "batch_config.py"):
        path = PEAKFIT / name
        source = path.read_text(encoding="utf-8")
        assert "datetime.now()" in source, f"{name} no longer uses datetime.now(); update this guard"
        assert _imports_datetime(path), f"{name} uses datetime.now() without importing datetime"
