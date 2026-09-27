"""Intensity normalization workflow."""

from .logic import mean_intensity_over_interval, normalization_interval

__all__ = [
    "build_normalization_control",
    "mean_intensity_over_interval",
    "normalization_interval",
]


def __getattr__(name: str):
    if name == "build_normalization_control":
        from .ui_bits import build_normalization_control
        return build_normalization_control
    raise AttributeError(name)
