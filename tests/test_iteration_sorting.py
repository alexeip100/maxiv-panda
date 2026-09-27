from maxiv_panda.file_naming import curve_detail_sort_key


def test_iteration_sort_key_uses_numeric_metadata():
    labels = ["Iteration 1", "Iteration 10", "Iteration 100", "Iteration 2", "Iteration 11", "Iteration 3"]
    metas = [{"iteration": int(label.split()[-1])} for label in labels]
    ordered = [label for label, meta in sorted(zip(labels, metas), key=lambda pair: curve_detail_sort_key(pair[1], pair[0]))]
    assert ordered == ["Iteration 1", "Iteration 2", "Iteration 3", "Iteration 10", "Iteration 11", "Iteration 100"]


def test_iteration_sort_key_falls_back_to_natural_label_order():
    labels = ["Iteration 1", "Iteration 10", "Iteration 100", "Iteration 2", "Iteration 11", "Iteration 3"]
    ordered = sorted(labels, key=lambda label: curve_detail_sort_key(None, label))
    assert ordered == ["Iteration 1", "Iteration 2", "Iteration 3", "Iteration 10", "Iteration 11", "Iteration 100"]
