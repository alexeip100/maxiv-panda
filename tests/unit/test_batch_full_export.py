import csv
import io
import zipfile

import numpy as np

from maxiv_panda.workflows.peakfit import batch_full_export


def _result(idx=1):
    x = [0.0, 1.0, 2.0]
    bg = np.array([2.0, 2.0, 2.0])
    c1 = np.array([1.0, 3.0, 1.0])
    c2 = np.array([0.5, 1.0, 0.5])
    model = bg + c1 + c2
    y = model + np.array([0.1, -0.2, 0.3])
    return {
        "spectrum_index": idx,
        "sequence_key": f"key:{idx}",
        "display": f"sample_{idx}.ibw",
        "status": "success",
        "message": "",
        "peaks": [{"index": 1, "label": "Fe 2p3/2"}, {"index": 2, "label": "Fe 2p1/2"}],
        "plot_data": {
            "x": x,
            "y": y.tolist(),
            "model": model.tolist(),
            "residual": (y - model).tolist(),
            "components": [c1.tolist(), c2.tolist()],
            "xlabel": "Binding Energy [eV]",
            "ylabel": "Intensity",
        },
    }


def test_result_curve_table_contains_background_and_components():
    headers, rows = batch_full_export.result_curve_table(_result())
    assert headers[:6] == ["Binding Energy [eV]", "Data", "Total Fit", "Background", "Peaks Sum", "Residual"]
    assert headers[6:] == ["P1_Fe_2p3_2", "P2_Fe_2p1_2"]
    assert len(rows) == 3
    np.testing.assert_allclose([r[3] for r in rows], [2.0, 2.0, 2.0])
    np.testing.assert_allclose([r[4] for r in rows], [1.5, 4.0, 1.5])


def test_batch_zip_contains_one_csv_per_fit_and_manifest(tmp_path):
    pass_obj = {
        "id": "pass_2",
        "label": "Pass 2: constrained",
        "source_pass_id": "pass_1",
        "store_all_fit_results": True,
        "results": [_result(1), _result(2)],
    }
    out = tmp_path / "fits.zip"
    counts = batch_full_export.write_batch_fits_zip(out, pass_obj)
    assert counts == {"fit_files": 2, "results": 2}
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "batch_manifest.csv" in names
        fit_names = [n for n in names if n.startswith("fits/")]
        assert len(fit_names) == 2
        first = zf.read(fit_names[0]).decode("utf-8")
        assert first.splitlines()[0].startswith("Binding Energy [eV],Data,Total Fit,Background,Peaks Sum,Residual")
        manifest = list(csv.reader(io.StringIO(zf.read("batch_manifest.csv").decode("utf-8"))))
        assert manifest[0][0:4] == ["fit_number", "spectrum_index", "fit_file", "sequence_key"]
        assert manifest[1][-1] == "yes"
