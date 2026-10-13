from pathlib import Path


def test_map_exchange_tooltips_concise_and_accurate():
    source = (Path(__file__).resolve().parents[1] / "src/maxiv_panda/ui_processed_data_mixin.py").read_text()
    assert "exchange_menu.setToolTipsVisible(True)" in source
    assert "Export a 2D matrix with energy axes for Igor, Origin or Python." in source
    assert "Import a PANDA ASCII matrix with its axes and processed intensities." in source
    assert "Import an Igor Binary Wave." in source
    assert "Import or export numerical 2D map data (not an image)." in source
    assert "Import 2D map (PANDA ASCII matrix)" in source
    assert 'exchange_menu.addAction("Export processed map (ASCII matrix)…)"' not in source  # no extra format
