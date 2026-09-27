from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AnnotationSettings:
    text: str = ""
    visible: bool = False
    x: float = 0.04
    y: float = 0.96
    style: dict = field(default_factory=lambda: {
        "fontsize": 12, "bold": False, "italic": False, "underline": False,
        "font_color": "#000000", "bg_enabled": True, "bg_color": "#FFFFFF",
        "border_enabled": True, "border_color": "#000000", "border_width": 0.8,
        "pad": 0.30,
    })


@dataclass
class LegendSettings:
    location: str = "best"
    anchor: tuple[float, float] | None = None
    style: dict = field(default_factory=lambda: {
        "alpha": 1.0, "borderpad": 0.4, "fontsize": 10,
        "bold": False, "italic": False, "underline": False,
    })
