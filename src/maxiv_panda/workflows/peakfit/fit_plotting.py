from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from matplotlib.ticker import AutoMinorLocator

try:
    from scipy.interpolate import PchipInterpolator
except Exception:
    PchipInterpolator = None

BG_CURVE_COLOR = "#6a3d9a"  # reserved for background curves only

DEFAULT_PEAK_COLORS = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#9467bd",  # purple
    "#8c564b",  # brown
    "#e377c2",  # pink
    "#7f7f7f",  # gray
    "#bcbd22",  # olive
    "#17becf",  # cyan
    "#393b79",  # indigo
]




def style_fit_axes(ax, ax_res) -> None:
    major_kwargs = {"linewidth": 1.0, "alpha": 0.66, "color": "0.68"}
    minor_kwargs = {"linestyle": "--", "linewidth": 0.72, "alpha": 0.46, "color": "0.78"}
    try:
        ax.tick_params(axis="x", labelbottom=False, labelsize=9)
        ax.tick_params(axis="y", labelsize=9)
        ax.yaxis.get_offset_text().set_size(9)
        ax.xaxis.label.set_size(10)
        ax.yaxis.label.set_size(10)
        ax.title.set_size(10)
        ax.ticklabel_format(axis="y", style="sci", scilimits=(-3, 3))
        try:
            ax.xaxis.set_minor_locator(AutoMinorLocator(5))
        except Exception:
            pass
        try:
            ax.yaxis.set_minor_locator(AutoMinorLocator(5))
        except Exception:
            pass
        ax.grid(True, which="major", axis="both", **major_kwargs)
        ax.grid(True, which="minor", axis="both", **minor_kwargs)
    except Exception:
        pass
    try:
        ax_res.tick_params(axis="x", labelsize=9)
        ax_res.tick_params(axis="y", labelsize=9)
        ax_res.yaxis.get_offset_text().set_size(9)
        ax_res.xaxis.label.set_size(10)
        ax_res.yaxis.label.set_size(10)
        try:
            ax_res.xaxis.set_minor_locator(AutoMinorLocator(5))
        except Exception:
            pass
        try:
            ax_res.minorticks_on()
        except Exception:
            pass
        ax_res.grid(True, which="major", axis="x", **major_kwargs)
        ax_res.grid(True, which="minor", axis="x", **minor_kwargs)
        ax_res.grid(True, which="major", axis="y", **major_kwargs)
        ax_res.grid(False, which="minor", axis="y")
    except Exception:
        pass


def plot_data_curve(ax, x_data, y_data):
    try:
        ax.plot(x_data, y_data, linewidth=0.9, color="black", zorder=2, label="Measured data")
        ax.scatter(x_data, y_data, s=16, color="black", zorder=3, linewidths=0, label="_nolegend_")
    except Exception:
        ax.plot(list(x_data), list(y_data), linewidth=0.9, color="black", zorder=2, label="Measured data")
        try:
            ax.scatter(list(x_data), list(y_data), s=16, color="black", zorder=3, linewidths=0, label="_nolegend_")
        except Exception:
            pass


def smooth_curve_for_display(x, y, num_points: int = 4000):
    try:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        if x.size < 4 or y.size != x.size or PchipInterpolator is None:
            return x, y
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
            return x, y
        descending = bool(x.size > 1 and x[0] > x[-1])
        x_work = x[::-1] if descending else x
        y_work = y[::-1] if descending else y
        # remove repeated x for spline stability
        xu, idx = np.unique(x_work, return_index=True)
        yu = y_work[idx]
        if xu.size < 4:
            return x, y
        n_out = max(int(num_points), int(xu.size) * 12)
        xs = np.linspace(float(xu.min()), float(xu.max()), n_out)
        ys = PchipInterpolator(xu, yu, extrapolate=False)(xs)
        if descending:
            xs = xs[::-1]
            ys = ys[::-1]
        return xs, ys
    except Exception:
        return x, y



def capture_axes_view(ax) -> dict[str, tuple[float, float]]:
    """Capture the current main-axis viewport for redraws that clear the axes."""
    state = {}
    try:
        state["xlim"] = tuple(float(v) for v in ax.get_xlim())
    except Exception:
        pass
    try:
        state["ylim"] = tuple(float(v) for v in ax.get_ylim())
    except Exception:
        pass
    return state


def restore_axes_view(ax, ax_res, view_state) -> None:
    """Restore a previously captured viewport without changing the fit/data state."""
    if not isinstance(view_state, dict):
        return
    try:
        if "xlim" in view_state:
            ax.set_xlim(*view_state["xlim"])
    except Exception:
        pass
    try:
        if "ylim" in view_state:
            ax.set_ylim(*view_state["ylim"])
    except Exception:
        pass
    try:
        if ax_res is not None and "xlim" in view_state:
            ax_res.set_xlim(*view_state["xlim"])
    except Exception:
        pass

def default_peak_color(index: int) -> str:
    if index < 1:
        index = 1
    return DEFAULT_PEAK_COLORS[(index - 1) % len(DEFAULT_PEAK_COLORS)]


def clear_artists(artists: Sequence[Any] | None) -> None:
    for a in list(artists or []):
        try:
            a.remove()
        except Exception:
            pass


def clear_artist_attributes(owner: Any, *attr_names: str) -> None:
    """Remove matplotlib artists stored on object attributes and reset them to None."""
    for attr in attr_names:
        try:
            obj = getattr(owner, attr, None)
        except Exception:
            obj = None
        if obj is None:
            continue
        if isinstance(obj, (list, tuple)):
            clear_artists(obj)
        else:
            clear_artists([obj])
        try:
            setattr(owner, attr, None)
        except Exception:
            pass


def plot_background_curve(ax, x, y_bg):
    try:
        (ln,) = ax.plot(x, y_bg, linestyle="--", linewidth=1.5, zorder=4, color=BG_CURVE_COLOR, alpha=0.95, label="Background")
        return ln
    except Exception:
        return None


def setup_payload_plot(ax, ax_res, payload, title: str = "") -> dict[str, Any] | None:
    """Draw the raw payload, configure axes, and return computed plot ranges."""
    try:
        x = np.asarray(getattr(payload, "x", []), dtype=float)
        y = np.asarray(getattr(payload, "y", []), dtype=float)
    except Exception:
        return None
    if x.size == 0 or y.size == 0:
        return None
    try:
        xmin = float(np.nanmin(x))
        xmax = float(np.nanmax(x))
        ymin = float(np.nanmin(y))
        ymax = float(np.nanmax(y))
    except Exception:
        return None
    ax.clear()
    plot_data_curve(ax, x, y)
    xlabel = getattr(payload, "xlabel", "Energy")
    ylabel = getattr(payload, "ylabel", "Height")
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title, pad=2)
    try:
        scale = str(getattr(payload, "energy_scale", "")).lower()
        reverse = (scale.startswith("bind") or scale in ("be", "binding"))
    except Exception:
        reverse = False
        scale = ""
    if reverse:
        ax.set_xlim(max(xmin, xmax), min(xmin, xmax))
    else:
        ax.set_xlim(min(xmin, xmax), max(xmin, xmax))
    clear_residual_axis(ax_res)
    try:
        ax_res.set_xlabel(xlabel)
        ax_res.set_xlim(ax.get_xlim())
        ax.tick_params(axis="x", labelbottom=False)
    except Exception:
        pass
    ax.relim()
    ax.autoscale_view(scalex=False, scaley=True)
    style_fit_axes(ax, ax_res)
    return {"x": x, "y": y, "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax, "xlabel": xlabel, "ylabel": ylabel, "scale": scale, "reverse": reverse}


def clear_residual_axis(ax_res) -> None:
    try:
        ax_res.clear()
        ax_res.axhline(0.0, linestyle="--", linewidth=0.8, color="0.5")
        ax_res.set_ylabel("Res")
        ax_res.set_xlabel("")
        ax_res.ticklabel_format(axis="y", style="sci", scilimits=(-3, 3))
        try:
            ax_res.tick_params(axis="x", labelsize=9)
            ax_res.tick_params(axis="y", labelsize=9)
            ax_res.yaxis.get_offset_text().set_size(9)
            ax_res.xaxis.label.set_size(10)
            ax_res.yaxis.label.set_size(10)
            ax_res.xaxis.set_minor_locator(AutoMinorLocator(5))
            ax_res.grid(True, which="major", axis="x", linewidth=1.0, alpha=0.66, color="0.68")
            ax_res.grid(True, which="minor", axis="x", linestyle="--", linewidth=0.72, alpha=0.46, color="0.78")
            ax_res.grid(True, which="major", axis="y", linewidth=1.0, alpha=0.66, color="0.68")
            ax_res.grid(False, which="minor", axis="y")
        except Exception:
            pass
    except Exception:
        pass


def plot_residuals(ax_res, x, y_data, y_fit, descending: bool = False, xlabel: str = "") -> None:
    try:
        x = np.asarray(x, dtype=float)
        y_data = np.asarray(y_data, dtype=float)
        y_fit = np.asarray(y_fit, dtype=float)
        if x.size == 0 or y_data.size != x.size or y_fit.size != x.size:
            clear_residual_axis(ax_res)
            return
        resid = y_data - y_fit
        x_plot = x if not descending else x[::-1]
        resid_plot = resid if not descending else resid[::-1]
        ax_res.clear()
        ax_res.axhline(0.0, linestyle="--", linewidth=0.8, color="0.5")
        ax_res.plot(x_plot, resid_plot, linewidth=1.0)
        ax_res.set_ylabel("Res")
        ax_res.set_xlabel(xlabel or "")
        ax_res.ticklabel_format(axis="y", style="sci", scilimits=(-3, 3))
        try:
            ax_res.tick_params(axis="x", labelsize=9)
            ax_res.tick_params(axis="y", labelsize=9)
            ax_res.yaxis.get_offset_text().set_size(9)
            ax_res.xaxis.label.set_size(10)
            ax_res.yaxis.label.set_size(10)
            ax_res.xaxis.set_minor_locator(AutoMinorLocator(5))
            ax_res.grid(True, which="major", axis="x", linewidth=1.0, alpha=0.66, color="0.68")
            ax_res.grid(True, which="minor", axis="x", linestyle="--", linewidth=0.72, alpha=0.46, color="0.78")
            ax_res.grid(True, which="major", axis="y", linewidth=1.0, alpha=0.66, color="0.68")
            ax_res.grid(False, which="minor", axis="y")
        except Exception:
            pass
    except Exception:
        clear_residual_axis(ax_res)


def refresh_peak_markers(ax, canvas, peak_widgets, calc_checked: bool, existing_artists):
    """Draw/update the interactive Energy/Height markers.

    Existing ``LineCollection`` marker artists are updated in place whenever
    possible.  This is important for color changes: rebuilding the calculated
    component curves can leave a queued canvas redraw while the old marker
    collection is still present, which in some Qt/Matplotlib combinations can
    make the marker appear to retain its previous color.  Updating the artist
    itself keeps position, height, and color synchronized immediately.

    ``calc_checked`` is retained for API compatibility, but markers deliberately
    remain visible while the calculated spectrum is shown so they can still be
    dragged to refine the live model.
    """
    widgets = list(peak_widgets or [])
    artists = list(existing_artists or [])

    # If the number of peaks changed, rebuild the collection list once.  With a
    # stable peak count we update the existing artists in place.
    if len(artists) != len(widgets):
        clear_artists(artists)
        artists = []
        for idx_marker, w in enumerate(widgets):
            try:
                x = float(w["E"].value())
                h = max(float(w["H"].value()), 0.0)
                color = str(w.get("_display_color") or w.get("color") or default_peak_color(idx_marker + 1))
                w["color"] = color
                art = ax.vlines(
                    x, 0.0, h, linewidth=2.0, alpha=0.95,
                    colors=color, zorder=12,
                )
                artists.append(art)
            except Exception:
                continue
    else:
        for idx_marker, (w, art) in enumerate(zip(widgets, artists)):
            try:
                x = float(w["E"].value())
                h = max(float(w["H"].value()), 0.0)
                color = str(w.get("_display_color") or w.get("color") or default_peak_color(idx_marker + 1))
                w["color"] = color
                # LineCollection produced by Axes.vlines.
                art.set_segments([[(x, 0.0), (x, h)]])
                art.set_color(color)
                art.set_alpha(0.95)
                art.set_linewidth(2.0)
                art.set_zorder(12)
            except Exception:
                # Fall back to a clean rebuild if an artist is stale or of an
                # unexpected type.
                clear_artists(artists)
                artists = []
                for j, ww in enumerate(widgets):
                    try:
                        xx = float(ww["E"].value())
                        hh = max(float(ww["H"].value()), 0.0)
                        cc = str(ww.get("_display_color") or ww.get("color") or default_peak_color(j + 1))
                        ww["color"] = cc
                        artists.append(ax.vlines(
                            xx, 0.0, hh, linewidth=2.0, alpha=0.95,
                            colors=cc, zorder=12,
                        ))
                    except Exception:
                        pass
                break
    try:
        canvas.draw_idle()
    except Exception:
        pass
    return artists

def draw_intermediate_fit(
    ax,
    ax_res,
    canvas,
    clear_bg_artist_fn,
    clear_peak_markers_fn,
    clear_calc_artists_fn,
    build_model_from_values_fn,
    peak_widgets,
    xu,
    fit_values: dict,
    bg_type: str,
    fit_data: dict,
    view_state=None,
    doublets=None,
    doublet_view: bool = False,
):
    from . import so_doublets
    try:
        y_sum_u, components = build_model_from_values_fn(
            xu,
            bg_type=bg_type,
            values=fit_values,
            measured_y=np.asarray(fit_data.get("yu", []), dtype=float) if bg_type == "Shirley" else None,
            energy_scale=str(getattr(fit_data.get("payload"), "energy_scale", "") or ""),
        )
    except Exception:
        return None
    try:
        pl = fit_data.get("payload")
        x_data = np.asarray(getattr(pl, "x", []), dtype=float)
        y_data = np.asarray(getattr(pl, "y", []), dtype=float)
        xlabel = getattr(pl, "xlabel", "Energy")
        ylabel = getattr(pl, "ylabel", "Height")
        title = getattr(pl, "title", "")
        scale = str(getattr(pl, "energy_scale", "")).lower()
    except Exception:
        x_data = fit_data.get("x", xu)
        y_data = fit_data.get("y", np.zeros_like(x_data))
        xlabel = "Energy"
        ylabel = "Height"
        title = ""
        scale = ""
    descending = bool(x_data.size > 1 and x_data[0] > x_data[-1])
    ax.clear()
    clear_bg_artist_fn()
    clear_peak_markers_fn()
    clear_calc_artists_fn()
    plot_data_curve(ax, x_data, y_data)
    bg_u = np.zeros_like(xu)
    if components:
        bg_u = y_sum_u.copy()
        for comp in components:
            bg_u -= comp
    x_plot = xu if not descending else xu[::-1]
    bg_plot = bg_u if not descending else bg_u[::-1]
    bg_artist = None
    calc_artists = []
    try:
        a_bg, = ax.plot(x_plot, bg_plot, linestyle="--", linewidth=1.5, zorder=4, color=BG_CURVE_COLOR, alpha=0.95, label="Background")
        bg_artist = a_bg
    except Exception:
        pass
    colors = [w.get("color", None) for w in peak_widgets]
    color_custom = [bool(w.get("color_custom", False)) for w in peak_widgets]
    labels = []
    for peak_index, w in enumerate(peak_widgets, start=1):
        try:
            text = str(w.get("label_edit").text()).strip()
        except Exception:
            text = ""
        labels.append(text or f"Peak {peak_index}")
    display_specs = so_doublets.grouped_component_specs(
        components, labels, colors, doublets or [], grouped=bool(doublet_view), color_custom=color_custom
    )
    for spec in display_specs:
        comp = spec["component"]
        y_plot = comp if not descending else comp[::-1]
        try:
            a, = ax.plot(
                x_plot, y_plot, linewidth=1.2, alpha=0.9,
                color=spec.get("color"), label=spec.get("label") or "Component"
            )
            calc_artists.append(a)
        except Exception:
            pass
    y_sum_plot = y_sum_u if not descending else y_sum_u[::-1]
    x_sum_plot, y_sum_plot_s = smooth_curve_for_display(x_plot, y_sum_plot)
    try:
        a_sum, = ax.plot(x_sum_plot, y_sum_plot_s, linewidth=2.2, color="red", zorder=5, antialiased=True, solid_joinstyle="round", solid_capstyle="round", label="Total fit")
        calc_artists.append(a_sum)
    except Exception:
        pass
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(f"{title} - fitting...", pad=2)
    plot_residuals(ax_res, xu, np.asarray(fit_data.get("yu", []), dtype=float), y_sum_u, descending=descending, xlabel=xlabel)
    try:
        xmin = float(np.nanmin(x_data)); xmax = float(np.nanmax(x_data))
        if scale.startswith("bind") or scale in ("be", "binding"):
            ax.set_xlim(max(xmin, xmax), min(xmin, xmax))
        else:
            ax.set_xlim(min(xmin, xmax), max(xmin, xmax))
    except Exception:
        pass
    try:
        ax_res.set_xlim(ax.get_xlim())
        ax.tick_params(axis="x", labelbottom=False)
    except Exception:
        pass
    ax.relim()
    ax.autoscale_view(scalex=False, scaley=True)
    style_fit_axes(ax, ax_res)
    restore_axes_view(ax, ax_res, view_state)
    try:
        canvas.draw()
    except Exception:
        try:
            canvas.draw_idle()
        except Exception:
            pass
    return {"bg_artist": bg_artist, "calc_artists": calc_artists}
