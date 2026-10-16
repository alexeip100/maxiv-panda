"""Cross-check the file-based Save paths against the shared writer and filename."""
from pathlib import Path
from maxiv_panda.workflows.peakfit import fit_io
ROOT = Path(__file__).resolve().parents[1]


def test_save_paths_use_same_schema_and_filename():
    src = (ROOT / 'src/maxiv_panda/workflows/peakfit/fit_export.py').read_text(encoding='utf-8')
    io = (ROOT / 'src/maxiv_panda/workflows/peakfit/fit_dialog_io_mixin.py').read_text(encoding='utf-8')
    assert 'fit_io.save_fit_setup_json(paths["json"], setup, metadata=metadata, fit_result=result_info)' in src
    assert 'fit_io.save_fit_setup_json(path, setup, metadata=metadata, fit_result=result_info)' in io
    assert 'default_base = fit_io.suggest_fit_setup_filename(metadata).removesuffix(".fit.json")' in src
    assert 'start_path = fit_io.suggest_fit_setup_path(self._fit_io_default_dir(), metadata)' in io
    assert 'paths["json"] = folder / f"{base}.fit.json"' in src
    assert 'paths["csv"] = folder / f"{base}_curves.csv"' in src


def test_shared_filename_is_loadable(tmp_path):
    metadata = {"source_file": "example.ibw", "region": "Sn_MNN#1", "curve_label": "Trace"}
    path = fit_io.suggest_fit_setup_path(tmp_path, metadata)
    fit_io.save_fit_setup_json(path, {"peak_states": [], "bg_state": {"bg_type": "constant"}}, metadata=metadata)
    setup, loaded = fit_io.load_fit_setup_json(path)
    assert loaded == metadata
    assert isinstance(setup["peak_states"], list)
