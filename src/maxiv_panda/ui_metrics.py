from __future__ import annotations

"""Central UI metrics for PANDA.

The metrics layer keeps generic spacing and control geometry in one place so
that the interface can be tuned coherently across operating systems and screen
sizes. Scientific/functional geometry remains local to the feature that owns
it.
"""

from dataclasses import dataclass, replace
from enum import Enum


class InterfaceDensity(str, Enum):
    """Supported application density preferences."""

    AUTOMATIC = "automatic"
    STANDARD = "standard"
    COMPACT = "compact"


@dataclass(frozen=True)
class UiMetrics:
    """Shared layout metrics in Qt logical pixels."""

    panel_margin: int
    dialog_margin: int
    layout_spacing: int
    compact_spacing: int
    standard_control_height: int
    compact_control_height: int
    small_button_min_height: int
    progress_bar_height: int
    icon_size: int
    strip_horizontal_margin: int
    strip_vertical_margin: int
    strip_spacing: int
    group_margin_h: int
    group_margin_top: int
    group_margin_bottom: int
    group_spacing: int
    loaded_tree_min_width: int
    selected_tree_min_width: int
    tab_h_padding: int
    tab_v_padding: int
    item_v_padding: int
    menu_v_padding: int


STANDARD_METRICS = UiMetrics(
    panel_margin=8,
    dialog_margin=10,
    layout_spacing=8,
    compact_spacing=6,
    standard_control_height=28,
    compact_control_height=24,
    small_button_min_height=32,
    progress_bar_height=10,
    icon_size=18,
    strip_horizontal_margin=14,
    strip_vertical_margin=10,
    strip_spacing=16,
    group_margin_h=8,
    group_margin_top=8,
    group_margin_bottom=6,
    group_spacing=6,
    loaded_tree_min_width=320,
    selected_tree_min_width=280,
    tab_h_padding=11,
    tab_v_padding=5,
    item_v_padding=2,
    menu_v_padding=4,
)

COMPACT_METRICS = UiMetrics(
    panel_margin=5,
    dialog_margin=7,
    layout_spacing=5,
    compact_spacing=4,
    # Compact density reduces whitespace, not functional control geometry.
    # Baseline control heights stay at the proven Standard values.
    standard_control_height=28,
    compact_control_height=24,
    small_button_min_height=32,
    progress_bar_height=9,
    icon_size=16,
    strip_horizontal_margin=9,
    strip_vertical_margin=5,
    strip_spacing=9,
    group_margin_h=6,
    group_margin_top=6,
    group_margin_bottom=4,
    group_spacing=4,
    loaded_tree_min_width=285,
    selected_tree_min_width=255,
    tab_h_padding=7,
    tab_v_padding=3,
    item_v_padding=1,
    menu_v_padding=2,
)


def resolve_automatic_density(*, available_width: int | None, available_height: int | None) -> InterfaceDensity:
    """Choose a conservative density profile from available logical screen size.

    Qt reports logical pixels, so normal OS scaling is already accounted for.
    Automatic intentionally chooses Compact only on genuinely constrained
    workspaces; users on ordinary desktop monitors retain Standard.
    """

    try:
        width = int(available_width or 0)
        height = int(available_height or 0)
    except Exception:
        return InterfaceDensity.STANDARD
    # Stay conservative: ordinary laptops (e.g. 1366x768 logical px) should
    # retain the established Standard geometry. Compact is reserved for
    # genuinely constrained workspaces.
    if width and width < 1180:
        return InterfaceDensity.COMPACT
    if height and height < 680:
        return InterfaceDensity.COMPACT
    return InterfaceDensity.STANDARD


def metrics_for_density(density: InterfaceDensity | str = InterfaceDensity.STANDARD) -> UiMetrics:
    """Return metrics for an already resolved Standard/Compact density."""

    try:
        resolved = InterfaceDensity(density)
    except (TypeError, ValueError):
        resolved = InterfaceDensity.STANDARD
    if resolved is InterfaceDensity.COMPACT:
        return COMPACT_METRICS
    return STANDARD_METRICS


def metrics_with_font_offset(metrics: UiMetrics, font_offset_pt: int = 0) -> UiMetrics:
    """Return density metrics expanded just enough for a larger UI font.

    Font enlargement is an accessibility feature rather than a density change.
    Horizontal spacing stays stable; vertical control geometry grows coherently
    so +1/+2 pt text is not squeezed into the baseline control heights.
    """

    try:
        offset = max(0, min(2, int(font_offset_pt)))
    except Exception:
        offset = 0
    if offset == 0:
        return metrics
    extra = 2 * offset
    return replace(
        metrics,
        standard_control_height=metrics.standard_control_height + extra,
        compact_control_height=metrics.compact_control_height + extra,
        small_button_min_height=metrics.small_button_min_height + extra,
        tab_v_padding=metrics.tab_v_padding + offset,
        item_v_padding=metrics.item_v_padding + offset,
        menu_v_padding=metrics.menu_v_padding + offset,
    )
