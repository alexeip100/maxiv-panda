"""WebEngine must be imported before QApplication construction on Windows."""
import ast
from pathlib import Path


def test_webengine_import_precedes_qapplication():
    path = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda" / "app.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    webengine_index = next(i for i, n in enumerate(main.body) if isinstance(n, ast.ImportFrom) and n.module == "PyQt6.QtWebEngineWidgets")
    app_index = next(i for i, n in enumerate(main.body) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "app" for t in n.targets))
    assert webengine_index < app_index
