from __future__ import annotations

import re
from typing import Any

import numpy as np
from matplotlib.transforms import offset_copy

from .guided_detection import _base_transition
from .matcher import PeakAssignment
from .spectrum_context import extract_photon_energy


def draw_signal_annotations(controller: Any) -> None:
    self = controller
    # Identification is intentionally a Raw Data-only overlay.  Raw and
    # Processed Data share the same axes, but the cached assignments belong to
    # the raw spectrum and must not be redrawn or recomputed on Processed Data.
    try:
        tabs = getattr(self.window, "tabs", None)
        raw_tab = getattr(self.window, "raw_data_tab", None)
        if tabs is not None and raw_tab is not None and tabs.currentWidget() is not raw_tab:
            return
    except Exception:
        return
    if not self.window.cb_identify_signals.isChecked() or not self.assignments:
        return
    current = self.current_single_curve()
    if current is None:
        return
    _payload, _meta, key = current
    if key != self._active_key:
        self.identify(show_messages=False)
    ax = self.window.plot_area.ax

    # Annotation positions must follow the curve as it is currently displayed
    # in Raw Data.  Reuse the plotted line data when its X grid matches the
    # active payload; otherwise fall back to the original payload arrays.
    try:
        display_x = np.asarray(_payload.x, dtype=float).reshape(-1)
        display_y = np.asarray(_payload.y, dtype=float).reshape(-1)
    except Exception:
        display_x = np.asarray([], dtype=float)
        display_y = np.asarray([], dtype=float)
    for plotted_line in ax.lines:
        try:
            line_x = np.asarray(plotted_line.get_xdata(), dtype=float).reshape(-1)
            line_y = np.asarray(plotted_line.get_ydata(), dtype=float).reshape(-1)
            if (
                line_x.size == display_x.size
                and line_y.size == display_y.size
                and line_x.size > 0
                and np.allclose(line_x, display_x, rtol=0.0, atol=1e-9, equal_nan=True)
            ):
                display_x = line_x
                display_y = line_y
                break
        except Exception:
            continue

    auger_groups: dict[tuple[str, str], list[Any]] = {}
    photoelectron = []
    for assignment in self.assignments:
        best = assignment.best
        if best is None:
            continue
        if best.kind == "Auger":
            show_auger = getattr(self.window, "cb_show_auger", None)
            if show_auger is None or show_auger.isChecked():
                auger_groups.setdefault((best.element, best.line), []).append(best)
        else:
            photoelectron.append(assignment)

    # Reserve vertical headroom for upright PE labels.  Determine the range
    # from the actual plotted spectra, before adding annotation guide lines,
    # so repeated redraws do not progressively enlarge the Y scale.
    plotted_y = []
    for line in ax.lines:
        try:
            values = line.get_ydata()
            plotted_y.extend(float(value) for value in values if value == value)
        except Exception:
            continue
    if plotted_y:
        data_min = min(plotted_y)
        data_max = max(plotted_y)
        span = max(data_max - data_min, abs(data_max) * 0.05, 1.0)
        current_bottom, _current_top = ax.get_ylim()
        ax.set_ylim(current_bottom, data_max + 0.24 * span)

    x_text_transform = ax.get_xaxis_transform()

    # Mark the valence-band interval as one region.  Individual maxima in
    # this interval are never matched to atomic core/shallow levels.
    vb_cutoff = max(0.0, float(self.settings.valence_band_cutoff_eV))
    if vb_cutoff > 0:
        scale = str(getattr(_payload, "energy_scale", "Unknown")).lower()
        photon = self.settings.photon_energy or extract_photon_energy(_meta)
        vb_lo = vb_hi = None
        if scale.startswith("bind"):
            vb_lo, vb_hi = 0.0, vb_cutoff
        elif scale.startswith("kin") and photon is not None:
            vb_lo, vb_hi = float(photon) - vb_cutoff, float(photon)
        if vb_lo is not None and vb_hi is not None:
            x_data = []
            try:
                x_data = [float(v) for v in _payload.x]
            except Exception:
                x_data = []
            if x_data and max(vb_lo, min(x_data)) <= min(vb_hi, max(x_data)):
                # The VB interval is a protected energy region, not a detected
                # peak.  Mark its geometrical centre rather than following the
                # strongest point, which is commonly located at one of the
                # interval edges.  Purple keeps this region visually distinct
                # from the blue Auger-family envelopes.
                vb_color = "tab:purple"
                ax.axvspan(vb_lo, vb_hi, alpha=0.070, color=vb_color, linewidth=0)
                try:
                    vb_x = np.asarray(display_x, dtype=float).reshape(-1)
                    vb_y = np.asarray(display_y, dtype=float).reshape(-1)
                    mask = (
                        np.isfinite(vb_x) & np.isfinite(vb_y)
                        & (vb_x >= min(vb_lo, vb_hi))
                        & (vb_x <= max(vb_lo, vb_hi))
                    )
                    if np.any(mask):
                        x_region = vb_x[mask]
                        y_region = vb_y[mask]
                        vb_mid_x = 0.5 * (float(vb_lo) + float(vb_hi))
                        nearest = int(np.nanargmin(np.abs(x_region - vb_mid_x)))
                        vb_mid_y = float(y_region[nearest])
                        vb_transform = offset_copy(
                            ax.transData, fig=ax.figure, x=0.0, y=11.0, units="points"
                        )
                        ax.axvline(
                            vb_mid_x, linewidth=0.7, linestyle=":", alpha=0.70,
                            color=vb_color,
                        )
                        ax.text(
                            vb_mid_x,
                            vb_mid_y,
                            "VB",
                            transform=vb_transform,
                            rotation=90,
                            ha="center",
                            va="bottom",
                            fontsize=10,
                            fontweight="normal",
                            color=vb_color,
                            clip_on=True,
                        )
                except Exception:
                    pass

    # Keep track of already used Auger-label rows.  When two family labels
    # occupy nearly the same horizontal screen position, place the later one
    # directly below instead of drawing both on top of each other.
    auger_label_slots: list[tuple[float, int]] = []

    # Give every visible Auger family one stable plot-local colour.  The same
    # colour is used for all of its measured envelopes, its label, and the
    # lightweight connector that points to the individual component centres.
    # Purple is deliberately omitted because it is reserved for the VB region.
    auger_palette = (
        "tab:blue", "tab:orange", "tab:green", "tab:red",
        "tab:brown", "tab:pink", "tab:gray", "tab:olive", "tab:cyan",
    )
    auger_keys = sorted(auger_groups, key=lambda item: (item[0], item[1]))
    auger_colors = {
        key: auger_palette[index % len(auger_palette)]
        for index, key in enumerate(auger_keys)
    }

    for (element, family) in auger_keys:
        candidates = auger_groups[(element, family)]
        family_color = auger_colors[(element, family)]
        references = sorted({float(c.expected_energy) for c in candidates})
        subregions = []
        for candidate in candidates:
            for region in getattr(candidate, "auger_subregions", ()):
                try:
                    subregions.append((
                        float(region.peak_energy),
                        float(region.tail_lo),
                        float(region.core_lo),
                        float(region.core_hi),
                        float(region.tail_hi),
                        float(region.significance),
                    ))
                except AttributeError:
                    # Compatibility with annotations created by older package
                    # objects during an in-place GUI update.
                    try:
                        center, region_lo, region_hi = region
                        width = max(float(region_hi) - float(region_lo), 1.0)
                        subregions.append((
                            float(center), float(region_lo),
                            float(center) - 0.20 * width,
                            float(center) + 0.20 * width,
                            float(region_hi), 1.0,
                        ))
                    except Exception:
                        continue
        if not subregions:
            soft_lo = min(
                c.soft_region_min if c.soft_region_min is not None else c.expected_energy
                for c in candidates
            )
            soft_hi = max(
                c.soft_region_max if c.soft_region_max is not None else c.expected_energy
                for c in candidates
            )
            center = float(np.average(references))
            width = max(float(soft_hi) - float(soft_lo), 1.0)
            subregions = [(
                center, float(soft_lo), center - 0.20 * width,
                center + 0.20 * width, float(soft_hi), 1.0,
            )]

        # Draw every experimentally supported component as a local envelope.
        # A family can recur in several well separated atomic clusters; each
        # cluster therefore gets its own short label/underline rather than one
        # connector spanning the empty energy between them.
        for peak_energy, tail_lo, core_lo, core_hi, tail_hi, significance in subregions:
            if not tail_lo <= core_lo <= core_hi <= tail_hi:
                continue
            total_w = max(tail_hi - tail_lo, 1e-9)
            steps = max(48, int(total_w / 0.45))
            edges = np.linspace(tail_lo, tail_hi, steps + 1)
            centers = 0.5 * (edges[:-1] + edges[1:])
            profile = np.ones(centers.shape, dtype=float)
            left = centers < core_lo
            if np.any(left):
                denominator = max(core_lo - tail_lo, 1e-9)
                phase = np.clip((centers[left] - tail_lo) / denominator, 0.0, 1.0)
                profile[left] = 0.5 * (1.0 - np.cos(np.pi * phase))
            right = centers > core_hi
            if np.any(right):
                denominator = max(tail_hi - core_hi, 1e-9)
                phase = np.clip((tail_hi - centers[right]) / denominator, 0.0, 1.0)
                profile[right] = 0.5 * (1.0 - np.cos(np.pi * phase))
            for i, value in enumerate(profile):
                if value < 0.01:
                    continue
                ax.axvspan(
                    edges[i], edges[i + 1], alpha=float(0.115 * value),
                    color=family_color, linewidth=0, zorder=0.35,
                )

            label_x = float(peak_energy)
            try:
                label_px = float(ax.transData.transform((label_x, 0.0))[0])
            except Exception:
                label_px = label_x
            row = 0
            while any(existing_row == row and abs(label_px - existing_px) < 72.0
                      for existing_px, existing_row in auger_label_slots):
                row += 1
            auger_label_slots.append((label_px, row))
            label_y = 0.97 - 0.055 * row
            connector_y = label_y - 0.026
            branch_y = connector_y - 0.018
            try:
                x_span = abs(float(ax.get_xlim()[1]) - float(ax.get_xlim()[0]))
            except Exception:
                x_span = 1.0
            half_length = max(0.006 * x_span, 0.8)
            ax.plot(
                [label_x - half_length, label_x + half_length],
                [connector_y, connector_y],
                transform=x_text_transform, color=family_color, linewidth=0.8,
                alpha=0.85, solid_capstyle="round", clip_on=True, zorder=4.0,
            )
            ax.plot(
                [label_x, label_x], [connector_y, branch_y],
                transform=x_text_transform, color=family_color, linewidth=0.75,
                alpha=0.85, solid_capstyle="round", clip_on=True, zorder=4.0,
            )
            ax.text(
                label_x, label_y, f"{element} {family}",
                transform=x_text_transform, ha="center", va="top", fontsize=10,
                color=family_color, clip_on=True, zorder=4.1,
            )

    # PE labels are centred directly above the *original plotted curve*,
    # not above the smoothed peak-detection trace.  The detector's peak
    # intensity may be lower than a sharp raw maximum, which previously
    # allowed the spectrum to run through the label.  Use the local raw
    # maximum and a fixed screen-space gap instead.
    try:
        raw_x = np.asarray(display_x, dtype=float).reshape(-1)
        raw_y = np.asarray(display_y, dtype=float).reshape(-1)
    except Exception:
        raw_x = np.asarray([], dtype=float)
        raw_y = np.asarray([], dtype=float)
    finite_raw = raw_x.size == raw_y.size and raw_x.size > 0
    if finite_raw:
        finite_mask = np.isfinite(raw_x) & np.isfinite(raw_y)
        raw_x = raw_x[finite_mask]
        raw_y = raw_y[finite_mask]
        if raw_x.size > 1:
            step = float(np.nanmedian(np.abs(np.diff(np.sort(raw_x)))))
            local_half_width = max(1.0, 3.0 * step)
        else:
            local_half_width = 1.0

    label_transform = offset_copy(ax.transData, fig=ax.figure, x=0.0, y=11.0, units="points")

    def _math_label(candidate) -> str:
        match = re.match(r"^(\d+[spdf])([1357]/2)$", str(candidate.line))
        suffix = r" \mathrm{(2nd)}" if candidate.order == 2 else ""
        if match:
            return rf"$\mathrm{{{candidate.element}\ {match.group(1)}}}_{{{match.group(2)}}}{suffix}$"
        return candidate.label

    # Suppress lower-priority labels that are inseparable from a stronger
    # major core-level assignment.  This is particularly important where
    # Ir 5p1/2 overlaps the Ir 4f doublet: the 5p contribution may exist,
    # but a separate label on the same survey feature is misleading and
    # visually collides with the 4f label.
    def _label_priority(assignment: PeakAssignment) -> int:
        best = assignment.best
        family = _base_transition(best.line) if best is not None else ""
        order = {"1s": 0, "2p": 1, "3d": 2, "4f": 3, "4d": 4, "3p": 5, "2s": 6, "3s": 7}
        return order.get(family, 20)

    filtered_photoelectron: list[PeakAssignment] = []
    for assignment in sorted(photoelectron, key=_label_priority):
        x = float(assignment.peak.energy)
        if any(
            abs(x - float(kept.peak.energy)) <= 2.0
            and _label_priority(kept) < _label_priority(assignment)
            for kept in filtered_photoelectron
        ):
            continue
        filtered_photoelectron.append(assignment)

    grouped_labels: dict[tuple[str, str, int], list[PeakAssignment]] = {}
    for assignment in filtered_photoelectron:
        best = assignment.best
        assert best is not None
        grouped_labels.setdefault((best.element, _base_transition(best.line), best.order), []).append(assignment)

    adaptive_groups = []
    for group in grouped_labels.values():
        group.sort(key=lambda a: float(a.peak.energy))
        separate_artists = []
        for assignment in group:
            best = assignment.best
            assert best is not None
            x = float(assignment.peak.energy)
            y = float(assignment.peak.intensity)
            if finite_raw and raw_x.size:
                local = np.abs(raw_x - x) <= local_half_width
                if np.any(local):
                    # Use the intensity of the curve currently shown on the
                    # axes.  ``assignment.peak.intensity`` belongs to the
                    # original identification spectrum and may be many orders
                    # of magnitude larger after display-only normalization.
                    y = float(np.nanmax(raw_y[local]))
            ax.axvline(x, linewidth=0.6, linestyle=":", alpha=0.55)
            artist = ax.text(
                x, y, _math_label(best), transform=label_transform,
                rotation=90, ha="center", va="bottom", fontsize=10, clip_on=True,
            )
            separate_artists.append(artist)

        combined_artist = None
        if len(group) >= 2:
            strongest = max(group, key=lambda a: float(a.peak.intensity))
            best0 = strongest.best
            x = float(strongest.peak.energy)
            y = float(strongest.peak.intensity)
            if finite_raw and raw_x.size:
                local = np.abs(raw_x - x) <= local_half_width
                if np.any(local):
                    # Use the intensity of the curve currently shown on the
                    # axes.  ``assignment.peak.intensity`` belongs to the
                    # original identification spectrum and may be many orders
                    # of magnitude larger after display-only normalization.
                    y = float(np.nanmax(raw_y[local]))
            combined_artist = ax.text(
                x, y, f"{best0.element} {_base_transition(best0.line)}",
                transform=label_transform, rotation=90, ha="center", va="bottom",
                fontsize=10, clip_on=True,
            )
            adaptive_groups.append((group, separate_artists, combined_artist))

    def _update_spin_orbit_visibility(_axes=None):
        for group, separate_artists, combined_artist in adaptive_groups:
            x_pixels = sorted(ax.transData.transform((float(a.peak.energy), 0.0))[0] for a in group)
            min_gap = min(np.diff(x_pixels)) if len(x_pixels) > 1 else float("inf")
            energy_span = max(float(a.peak.energy) for a in group) - min(float(a.peak.energy) for a in group)
            # Large physical splittings such as Ir 4d are always shown
            # separately.  Close doublets switch automatically after zoom.
            show_separate = energy_span >= 6.0 or min_gap >= 24.0
            for artist in separate_artists:
                artist.set_visible(show_separate)
            combined_artist.set_visible(not show_separate)
        self.window.plot_area.canvas.draw_idle()

    _update_spin_orbit_visibility()
    if adaptive_groups:
        ax.callbacks.connect("xlim_changed", _update_spin_orbit_visibility)
    self.window.plot_area.canvas.draw_idle()
