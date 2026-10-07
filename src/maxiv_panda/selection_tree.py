from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import QPushButton, QTreeWidgetItem

from .file_naming import curve_detail_sort_key, derive_file_tag, file_number_sort_key, format_curve_source_label


def collect_region_names(files_root: Any) -> list[str]:
    regions: set[str] = set()
    for i in range(files_root.childCount()):
        file_item = files_root.child(i)
        if file_item is None:
            continue
        for j in range(file_item.childCount()):
            region_item = file_item.child(j)
            if region_item is None:
                continue
            name = region_item.text(0).strip()
            if name and name.lower() not in {'warnings'}:
                regions.add(name)
    return sorted(regions)


def iter_curve_leaves(files_root: Any, *, role_payload: int, payload_type: type[Any]) -> list[Any]:
    leaves: list[Any] = []
    for i in range(files_root.childCount()):
        file_item = files_root.child(i)
        if file_item is None:
            continue
        for j in range(file_item.childCount()):
            region_item = file_item.child(j)
            if region_item is None:
                continue
            for k in range(region_item.childCount()):
                child = region_item.child(k)
                if child is None:
                    continue
                payload = child.data(0, role_payload)
                if isinstance(payload, payload_type):
                    leaves.append(child)
                    continue
                for kk in range(child.childCount()):
                    leaf = child.child(kk)
                    if leaf is None:
                        continue
                    payload2 = leaf.data(0, role_payload)
                    if isinstance(payload2, payload_type):
                        leaves.append(leaf)
    return leaves


def is_average_or_trace(meta: dict[str, Any] | None, label: str) -> bool:
    kind = ''
    if isinstance(meta, dict):
        kind = str(meta.get('kind', ''))
    text = label.strip().lower()
    return kind in {'average', 'trace'} or text in {'average', 'trace'}


def should_group_under_region(*, all_in_region_enabled: bool, target_region: str, region_name: str, meta: dict[str, Any] | None, label: str) -> bool:
    if not all_in_region_enabled:
        return False
    return bool(target_region) and region_name == target_region and is_average_or_trace(meta, label)



def determine_selected_parent_file(
    *,
    file_name: str,
    region_name: str,
    meta: dict[str, Any] | None,
    label: str,
    all_in_region_enabled: bool,
    target_region: str,
) -> str:
    """Return the canonical Selected-curves parent identity.

    Ordinary Average/Trace spectra are always grouped by region name,
    independent of *how* the user selected them.  This keeps the right-hand
    Selected curves tree stable for individual checkbox selection, All in
    region, session restoration, and other selection paths.

    Iteration leaves deliberately retain their real source-file parent because
    source identity defines a coherent physical sequence for MAP mode.

    ``all_in_region_enabled`` and ``target_region`` are retained in the
    signature for API/backward compatibility with callers; grouping no longer
    depends on that transient UI state.
    """
    if is_average_or_trace(meta, label):
        return '__GROUP__'
    return file_name


class SelectedTreeManager:
    def __init__(
        self,
        *,
        selected_tree: Any,
        role_payload: int,
        role_key: int,
        role_region: int,
        role_meta: int,
        role_file: int,
        region_items: dict[tuple[str, str], Any],
        selected_by_key: dict[str, Any],
        region_map_buttons: dict[tuple[str, str], Any],
        region_cmap: dict[tuple[str, str], str],
        map_toggle_callback: Any,
        choose_cmap_callback: Any,
    ):
        self.selected_tree = selected_tree
        self.role_payload = role_payload
        self.role_key = role_key
        self.role_region = role_region
        self.role_meta = role_meta
        self.role_file = role_file
        self.region_items = region_items
        self.selected_by_key = selected_by_key
        self.region_map_buttons = region_map_buttons
        self.region_cmap = region_cmap
        self.map_toggle_callback = map_toggle_callback
        self.choose_cmap_callback = choose_cmap_callback

    def ensure_region(self, file_name: str, region_name: str) -> Any:
        key = (file_name, region_name)
        if key in self.region_items:
            return self.region_items[key]

        file_tag = derive_file_tag(file_name)
        if str(file_name) == '__GROUP__':
            parent = QTreeWidgetItem([region_name])
            parent.setData(0, self.role_file, '')
        else:
            parent = QTreeWidgetItem([format_curve_source_label(file_name, region_name)])
            parent.setData(0, self.role_file, file_name)

        parent.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
        parent.setCheckState(0, Qt.CheckState.Checked)
        parent.setData(0, self.role_region, region_name)

        if str(file_name) == '__GROUP__':
            self.selected_tree.addTopLevelItem(parent)
        else:
            self._insert_top_level_sorted(parent, file_name=file_name, region_name=region_name)
        self.region_items[key] = parent

        # A MAP action only makes sense once a region group contains at least
        # two curves.  The button is therefore created lazily when the second
        # child is added, rather than showing a dead action beside standalone
        # 1D spectra.
        self.region_cmap.setdefault(key, 'terrain')
        return parent

    def _create_map_button(self, key: tuple[str, str], parent: Any) -> Any:
        btn = QPushButton('MAP', self.selected_tree)
        btn.setCheckable(True)
        btn.setAutoDefault(False)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setToolTip('Show selected iterations as a 2D map')
        # MAP changes the representation of Processed Data, so make it
        # intentionally more prominent than ordinary tree-row actions.  The
        # palette control now lives in the Processed Data map toolbar, freeing
        # this row to give MAP more width and height without widening the tree.
        btn.setMinimumWidth(72)
        btn.setMaximumWidth(78)
        btn.setMinimumHeight(32)
        parent.setSizeHint(1, QSize(80, 36))
        btn.setStyleSheet(
            'QPushButton { padding: 4px 8px; border: 1px solid #6F8EAD; border-radius: 5px; '
            'background: #E5F0FA; color: #1E3F5D; font-weight: 700; }'
            'QPushButton:hover { background: #D3E8F8; border-color: #4F769B; }'
            'QPushButton:pressed { background: #C4DFF4; }'
            'QPushButton:checked { background: #B9D9F2; border: 2px solid #3F6F99; color: #17364F; }'
            'QPushButton:disabled { background: #F0F1F2; color: #A3A7AB; border-color: #D0D3D6; }'
        )
        btn.toggled.connect(lambda checked, it=parent: self.map_toggle_callback(it, checked))
        self.selected_tree.setItemWidget(parent, 1, btn)
        self.region_map_buttons[key] = btn
        return btn

    def _sync_map_button(self, key: tuple[str, str], parent: Any) -> None:
        """Show MAP only for genuine multi-iteration datasets.

        Synthetic ``All in...`` groups collect independent spectra from different
        source files and do not define a physical second map dimension.  Likewise,
        a group of ordinary 1D traces is not map-capable merely because it has
        multiple children.  Require at least two iteration leaves from one real
        source group before exposing the MAP action.
        """
        existing = self.region_map_buttons.get(key)
        source_group, _region = key
        iteration_count = 0
        if str(source_group) != '__GROUP__':
            for index in range(parent.childCount()):
                child = parent.child(index)
                if child is None:
                    continue
                meta = child.data(0, self.role_meta)
                if isinstance(meta, dict) and meta.get('kind') == 'iteration' and isinstance(meta.get('iteration'), int):
                    iteration_count += 1
        should_show = iteration_count >= 2
        if should_show and existing is None:
            self._create_map_button(key, parent)
            return
        if should_show or existing is None:
            return

        # If a map-capable group shrinks back to one curve, leave map mode
        # cleanly before removing its now-misleading action.
        try:
            if existing.isChecked():
                existing.setChecked(False)
        except Exception:
            pass
        self.selected_tree.removeItemWidget(parent, 1)
        self.region_map_buttons.pop(key, None)
        parent.setSizeHint(1, QSize(0, 0))

    def _region_key_for_parent(self, parent: Any) -> tuple[str, str] | None:
        for key, item in self.region_items.items():
            if item is parent:
                return key
        return None

    def _insert_top_level_sorted(self, parent: Any, *, file_name: str, region_name: str) -> None:
        """Insert a selected-curve group in ascending acquisition-number order."""
        new_key = (file_number_sort_key(file_name), str(region_name).casefold())
        insert_at = self.selected_tree.topLevelItemCount()
        for index in range(self.selected_tree.topLevelItemCount()):
            current = self.selected_tree.topLevelItem(index)
            if current is None:
                continue
            current_file = current.data(0, self.role_file)
            if not isinstance(current_file, str) or not current_file:
                # Grouped "All in region" entries are intentionally left where
                # they are; numeric source groups are ordered around real files.
                continue
            current_region = current.data(0, self.role_region)
            current_key = (
                file_number_sort_key(current_file),
                str(current_region or '').casefold(),
            )
            if new_key < current_key:
                insert_at = index
                break
        self.selected_tree.insertTopLevelItem(insert_at, parent)

    def _insert_child_sorted(self, parent: Any, child: Any, *, source_file: str, display: str, meta: Any = None) -> None:
        """Keep children ordered by source acquisition number and iteration."""
        meta_dict = meta if isinstance(meta, dict) else None
        new_key = (file_number_sort_key(source_file), curve_detail_sort_key(meta_dict, display))

        # Rebuilds normally receive leaves already in acquisition/iteration
        # order.  Appending in that common case avoids an O(n^2) scan through
        # existing children (and repeated Qt QVariant -> Python metadata
        # conversions) when hundreds of iterations are selected at once.
        count = parent.childCount()
        if count:
            last = parent.child(count - 1)
            if last is not None:
                last_file = last.data(0, self.role_file)
                if not isinstance(last_file, str):
                    last_file = ''
                last_meta = last.data(0, self.role_meta)
                last_meta_dict = last_meta if isinstance(last_meta, dict) else None
                last_key = (
                    file_number_sort_key(last_file),
                    curve_detail_sort_key(last_meta_dict, str(last.text(0))),
                )
                if new_key >= last_key:
                    parent.addChild(child)
                    return

        insert_at = count
        for index in range(count):
            current = parent.child(index)
            if current is None:
                continue
            current_file = current.data(0, self.role_file)
            if not isinstance(current_file, str):
                current_file = ''
            current_meta = current.data(0, self.role_meta)
            current_meta_dict = current_meta if isinstance(current_meta, dict) else None
            current_key = (
                file_number_sort_key(current_file),
                curve_detail_sort_key(current_meta_dict, str(current.text(0))),
            )
            if new_key < current_key:
                insert_at = index
                break
        parent.insertChild(insert_at, child)

    def add_from_loaded_item(
        self,
        *,
        loaded_item: Any,
        all_in_region_enabled: bool,
        target_region: str,
    ) -> bool:
        payload = loaded_item.data(0, self.role_payload)
        key_display = loaded_item.data(0, self.role_key)
        region_name = loaded_item.data(0, self.role_region)
        if not isinstance(key_display, tuple) or not isinstance(region_name, str):
            return False
        key, display = key_display
        file_name = loaded_item.data(0, self.role_file)
        if not isinstance(file_name, str):
            file_name = ''
        meta = loaded_item.data(0, self.role_meta)
        meta_dict = meta if isinstance(meta, dict) else None
        parent_file = determine_selected_parent_file(
            file_name=file_name,
            region_name=region_name,
            meta=meta_dict,
            label=loaded_item.text(0),
            all_in_region_enabled=all_in_region_enabled,
            target_region=target_region,
        )
        self.add_selected_leaf(
            parent_file=parent_file,
            region_name=region_name,
            display=display,
            key=str(key),
            payload=payload,
            meta=meta,
            source_file=file_name,
        )
        return True

    def rebuild_from_loaded(
        self,
        *,
        loaded_items: list[Any],
        all_in_region_enabled: bool,
        target_region: str,
    ) -> None:
        # The left-hand loaded-data tree controls *membership* of the selected
        # curves list.  The checkboxes in the selected-curves tree independently
        # control plot visibility.  Rebuilding the selected tree must therefore
        # preserve the visibility state of curves that were already present.
        # Only genuinely new curves receive the normal default (Checked).
        previous_check_states: dict[str, Any] = {}
        for key, selected_item in self.selected_by_key.items():
            try:
                previous_check_states[str(key)] = selected_item.checkState(0)
            except Exception:
                pass

        self.clear()
        for item in loaded_items:
            added = self.add_from_loaded_item(
                loaded_item=item,
                all_in_region_enabled=all_in_region_enabled,
                target_region=target_region,
            )
            if not added:
                continue
            key_display = item.data(0, self.role_key)
            if not isinstance(key_display, tuple) or not key_display:
                continue
            key = str(key_display[0])
            if key not in previous_check_states:
                continue
            selected_item = self.selected_by_key.get(key)
            if selected_item is not None:
                selected_item.setCheckState(0, previous_check_states[key])

    def add_selected_leaf(
        self,
        *,
        parent_file: str,
        region_name: str,
        display: str,
        key: str,
        payload: Any,
        meta: Any,
        source_file: str | None = None,
    ) -> Any:
        if key in self.selected_by_key:
            return self.selected_by_key[key]
        parent = self.ensure_region(parent_file, region_name)
        sel = QTreeWidgetItem([display])
        sel.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
        sel.setCheckState(0, Qt.CheckState.Checked)
        sel.setData(0, self.role_payload, payload)
        sel.setData(0, self.role_key, key)
        sel.setData(0, self.role_region, region_name)
        sel.setData(0, self.role_meta, meta)
        effective_source_file = str(source_file if source_file is not None else parent_file)
        sel.setData(0, self.role_file, effective_source_file)
        self._insert_child_sorted(
            parent,
            sel,
            source_file=effective_source_file,
            display=display,
            meta=meta,
        )
        parent.setExpanded(True)
        self.selected_by_key[str(key)] = sel
        region_key = (parent_file, region_name)
        self._sync_map_button(region_key, parent)
        return sel

    def remove_selected_leaf(self, key: str) -> bool:
        if key not in self.selected_by_key:
            return False
        sel = self.selected_by_key.pop(key)
        parent = sel.parent()
        if parent is not None:
            parent.removeChild(sel)
            rkey = self._region_key_for_parent(parent)
            if rkey is not None and parent.childCount() > 0:
                self._sync_map_button(rkey, parent)
            if parent.childCount() == 0:
                if rkey is not None:
                    idx = self.selected_tree.indexOfTopLevelItem(parent)
                    if idx >= 0:
                        self.selected_tree.takeTopLevelItem(idx)
                    self.region_items.pop(rkey, None)
                    self.region_map_buttons.pop(rkey, None)
        return True

    def clear(self) -> None:
        self.selected_tree.clear()
        self.selected_by_key.clear()
        self.region_items.clear()
        self.region_map_buttons.clear()

    def sync_loaded_leaf(
        self,
        *,
        loaded_item: Any,
        checked: bool,
        all_in_region_enabled: bool,
        target_region: str,
    ) -> bool:
        payload = loaded_item.data(0, self.role_payload)
        key_display = loaded_item.data(0, self.role_key)
        region_name = loaded_item.data(0, self.role_region)
        if not isinstance(key_display, tuple) or not isinstance(region_name, str):
            return False
        key, display = key_display
        file_name = loaded_item.data(0, self.role_file)
        if not isinstance(file_name, str):
            file_name = ''
        meta = loaded_item.data(0, self.role_meta)
        meta_dict = meta if isinstance(meta, dict) else None

        if checked:
            self.add_from_loaded_item(
                loaded_item=loaded_item,
                all_in_region_enabled=all_in_region_enabled,
                target_region=target_region,
            )
        else:
            self.remove_selected_leaf(str(key))
        return True
