from maxiv_panda.file_naming import derive_file_tag, file_number_sort_key, format_curve_source_label


def test_ibw_region_suffix_does_not_replace_xps_file_number():
    assert derive_file_tag("XPS_0070S2p_260.ibw") == "0070"


def test_txt_file_number_uses_same_rule():
    assert derive_file_tag("XPS_0070.txt") == "0070"


def test_ibw_descriptive_suffix_uses_xps_file_number():
    assert derive_file_tag("XPS_0009Survey 1000(1).ibw") == "0009"


def test_selected_curve_label_uses_file_number_first():
    assert format_curve_source_label("XPS_0070S2p_260.ibw", "S2p_260") == "0070: S2p_260"
    assert format_curve_source_label("XPS_0070.txt", "S2p_260") == "0070: S2p_260"
    assert format_curve_source_label("XPS_0070.txt", "S2p_260", "Average") == "0070: S2p_260 (Average)"


def test_file_number_sort_key_is_numeric_not_selection_order():
    names = [
        "XPS_0100.txt",
        "XPS_0009Survey.ibw",
        "XPS_0070S2p_260.ibw",
        "XPS_0012.txt",
    ]
    assert sorted(names, key=file_number_sort_key) == [
        "XPS_0009Survey.ibw",
        "XPS_0012.txt",
        "XPS_0070S2p_260.ibw",
        "XPS_0100.txt",
    ]
