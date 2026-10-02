from pathlib import Path

from maxiv_panda.session_io import load_session_file, make_manifest, save_session_file


ROOT = Path(__file__).resolve().parents[1]
UI_ACTIONS = ROOT / "src" / "maxiv_panda" / "ui_actions_mixin.py"


def test_session_manifest_roundtrip_preserves_signal_identification_state(tmp_path):
    state = {
        "checked": True,
        "show_auger": False,
        "spectrum_key": "survey-key",
        "settings": {
            "photon_energy": 1000.0,
            "tolerance_eV": 4.0,
            "prominence_fraction": 0.006,
            "include_auger": True,
            "include_second_order": True,
            "small_charging_possible": True,
            "elements": ["Au", "C", "O"],
            "sample_mode": "Automatic (prefer solids)",
            "valence_band_cutoff_eV": 12.0,
        },
    }
    manifest = make_manifest(panda_version="0.12.1", sources=[], signal_identification_state=state)
    path = tmp_path / "signal_state.panda"
    save_session_file(path, manifest)
    restored = load_session_file(path)
    assert restored.signal_identification_state == state


def test_older_session_without_signal_state_remains_compatible(tmp_path):
    manifest = make_manifest(panda_version="0.12.1", sources=[])
    path = tmp_path / "old_style.panda"
    save_session_file(path, manifest)
    restored = load_session_file(path)
    assert restored.signal_identification_state == {}


def test_clear_all_rebuilds_all_in_region_selector():
    source = UI_ACTIONS.read_text(encoding="utf-8")
    clear_all = source[source.index("    def clear_all("):source.index("    def _session_sources(")]
    assert '_refresh_all_region_combo' in clear_all
    assert 'refresh_regions()' in clear_all


def test_session_dialogs_persist_session_directory_across_restarts():
    source = UI_ACTIONS.read_text(encoding="utf-8")
    save = source[source.index("    def _save_session("):source.index("    def _source_snapshot_from_session(")]
    open_ = source[source.index("    def _open_session("):source.index("    def _load_file(")]
    helpers = source[source.index("    _SESSION_DIRECTORY_SETTINGS_KEY"):source.index("    def _update_load_menu_state(")]
    assert 'QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)' in helpers
    assert 'files/last_session_directory' in helpers
    assert 'start_dir = str(self._remembered_session_directory())' in save
    assert 'self._set_session_directory(target.parent)' in save
    assert 'start_dir = str(self._remembered_session_directory())' in open_
    assert 'self._set_session_directory(session_path.parent)' in open_


def test_session_restore_separates_selected_membership_from_plot_visibility():
    source = UI_ACTIONS.read_text(encoding="utf-8")
    restore = source[source.index("    def _restore_processed_workspace("):source.index("    def _open_session(")]
    assert 'Qt.CheckState.Checked if entry is not None else Qt.CheckState.Unchecked' in restore
    assert 'item.setCheckState(' in restore
    assert 'Qt.CheckState.Checked if entry.checked else Qt.CheckState.Unchecked' in restore
    # Hidden members must not be re-added outside the restored All-in-region group.
    assert 'all_in_region_enabled=False, target_region=""' not in restore.split('required_source_keys', 1)[0]


def test_signal_identification_is_captured_and_restored_by_session_actions():
    source = UI_ACTIONS.read_text(encoding="utf-8")
    assert "def _session_signal_identification_state" in source
    assert "def _restore_signal_identification_state" in source
    save = source[source.index("    def _save_session("):source.index("    def _source_snapshot_from_session(")]
    open_ = source[source.index("    def _open_session("):source.index("    def _load_file(")]
    assert "signal_identification_state=self._session_signal_identification_state()" in save
    assert "problems.extend(self._restore_signal_identification_state(manifest))" in open_
