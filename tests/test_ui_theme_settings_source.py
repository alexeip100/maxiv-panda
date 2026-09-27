from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "maxiv_panda"


def test_theme_is_persisted_and_applied_live():
    style = (ROOT / "ui_style.py").read_text(encoding="utf-8")
    dialog = (ROOT / "widgets" / "appearance_settings_dialog.py").read_text(encoding="utf-8")
    assert 'class UiTheme(str, Enum)' in style
    assert 'settings.setValue("theme", theme.value)' in style
    assert '_apply_theme_palette(app, config.theme)' in style
    assert 'app.setProperty("flexpes_ui_theme", config.theme.value)' in style
    assert 'self.theme_combo.addItem("System", UiTheme.SYSTEM.value)' in dialog
    assert 'self.theme_combo.addItem("Light", UiTheme.LIGHT.value)' in dialog
    assert 'self.theme_combo.addItem("Dark", UiTheme.DARK.value)' in dialog


def test_settings_dialog_is_intentionally_compact():
    dialog = (ROOT / "widgets" / "appearance_settings_dialog.py").read_text(encoding="utf-8")
    assert 'QGroupBox("Appearance"' in dialog
    assert 'Adjust interface density and text size coherently' not in dialog
    assert 'Changes are applied immediately' not in dialog
