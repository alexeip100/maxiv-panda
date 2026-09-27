from pathlib import Path


def test_legacy_namespace_is_absent_from_public_package():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "src" / "flexpes_pes").exists()


def test_primary_namespace_exists_and_contains_application():
    root = Path(__file__).resolve().parents[1]
    primary = root / "src" / "maxiv_panda"
    assert (primary / "__init__.py").is_file()
    assert (primary / "app.py").is_file()
