from pathlib import Path

from maxiv_panda.workflows.peakfit import fit_io


ROOT = Path(__file__).resolve().parents[1]


def test_real_loaded_curve_region_index_is_not_repeated_in_save_dialog_name(tmp_path):
    # Loaded-tree keys append #N to the region identity.  That index must be
    # retained, but it must not prevent deduplication of the physical region
    # already present at the end of the source filename.
    metadata = {
        "source_file": "XPS_0005Ir4f_170eV.ibw",
        "region": "Ir4f_170eV#1",
        "curve_label": "Trace",
    }
    path = fit_io.suggest_fit_setup_path(tmp_path, metadata)
    assert path == tmp_path / "XPS_0005Ir4f_170eV_#1_Trace.fit.json"


def test_region_index_and_region_prefixed_curve_label_are_deduplicated_together(tmp_path):
    metadata = {
        "source_file": "XPS_0005Ir4f_170eV.ibw",
        "region": "Ir4f_170eV#1",
        "curve_label": "Ir4f_170eV#1_Trace",
    }
    path = fit_io.suggest_fit_setup_path(tmp_path, metadata)
    assert path.name == "XPS_0005Ir4f_170eV_#1_Trace.fit.json"


def test_missing_region_metadata_still_deduplicates_region_like_curve_prefix(tmp_path):
    metadata = {
        "source_file": "XPS_0005Ir4f_170eV.ibw",
        "region": "",
        "curve_label": "Ir4f_170eV#1_Trace",
    }
    path = fit_io.suggest_fit_setup_path(tmp_path, metadata)
    assert path.name == "XPS_0005Ir4f_170eV_#1_Trace.fit.json"


def test_copy_suffix_does_not_break_region_deduplication(tmp_path):
    metadata = {
        "source_file": "XPS_0005Ir4f_170eV(1).ibw",
        "region": "Ir4f_170eV#1",
        "curve_label": "Trace",
    }
    path = fit_io.suggest_fit_setup_path(tmp_path, metadata)
    assert path.name == "XPS_0005Ir4f_170eV(1)_#1_Trace.fit.json"


def test_save_dialog_uses_the_tested_path_helper():
    source = (
        ROOT / "src/maxiv_panda/workflows/peakfit/fit_dialog_io_mixin.py"
    ).read_text(encoding="utf-8")
    assert "start_path = fit_io.suggest_fit_setup_path(self._fit_io_default_dir(), metadata)" in source
    assert "QFileDialog.getSaveFileName(" in source
    assert "str(start_path)" in source
