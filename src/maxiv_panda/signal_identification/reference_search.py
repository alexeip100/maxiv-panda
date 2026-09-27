from __future__ import annotations

from dataclasses import dataclass

from .auger_energies import AugerEnergyEntry, all_auger_energy_entries
from .binding_energies import BindingEnergyEntry, all_binding_energy_entries


@dataclass(frozen=True)
class XPSReferenceCandidate:
    kind: str  # "core" or "auger"
    entry: BindingEnergyEntry | AugerEnergyEntry
    be_min_eV: float
    be_max_eV: float

    @property
    def be_text(self) -> str:
        if abs(self.be_max_eV - self.be_min_eV) < 1e-9:
            return f"{0.5 * (self.be_min_eV + self.be_max_eV):.1f}"
        return f"{self.be_min_eV:.1f}–{self.be_max_eV:.1f}"

    @property
    def representative_be_eV(self) -> float:
        return 0.5 * (self.be_min_eV + self.be_max_eV)


def auger_ke_to_apparent_be_interval(
    energy_min_eV: float,
    energy_max_eV: float,
    photon_energy_eV: float,
) -> tuple[float, float]:
    """Convert an Auger KE interval to its apparent position on a BE axis.

    PANDA already uses BE = hν - KE for internal PE/Auger consistency.
    Reversing the endpoints preserves ascending interval order.
    """
    lo = float(photon_energy_eV) - float(energy_max_eV)
    hi = float(photon_energy_eV) - float(energy_min_eV)
    return (min(lo, hi), max(lo, hi))


def _overlaps(lo: float, hi: float, roi_lo: float, roi_hi: float) -> bool:
    return hi >= roi_lo and lo <= roi_hi


def candidates_in_be_region(
    be_min_eV: float,
    be_max_eV: float,
    photon_energy_eV: float | None = None,
    *,
    include_auger: bool = False,
) -> tuple[XPSReferenceCandidate, ...]:
    """Return core-level candidates, optionally including Auger families, in a BE region."""
    roi_lo, roi_hi = sorted((float(be_min_eV), float(be_max_eV)))
    photon = None if photon_energy_eV is None else float(photon_energy_eV)
    rows: list[XPSReferenceCandidate] = []

    for entry in all_binding_energy_entries():
        lo, hi = float(entry.energy_min_eV), float(entry.energy_max_eV)
        if _overlaps(lo, hi, roi_lo, roi_hi):
            rows.append(XPSReferenceCandidate("core", entry, lo, hi))

    if include_auger:
        if photon is None or photon <= 0:
            raise ValueError("Photon energy must be positive when Auger candidates are included.")
        for entry in all_auger_energy_entries():
            lo, hi = auger_ke_to_apparent_be_interval(
                entry.energy_min_eV, entry.energy_max_eV, photon
            )
            if _overlaps(lo, hi, roi_lo, roi_hi):
                rows.append(XPSReferenceCandidate("auger", entry, lo, hi))

    return tuple(sorted(
        rows,
        key=lambda row: (
            row.representative_be_eV,
            0 if row.kind == "core" else 1,
            row.entry.z,
            getattr(row.entry, "transition", getattr(row.entry, "family", "")),
        ),
    ))
