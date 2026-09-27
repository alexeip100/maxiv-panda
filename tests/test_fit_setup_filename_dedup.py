from maxiv_panda.workflows.peakfit.fit_io import suggest_fit_setup_filename


def test_region_not_repeated_when_source_stem_already_ends_with_region():
    name = suggest_fit_setup_filename({
        "source_file": "XPS_0005Ir4f_170eV.ibw",
        "region": "Ir4f_170eV",
        "curve_label": "#1_Trace",
    })
    assert name == "XPS_0005Ir4f_170eV_#1_Trace.fit.json"


def test_region_not_repeated_across_separator_variants():
    name = suggest_fit_setup_filename({
        "source_file": "XPS_0005_Ir4f-170eV.ibw",
        "region": "Ir4f 170eV",
        "curve_label": "#1_Trace",
    })
    assert name == "XPS_0005_Ir4f-170eV_#1_Trace.fit.json"


def test_region_is_kept_when_not_present_in_source_stem():
    name = suggest_fit_setup_filename({
        "source_file": "XPS_0005.ibw",
        "region": "Ir4f_170eV",
        "curve_label": "#1_Trace",
    })
    assert name == "XPS_0005_Ir4f_170eV_#1_Trace.fit.json"


def test_anchor_filename_uses_same_region_deduplication_rule():
    name = suggest_fit_setup_filename({
        "source_file": "XPS_0005Ir4f_170eV.ibw",
        "region": "Ir4f_170eV",
        "anchor_label": "Start anchor",
        "anchor_range": "1-3",
    })
    assert name.count("Ir4f_170eV") == 1


def test_region_not_repeated_when_curve_label_also_starts_with_region():
    name = suggest_fit_setup_filename({
        "source_file": "XPS_0005Ir4f_170eV.ibw",
        "region": "Ir4f_170eV",
        "curve_label": "Ir4f_170eV#1_Trace",
    })
    assert name == "XPS_0005Ir4f_170eV_#1_Trace.fit.json"


def test_region_prefix_is_removed_from_curve_label_when_region_is_separate_token():
    name = suggest_fit_setup_filename({
        "source_file": "XPS_0005.ibw",
        "region": "Ir4f_170eV",
        "curve_label": "Ir4f-170eV #1 Trace",
    })
    assert name == "XPS_0005_Ir4f_170eV_#1_Trace.fit.json"
