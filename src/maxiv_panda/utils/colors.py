from __future__ import annotations

from typing import Any, Tuple
import ast

from matplotlib.colors import to_hex, to_rgba


def _coerce_mpl_color(color: Any) -> Any:
    """Recover native tuple colors that may have been stringified upstream.

    Matplotlib may return RGB/RGBA tuples from ``Line2D.get_color()`` depending
    on the active style/version.  Older code converted those values with
    ``str()``, producing strings such as ``"(0.1, 0.2, 0.3, 1.0)"`` which
    Matplotlib itself does not accept as color specifications.  Accept that
    legacy form defensively while new code preserves native objects.
    """
    if isinstance(color, str):
        text = color.strip()
        if text.startswith("(") and text.endswith(")"):
            try:
                value = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return color
            if isinstance(value, tuple) and len(value) in (3, 4):
                return value
    return color


def mpl_color_to_rgba8(color: Any) -> Tuple[int, int, int, int]:
    """Convert any Matplotlib-compatible color specification to 8-bit RGBA.

    Qt's QColor parser does not understand all Matplotlib color syntaxes
    (notably ``C0`` and ``tab:blue``).  Convert through Matplotlib first so
    GUI color swatches remain portable across Matplotlib/Qt environments.
    """
    r, g, b, a = to_rgba(_coerce_mpl_color(color))
    return tuple(int(round(channel * 255.0)) for channel in (r, g, b, a))


def mpl_color_to_hex(color: Any, *, keep_alpha: bool = False) -> str:
    """Return a CSS/Qt-compatible hex string for a Matplotlib color."""
    return to_hex(to_rgba(_coerce_mpl_color(color)), keep_alpha=keep_alpha)
