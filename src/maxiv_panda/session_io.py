from __future__ import annotations

"""PANDA session container support.

A ``.panda`` file is a ZIP container with a JSON manifest and, from build 3,
compressed NumPy arrays for persistent Processed Data curves.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path
from typing import Any
import zipfile

import numpy as np

SESSION_FORMAT = "maxiv_panda_session"
SESSION_SCHEMA_VERSION = 1
MANIFEST_NAME = "session.json"


def json_safe(value: Any) -> Any:
    """Return a JSON-safe representation for ordinary PANDA metadata."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


@dataclass(frozen=True)
class SessionSource:
    kind: str
    snapshot_id: str
    canonical_path: str
    physical_path: str
    file_name: str
    source_label: str
    loaded_at: str
    file_mtime_ns: int | None = None
    file_size: int | None = None


@dataclass(frozen=True)
class SessionSelection:
    key: str
    checked: bool = True


@dataclass(frozen=True)
class SessionProcessedCurve:
    key: str
    display: str
    parent_file: str
    source_file: str
    region_name: str
    array_member: str
    title: str
    xlabel: str
    ylabel: str
    energy_scale: str
    metadata: dict[str, Any] = field(default_factory=dict)
    item_meta: dict[str, Any] = field(default_factory=dict)
    checked: bool = True


@dataclass(frozen=True)
class SessionManifest:
    format: str
    schema_version: int
    panda_version: str
    created_at: str
    sources: tuple[SessionSource, ...]
    selected_raw: tuple[SessionSelection, ...] = ()
    processed_curves: tuple[SessionProcessedCurve, ...] = ()
    processed_view: dict[str, Any] = field(default_factory=dict)
    fitting_state: dict[str, Any] = field(default_factory=dict)
    plotted_state: dict[str, Any] = field(default_factory=dict)
    workspace_state: dict[str, Any] = field(default_factory=dict)
    signal_identification_state: dict[str, Any] = field(default_factory=dict)


def make_manifest(*, panda_version: str, sources: list[SessionSource],
                  selected_raw: list[SessionSelection] | None = None,
                  processed_curves: list[SessionProcessedCurve] | None = None,
                  processed_view: dict[str, Any] | None = None,
                  fitting_state: dict[str, Any] | None = None,
                  plotted_state: dict[str, Any] | None = None,
                  workspace_state: dict[str, Any] | None = None,
                  signal_identification_state: dict[str, Any] | None = None) -> SessionManifest:
    return SessionManifest(
        format=SESSION_FORMAT,
        schema_version=SESSION_SCHEMA_VERSION,
        panda_version=str(panda_version),
        created_at=datetime.now().isoformat(timespec="seconds"),
        sources=tuple(sources),
        selected_raw=tuple(selected_raw or ()),
        processed_curves=tuple(processed_curves or ()),
        processed_view=json_safe(processed_view or {}),
        fitting_state=json_safe(fitting_state or {}),
        plotted_state=json_safe(plotted_state or {}),
        workspace_state=json_safe(workspace_state or {}),
        signal_identification_state=json_safe(signal_identification_state or {}),
    )


def save_session_file(path: str | Path, manifest: SessionManifest,
                      processed_arrays: dict[str, tuple[Any, Any]] | None = None) -> None:
    target = Path(path)
    payload = json_safe(asdict(manifest))
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(MANIFEST_NAME, text)
        for member, (x, y) in (processed_arrays or {}).items():
            buffer = BytesIO()
            np.savez_compressed(buffer, x=np.asarray(x), y=np.asarray(y))
            archive.writestr(str(member), buffer.getvalue())


def _parse_manifest(payload: dict[str, Any]) -> SessionManifest:
    if payload.get("format") != SESSION_FORMAT:
        raise ValueError("Unsupported session format")
    schema = int(payload.get("schema_version", 0))
    if schema != SESSION_SCHEMA_VERSION:
        raise ValueError(f"Unsupported PANDA session schema {schema}; expected {SESSION_SCHEMA_VERSION}")

    sources = [SessionSource(**{k: entry.get(k) for k in SessionSource.__dataclass_fields__})
               for entry in payload.get("sources", []) if isinstance(entry, dict)]
    selected_raw = [SessionSelection(key=str(entry.get("key") or ""), checked=bool(entry.get("checked", True)))
                    for entry in payload.get("selected_raw", []) if isinstance(entry, dict)]
    processed = []
    for entry in payload.get("processed_curves", []):
        if not isinstance(entry, dict):
            continue
        processed.append(SessionProcessedCurve(
            key=str(entry.get("key") or ""), display=str(entry.get("display") or ""),
            parent_file=str(entry.get("parent_file") or ""), source_file=str(entry.get("source_file") or ""),
            region_name=str(entry.get("region_name") or ""), array_member=str(entry.get("array_member") or ""),
            title=str(entry.get("title") or ""), xlabel=str(entry.get("xlabel") or "x"),
            ylabel=str(entry.get("ylabel") or "Intensity"), energy_scale=str(entry.get("energy_scale") or "Unknown"),
            metadata=dict(entry.get("metadata") or {}), item_meta=dict(entry.get("item_meta") or {}),
            checked=bool(entry.get("checked", True)),
        ))
    return SessionManifest(
        format=SESSION_FORMAT, schema_version=schema,
        panda_version=str(payload.get("panda_version") or ""), created_at=str(payload.get("created_at") or ""),
        sources=tuple(sources), selected_raw=tuple(selected_raw), processed_curves=tuple(processed),
        processed_view=dict(payload.get("processed_view") or {}),
        fitting_state=dict(payload.get("fitting_state") or {}),
        plotted_state=dict(payload.get("plotted_state") or {}),
        workspace_state=dict(payload.get("workspace_state") or {}),
        signal_identification_state=dict(payload.get("signal_identification_state") or {}),
    )


def load_session_file(path: str | Path) -> SessionManifest:
    try:
        with zipfile.ZipFile(Path(path), "r") as archive:
            raw = archive.read(MANIFEST_NAME)
    except KeyError as exc:
        raise ValueError(f"Session archive does not contain {MANIFEST_NAME}") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError("Not a valid PANDA session archive") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Session manifest is not valid UTF-8 JSON") from exc
    return _parse_manifest(payload)


def load_array_pair(path: str | Path, member: str) -> tuple[np.ndarray, np.ndarray]:
    """Load one x/y NPZ member from a PANDA session archive."""
    with zipfile.ZipFile(Path(path), "r") as archive:
        try:
            raw = archive.read(str(member))
        except KeyError as exc:
            raise ValueError(f"Session is missing array member {member}") from exc
    with np.load(BytesIO(raw), allow_pickle=False) as data:
        return np.asarray(data["x"]), np.asarray(data["y"])


def load_processed_arrays(path: str | Path, manifest: SessionManifest) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    arrays: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    with zipfile.ZipFile(Path(path), "r") as archive:
        for curve in manifest.processed_curves:
            if not curve.array_member:
                continue
            try:
                raw = archive.read(curve.array_member)
                with np.load(BytesIO(raw), allow_pickle=False) as data:
                    arrays[curve.key] = (np.asarray(data["x"]), np.asarray(data["y"]))
            except KeyError as exc:
                raise ValueError(f"Session is missing processed data for {curve.display or curve.key}") from exc
    return arrays
