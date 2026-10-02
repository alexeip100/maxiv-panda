from __future__ import annotations

import json
from pathlib import Path
import zipfile

import pytest

from maxiv_panda.session_io import (
    MANIFEST_NAME,
    SESSION_FORMAT,
    SESSION_SCHEMA_VERSION,
    SessionSource,
    load_session_file,
    make_manifest,
    save_session_file,
)


def _source() -> SessionSource:
    return SessionSource(
        kind="XY",
        snapshot_id="src_keep_me",
        canonical_path="c:/data/example.xy",
        physical_path="C:/Data/example.xy",
        file_name="example.xy",
        source_label="example.xy [updated]",
        loaded_at="2026-10-01T21:00:00",
        file_mtime_ns=123456789,
        file_size=98765,
    )


def test_session_archive_round_trip_preserves_source_identity(tmp_path: Path):
    target = tmp_path / "work.panda"
    manifest = make_manifest(panda_version="0.12.1", sources=[_source()])
    save_session_file(target, manifest)

    assert zipfile.is_zipfile(target)
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == [MANIFEST_NAME]
        payload = json.loads(archive.read(MANIFEST_NAME))
    assert payload["format"] == SESSION_FORMAT
    assert payload["schema_version"] == SESSION_SCHEMA_VERSION

    loaded = load_session_file(target)
    assert loaded.panda_version == "0.12.1"
    assert loaded.sources == (_source(),)
    assert loaded.sources[0].snapshot_id == "src_keep_me"


def test_empty_session_is_valid(tmp_path: Path):
    target = tmp_path / "empty.panda"
    save_session_file(target, make_manifest(panda_version="0.12.1", sources=[]))
    assert load_session_file(target).sources == ()


def test_rejects_non_session_zip(tmp_path: Path):
    target = tmp_path / "bad.panda"
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("other.json", "{}")
    with pytest.raises(ValueError, match="session.json"):
        load_session_file(target)


def test_rejects_wrong_schema(tmp_path: Path):
    target = tmp_path / "future.panda"
    payload = {
        "format": SESSION_FORMAT,
        "schema_version": SESSION_SCHEMA_VERSION + 1,
        "panda_version": "9.9.9",
        "created_at": "now",
        "sources": [],
    }
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr(MANIFEST_NAME, json.dumps(payload))
    with pytest.raises(ValueError, match="schema"):
        load_session_file(target)
