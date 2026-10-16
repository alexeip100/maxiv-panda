"""Both disk-based Save actions must share the JSON format and filename."""
from pathlib import Path
from unittest.mock import patch
import json
from maxiv_panda.workflows.peakfit import fit_io
import pytest
fit_export = pytest.importorskip("maxiv_panda.workflows.peakfit.fit_export")


def test_same_suggested_json_filename():
    md = {"source_file": "XPS_0024XPS_024.ibw", "region": "Sn_MNN_AES_520eV#1", "curve_label": "Trace"}
    setup_name = fit_io.suggest_fit_setup_filename(md)
    export_base = fit_io.suggest_fit_setup_filename(md).removesuffix('.fit.json')
    assert f'{export_base}.fit.json' == setup_name
    assert setup_name.endswith('.fit.json')


def test_export_json_uses_same_writer_and_setup_as_save_config(tmp_path):
    class Dialog:
        _last_fit_result = object()
        _last_fit_data = {'xu': [], 'yu': []}
        _last_fit_bg_type = 'constant'
        _last_fit_status = 'Converged'
        def _current_fit_io_metadata(self):
            return {'source_file': 'test.ibw', 'curve_label': 'Trace'}
        def _fit_io_default_dir(self):
            return tmp_path
        def _capture_fit_setup_template(self):
            return {'peak_states': [], 'bg_state': {'bg_type': 'constant'}, 'fit_range': None}
        def _remember_fit_io_dir(self, path):
            self.remembered = path

    class FakeExportDialog:
        def __init__(self, parent, default_dir, default_base):
            assert default_base == fit_io.suggest_fit_setup_filename(parent._current_fit_io_metadata()).removesuffix('.fit.json')
            self.path = default_dir / f'{default_base}.fit.json'
        def exec(self):
            return fit_export.QDialog.DialogCode.Accepted
        def selected_paths(self):
            return {'json': self.path}

    d = Dialog()
    with patch.object(fit_export, 'SingleFitExportDialog', FakeExportDialog), patch.object(fit_export.QMessageBox, 'information'):
        fit_export.export_single_fit_results(d)
    data = json.loads(Path(d.remembered).read_text(encoding='utf-8'))
    assert data['format'] == fit_io.FORMAT_NAME
    assert data['metadata'] == d._current_fit_io_metadata()
    restored, md = fit_io.load_fit_setup_json(d.remembered)
    assert md == d._current_fit_io_metadata()
    assert restored == fit_io.FitSetupState.from_mapping(d._capture_fit_setup_template()).to_mapping()
