from __future__ import annotations

import ast
from pathlib import Path

PEAKFIT = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda" / "workflows" / "peakfit"


def _unused_imports(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.asname or alias.name.split(".")[0], node.lineno))
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            for alias in node.names:
                if alias.name != "*":
                    imports.append((alias.asname or alias.name, node.lineno))
    loaded = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }
    return [(name, line) for name, line in imports if name not in loaded]


def test_peakfit_modules_have_no_stale_top_level_imports():
    problems: list[str] = []
    for path in sorted(PEAKFIT.glob("*.py")):
        for name, line in _unused_imports(path):
            problems.append(f"{path.name}:{line}: {name}")
    assert not problems, "Unused peakfit imports remain:\n" + "\n".join(problems)


def test_release_version_is_not_older_than_01158():
    version_py = (Path(__file__).resolve().parents[1] / "src" / "maxiv_panda" / "version.py").read_text(encoding="utf-8")
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    import re

    match = re.search(r'__version__\s*=\s*"(\d+)\.(\d+)\.(\d+)"', version_py)
    assert match is not None
    current = tuple(int(x) for x in match.groups())
    assert current >= (0, 11, 58)
    assert f'version = "{current[0]}.{current[1]}.{current[2]}"' in pyproject
