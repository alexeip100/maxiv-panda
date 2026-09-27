from pathlib import Path


def _source(relative: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / relative).read_text(encoding="utf-8")


def test_show_auger_control_is_default_checked_and_initially_disabled():
    src = _source("src/maxiv_panda/ui_raw_data_mixin.py")
    assert 'QCheckBox("Show Auger"' in src
    assert 'self.cb_show_auger.setChecked(True)' in src
    assert 'self.cb_show_auger.setEnabled(False)' in src
    assert 'self.cb_show_auger.toggled.connect(self._signal_identification.set_show_auger)' in src


def test_show_auger_toggle_is_display_only():
    src = _source("src/maxiv_panda/signal_identification/controller.py")
    start = src.index("    def set_show_auger")
    end = src.index("    def identify", start)
    body = src[start:end]
    assert "_update_plot_from_selected" in body
    assert "self.identify(" not in body
    assert "self.assignments =" not in body


def test_auger_annotations_respect_show_auger_checkbox():
    src = _source("src/maxiv_panda/signal_identification/annotation_plotting.py")
    assert 'getattr(self.window, "cb_show_auger", None)' in src
    assert 'show_auger is None or show_auger.isChecked()' in src
