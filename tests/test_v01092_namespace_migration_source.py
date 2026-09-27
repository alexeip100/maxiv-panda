from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_primary_package_namespace_is_maxiv_panda():
    assert (ROOT / "src" / "maxiv_panda" / "__init__.py").is_file()
    assert (ROOT / "src" / "maxiv_panda" / "app.py").is_file()


def test_launchers_target_new_namespace():
    assert 'panda = "maxiv_panda.app:main"' in PYPROJECT
    assert 'maxiv-panda = "maxiv_panda.app:main"' in PYPROJECT
    assert 'panda = "flexpes_pes.app:main"' not in PYPROJECT
    assert 'maxiv-panda = "flexpes_pes.app:main"' not in PYPROJECT


def test_package_data_targets_new_namespace():
    assert 'maxiv_panda = ["docs/*.md"' in PYPROJECT


def test_legacy_python_namespace_is_removed():
    assert not (ROOT / "src" / "flexpes_pes").exists()


def test_legacy_saved_format_ids_are_still_supported():
    fit_io = (ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit" / "fit_io.py").read_text(encoding="utf-8")
    fit_schema = (ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit" / "fit_schema.py").read_text(encoding="utf-8")
    fit_export = (ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit" / "fit_export.py").read_text(encoding="utf-8")
    batch = (ROOT / "src" / "maxiv_panda" / "workflows" / "peakfit" / "batch_config.py").read_text(encoding="utf-8")
    assert 'FORMAT_NAME = "flexpes_pes_fit_setup"' in fit_schema
    assert 'FORMAT_NAME = fit_schema.FORMAT_NAME' in fit_io
    assert 'FORMAT_NAME = "flexpes_pes_single_fit_result"' in fit_export
    assert '"format": "flexpes_pes_batch_setup"' in batch
