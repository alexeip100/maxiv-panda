from pathlib import Path


def test_lazy_and_eager_iterations_share_checkbox_configuration():
    src = (Path(__file__).parents[1] / "src" / "maxiv_panda" / "loaded_tree.py").read_text(encoding="utf-8")
    assert "def _configure_iterations_root" in src
    assert src.count("self._configure_iterations_root(") >= 3
    assert "self.tree.itemChanged.connect(self._on_lazy_item_changed)" in src
    assert "def _materialize_lazy_iterations" in src
