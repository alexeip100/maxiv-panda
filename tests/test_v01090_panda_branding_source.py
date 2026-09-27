from pathlib import Path


def test_visible_application_branding_is_panda():
    root = Path(__file__).resolve().parents[1]
    ui = (root / "src" / "maxiv_panda" / "ui.py").read_text(encoding="utf-8")
    actions = (root / "src" / "maxiv_panda" / "ui_actions_mixin.py").read_text(encoding="utf-8")
    icon = (root / "src" / "maxiv_panda" / "icon.py").read_text(encoding="utf-8")
    assert 'self.setWindowTitle("PANDA")' in ui
    assert 'msg.setWindowTitle("About PANDA")' in actions
    assert 'Photoemission Analysis, Normalization and Data Assessment' in actions
    assert 'It was developed at the FlexPES beamline at ' in actions
    assert 'MAX IV Laboratory.' in actions
    assert '("setApplicationName", "PANDA")' in icon
    assert '("setApplicationDisplayName", "PANDA")' in icon


def test_qsettings_storage_identity_is_preserved_for_existing_preferences():
    root = Path(__file__).resolve().parents[1]
    style = (root / "src" / "maxiv_panda" / "ui_style.py").read_text(encoding="utf-8")
    assert 'SETTINGS_APPLICATION = "FlexPES PES Processor"' in style
