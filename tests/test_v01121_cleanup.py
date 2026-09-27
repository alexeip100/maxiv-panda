from pathlib import Path

from maxiv_panda.workflows.peakfit import fit_io
from maxiv_panda.workflows.peakfit.fit_io import suggest_fit_setup_filename


ROOT = Path(__file__).resolve().parents[1]


def test_obsolete_plotting_modules_and_legacy_icons_are_absent():
    plotting = ROOT / "src/maxiv_panda/workflows/plotting"
    for name in ("curve_list.py", "dialogs.py", "io.py"):
        assert not (plotting / name).exists()
    data = ROOT / "src/maxiv_panda/data"
    for name in ("flexpes_xps_icon_light.ico", "flexpes_xps_icon_light.png"):
        assert not (data / name).exists()


def test_legacy_python_namespace_is_absent():
    assert not (ROOT / "src/flexpes_pes").exists()


def test_single_fit_export_and_setup_share_region_deduplication():
    md = {
        "source_file": "XPS_0005Ir4f_170eV.ibw",
        "region": "Ir4f_170eV",
        "curve_label": "Ir4f_170eV#1_Trace",
    }
    assert suggest_fit_setup_filename(md) == "XPS_0005Ir4f_170eV_#1_Trace.fit.json"
    parts = fit_io.compact_fit_identity_parts(md, curve_keys=("curve_label", "display_label", "curve_id"), include_anchor=False)
    assert parts == ["XPS_0005Ir4f_170eV", "#1_Trace"]
    export_src = (ROOT / "src/maxiv_panda/workflows/peakfit/fit_export.py").read_text(encoding="utf-8")
    assert "fit_io.compact_fit_identity_parts(" in export_src


def test_fit_cancel_exception_has_one_shared_definition():
    peakfit = ROOT / "src/maxiv_panda/workflows/peakfit"
    definitions = []
    for path in peakfit.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "class FitCancelled(Exception):" in text:
            definitions.append(path.name)
        assert "class _FitCancelled(Exception):" not in text
    assert definitions == ["fit_exceptions.py"]
