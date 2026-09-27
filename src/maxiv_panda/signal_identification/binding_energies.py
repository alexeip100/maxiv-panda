from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .reference_data import core_level_records


@dataclass(frozen=True)
class BindingEnergyEntry:
    element: str
    z: int
    transition: str
    energy_min_eV: float
    energy_max_eV: float
    representative_energy_eV: float
    environment: str
    phase: str
    category: str
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


def _entry(record: dict) -> BindingEnergyEntry | None:
    try:
        return BindingEnergyEntry(
            element=str(record["element"]), z=int(record["Z"]),
            transition=str(record["transition"]),
            energy_min_eV=float(record["energy_min_eV"]),
            energy_max_eV=float(record["energy_max_eV"]),
            representative_energy_eV=float(record["representative_energy_eV"]),
            environment=str(record.get("environment", "")),
            phase=str(record.get("phase", "")),
            category=str(record.get("category", "")),
            source=str(record.get("source", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def all_binding_energy_entries() -> tuple[BindingEnergyEntry, ...]:
    return tuple(item for record in core_level_records() if (item := _entry(record)) is not None)


def available_binding_elements() -> tuple[str, ...]:
    by_z = {entry.z: entry.element for entry in all_binding_energy_entries()}
    return tuple(by_z[z] for z in sorted(by_z))


def available_binding_shells(elements: Iterable[str]) -> tuple[str, ...]:
    chosen = set(elements)
    shells = {e.transition for e in all_binding_energy_entries() if e.element in chosen}
    def key(shell: str):
        import re
        m = re.match(r"(\d+)([spdf])(.*)", shell)
        return (int(m.group(1)), "spdf".find(m.group(2)), m.group(3)) if m else (99, 99, shell)
    return tuple(sorted(shells, key=key))


def entries_for_selection(elements: Iterable[str], shells: Iterable[str] = ()) -> tuple[BindingEnergyEntry, ...]:
    chosen_elements, chosen_shells = set(elements), set(shells)
    rows = [e for e in all_binding_energy_entries()
            if e.element in chosen_elements and (not chosen_shells or e.transition in chosen_shells)]
    return tuple(sorted(rows, key=lambda e: (e.z, e.representative_energy_eV, e.transition, e.environment)))


def candidates_near_energy(energy_eV: float, tolerance_eV: float) -> tuple[tuple[BindingEnergyEntry, float], ...]:
    rows = [(e, e.distance_from(energy_eV)) for e in all_binding_energy_entries()]
    rows = [(e, d) for e, d in rows if d <= tolerance_eV]
    return tuple(sorted(rows, key=lambda pair: (pair[1], pair[0].z, pair[0].transition, pair[0].environment)))
