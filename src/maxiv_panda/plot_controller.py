from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import Qt
from matplotlib import rcParams

from .log_utils import log_noncritical_error
from .ui_helpers import RegionTitleState, build_plot_title


@dataclass
class PlotSelection:
    payloads: list[Any]
    items_in_order: list[tuple[Any, str]]
    images: list[tuple[Any, Any, Any, str, str, str]]


class PlotSelectionController:
    def __init__(self, window: Any):
        self.window = window

    def collect_selection(self) -> PlotSelection:
        w = self.window
        payloads: list[Any] = []
        items_in_order: list[tuple[Any, str]] = []
        images: list[tuple[Any, Any, Any, str, str, str]] = []

        for i in range(w.selected_tree.topLevelItemCount()):
            region_item = w.selected_tree.topLevelItem(i)
            if region_item is None:
                continue
            try:
                if region_item.isHidden():
                    continue
            except Exception as exc:
                log_noncritical_error("checking selected region visibility", exc, logger=w._logger)

            region_name = str(region_item.data(0, w.ROLE_REGION) or region_item.text(0))
            file_name = region_item.data(0, w.ROLE_FILE)
            region_key = (file_name, region_name) if isinstance(file_name, str) else None

            map_enabled = False
            btn = w._region_map_buttons.get(region_key) if region_key is not None else None
            if btn is not None:
                try:
                    map_enabled = bool(btn.isChecked())
                except Exception as exc:
                    log_noncritical_error("reading region map toggle", exc, logger=w._logger)
                    map_enabled = False

            if map_enabled:
                stack = w._region_iteration_stack.get(region_key) if region_key is not None else None
                if stack is not None:
                    x, Y, xlabel = stack[:3]
                    dim2_values = stack[3] if len(stack) >= 4 else None
                    dim2_name = stack[4] if len(stack) >= 5 else ""
                    selected_iters: list[int] = []
                    selected_axis_values: dict[int, float] = {}
                    selected_axis_name = ""
                    source_dim2_values = None
                    source_dim2_name = ""
                    for j in range(region_item.childCount()):
                        ch = region_item.child(j)
                        if ch is None:
                            continue
                        try:
                            if ch.isHidden():
                                continue
                        except Exception as exc:
                            log_noncritical_error("checking selected curve visibility in map mode", exc, logger=w._logger)
                        try:
                            is_checked = ch.checkState(0) == Qt.CheckState.Checked
                        except Exception as exc:
                            log_noncritical_error("reading curve check state in map mode", exc, logger=w._logger)
                            is_checked = False
                        if not is_checked:
                            continue
                        meta = ch.data(0, w.ROLE_META)
                        if isinstance(meta, dict):
                            it_no = meta.get("iteration")
                            if isinstance(it_no, int):
                                selected_iters.append(it_no)
                                try:
                                    axis_value = meta.get("iteration_axis_value")
                                    axis_name = str(meta.get("iteration_axis_name") or "").strip()
                                    if axis_value is not None and axis_name:
                                        selected_axis_values[it_no] = float(axis_value)
                                        if not selected_axis_name:
                                            selected_axis_name = axis_name
                                except Exception:
                                    pass
                                # A second, source-metadata based recovery path.
                                # Processed/selected trees can outlive or reconstruct
                                # the cached region stack, but every iteration leaf
                                # preserves the original Region metadata.  Parse the
                                # Dimension 2 scale once from there when available.
                                if source_dim2_values is None:
                                    try:
                                        src = meta.get("source_metadata")
                                        if isinstance(src, dict):
                                            raw_vals = str(src.get("Dimension 2 scale") or "").strip()
                                            raw_name = str(src.get("Dimension 2 name") or "").strip()
                                            if not raw_name:
                                                note_hint = " ".join(str(src.get(k) or "") for k in (
                                                    "Wave note", "Axis Label", "Label", "Spectrum Name"
                                                ))
                                                if "photon energy" in note_hint.lower():
                                                    raw_name = "Photon Energy [eV]"
                                            if raw_vals:
                                                vals = [float(v) for v in raw_vals.split()]
                                                if vals:
                                                    source_dim2_values = vals
                                                    source_dim2_name = raw_name
                                    except Exception:
                                        pass

                    try:
                        selected_iters_sorted = sorted(set(selected_iters))
                        if selected_iters_sorted:
                            y = []
                            Y_sel = []
                            for it_no in selected_iters_sorted:
                                idx = it_no - 1
                                if 0 <= idx < len(Y):
                                    y.append(it_no)
                                    Y_sel.append(Y[idx])
                            if Y_sel:
                                secondary_y = None
                                secondary_label = str(dim2_name or "").strip()
                                if dim2_values is not None:
                                    try:
                                        secondary_y = [dim2_values[it_no - 1] for it_no in selected_iters_sorted]
                                    except Exception:
                                        secondary_y = None
                                # Fallback to metadata carried by the selected
                                # iteration leaves.  This is especially useful
                                # for Processed Data copies, whose region stack
                                # can be older or reconstructed without the
                                # optional second-dimension fields.
                                if secondary_y is not None and not secondary_label:
                                    secondary_label = selected_axis_name or source_dim2_name
                                if secondary_y is None and selected_axis_values:
                                    try:
                                        vals = [selected_axis_values[it_no] for it_no in selected_iters_sorted]
                                        if len(vals) == len(selected_iters_sorted):
                                            secondary_y = vals
                                            secondary_label = selected_axis_name
                                    except Exception:
                                        secondary_y = None
                                if secondary_y is None and source_dim2_values is not None:
                                    try:
                                        vals = [source_dim2_values[it_no - 1] for it_no in selected_iters_sorted]
                                        if len(vals) == len(selected_iters_sorted):
                                            secondary_y = vals
                                            secondary_label = source_dim2_name
                                    except Exception:
                                        secondary_y = None
                                cmap_name = w._region_cmap.get(region_key, "terrain") if region_key is not None else "terrain"
                                images.append((
                                    x, y, Y_sel, f"{region_name} (map)", xlabel, cmap_name,
                                    secondary_y, secondary_label
                                ))
                    except Exception as exc:
                        log_noncritical_error("building map payload", exc, logger=w._logger)

                for j in range(region_item.childCount()):
                    it = region_item.child(j)
                    if it is None:
                        continue
                    try:
                        if it.isHidden():
                            continue
                    except Exception as exc:
                        log_noncritical_error("checking non-iteration overlay visibility", exc, logger=w._logger)
                    label = (it.text(0) or "").lower()
                    if "iteration" in label:
                        continue
                    try:
                        if it.checkState(0) != Qt.CheckState.Checked:
                            continue
                    except Exception as exc:
                        log_noncritical_error("reading non-iteration overlay check state", exc, logger=w._logger)
                        continue
                    p = it.data(0, w.ROLE_PAYLOAD)
                    if p is not None:
                        payloads.append(p)
                        key = it.data(0, w.ROLE_KEY)
                        items_in_order.append((it, key if isinstance(key, str) else ""))
                continue

            try:
                region_visible = region_item.checkState(0) != Qt.CheckState.Unchecked
            except Exception as exc:
                log_noncritical_error("reading region check state for plotting", exc, logger=w._logger)
                region_visible = True
            if not region_visible:
                continue

            for j in range(region_item.childCount()):
                it = region_item.child(j)
                if it is None:
                    continue
                try:
                    if it.isHidden():
                        continue
                except Exception as exc:
                    log_noncritical_error("checking curve visibility for plotting", exc, logger=w._logger)
                try:
                    if it.checkState(0) != Qt.CheckState.Checked:
                        continue
                except Exception as exc:
                    log_noncritical_error("reading curve check state for plotting", exc, logger=w._logger)
                    continue
                p = it.data(0, w.ROLE_PAYLOAD)
                if p is not None:
                    payloads.append(p)
                    key = it.data(0, w.ROLE_KEY)
                    items_in_order.append((it, key if isinstance(key, str) else ""))

        return PlotSelection(payloads=payloads, items_in_order=items_in_order, images=images)

    def compute_title(self) -> str:
        w = self.window
        region_entries: list[RegionTitleState] = []

        for i in range(w.selected_tree.topLevelItemCount()):
            region_item = w.selected_tree.topLevelItem(i)
            if region_item is None:
                continue
            try:
                if region_item.isHidden():
                    continue
            except Exception as exc:
                log_noncritical_error("checking region visibility for plot title", exc, logger=w._logger)

            region_name = str(region_item.data(0, w.ROLE_REGION) or region_item.text(0))
            file_name = region_item.data(0, w.ROLE_FILE)
            region_key = (file_name, region_name) if isinstance(file_name, str) else None
            btn = w._region_map_buttons.get(region_key) if region_key is not None else None
            map_enabled = False
            if btn is not None:
                try:
                    map_enabled = bool(btn.isChecked())
                except Exception as exc:
                    log_noncritical_error("reading map toggle for plot title", exc, logger=w._logger)
            try:
                region_visible = region_item.checkState(0) != Qt.CheckState.Unchecked
            except Exception as exc:
                log_noncritical_error("reading region check state for plot title", exc, logger=w._logger)
                region_visible = True
            if not region_visible:
                continue

            metas: list[dict[str, Any]] = []
            for j in range(region_item.childCount()):
                it = region_item.child(j)
                if it is None:
                    continue
                try:
                    if it.isHidden():
                        continue
                except Exception as exc:
                    log_noncritical_error("checking curve visibility for plot title", exc, logger=w._logger)
                try:
                    if it.checkState(0) != Qt.CheckState.Checked:
                        continue
                except Exception as exc:
                    log_noncritical_error("reading curve check state for plot title", exc, logger=w._logger)
                    continue
                meta = it.data(0, w.ROLE_META)
                if isinstance(meta, dict):
                    metas.append(meta)
            if metas or map_enabled:
                region_entries.append(RegionTitleState(region_name=region_item.text(0), map_enabled=map_enabled, metas=metas))

        show_processed = False
        try:
            cur_is_processed_tab = (w.data_view_splitter.parentWidget() == w.processed_view_holder)
            if cur_is_processed_tab and w._has_any_processed_curves():
                try:
                    show_processed = bool(w.btn_e_cal_toggle.isChecked())
                except Exception:
                    show_processed = True
        except Exception as exc:
            log_noncritical_error("detecting processed state for plot title", exc, logger=w._logger)
            show_processed = False
        return build_plot_title(region_entries, show_processed=show_processed)

    def build_color_list(self, items_in_order: list[tuple[Any, str]]) -> list[str]:
        w = self.window
        cycle = rcParams.get('axes.prop_cycle').by_key().get('color', [])
        if not cycle:
            cycle = [f"C{i}" for i in range(10)]

        color_list: list[str] = []
        for (_item, key) in items_in_order:
            if not key:
                color_list.append(cycle[w._next_color_index % len(cycle)])
                w._next_color_index += 1
                continue
            if key not in w._curve_color_map:
                w._curve_color_map[key] = cycle[w._next_color_index % len(cycle)]
                w._next_color_index += 1
            color_list.append(w._curve_color_map[key])
        return color_list
