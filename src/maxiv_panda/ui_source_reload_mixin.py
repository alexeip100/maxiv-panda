from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from .source_snapshots import (
    SourceDependencySummary,
    SourceSnapshot,
    canonical_source_path,
    make_source_snapshot,
    updated_source_label,
)


class UiSourceReloadMixin:
    """Central source-snapshot lookup, dependency checks, and reload policy."""

    def _iter_loaded_file_items(self):
        root = getattr(self, "_files_root", None)
        if root is None:
            return
        for index in range(root.childCount()):
            item = root.child(index)
            if item is not None:
                yield item

    def _loaded_file_item_for_path(self, path: str | Path):
        wanted = canonical_source_path(path)
        matches = []
        for item in self._iter_loaded_file_items() or ():
            meta = item.data(0, self.ROLE_META)
            if not isinstance(meta, dict):
                continue
            existing = str(meta.get("source_canonical_path") or "")
            if not existing:
                existing = canonical_source_path(meta.get("file_path") or "")
            if existing == wanted:
                matches.append(item)
        # If several immutable snapshots of one path are present, treat the most
        # recently loaded one as the current snapshot for another Load action.
        return matches[-1] if matches else None

    def _snapshot_from_file_item(self, item) -> SourceSnapshot | None:
        if item is None:
            return None
        meta = item.data(0, self.ROLE_META)
        if not isinstance(meta, dict):
            return None
        sid = str(meta.get("source_snapshot_id") or "")
        if not sid:
            return None
        return SourceSnapshot(
            snapshot_id=sid,
            canonical_path=str(meta.get("source_canonical_path") or ""),
            physical_path=str(meta.get("source_physical_path") or meta.get("file_path") or ""),
            file_name=str(meta.get("file_name") or item.text(0) or ""),
            source_label=str(meta.get("source_label") or item.text(0) or ""),
            loaded_at=str(meta.get("source_loaded_at") or ""),
            file_mtime_ns=meta.get("source_file_mtime_ns"),
            file_size=meta.get("source_file_size"),
        )

    def _source_dependency_summary(self, snapshot_id: str) -> SourceDependencySummary:
        processed = 0
        selected_tree = getattr(self, "selected_tree", None)
        if selected_tree is not None:
            stack = [selected_tree.topLevelItem(i) for i in range(selected_tree.topLevelItemCount())]
            while stack:
                item = stack.pop()
                if item is None:
                    continue
                meta = item.data(0, self.ROLE_META)
                if isinstance(meta, dict):
                    same = str(meta.get("source_snapshot_id") or "") == snapshot_id
                    if same and bool(meta.get("processed", False)):
                        processed += 1
                for i in range(item.childCount()):
                    stack.append(item.child(i))

        plotted = 0
        panel = getattr(self, "plotted_data_panel", None)
        if panel is not None:
            for curve in getattr(panel, "curves", ()):
                meta = dict(getattr(curve, "metadata", {}) or {})
                if str(meta.get("source_snapshot_id") or "") == snapshot_id:
                    plotted += 1

        workflow_uses: tuple[str, ...] = ()
        file_item = self._loaded_file_item_for_snapshot_id(snapshot_id)
        if file_item is not None:
            meta = file_item.data(0, self.ROLE_META)
            if isinstance(meta, dict):
                raw_uses = meta.get("source_workflow_uses") or ()
                if isinstance(raw_uses, (list, tuple, set)):
                    workflow_uses = tuple(sorted({str(v) for v in raw_uses if str(v)}))

        return SourceDependencySummary(
            processed_curves=processed,
            plotted_curves=plotted,
            workflow_uses=workflow_uses,
        )

    def _mark_source_snapshot_usage(self, snapshot_id: str, usage: str) -> None:
        """Persist a non-tree workflow use on the loaded source snapshot.

        Some operations, notably reversible normalization and fitting, do not
        create a persistent processed-tree child.  Recording their use on the
        immutable source snapshot lets reload protection remain conservative
        without changing those workflows into stored derivative curves.
        """
        sid = str(snapshot_id or "")
        label = str(usage or "").strip()
        if not sid or not label:
            return
        item = self._loaded_file_item_for_snapshot_id(sid)
        if item is None:
            return
        meta = item.data(0, self.ROLE_META)
        if not isinstance(meta, dict):
            return
        updated = dict(meta)
        uses = {str(v) for v in (updated.get("source_workflow_uses") or ()) if str(v)}
        uses.add(label)
        updated["source_workflow_uses"] = sorted(uses)
        item.setData(0, self.ROLE_META, updated)

    def _mark_source_usage_from_items(self, items, usage: str) -> None:
        for entry in items or ():
            item = entry[0] if isinstance(entry, tuple) and entry else entry
            try:
                meta = item.data(0, self.ROLE_META)
            except Exception:
                meta = None
            if isinstance(meta, dict):
                self._mark_source_snapshot_usage(str(meta.get("source_snapshot_id") or ""), usage)

    def _mark_source_usage_from_payloads(self, payloads, usage: str) -> None:
        for entry in payloads or ():
            payload = entry[1] if isinstance(entry, tuple) and len(entry) > 1 else entry
            meta = dict(getattr(payload, "metadata", {}) or {})
            self._mark_source_snapshot_usage(str(meta.get("source_snapshot_id") or ""), usage)

    def _existing_source_labels(self) -> list[str]:
        labels: list[str] = []
        for item in self._iter_loaded_file_items() or ():
            meta = item.data(0, self.ROLE_META)
            if isinstance(meta, dict):
                labels.append(str(meta.get("source_label") or item.text(0) or ""))
            else:
                labels.append(str(item.text(0) or ""))
        return labels

    def _new_source_snapshot(self, path: str | Path, *, updated_copy: bool = False) -> SourceSnapshot:
        p = Path(path)
        label = p.name
        if updated_copy:
            label = updated_source_label(p.name, self._existing_source_labels())
        return make_source_snapshot(p, source_label=label)

    def _ask_duplicate_load_policy(self, item) -> str:
        """Return one of: replace, copy, remove_replace, cancel."""
        snapshot = self._snapshot_from_file_item(item)
        if snapshot is None:
            return "cancel"
        deps = self._source_dependency_summary(snapshot.snapshot_id)
        if not deps.has_dependencies:
            answer = QMessageBox.question(
                self,
                "File already loaded",
                "This file is already loaded. Reload the current disk contents and replace the loaded snapshot?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            return "replace" if answer == QMessageBox.StandardButton.Yes else "cancel"

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("File already used by processing or derived data")
        box.setText(
            "This loaded source snapshot is already used by processing or derived data:\n\n"
            f"{deps.describe()}\n\n"
            "Replacing it silently could invalidate work or break data provenance."
        )
        copy_btn = box.addButton("Load updated copy", QMessageBox.ButtonRole.AcceptRole)
        remove_btn = box.addButton("Replace and remove dependent data", QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(copy_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is copy_btn:
            return "copy"
        if clicked is remove_btn:
            return "remove_replace"
        if clicked is cancel_btn:
            return "cancel"
        return "cancel"

    def _capture_checked_leaf_signatures(self, file_item) -> set[tuple[str, str]]:
        checked: set[tuple[str, str]] = set()
        stack = [file_item]
        while stack:
            item = stack.pop()
            for i in range(item.childCount()):
                stack.append(item.child(i))
            try:
                if item.childCount() == 0 and item.checkState(0) == Qt.CheckState.Checked:
                    region = str(item.data(0, self.ROLE_REGION) or "")
                    checked.add((region, str(item.text(0) or "")))
            except Exception:
                pass
        return checked

    def _restore_checked_leaf_signatures(self, file_item, signatures: set[tuple[str, str]]) -> None:
        if not signatures:
            return
        stack = [file_item]
        while stack:
            item = stack.pop()
            for i in range(item.childCount()):
                stack.append(item.child(i))
            try:
                if item.childCount() == 0:
                    region = str(item.data(0, self.ROLE_REGION) or "")
                    if (region, str(item.text(0) or "")) in signatures:
                        item.setCheckState(0, Qt.CheckState.Checked)
            except Exception:
                pass

    def _remove_plotted_snapshot_dependencies(self, snapshot_id: str) -> None:
        panel = getattr(self, "plotted_data_panel", None)
        if panel is None:
            return
        remove = getattr(panel, "remove_curves_by_metadata", None)
        if callable(remove):
            remove("source_snapshot_id", snapshot_id)

    def _remove_selected_snapshot_items(self, snapshot_id: str) -> None:
        manager = getattr(self, "_selected_tree_manager", None)
        if manager is None:
            return
        keys_to_remove: list[str] = []
        for key, item in list(getattr(self, "_selected_by_key", {}).items()):
            meta = item.data(0, self.ROLE_META)
            if isinstance(meta, dict) and str(meta.get("source_snapshot_id") or "") == snapshot_id:
                keys_to_remove.append(str(key))
        for key in keys_to_remove:
            try:
                manager.remove_selected_leaf(key)
            except Exception:
                pass

    def _sync_checked_loaded_leaves_for_file(self, file_item) -> None:
        manager = getattr(self, "_selected_tree_manager", None)
        if manager is None or file_item is None:
            return
        stack = [file_item]
        while stack:
            item = stack.pop()
            for i in range(item.childCount()):
                stack.append(item.child(i))
            try:
                if item.childCount() != 0 or item.checkState(0) != Qt.CheckState.Checked:
                    continue
                payload = item.data(0, self.ROLE_PAYLOAD)
                if payload is None:
                    continue
                manager.sync_loaded_leaf(
                    loaded_item=item,
                    checked=True,
                    all_in_region_enabled=bool(self.cb_all_in_region.isChecked()),
                    target_region=self._selected_target_region(),
                )
            except Exception:
                pass

    def _remove_loaded_file_item(self, item) -> None:
        if item is None:
            return
        label = str(item.data(0, self.ROLE_FILE) or item.text(0) or "")
        root = getattr(self, "_files_root", None)
        if root is not None:
            idx = root.indexOfChild(item)
            if idx >= 0:
                root.takeChild(idx)
        stacks = getattr(self, "_region_iteration_stack", None)
        if isinstance(stacks, dict):
            for key in list(stacks):
                if isinstance(key, tuple) and key and str(key[0]) == label:
                    stacks.pop(key, None)

    def _replace_loaded_snapshot(self, *, item, parsed: Any, snapshot: SourceSnapshot, remove_dependencies: bool) -> None:
        old_snapshot = self._snapshot_from_file_item(item)
        checked = self._capture_checked_leaf_signatures(item)
        if old_snapshot is not None:
            if remove_dependencies:
                self._remove_plotted_snapshot_dependencies(old_snapshot.snapshot_id)
            # Raw selected curves also point at the old snapshot object.  Remove
            # only this snapshot's selected items; other files' processed data
            # remain untouched.
            self._remove_selected_snapshot_items(old_snapshot.snapshot_id)
        self._remove_loaded_file_item(item)
        self._add_txt_to_tree(parsed, snapshot=snapshot)
        new_item = self._loaded_file_item_for_snapshot_id(snapshot.snapshot_id)
        if new_item is not None:
            self._restore_checked_leaf_signatures(new_item, checked)
            self._sync_checked_loaded_leaves_for_file(new_item)
        try:
            self._update_plot_from_selected()
        except Exception:
            pass

    def _loaded_file_item_for_snapshot_id(self, snapshot_id: str):
        for item in self._iter_loaded_file_items() or ():
            meta = item.data(0, self.ROLE_META)
            if isinstance(meta, dict) and str(meta.get("source_snapshot_id") or "") == snapshot_id:
                return item
        return None

    def _reload_source_path_with_policy(self, path: str | Path) -> bool:
        """Reload the newest loaded snapshot for *path* through the standard policy.

        This is the shared entry point for secondary UI surfaces such as the
        Live Monitor.  It deliberately delegates to ``_reload_loaded_file_item``
        so dependency checks, provenance choices, and replacement behavior stay
        identical to **Reload from disk** in the Loaded files tree.
        """
        item = self._loaded_file_item_for_path(path)
        if item is None:
            return False
        return bool(self._reload_loaded_file_item(item))

    def _reload_loaded_file_item(self, item) -> bool:
        snapshot = self._snapshot_from_file_item(item)
        if snapshot is None or not snapshot.physical_path:
            return False
        path = Path(snapshot.physical_path)
        suffix = path.suffix.lower()
        kind = "IBW" if suffix == ".ibw" else ("XY" if suffix == ".xy" else "TXT")
        policy = self._ask_duplicate_load_policy(item)
        if policy == "cancel":
            return False
        try:
            from .loaders import parse_file
            parsed = parse_file(path, kind=kind)
        except Exception as exc:
            QMessageBox.critical(self, "Reload failed", f"Could not parse {path.name}\n\n{exc}")
            return False
        if policy == "copy":
            new_snapshot = self._new_source_snapshot(path, updated_copy=True)
            self._add_txt_to_tree(parsed, snapshot=new_snapshot)
        else:
            new_snapshot = self._new_source_snapshot(path, updated_copy=False)
            self._replace_loaded_snapshot(
                item=item,
                parsed=parsed,
                snapshot=new_snapshot,
                remove_dependencies=(policy == "remove_replace"),
            )
        self._refresh_all_region_combo()
        return True
