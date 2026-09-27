"""Typed internal state models for PANDA peak fitting.

The GUI and fitting engine still exchange plain dictionaries at their public
boundaries.  These dataclasses provide one place to normalize, validate and
round-trip those dictionaries without changing the on-disk ``.fit.json``
schema used by existing PANDA releases.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

PEAK_PARAMETERS = ("E", "H", "L", "G", "A")

# Defaults mirror the peak editor's initial state.  They are used only when a
# field is absent; existing values from saved/captured states are preserved.
_PEAK_DEFAULTS: dict[str, tuple[float, float, float]] = {
    "E": (0.0, -1e9, 1e9),
    "H": (0.0, 0.0, 1.0),
    "L": (0.2, 0.05, 1.0),
    "G": (0.3, 0.05, 2.0),
    "A": (0.0, 0.0, 0.2),
}

STATISTICAL_RATIOS = {"p": 2.0, "d": 1.5, "f": 4.0 / 3.0, "Custom": 2.0}


class StateValidationError(ValueError):
    """Raised when a persisted/captured fit state is structurally invalid."""


def statistical_ratio(orbital: str) -> float:
    return float(STATISTICAL_RATIOS.get(str(orbital or "Custom"), 2.0))


def _finite_float(value: Any, *, field_name: str, default: float) -> float:
    if value is None:
        return float(default)
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise StateValidationError(f"{field_name} must be numeric.") from exc
    if not math.isfinite(result):
        raise StateValidationError(f"{field_name} must be finite.")
    return result


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class PeakParameterState:
    value: float
    minimum: float
    maximum: float
    mode: str = "Free"
    present_fields: frozenset[str] = frozenset({"value", "min", "max", "mode"})

    @classmethod
    def from_mapping(cls, state: Mapping[str, Any], prefix: str) -> "PeakParameterState":
        default_value, default_min, default_max = _PEAK_DEFAULTS[prefix]
        value = _finite_float(state.get(prefix), field_name=prefix, default=default_value)
        minimum = _finite_float(state.get(f"{prefix}_min"), field_name=f"{prefix}_min", default=default_min)
        maximum = _finite_float(state.get(f"{prefix}_max"), field_name=f"{prefix}_max", default=default_max)
        if f"{prefix}_min" in state and f"{prefix}_max" in state and maximum < minimum:
            raise StateValidationError(f"{prefix}_max must be greater than or equal to {prefix}_min.")
        mode = str(state.get(f"{prefix}_mode") or "Free")
        present: set[str] = set()
        if prefix in state: present.add("value")
        if f"{prefix}_min" in state: present.add("min")
        if f"{prefix}_max" in state: present.add("max")
        if f"{prefix}_mode" in state: present.add("mode")
        return cls(value=value, minimum=minimum, maximum=maximum, mode=mode, present_fields=frozenset(present))

    def add_to_mapping(self, out: dict[str, Any], prefix: str) -> None:
        if "value" in self.present_fields:
            out[prefix] = float(self.value)
        if "min" in self.present_fields:
            out[f"{prefix}_min"] = float(self.minimum)
        if "max" in self.present_fields:
            out[f"{prefix}_max"] = float(self.maximum)
        if "mode" in self.present_fields:
            out[f"{prefix}_mode"] = str(self.mode or "Free")


@dataclass(slots=True)
class PeakState:
    """Typed representation of one mathematical fit peak."""

    label: str
    parameters: dict[str, PeakParameterState]
    color: str | None = None
    color_custom: bool | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, state: Mapping[str, Any], *, ordinal: int = 1) -> "PeakState":
        if not isinstance(state, Mapping):
            raise StateValidationError("Each peak state must be an object.")
        params = {prefix: PeakParameterState.from_mapping(state, prefix) for prefix in PEAK_PARAMETERS}
        label = str(state.get("label") or f"P{ordinal}")
        color = str(state.get("color")) if state.get("color") is not None else None
        color_custom = bool(state.get("color_custom")) if "color_custom" in state else None
        known = {"label", "color", "color_custom"}
        for prefix in PEAK_PARAMETERS:
            known.update({prefix, f"{prefix}_min", f"{prefix}_max", f"{prefix}_mode"})
        extras = {str(k): deepcopy(v) for k, v in state.items() if k not in known}
        return cls(label=label, parameters=params, color=color, color_custom=color_custom, extras=extras)

    def to_mapping(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for prefix in PEAK_PARAMETERS:
            self.parameters[prefix].add_to_mapping(out, prefix)
        out["label"] = str(self.label)
        if self.color is not None:
            out["color"] = str(self.color)
        if self.color_custom is not None:
            out["color_custom"] = bool(self.color_custom)
        out.update(deepcopy(self.extras))
        return out


@dataclass(slots=True)
class DoubletState:
    """Typed representation of one SO-doublet relationship."""

    id: int
    major: int
    minor: int
    label: str
    orbital: str
    split: float
    split_min: float
    split_max: float
    split_mode: str
    split_tie_target: int | None
    ratio: float
    ratio_min: float
    ratio_max: float
    ratio_mode: str
    ratio_tie_target: int | None
    L_relation: str
    G_relation: str
    A_relation: str
    extras: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, state: Mapping[str, Any], *, ordinal: int = 1) -> "DoubletState":
        if not isinstance(state, Mapping):
            raise StateValidationError("Each SO-doublet state must be an object.")
        did = int(state.get("id", ordinal))
        major = int(state.get("major", 1))
        minor = int(state.get("minor", 2))
        label = str(state.get("label") or f"Doublet #{ordinal}")
        orbital = str(state.get("orbital") or "p")
        if orbital not in ("p", "d", "f", "Custom"):
            orbital = "Custom"

        split = abs(_finite_float(state.get("split"), field_name="split", default=1.0))
        split_min = max(0.0, _finite_float(
            state.get("split_min"), field_name="split_min", default=max(0.0, split * 0.8)
        ))
        split_max = _finite_float(
            state.get("split_max"), field_name="split_max", default=max(split * 1.2, split + 0.1)
        )
        split_max = max(split_min, split_max)
        split_mode = str(state.get("split_mode") or "Fixed")
        if split_mode not in ("Fixed", "Free", "Tied"):
            split_mode = "Fixed"
        split_tie_target = _optional_int(state.get("split_tie_target"))

        ratio = max(1e-6, _finite_float(
            state.get("ratio"), field_name="ratio", default=statistical_ratio(orbital)
        ))
        ratio_min = max(1e-6, _finite_float(
            state.get("ratio_min"), field_name="ratio_min", default=max(0.1, ratio * 0.75)
        ))
        ratio_max = _finite_float(
            state.get("ratio_max"), field_name="ratio_max", default=max(ratio * 1.25, ratio + 0.2)
        )
        ratio_max = max(ratio_min, ratio_max)
        ratio_mode = str(state.get("ratio_mode") or "Fixed")
        if ratio_mode not in ("Fixed", "Free", "Tied"):
            ratio_mode = "Fixed"
        ratio_tie_target = _optional_int(state.get("ratio_tie_target"))

        relations: dict[str, str] = {}
        for prefix in ("L", "G", "A"):
            relation = str(state.get(f"{prefix}_relation") or "Same")
            relations[prefix] = relation if relation in ("Same", "Independent") else "Same"

        known = {
            "id", "major", "minor", "label", "orbital",
            "split", "split_min", "split_max", "split_mode", "split_tie_target",
            "ratio", "ratio_min", "ratio_max", "ratio_mode", "ratio_tie_target",
            "L_relation", "G_relation", "A_relation",
        }
        extras = {str(k): deepcopy(v) for k, v in state.items() if k not in known}
        return cls(
            id=did, major=major, minor=minor, label=label, orbital=orbital,
            split=split, split_min=split_min, split_max=split_max,
            split_mode=split_mode, split_tie_target=split_tie_target,
            ratio=ratio, ratio_min=ratio_min, ratio_max=ratio_max,
            ratio_mode=ratio_mode, ratio_tie_target=ratio_tie_target,
            L_relation=relations["L"], G_relation=relations["G"], A_relation=relations["A"],
            extras=extras,
        )

    def to_mapping(self) -> dict[str, Any]:
        out = {
            "id": int(self.id),
            "major": int(self.major),
            "minor": int(self.minor),
            "label": str(self.label),
            "orbital": str(self.orbital),
            "split": float(self.split),
            "split_min": float(self.split_min),
            "split_max": float(self.split_max),
            "split_mode": str(self.split_mode),
            "split_tie_target": self.split_tie_target,
            "ratio": float(self.ratio),
            "ratio_min": float(self.ratio_min),
            "ratio_max": float(self.ratio_max),
            "ratio_mode": str(self.ratio_mode),
            "ratio_tie_target": self.ratio_tie_target,
            "L_relation": str(self.L_relation),
            "G_relation": str(self.G_relation),
            "A_relation": str(self.A_relation),
        }
        out.update(deepcopy(self.extras))
        return out


@dataclass(slots=True)
class FitSetupState:
    """Typed boundary object for the persisted/copyable fit setup."""

    peak_states: list[PeakState]
    so_doublets: list[DoubletState]
    bg_state: dict[str, Any]
    extras: dict[str, Any] = field(default_factory=dict)
    had_peak_states_key: bool = True
    had_so_doublets_key: bool = True
    had_bg_state_key: bool = True

    @classmethod
    def from_mapping(cls, setup: Mapping[str, Any]) -> "FitSetupState":
        if not isinstance(setup, Mapping):
            raise StateValidationError("The fit setup section is missing or malformed.")
        raw_peaks = setup.get("peak_states", [])
        if not isinstance(raw_peaks, list):
            raise StateValidationError("The peak_states section is malformed.")
        raw_doublets = setup.get("so_doublets", [])
        if not isinstance(raw_doublets, list):
            raise StateValidationError("The so_doublets section is malformed.")
        raw_bg = setup.get("bg_state", {})
        if not isinstance(raw_bg, Mapping):
            raise StateValidationError("The bg_state section is malformed.")

        peaks = [PeakState.from_mapping(state, ordinal=i) for i, state in enumerate(raw_peaks, start=1)]
        doublets = [DoubletState.from_mapping(state, ordinal=i) for i, state in enumerate(raw_doublets, start=1)]
        known = {"peak_states", "so_doublets", "bg_state"}
        extras = {str(k): deepcopy(v) for k, v in setup.items() if k not in known}
        return cls(
            peak_states=peaks,
            so_doublets=doublets,
            bg_state=deepcopy(dict(raw_bg)),
            extras=extras,
            had_peak_states_key="peak_states" in setup,
            had_so_doublets_key="so_doublets" in setup,
            had_bg_state_key="bg_state" in setup,
        )

    def to_mapping(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.had_peak_states_key or self.peak_states:
            out["peak_states"] = [state.to_mapping() for state in self.peak_states]
        if self.had_so_doublets_key or self.so_doublets:
            out["so_doublets"] = [state.to_mapping() for state in self.so_doublets]
        if self.had_bg_state_key:
            out["bg_state"] = deepcopy(self.bg_state)
        out.update(deepcopy(self.extras))
        return out


def normalize_peak_states(states: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [PeakState.from_mapping(state, ordinal=i).to_mapping() for i, state in enumerate(states or [], start=1)]


def normalize_fit_setup(setup: Mapping[str, Any]) -> dict[str, Any]:
    return FitSetupState.from_mapping(setup).to_mapping()
