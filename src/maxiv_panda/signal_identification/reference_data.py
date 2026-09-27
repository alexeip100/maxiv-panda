from __future__ import annotations

from functools import lru_cache
import json
from importlib.resources import files
from typing import Any


def _load_json(name: str) -> dict[str, Any]:
    path = files("maxiv_panda").joinpath("data", "signal_references", name)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def core_level_records() -> tuple[dict[str, Any], ...]:
    return tuple(_load_json("core_levels.json").get("records", []))


@lru_cache(maxsize=1)
def auger_handbook_records() -> tuple[dict[str, Any], ...]:
    return tuple(_load_json("auger_lines_xps_international_handbook.json").get("records", []))


@lru_cache(maxsize=1)
def auger_eadl_records() -> tuple[dict[str, Any], ...]:
    return tuple(_load_json("auger_lines_eadl.json").get("records", []))


@lru_cache(maxsize=1)
def auger_records() -> tuple[dict[str, Any], ...]:
    """Primary handbook records plus conservative EADL supplements.

    EADL clusters are added only when their representative energy is not already
    covered within 6 eV by a handbook record for the same element/family.
    Source records remain separate on disk and retain provenance in memory.
    """
    primary = list(auger_handbook_records())
    by_family: dict[tuple[str, str], list[float]] = {}
    for record in primary:
        key = (str(record.get("element", "")), str(record.get("family", "Auger")))
        try:
            by_family.setdefault(key, []).append(float(record["kinetic_energy_eV"]))
        except Exception:
            continue
    supplements: list[dict[str, Any]] = []
    for record in auger_eadl_records():
        key = (str(record.get("element", "")), str(record.get("family", "Auger")))
        try:
            energy = float(record["kinetic_energy_eV"])
        except Exception:
            continue
        existing = by_family.get(key, [])
        lo = float(record.get("kinetic_energy_min_eV", energy))
        hi = float(record.get("kinetic_energy_max_eV", energy))
        if existing and any((lo - 6.0) <= value <= (hi + 6.0) for value in existing):
            continue
        supplements.append(record)
    return tuple(primary + supplements)


@lru_cache(maxsize=1)
def element_symbols() -> tuple[str, ...]:
    records = core_level_records()
    by_z: dict[int, str] = {}
    for record in records:
        try:
            by_z[int(record["Z"])] = str(record["element"])
        except Exception:
            continue
    return tuple(by_z[z] for z in sorted(by_z))
