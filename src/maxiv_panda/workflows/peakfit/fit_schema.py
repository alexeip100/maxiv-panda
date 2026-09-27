"""Versioned schema handling for PANDA peak-fit setup JSON files.

The persisted fit-setup schema is currently version 1.  This module owns the
version contract and migration path so future schema changes can be introduced
without scattering compatibility logic across the GUI or fit engine.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

FORMAT_NAME = "flexpes_pes_fit_setup"
CURRENT_FORMAT_VERSION = 1
MIN_SUPPORTED_FORMAT_VERSION = 1


class FitSetupSchemaError(ValueError):
    """Raised when a fit-setup JSON envelope/version cannot be supported."""


Migration = Callable[[dict[str, Any]], dict[str, Any]]
_MIGRATIONS: dict[int, Migration] = {}


def _coerce_version(value: Any) -> int:
    try:
        version = int(value)
    except (TypeError, ValueError) as exc:
        raise FitSetupSchemaError("Fit setup file has an invalid format_version.") from exc
    if version < 1:
        raise FitSetupSchemaError("Fit setup file has an invalid format_version.")
    return version


def canonicalize_fit_setup_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Return a canonical current-version fit-setup envelope.

    Wrapped PANDA files are validated by format/version and migrated one schema
    version at a time when required.  Historical development files containing a
    raw fit-setup dictionary are accepted as implicit v1 input and wrapped only
    internally; this does not alter the file on disk.
    """
    if not isinstance(data, Mapping):
        raise FitSetupSchemaError("Fit setup file does not contain a JSON object.")

    if data.get("format") == FORMAT_NAME:
        payload = deepcopy(dict(data))
        version = _coerce_version(payload.get("format_version"))
    elif "peak_states" in data or "bg_state" in data or "so_doublets" in data:
        payload = {
            "format": FORMAT_NAME,
            "format_version": 1,
            "metadata": {},
            "fit_setup": deepcopy(dict(data)),
        }
        version = 1
    else:
        raise FitSetupSchemaError("This file does not look like a PANDA fit setup JSON file.")

    if version > CURRENT_FORMAT_VERSION:
        raise FitSetupSchemaError(
            f"This fit setup uses format version {version}, but this PANDA release supports "
            f"up to version {CURRENT_FORMAT_VERSION}. Please open it with a newer PANDA release."
        )
    if version < MIN_SUPPORTED_FORMAT_VERSION:
        raise FitSetupSchemaError(
            f"Fit setup format version {version} is no longer supported by this PANDA release."
        )

    while version < CURRENT_FORMAT_VERSION:
        migrate = _MIGRATIONS.get(version)
        if migrate is None:
            raise FitSetupSchemaError(
                f"No migration is available from fit setup format version {version}."
            )
        payload = migrate(payload)
        next_version = _coerce_version(payload.get("format_version"))
        if next_version != version + 1:
            raise FitSetupSchemaError(
                f"Invalid fit setup migration {version} -> {next_version}; migrations must advance one version."
            )
        version = next_version

    setup = payload.get("fit_setup")
    if not isinstance(setup, Mapping):
        raise FitSetupSchemaError("The fit_setup section is missing or malformed.")
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        metadata = {}

    payload["format"] = FORMAT_NAME
    payload["format_version"] = CURRENT_FORMAT_VERSION
    payload["fit_setup"] = deepcopy(dict(setup))
    payload["metadata"] = deepcopy(dict(metadata))
    return payload
