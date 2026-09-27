from __future__ import annotations

import re
from typing import Any

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QPushButton, QTreeWidgetItem

from ...colormap_dialog import choose_colormap
from ...file_naming import file_number_sort_key
from ...ui import PlotPayload
from ...utils.colors import mpl_color_to_hex

class BatchSelectionMixin:
    """Extracted behavior for the batch Prepare workflow."""

    def _collect_original_entries_from_main_selected(self) -> None:
        """Build the batch sequence from the exact selection passed to the dialog.

        ``open_fit_corelevel_dialog`` already filters the main Selected-curves
        tree to checked *and visible* leaves.  Re-scanning the whole main tree
        here used to reintroduce hidden raw curves when the Processed tab was
        showing only E-calibrated curves.  Treat ``self._selected_items`` as the
        authoritative snapshot and only use the main tree to recover metadata.
        """
        self._original_entries.clear()

        selected_by_key = getattr(self._mw, "_selected_by_key", {})
        role_region = getattr(self._mw, "ROLE_REGION", self.ROLE_REGION)
        role_file = getattr(self._mw, "ROLE_FILE", self.ROLE_FILE)
        role_meta = getattr(self._mw, "ROLE_META", self.ROLE_META)

        for key, payload, label in list(self._selected_items):
            key = str(key)
            src_child = selected_by_key.get(key) if isinstance(selected_by_key, dict) else None

            region_name = ""
            file_name = ""
            meta = None
            display = str(label or getattr(payload, "title", key))

            if src_child is not None:
                try:
                    region_name = src_child.data(0, role_region)
                except Exception:
                    region_name = ""
                try:
                    file_name = src_child.data(0, role_file)
                except Exception:
                    file_name = ""
                try:
                    meta = src_child.data(0, role_meta)
                except Exception:
                    meta = None
                try:
                    display = src_child.text(0) or display
                except Exception:
                    pass

                # Some older/synthetic leaves keep region/file identity only on
                # the parent.  Recover it there without changing the selection.
                try:
                    parent = src_child.parent()
                except Exception:
                    parent = None
                if parent is not None:
                    if not isinstance(region_name, str) or not region_name:
                        try:
                            region_name = parent.data(0, role_region)
                        except Exception:
                            pass
                    if not isinstance(file_name, str) or not file_name:
                        try:
                            file_name = parent.data(0, role_file)
                        except Exception:
                            pass

            if not isinstance(region_name, str):
                region_name = str(region_name or "")
            if not isinstance(file_name, str):
                file_name = str(file_name or "")

            self._original_entries.append({
                "file_name": file_name,
                "region_name": region_name,
                "display": display,
                "key": key,
                "payload": payload,
                "meta": meta,
            })

        self._original_checked_keys = {str(e["key"]) for e in self._original_entries}


    def _base_region_name(self, region_name: str) -> str:
        """Return the source-region identity shared by original and binned views."""
        return re.sub(r"\s+—\s+binned by \d+\s*$", "", str(region_name)).strip()


    def _base_region_key(self, file_name: str, region_name: str) -> tuple[str, str]:
        return (str(file_name or ""), self._base_region_name(region_name))


    def _capture_region_view_state(self) -> None:
        """Preserve map/cmap state across original/binned tree rebuilds."""
        for (file_name, region_name), btn in list(self._region_map_buttons.items()):
            base_key = self._base_region_key(file_name, region_name)
            try:
                if bool(btn.isChecked()):
                    self._map_enabled_bases.add(base_key)
                else:
                    self._map_enabled_bases.discard(base_key)
            except Exception:
                pass
            cmap = self._region_cmap.get((file_name, region_name))
            if isinstance(cmap, str) and cmap:
                self._cmap_by_base[base_key] = cmap


    def _restore_region_view_state(self) -> None:
        """Apply preserved map/cmap state to a freshly rebuilt tree."""
        for (file_name, region_name), btn in list(self._region_map_buttons.items()):
            base_key = self._base_region_key(file_name, region_name)
            if base_key in self._cmap_by_base:
                self._region_cmap[(file_name, region_name)] = self._cmap_by_base[base_key]
            try:
                btn.blockSignals(True)
                btn.setChecked(base_key in self._map_enabled_bases)
            except Exception:
                pass
            finally:
                try:
                    btn.blockSignals(False)
                except Exception:
                    pass


    def _populate_tree_from_entries(self, entries: list[dict[str, Any]], *, mode: str) -> None:
        """Populate the batch tree as one top-level row per spectrum.

        The main Selected-curves widget is hierarchical (source/region parent +
        curve child), but that hierarchy is redundant in batch fitting because
        each row represents one spectrum that can independently be included in
        the sequence.  Keeping the batch tree flat avoids duplicate parent/child
        checkboxes while preserving the source label, color marker and map/cmap
        controls for the first row of each source-region group.
        """
        self._capture_region_view_state()
        self._updating_tree = True
        self.selected_tree.blockSignals(True)
        try:
            self.selected_tree.clear()
            self._selected_by_key.clear()
            self._selected_region_items.clear()
            self._region_map_buttons.clear()
            self._region_cmap.clear()
            self._region_iteration_stack.clear()

            if mode == "original":
                src_stacks = getattr(self._mw, "_region_iteration_stack", {})
                for rkey, stack in src_stacks.items():
                    self._region_iteration_stack[rkey] = stack

            checked_keys = self._original_checked_keys if mode == "original" else self._binned_checked_keys
            ordered_entries = sorted(
                list(entries),
                key=lambda e: (
                    file_number_sort_key(str(e.get("file_name", ""))),
                    str(e.get("display", "")).casefold(),
                    str(e.get("key", "")).casefold(),
                ),
            )

            for entry in ordered_entries:
                file_name = str(entry.get("file_name", ""))
                region_name = str(entry.get("region_name", ""))
                display = str(entry.get("display", ""))
                key = str(entry.get("key", ""))

                item = QTreeWidgetItem([display, "", ""])
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked if (not checked_keys or key in checked_keys) else Qt.CheckState.Unchecked)
                item.setData(0, self.ROLE_KEY, key)
                item.setData(0, self.ROLE_PAYLOAD, entry.get("payload"))
                item.setData(0, self.ROLE_REGION, region_name)
                item.setData(0, self.ROLE_FILE, file_name)
                item.setData(0, self.ROLE_META, entry.get("meta"))
                self.selected_tree.addTopLevelItem(item)
                self._selected_by_key[key] = item

                # Keep one map/cmap control pair for each source-region group.
                # If several actual spectra belong to the same group, only the
                # first row carries the controls; all rows remain independent
                # one-checkbox spectra.
                rkey = (file_name, region_name)
                if rkey not in self._selected_region_items:
                    self._selected_region_items[rkey] = item
                    btn = QPushButton("map", self.selected_tree)
                    btn.setCheckable(True)
                    btn.setAutoDefault(False)
                    btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    btn.setToolTip("Show selected iterations as a colormap")
                    btn.setMinimumWidth(42)
                    btn.setMaximumWidth(60)
                    btn.setStyleSheet(
                        "QPushButton { padding: 2px 6px; border: 1px solid #888; border-radius: 4px; }"
                        "QPushButton:checked { border: 2px solid #444; font-weight: bold; }"
                    )
                    btn.toggled.connect(lambda checked, it=item: self._on_region_map_toggled(it, checked))
                    self.selected_tree.setItemWidget(item, 1, btn)
                    self._region_map_buttons[rkey] = btn

                    # Palette is changed by right-clicking the active 2D map.
                    self._region_cmap.setdefault(rkey, "terrain")

            self._restore_region_view_state()
        finally:
            self.selected_tree.blockSignals(False)
            self._updating_tree = False
        self._tree_mode = mode


    def _binned_mode_active(self) -> bool:
        """Return whether sequence binning changes the effective spectra.

        Bin size 1 is deliberately the unbinned/default state, so there is no
        separate enable flag to keep in sync.
        """
        try:
            return int(self.sb_bin_size.value()) > 1
        except Exception:
            return False


    def _remember_visible_tree_checks(self) -> None:
        checked: set[str] = set()
        for i in range(self.selected_tree.topLevelItemCount()):
            item = self.selected_tree.topLevelItem(i)
            if item is None:
                continue
            try:
                if item.isHidden() or item.checkState(0) != Qt.CheckState.Checked:
                    continue
            except Exception:
                continue
            key = item.data(0, self.ROLE_KEY)
            if isinstance(key, str):
                checked.add(key)
        if self._tree_mode == "binned":
            self._binned_checked_keys = checked
        else:
            self._original_checked_keys = checked


    def _rebuild_tree_for_current_binning(self) -> None:
        self._remember_visible_tree_checks()
        if self._binned_mode_active():
            entries, _discarded = self._build_binned_entries()
            entry_keys = {str(e["key"]) for e in entries}
            # A changed bin size creates a new set of synthetic keys. In that case,
            # default to all new bins checked rather than carrying over a stale
            # empty intersection from the previous binning.
            if not self._binned_checked_keys or not (self._binned_checked_keys & entry_keys):
                self._binned_checked_keys = set(entry_keys)
            self._populate_tree_from_entries(entries, mode="binned")
            self._install_binned_iteration_stacks(entries)
        else:
            self._populate_tree_from_entries(self._original_entries, mode="original")


    def _on_binning_settings_changed(self, *_args: Any) -> None:
        # If a large group checkbox operation has just happened, make sure the
        # latest visible check state is captured before rebuilding the tree.
        # Do not force an intermediate redraw here; the rebuilt effective tree
        # will be drawn once below.
        try:
            if self._prepare_update_timer.isActive():
                self._prepare_update_timer.stop()
        except Exception:
            pass
        self._defer_remember_visible_checks = False
        self._remember_visible_tree_checks()
        self._rebuild_tree_for_current_binning()
        self._invalidate_anchors("binning changed")
        self._update_prepare_plot_from_selected()


    def _schedule_prepare_plot_update(self, *, remember_checks: bool = True) -> None:
        """Coalesce checkbox storms into one tree-state capture and redraw.

        Group checking/unchecking in a QTreeWidget can emit one itemChanged
        signal per child. Redrawing Plot A for every child makes large sequence
        selections feel frozen. A short single-shot timer lets Qt finish the
        checkbox cascade first, then updates the effective sequence once.
        """
        if remember_checks:
            self._defer_remember_visible_checks = True
        try:
            self._prepare_update_timer.start(0)
        except Exception:
            self._run_deferred_prepare_update()


    def _run_deferred_prepare_update(self) -> None:
        if self._updating_tree:
            self._schedule_prepare_plot_update(remember_checks=self._defer_remember_visible_checks)
            return
        if self._defer_remember_visible_checks:
            self._defer_remember_visible_checks = False
            self._remember_visible_tree_checks()
            self._invalidate_anchors("selection changed")
        self._update_prepare_plot_from_selected()


    def _on_selected_tree_item_pressed(self, item: QTreeWidgetItem, column: int) -> None:
        self._last_selected_tree_press = (item, column)


    def _on_selected_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._updating_tree or column != 0:
            return
        if item.parent() is None:
            region_name = str(item.data(0, self.ROLE_REGION) or item.text(0))
            file_name = item.data(0, self.ROLE_FILE)
            rkey = (file_name, region_name) if isinstance(file_name, str) else None
            btn = self._region_map_buttons.get(rkey) if rkey is not None else None
            try:
                region_state = item.checkState(0)
            except Exception:
                region_state = Qt.CheckState.Checked
            if btn is not None:
                pressed = self._last_selected_tree_press
                user_clicked_this = (pressed is not None and pressed[0] is item and pressed[1] == 0)
                try:
                    if user_clicked_this and btn.isChecked() and region_state != Qt.CheckState.Unchecked:
                        self.selected_tree.blockSignals(True)
                        try:
                            btn.setChecked(False)
                        finally:
                            self.selected_tree.blockSignals(False)
                        self._on_region_map_toggled(item, False)
                except Exception:
                    pass
            self._last_selected_tree_press = None
        self._schedule_prepare_plot_update(remember_checks=True)


    def _choose_active_map_cmap(self) -> None:
        """Open the palette chooser for the active Prepare 2D map."""
        for key, button in getattr(self, "_region_map_buttons", {}).items():
            try:
                if button is not None and button.isChecked():
                    file_name, region_name = key
                    self._choose_region_cmap(file_name, region_name)
                    self._schedule_prepare_plot_update(remember_checks=True)
                    return
            except Exception:
                continue

    def _choose_region_cmap(self, file_name: str, region_name: str) -> None:
        key = (file_name, region_name)
        current = self._region_cmap.get(key, 'terrain')
        choice = choose_colormap(self, current)
        if not choice:
            return
        choice_str = str(choice)
        self._region_cmap[key] = choice_str
        self._cmap_by_base[self._base_region_key(file_name, region_name)] = choice_str

    def _on_region_map_toggled(self, region_item: QTreeWidgetItem, checked: bool) -> None:
        file_name = region_item.data(0, self.ROLE_FILE)
        region_name = str(region_item.data(0, self.ROLE_REGION) or region_item.text(0))
        if isinstance(file_name, str):
            base_key = self._base_region_key(file_name, region_name)
            if checked:
                self._map_enabled_bases.add(base_key)
            else:
                self._map_enabled_bases.discard(base_key)
        self._update_prepare_plot_from_selected()


    def _checked_leaf_items(self) -> list[QTreeWidgetItem]:
        """Return checked batch spectra; the batch tree is intentionally flat."""
        items: list[QTreeWidgetItem] = []
        for i in range(self.selected_tree.topLevelItemCount()):
            item = self.selected_tree.topLevelItem(i)
            if item is None:
                continue
            try:
                if item.isHidden() or item.checkState(0) != Qt.CheckState.Checked:
                    continue
            except Exception:
                continue
            if item.data(0, self.ROLE_PAYLOAD) is not None:
                items.append(item)
        return items


    def _source_iteration_number(self, entry: dict[str, Any], fallback: int) -> int | None:
        meta = entry.get("meta")
        if isinstance(meta, dict):
            it = meta.get("iteration")
            if isinstance(it, int):
                return it
            try:
                if it is not None:
                    return int(it)
            except Exception:
                pass
        text = str(entry.get("display", ""))
        m = re.search(r"(?:iteration|it)\D*(\d+)", text, flags=re.IGNORECASE)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                pass
        return fallback


    def _format_source_iteration_span(self, iterations: list[int | None], labels: list[str]) -> str:
        vals = [int(v) for v in iterations if isinstance(v, int)]
        if vals and len(vals) == len(iterations):
            width = max(3, len(str(max(vals))))
            contiguous = vals == list(range(vals[0], vals[-1] + 1))
            if contiguous:
                return f"it{vals[0]:0{width}d}–it{vals[-1]:0{width}d}"
            if len(vals) <= 4:
                return ",".join(f"it{v:0{width}d}" for v in vals)
            return f"it{vals[0]:0{width}d},it{vals[1]:0{width}d}…it{vals[-1]:0{width}d} ({len(vals)} it.)"
        if labels:
            if len(labels) == 1:
                return labels[0]
            return f"curves 001–{len(labels):03d}"
        return "curves"


    def _build_binned_entries(self) -> tuple[list[dict[str, Any]], int]:
        bin_size = max(1, int(self.sb_bin_size.value()))
        if bin_size <= 1:
            return list(self._original_entries), 0
        active = [e for e in self._original_entries if str(e.get("key", "")) in self._original_checked_keys]
        out: list[dict[str, Any]] = []
        discarded_total = 0
        # Bin separately per original region/file group to avoid silently mixing
        # unrelated source groups.
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for entry in active:
            grouped.setdefault((str(entry.get("file_name", "")), str(entry.get("region_name", ""))), []).append(entry)
        for (file_name, region_name), entries in grouped.items():
            usable = (len(entries) // bin_size) * bin_size
            discarded_total += len(entries) - usable
            if usable <= 0:
                continue
            for start in range(0, usable, bin_size):
                chunk = entries[start:start + bin_size]
                x_arrays: list[np.ndarray] = []
                y_arrays: list[np.ndarray] = []
                min_len: int | None = None
                for entry in chunk:
                    p = entry.get("payload")
                    try:
                        x = np.asarray(p.x, dtype=float)
                        y = np.asarray(p.y, dtype=float)
                    except Exception:
                        continue
                    n = min(x.size, y.size)
                    if n <= 0:
                        continue
                    min_len = n if min_len is None else min(min_len, n)
                    x_arrays.append(x)
                    y_arrays.append(y)
                if not x_arrays or min_len is None or min_len <= 0:
                    continue
                x_stack = np.vstack([x[:min_len] for x in x_arrays])
                y_stack = np.vstack([y[:min_len] for y in y_arrays])
                x_avg = np.nanmean(x_stack, axis=0)
                y_avg = np.nanmean(y_stack, axis=0)
                bin_index = (start // bin_size) + 1
                iterations = [self._source_iteration_number(e, start + idx + 1) for idx, e in enumerate(chunk)]
                labels = [str(e.get("display", "")) for e in chunk]
                span = self._format_source_iteration_span(iterations, labels)
                display = f"bin{bin_index:03d}: {span}"
                title = display
                first_payload = chunk[0].get("payload")
                payload = PlotPayload(
                    title=title,
                    x=x_avg,
                    y=y_avg,
                    xlabel=getattr(first_payload, "xlabel", "x"),
                    ylabel=getattr(first_payload, "ylabel", "Intensity"),
                    energy_scale=getattr(first_payload, "energy_scale", "Unknown"),
                )
                meta = {
                    "kind": "binned",
                    "iteration": bin_index,
                    "bin_index": bin_index,
                    "bin_size": bin_size,
                    "source_iterations": [v for v in iterations if isinstance(v, int)],
                    "source_labels": labels,
                    "source_keys": [str(e.get("key", "")) for e in chunk],
                }
                out.append({
                    "file_name": file_name,
                    "region_name": f"{region_name} — binned by {bin_size}",
                    "display": display,
                    "key": f"bin:{file_name}:{region_name}:{bin_size}:{bin_index:03d}",
                    "payload": payload,
                    "meta": meta,
                })
        return out, discarded_total


    def _install_binned_iteration_stacks(self, entries: list[dict[str, Any]]) -> None:
        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for entry in entries:
            grouped.setdefault((str(entry.get("file_name", "")), str(entry.get("region_name", ""))), []).append(entry)
        for rkey, group in grouped.items():
            rows: list[np.ndarray] = []
            x_ref = None
            xlabel = "x"
            min_len: int | None = None
            for entry in group:
                p = entry.get("payload")
                try:
                    x = np.asarray(p.x, dtype=float)
                    y = np.asarray(p.y, dtype=float)
                except Exception:
                    continue
                n = min(x.size, y.size)
                if n <= 0:
                    continue
                min_len = n if min_len is None else min(min_len, n)
                if x_ref is None:
                    x_ref = x
                    xlabel = getattr(p, "xlabel", "x")
                rows.append(y)
            if x_ref is None or not rows or min_len is None or min_len <= 0:
                continue
            self._region_iteration_stack[rkey] = (x_ref[:min_len], [row[:min_len] for row in rows], xlabel)


    def _bin_image_payloads(self, images: list[tuple[Any, Any, Any, str, str, str]]) -> tuple[list[tuple[Any, Any, Any, str, str, str]], int]:
        # Kept for compatibility with older tree modes. In the current effective
        # binned-tree mode the image payloads are already built from binned rows.
        bin_size = int(self.sb_bin_size.value())
        if bin_size <= 1:
            return images, 0
        return images, 0


    def _apply_curve_color_icons(self, items: list[tuple[Any, str]], colors: list[Any]) -> None:
        self.selected_tree.blockSignals(True)
        try:
            for (it, _key), col in zip(items, colors):
                if it is None:
                    continue
                try:
                    pix = QPixmap(12, 12)
                    pix.fill(QColor(mpl_color_to_hex(col)))
                    it.setIcon(0, QIcon(pix))
                except Exception:
                    pass
        finally:
            self.selected_tree.blockSignals(False)


    def _prepare_plot_title(self, *, checked_count: int, images: list[Any], payloads: list[PlotPayload]) -> str:
        """Return a sequence-level title for Plot A.

        PlotArea.plot_many() defaults to the title of the first curve. That is
        useful on the main window, but misleading in the sequence-preparation
        view where Plot A represents the full effective set. Build a compact
        title from the visible tree instead.
        """
        regions: list[str] = []
        try:
            for i in range(self.selected_tree.topLevelItemCount()):
                item = self.selected_tree.topLevelItem(i)
                if item is None:
                    continue
                try:
                    if item.checkState(0) != Qt.CheckState.Checked:
                        continue
                except Exception:
                    continue
                name = str(item.data(0, self.ROLE_REGION) or "")
                if name and name not in regions:
                    regions.append(name)
        except Exception:
            regions = []

        count = int(checked_count)
        if count <= 0:
            if payloads:
                count = len(payloads)
            elif images:
                try:
                    count = sum(len(img[1]) for img in images)
                except Exception:
                    count = len(images)

        spectrum_word = "spectrum" if count == 1 else "spectra"
        if not regions:
            base = "Sequence preview"
        elif len(regions) == 1:
            base = regions[0]
        else:
            base = f"{len(regions)} sequence groups"
        return f"{base} ({count} {spectrum_word})"


    def _collect_flat_batch_selection(self):
        """Collect line/map payloads from the flat batch spectrum list.

        This mirrors the subset of PlotSelectionController needed by the batch
        Prepare tab, but treats every top-level item as an actual spectrum.
        """
        payloads: list[Any] = []
        items_in_order: list[tuple[Any, str]] = []
        images: list[Any] = []

        checked_by_region: dict[tuple[str, str], list[QTreeWidgetItem]] = {}
        for item in self._checked_leaf_items():
            file_name = item.data(0, self.ROLE_FILE)
            region_name = str(item.data(0, self.ROLE_REGION) or "")
            rkey = (file_name, region_name) if isinstance(file_name, str) else None
            if rkey is not None:
                checked_by_region.setdefault(rkey, []).append(item)

        mapped_regions: set[tuple[str, str]] = set()
        for i in range(self.selected_tree.topLevelItemCount()):
            item = self.selected_tree.topLevelItem(i)
            if item is None:
                continue
            try:
                if item.isHidden() or item.checkState(0) != Qt.CheckState.Checked:
                    continue
            except Exception:
                continue

            file_name = item.data(0, self.ROLE_FILE)
            region_name = str(item.data(0, self.ROLE_REGION) or "")
            rkey = (file_name, region_name) if isinstance(file_name, str) else None
            btn = self._region_map_buttons.get(rkey) if rkey is not None else None
            map_enabled = bool(btn.isChecked()) if btn is not None else False

            if map_enabled and rkey is not None and rkey not in mapped_regions:
                mapped_regions.add(rkey)
                stack = self._region_iteration_stack.get(rkey)
                if stack is not None:
                    x, Y, xlabel = stack[:3]
                    dim2_values = stack[3] if len(stack) >= 4 else None
                    dim2_name = stack[4] if len(stack) >= 5 else ""
                    selected_iters: list[int] = []
                    for ch in checked_by_region.get(rkey, []):
                        meta = ch.data(0, self.ROLE_META)
                        if isinstance(meta, dict):
                            it_no = meta.get("iteration")
                            if isinstance(it_no, int):
                                selected_iters.append(it_no)
                    selected_iters = sorted(set(selected_iters))
                    if selected_iters:
                        y = []
                        Y_sel = []
                        secondary_y = [] if dim2_values is not None else None
                        for it_no in selected_iters:
                            idx = it_no - 1
                            if 0 <= idx < len(Y):
                                y.append(it_no)
                                Y_sel.append(Y[idx])
                                if secondary_y is not None:
                                    try:
                                        secondary_y.append(dim2_values[idx])
                                    except Exception:
                                        secondary_y = None
                        if Y_sel:
                            cmap_name = self._region_cmap.get(rkey, "terrain")
                            images.append((
                                x, y, Y_sel, f"{region_name} (map)", xlabel, cmap_name,
                                secondary_y, str(dim2_name or ""),
                            ))
                continue

            # If this row belongs to a region currently shown as a map, do not
            # overlay its line on the map.
            if map_enabled:
                continue
            p = item.data(0, self.ROLE_PAYLOAD)
            if p is not None:
                payloads.append(p)
                key = item.data(0, self.ROLE_KEY)
                items_in_order.append((item, key if isinstance(key, str) else ""))

        return payloads, items_in_order, images


    def _update_prepare_plot_from_selected(self) -> None:
        payloads, items_in_order, images = self._collect_flat_batch_selection()

        # In the batch-preparation window, map mode should be a clean 2D
        # representation of the selected/effective sequence. The generic
        # PlotSelectionController supports line overlays on top of maps for
        # the main window, but here overlays duplicate the map content and are
        # visually confusing.
        if images:
            payloads = []
            items_in_order = []

        checked_count = len(self._checked_leaf_items())
        discarded = 0
        if self._binned_mode_active():
            try:
                _entries, discarded = self._build_binned_entries()
            except Exception:
                discarded = 0
        effective_count = len(payloads)
        if images and not payloads:
            try:
                effective_count = max((len(img[1]) for img in images), default=0)
            except Exception:
                effective_count = 0
        if self._binned_mode_active():
            original_checked = len([e for e in self._original_entries if str(e.get("key", "")) in self._original_checked_keys])
            total_binned = len(self._build_binned_entries()[0])
            self.lab_binning_info.setText(
                f"{original_checked} → {total_binned} binned"
                + (f" (+{discarded} discarded)" if discarded else "")
                + (f"; {checked_count} checked" if checked_count != total_binned else "")
            )
            self.lab_binning_info.setVisible(True)
        else:
            self.lab_binning_info.clear()
            self.lab_binning_info.setVisible(False)
        if not payloads and not images:
            self.plot_sequence.clear("No checked curves to display")
            self._style_prepare_plot_area(self.plot_sequence)
            self._compact_plot_margins(self.plot_sequence)
            return

        flip_be = bool(getattr(self._mw, "cb_flip_be", None).isChecked()) if getattr(self._mw, "cb_flip_be", None) is not None else False
        color_list = self._plot_selection_controller.build_color_list(items_in_order)
        display_payloads = self._apply_waterfall_offsets(payloads) if payloads and not images else payloads
        display_colors = self._waterfall_color_list(len(display_payloads)) if display_payloads and not images else None
        if display_colors is None:
            display_colors = color_list
        used_colors = self.plot_sequence.plot_many(display_payloads, flip_binding_energy=flip_be, colors=display_colors, images=images)
        try:
            self.plot_sequence.ax.set_title(self._prepare_plot_title(checked_count=checked_count, images=images, payloads=display_payloads))
        except Exception:
            pass
        self._style_prepare_plot_area(self.plot_sequence)
        self._compact_plot_margins(self.plot_sequence)
        self._apply_curve_color_icons(items_in_order, used_colors)


