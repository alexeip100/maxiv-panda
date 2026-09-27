"""Public Yeh-Lindau core-level cross-section access.

The API intentionally exposes complete tabulated curves as well as scalar
interpolation.  The identification code uses scalar values today; a future GUI
can plot the same curves without reading HDF5 internals directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import re

import h5py
import numpy as np


@dataclass(frozen=True)
class CrossSectionCurve:
    element: str
    subshell: str
    photon_energy_eV: np.ndarray
    cross_section_mb: np.ndarray
    asymmetry_beta: np.ndarray


def _normalise_subshell(subshell: str) -> str:
    text = str(subshell).strip().replace(" ", "")
    text = re.sub(r"([spdf])([1357])/2$", r"\1\2_2", text)
    text = text.replace("/", "_")
    return text


def _display_subshell(key: str) -> str:
    return re.sub(r"([spdf])([1357])_2$", r"\1\2/2", str(key))


def _database_path():
    return files("maxiv_panda.data").joinpath("core_levels_cross_sections.h5")


@lru_cache(maxsize=1)
def available_elements() -> tuple[str, ...]:
    with h5py.File(_database_path(), "r") as handle:
        return tuple(sorted(str(key) for key in handle.keys()))


@lru_cache(maxsize=256)
def available_subshells(element: str) -> tuple[str, ...]:
    with h5py.File(_database_path(), "r") as handle:
        if element not in handle:
            return ()
        return tuple(
            _display_subshell(key) for key in sorted(handle[element].keys())
            if key != "Z_value" and isinstance(handle[element][key], h5py.Group)
        )


@lru_cache(maxsize=1024)
def get_cross_section_curve(element: str, subshell: str) -> CrossSectionCurve | None:
    key = _normalise_subshell(subshell)
    with h5py.File(_database_path(), "r") as handle:
        if element not in handle or key not in handle[element]:
            return None
        group = handle[element][key]
        energy = np.asarray(group.get("energy", ()), dtype=float).reshape(-1)
        cross = np.asarray(group.get("cross_section", ()), dtype=float).reshape(-1)
        beta = np.asarray(group.get("asymmetry", ()), dtype=float).reshape(-1)
    valid = np.isfinite(energy) & np.isfinite(cross) & (energy > 0.0) & (cross > 0.0)
    energy, cross = energy[valid], cross[valid]
    if beta.size == valid.size:
        beta = beta[valid]
    else:
        beta = np.full(energy.shape, np.nan)
    if energy.size == 0:
        return None
    order = np.argsort(energy)
    energy, cross, beta = energy[order], cross[order], beta[order]
    # Arrays are read-only so cached curves cannot be mutated by callers.
    for array in (energy, cross, beta):
        array.setflags(write=False)
    return CrossSectionCurve(element, _display_subshell(key), energy, cross, beta)


def cross_section_at(element: str, subshell: str, photon_energy_eV: float) -> float | None:
    curve = get_cross_section_curve(element, subshell)
    if curve is None:
        return None
    energy = float(photon_energy_eV)
    x = curve.photon_energy_eV
    y = curve.cross_section_mb
    if not np.isfinite(energy) or energy < float(x[0]) or energy > float(x[-1]):
        return None
    return float(np.exp(np.interp(np.log(energy), np.log(x), np.log(y))))


def family_cross_section_at(element: str, family: str, photon_energy_eV: float) -> float | None:
    base = re.sub(r"([spdf])[1357]/2$", r"\1", str(family).strip())
    values = []
    for subshell in available_subshells(element):
        if re.sub(r"([spdf])[1357]/2$", r"\1", subshell) != base:
            continue
        value = cross_section_at(element, subshell, photon_energy_eV)
        if value is not None:
            values.append(value)
    return float(sum(values)) if values else None


@dataclass(frozen=True)
class AngularCrossSectionCurve:
    element: str
    subshell: str
    angle_deg: float
    photon_energy_eV: np.ndarray
    cross_section_mb: np.ndarray


def asymmetry_at(element: str, subshell: str, photon_energy_eV: float) -> float | None:
    """Interpolate the Yeh–Lindau asymmetry parameter at one photon energy."""
    curve = get_cross_section_curve(element, subshell)
    if curve is None:
        return None
    energy = float(photon_energy_eV)
    x = curve.photon_energy_eV
    beta = curve.asymmetry_beta
    valid = np.isfinite(x) & np.isfinite(beta)
    if np.count_nonzero(valid) < 2:
        return None
    xv = x[valid]
    bv = beta[valid]
    if not np.isfinite(energy) or energy < float(xv[0]) or energy > float(xv[-1]):
        return None
    return float(np.interp(np.log(energy), np.log(xv), bv))


def angular_factor(beta: float, angle_deg: float) -> float:
    """Return the linearly-polarized dipole angular factor.

    The factor omits the common 1/(4π) term so the geometry-weighted values
    retain Mbarn units and remain directly comparable with tabulated σ values.
    """
    theta = np.deg2rad(float(angle_deg))
    return float(1.0 + 0.5 * float(beta) * (3.0 * np.cos(theta) ** 2 - 1.0))


def angular_cross_section_at(
    element: str, subshell: str, photon_energy_eV: float, angle_deg: float
) -> float | None:
    total = cross_section_at(element, subshell, photon_energy_eV)
    beta = asymmetry_at(element, subshell, photon_energy_eV)
    if total is None or beta is None:
        return None
    return float(total * angular_factor(beta, angle_deg))


def angular_cross_section_curve(
    element: str, subshell: str, angle_deg: float
) -> AngularCrossSectionCurve | None:
    """Return a geometry-weighted curve suitable for plotting in a GUI."""
    curve = get_cross_section_curve(element, subshell)
    if curve is None:
        return None
    beta = curve.asymmetry_beta
    valid = np.isfinite(beta)
    if not np.any(valid):
        return None
    theta = np.deg2rad(float(angle_deg))
    factors = 1.0 + 0.5 * beta * (3.0 * np.cos(theta) ** 2 - 1.0)
    values = np.asarray(curve.cross_section_mb * factors, dtype=float)
    valid = np.isfinite(values) & (values > 0.0)
    if not np.any(valid):
        return None
    energy = np.asarray(curve.photon_energy_eV[valid], dtype=float)
    values = np.asarray(values[valid], dtype=float)
    energy.setflags(write=False)
    values.setflags(write=False)
    return AngularCrossSectionCurve(
        element=curve.element,
        subshell=curve.subshell,
        angle_deg=float(angle_deg),
        photon_energy_eV=energy,
        cross_section_mb=values,
    )
