from pathlib import Path
ROOT = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"

def test_separate_subtraction_palette_and_symmetric_contrast():
    src = (ROOT / "ui_map_plot_mixin.py").read_text()
    assert 'cmap = str(difference_cmap or "RdBu_r")' in src
    assert 'limit = amplitude * 100.0 / max(100, int(difference_contrast))' in src
    assert '"vmin": -limit, "vmax": limit' in src

def test_slider_changes_artist_only():
    src = (ROOT / "ui_map_controls_mixin.py").read_text()
    block = src.split('def _refresh_subtraction_color_display(self)')[1].split('def _seed_respes_preedge_interval')[0]
    assert 'artist.set_clim(-limit, limit)' in block
    assert 'artist.set_cmap(cmap)' in block
    assert '_update_plot_from_selected' not in block

def test_session_fields():
    src = (ROOT / "ui_actions_mixin.py").read_text()
    for key in ('respes_difference_cmap', 'respes_difference_contrast'):
        assert f'"{key}"' in src
