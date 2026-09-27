from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"


def test_current_font_is_preserved_as_default_and_only_enlarged():
    style = (ROOT / "ui_style.py").read_text(encoding="utf-8")
    dialog = (ROOT / "widgets" / "appearance_settings_dialog.py").read_text(encoding="utf-8")
    assert "BASELINE_FONT_INCREMENT = 2" in style
    assert "ALLOWED_FONT_OFFSETS = (0, 1, 2)" in style
    assert '"Default (current)"' in dialog
    assert '"Larger (+1 pt)"' in dialog
    assert '"Largest (+2 pt)"' in dialog


def test_density_defaults_to_existing_standard_layout():
    style = (ROOT / "ui_style.py").read_text(encoding="utf-8")
    metrics = (ROOT / "ui_metrics.py").read_text(encoding="utf-8")
    assert "density: InterfaceDensity = InterfaceDensity.STANDARD" in style
    assert "COMPACT_METRICS = UiMetrics(" in metrics
    assert "resolve_automatic_density" in metrics


def test_settings_cog_replaces_help_appearance_action():
    ui = (ROOT / "ui.py").read_text(encoding="utf-8")
    actions = (ROOT / "ui_actions_mixin.py").read_text(encoding="utf-8")
    assert 'self.btn_settings.setText("⚙")' in ui
    assert 'self.btn_settings.setToolTip("Settings")' in ui
    assert "self.btn_settings.clicked.connect(self.show_settings)" in ui
    assert 'addAction("Appearance...")' not in ui
    assert "SettingsDialog" in actions
    assert "apply_ui_configuration_live" in actions


def test_first_dialogs_use_shared_metrics():
    actions = (ROOT / "ui_actions_mixin.py").read_text(encoding="utf-8")
    metadata = (ROOT / "widgets" / "metadata_dialog.py").read_text(encoding="utf-8")
    assert "apply_dialog_metrics(layout, compact=True)" in actions
    assert "apply_control_metrics(dlg)" in actions
    assert "apply_dialog_metrics(root)" in metadata
    assert "apply_control_metrics(self)" in metadata


def test_appearance_updates_existing_gui_immediately_and_uniformly():
    style = (ROOT / "ui_style.py").read_text(encoding="utf-8")
    actions = (ROOT / "ui_actions_mixin.py").read_text(encoding="utf-8")
    dialog = (ROOT / "widgets" / "appearance_settings_dialog.py").read_text(encoding="utf-8")
    assert "def apply_ui_configuration_live" in style
    assert "def refresh_existing_widgets" in style
    assert 'QWidget {{ {font_rule} }}' in style
    assert "_BASE_APPLICATION_FONT" in style
    assert "apply_ui_configuration_live(dlg.configuration())" in actions
    assert "SettingsDialog" in dialog
    assert "next time FlexPES" not in dialog


def test_main_layouts_participate_in_live_density_refresh():
    ui = (ROOT / "ui.py").read_text(encoding="utf-8")
    raw = (ROOT / "ui_raw_data_mixin.py").read_text(encoding="utf-8")
    processed = (ROOT / "ui_processed_data_mixin.py").read_text(encoding="utf-8")
    assert 'register_layout_role(root_layout, "panel")' in ui
    assert 'register_widget_role(self.tree, "loaded_tree")' in ui
    assert 'register_widget_role(self.selected_tree, "selected_tree")' in ui
    assert 'register_layout_role(raw_top, "strip")' in raw
    assert 'register_layout_role(raw_bottom, "strip")' in raw
    assert 'register_layout_role(proc_top, "strip")' in processed
    assert 'register_layout_role(calibration_layout, "group")' in processed
