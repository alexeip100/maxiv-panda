from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from .reference_data import auger_records


@dataclass(frozen=True)
class AugerEnergyEntry:
    element: str
    z: int
    family: str
    energy_min_eV: float
    energy_max_eV: float
    representative_energy_eV: float
    environment: str
    source: str

    @property
    def energy_text(self) -> str:
        if abs(self.energy_max_eV - self.energy_min_eV) < 1e-9:
            return f"{self.representative_energy_eV:.1f}"
        return f"{self.energy_min_eV:.1f}–{self.energy_max_eV:.1f}"

    def distance_from(self, energy_eV: float) -> float:
        if self.energy_min_eV <= energy_eV <= self.energy_max_eV:
            return 0.0
        return min(abs(energy_eV - self.energy_min_eV), abs(energy_eV - self.energy_max_eV))


def _source_kind(record: dict) -> str:
    source = str(record.get("source", ""))
    return "handbook" if "Handbook" in source else "eadl"


def _raw_entries() -> list[AugerEnergyEntry]:
    records = list(auger_records())
    grouped_handbook: dict[tuple[str, int, str], list[dict]] = defaultdict(list)
    eadl: list[dict] = []
    for record in records:
        try:
            key = (str(record["element"]), int(record["Z"]), str(record.get("family", "Auger")))
            if _source_kind(record) == "handbook":
                grouped_handbook[key].append(record)
            else:
                eadl.append(record)
        except (KeyError, TypeError, ValueError):
            continue

    entries: list[AugerEnergyEntry] = []
    # The handbook often lists several experimental positions for one broad
    # Auger family.  Present them as one simple family region for reference use.
    for (element, z, family), items in grouped_handbook.items():
        energies = sorted(float(item["kinetic_energy_eV"]) for item in items)
        entries.append(AugerEnergyEntry(
            element=element,
            z=z,
            family=family,
            energy_min_eV=min(energies),
            energy_max_eV=max(energies),
            representative_energy_eV=sum(energies) / len(energies),
            environment="experimental family region",
            source="XPS International Handbook lookup table",
        ))

    # EADL records are already clustered atomic-relaxation regions.  Keep each
    # cluster as one interval rather than exposing individual multiplet lines.
    for record in eadl:
        try:
            center = float(record["kinetic_energy_eV"])
            lo = float(record.get("kinetic_energy_min_eV", center))
            hi = float(record.get("kinetic_energy_max_eV", center))
            entries.append(AugerEnergyEntry(
                element=str(record["element"]),
                z=int(record["Z"]),
                family=str(record.get("family", "Auger")),
                energy_min_eV=min(lo, hi),
                energy_max_eV=max(lo, hi),
                representative_energy_eV=center,
                environment="theoretical atomic-relaxation region",
                source="EADL 2025",
            ))
        except (KeyError, TypeError, ValueError):
            continue
    return entries


def all_auger_energy_entries() -> tuple[AugerEnergyEntry, ...]:
    return tuple(sorted(_raw_entries(), key=lambda e: (e.z, e.family, e.energy_min_eV, e.source)))


def available_auger_families(elements: Iterable[str]) -> tuple[str, ...]:
    chosen = set(elements)
    return tuple(sorted({e.family for e in all_auger_energy_entries() if e.element in chosen}))


def auger_entries_for_selection(elements: Iterable[str], families: Iterable[str] = ()) -> tuple[AugerEnergyEntry, ...]:
    chosen_elements, chosen_families = set(elements), set(families)
    rows = [e for e in all_auger_energy_entries()
            if e.element in chosen_elements and (not chosen_families or e.family in chosen_families)]
    return tuple(rows)


def auger_candidates_near_energy(energy_eV: float, tolerance_eV: float) -> tuple[tuple[AugerEnergyEntry, float], ...]:
    rows = [(e, e.distance_from(energy_eV)) for e in all_auger_energy_entries()]
    rows = [(e, d) for e, d in rows if d <= tolerance_eV]
    return tuple(sorted(rows, key=lambda pair: (pair[1], pair[0].z, pair[0].family, pair[0].energy_min_eV)))
