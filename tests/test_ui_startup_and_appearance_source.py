from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"


def test_advanced_panels_are_eagerly_constructed():
    ui = (ROOT / "ui.py").read_text(encoding="utf-8")
    raw = (ROOT / "ui_raw_data_mixin.py").read_text(encoding="utf-8")
    assert "self.plotted_data_panel = PlottedDataPanel(" in ui
    assert "self.cross_section_reference_panel = CrossSectionReferencePanel(" in ui
    assert "self.binding_energy_reference_panel = BindingEnergyReferencePanel(" in ui
    assert "self._signal_identification = SignalIdentificationController(self)" in raw


def test_plot_area_uses_standard_toolbar_without_appearance_persistence():
    ui = (ROOT / "ui.py").read_text(encoding="utf-8")
    assert "self.toolbar = NavigationToolbar(self.canvas, self)" in ui
    assert "_PersistentNavigationToolbar" not in ui
    assert "_capture_appearance_state" not in ui
    assert "_appearance_states" not in ui


def test_loaded_tree_exposes_metadata_context_action():
    ui = (ROOT / "ui.py").read_text(encoding="utf-8")
    loaded = (ROOT / "loaded_tree.py").read_text(encoding="utf-8")
    assert "Show metadata" in ui
    assert "Right-click for metadata and other options" in loaded
    assert "metadata_scope" in loaded


def test_about_title_is_not_repetitive():
    actions = (ROOT / "ui_actions_mixin.py").read_text(encoding="utf-8")
    assert 'msg.setWindowTitle("About PANDA")' in actions
    assert 'About FlexPES PES data processor - FlexPES PES Processor' not in actions
