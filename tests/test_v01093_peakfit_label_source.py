from pathlib import Path


def test_peak_parameters_label_is_not_duplicated():
    source = (
        Path(__file__).parents[1]
        / "src"
        / "maxiv_panda"
        / "workflows"
        / "peakfit"
        / "fit_dialog.py"
    ).read_text(encoding="utf-8")

    assert 'self.right_tabs.addTab(peak_tab, "Peak parameters")' in source
    assert 'QGroupBox("Peak parameters", peak_tab)' not in source
