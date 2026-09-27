from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QKeySequence, QTextDocument, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpinBox, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)
from maxiv_panda.silent_message_box import SilentMessageBox as QMessageBox

from .version import __date__, __version__
from .loaders import filter_for_kind, open_files_dialog, parse_file
from .icon import application_icon
from .utils.help_text import get_usage_html
from .widgets.help_browser import HelpBrowser
from .widgets.appearance_settings_dialog import SettingsDialog
from .ui_style import current_ui_configuration, apply_ui_configuration_live, apply_dialog_metrics, apply_control_metrics


class UiActionsMixin:
    """File, help, and top-level application actions for ``MainWindow``."""

    def _update_load_menu_state(self) -> None:
        """Enable/disable Load submenu entries based on loaded file kind."""
        try:
            if getattr(self, '_loaded_kind', None) == 'TXT':
                self.act_txt.setEnabled(True)
                self.act_ibw.setEnabled(False)
                self.act_xy.setEnabled(False)
                self.tree.setHeaderLabels(['TXT file structure'])
            elif getattr(self, '_loaded_kind', None) == 'IBW':
                self.act_txt.setEnabled(False)
                self.act_ibw.setEnabled(True)
                self.act_xy.setEnabled(False)
                self.tree.setHeaderLabels(['IBW file structure'])
            elif getattr(self, '_loaded_kind', None) == 'XY':
                self.act_txt.setEnabled(False)
                self.act_ibw.setEnabled(False)
                self.act_xy.setEnabled(True)
                self.tree.setHeaderLabels(['SPECS Prodigy XY file structure'])
            else:
                self.act_txt.setEnabled(True)
                self.act_ibw.setEnabled(True)
                self.act_xy.setEnabled(True)
                self.tree.setHeaderLabels(['File structure'])
        except Exception:
            pass


    def _set_loaded_kind(self, kind: str | None) -> None:
        self._loaded_kind = kind
        self._update_load_menu_state()


    def _reset_signal_identification(self) -> None:
        """Restore signal identification to its new-session state."""
        controller = getattr(self, "_signal_identification", None)
        if controller is not None:
            controller.reset_to_defaults()



    def _return_to_raw_data(self) -> None:
        """Return the main workspace to Raw Data after a top-level reset."""
        try:
            self.tabs.setCurrentWidget(self.raw_data_tab)
        except Exception:
            pass

    def close_all(self) -> None:
        """Close all loaded files (clear tree and plot)."""

        self._reset_signal_identification()
        reset_map_norm = getattr(self, "_reset_map_normalization_context", None)
        if callable(reset_map_norm):
            reset_map_norm(close_dialog=True)
        self._files_root.takeChildren()
        self._files_root.setExpanded(True)
        self._set_loaded_kind(None)
        self.folder_label.setText("No folder selected")
        self._selected_tree_manager.clear()
        terminate_comparison = getattr(self, "_terminate_trace_comparison_session", None)
        if callable(terminate_comparison):
            terminate_comparison()
        reset_respes = getattr(self, "_reset_respes_context", None)
        if callable(reset_respes):
            reset_respes()
        sync_processed = getattr(self, "_sync_processed_controls_for_map_mode", None)
        if callable(sync_processed):
            sync_processed()
        self._curve_color_map.clear()
        self._next_color_index = 0
        self.plot_area.clear("Load a TXT or IBW file to begin")

        # Reset group-loading controls.
        try:
            self.cb_all_in_region.blockSignals(True)
            self.combo_all_region.blockSignals(True)
            self.cb_all_in_region.setChecked(False)
            self.combo_all_region.clear()
            self.combo_all_region.setEnabled(False)
        finally:
            try:
                self.cb_all_in_region.blockSignals(False)
                self.combo_all_region.blockSignals(False)
            except Exception:
                pass

        self._return_to_raw_data()


    def clear_all(self) -> None:
        """Clear all selected curves without unloading files.

        - Unchecks all checkboxes in the left (loaded files) tree.
        - Clears the selected-curves tree.
        - Clears the plot.
        - Disables signal identification and restores its default settings.
        """

        self._reset_signal_identification()
        reset_map_norm = getattr(self, "_reset_map_normalization_context", None)
        if callable(reset_map_norm):
            reset_map_norm(close_dialog=True)

        # Uncheck everything in the loaded-files tree without triggering updates on every item.
        try:
            self.tree.blockSignals(True)
            # Walk the tree recursively starting from the root.
            def _walk(item: QTreeWidgetItem) -> None:
                for i in range(item.childCount()):
                    ch = item.child(i)
                    # Only touch checkable items.
                    try:
                        if ch.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                            ch.setCheckState(0, Qt.CheckState.Unchecked)
                    except Exception:
                        pass
                    _walk(ch)

            _walk(self._files_root)
        finally:
            try:
                self.tree.blockSignals(False)
            except Exception:
                pass

        # Clear selection state and plot.
        self._selected_tree_manager.clear()
        terminate_comparison = getattr(self, "_terminate_trace_comparison_session", None)
        if callable(terminate_comparison):
            terminate_comparison()
        reset_respes = getattr(self, "_reset_respes_context", None)
        if callable(reset_respes):
            reset_respes()
        sync_processed = getattr(self, "_sync_processed_controls_for_map_mode", None)
        if callable(sync_processed):
            sync_processed()
        # Do NOT clear self._curve_color_map so colors remain stable when re-selecting.
        self.plot_area.clear("No curves selected")

        # Reset group-loading controls.
        try:
            self.cb_all_in_region.blockSignals(True)
            self.combo_all_region.blockSignals(True)
            self.cb_all_in_region.setChecked(False)
        finally:
            try:
                self.cb_all_in_region.blockSignals(False)
                self.combo_all_region.blockSignals(False)
            except Exception:
                pass

        self._return_to_raw_data()


    def _load_file(self, kind: str) -> None:
        filt = filter_for_kind(kind)
        paths = self._open_files_dialog(kind=kind, filter_string=filt)
        if not paths:
            return
        self._load_paths(paths=paths, kind=kind)


    def _load_paths(self, paths: list[Any], kind: str) -> None:
        # Prevent mixing TXT and IBW in one session.
        if self._loaded_kind is not None and self._loaded_kind != kind:
            QMessageBox.information(
                self,
                'Load not allowed',
                "Only one file type at a time is supported.\n\n"
                f"You currently have {self._loaded_kind} files loaded. Please use 'Close all' first.",
            )
            return

        success_count = 0
        folders = sorted({p.parent for p in paths})
        if len(folders) == 1:
            self.folder_label.setText(str(folders[0]))
            self._current_data_directory = folders[0]
        else:
            self.folder_label.setText("Multiple folders")
            # Use the directory of the most recently supplied file for later
            # import/export dialogs while still showing the multi-folder label.
            self._current_data_directory = paths[-1].parent
        plotted_panel = getattr(self, "plotted_data_panel", None)
        if plotted_panel is not None:
            plotted_panel.set_default_directory(self._current_data_directory)

        for path in paths:
            existing = self._loaded_file_item_for_path(path)
            policy = None
            if existing is not None:
                policy = self._ask_duplicate_load_policy(existing)
                if policy == "cancel":
                    continue
            try:
                parsed = parse_file(path, kind=kind)
            except Exception as exc:
                QMessageBox.critical(self, "Load failed", f"Could not parse {path.name}\n\n{exc}")
                continue

            if existing is None:
                snapshot = self._new_source_snapshot(path, updated_copy=False)
                self._add_txt_to_tree(parsed, snapshot=snapshot)
            elif policy == "copy":
                snapshot = self._new_source_snapshot(path, updated_copy=True)
                self._add_txt_to_tree(parsed, snapshot=snapshot)
            else:
                snapshot = self._new_source_snapshot(path, updated_copy=False)
                self._replace_loaded_snapshot(
                    item=existing,
                    parsed=parsed,
                    snapshot=snapshot,
                    remove_dependencies=(policy == "remove_replace"),
                )
            success_count += 1

        if success_count > 0:
            self._refresh_all_region_combo()

        if success_count > 0 and self._loaded_kind is None:
            self._set_loaded_kind(kind)


    def _load_dropped_files(self, raw_paths: list[str]) -> None:
        from pathlib import Path

        paths = [Path(p) for p in raw_paths if p]
        if not paths:
            return

        exts = {p.suffix.lower() for p in paths}
        supported = {'.txt', '.ibw', '.xy'}
        exts = {e for e in exts if e in supported}
        if not exts:
            return
        if len(exts) > 1:
            QMessageBox.information(
                self,
                'Load not allowed',
                "Please drop either TXT files or IBW files in one action, not both together.",
            )
            return

        ext = next(iter(exts))
        kind = 'TXT' if ext == '.txt' else ('IBW' if ext == '.ibw' else 'XY')
        self._load_paths(paths=paths, kind=kind)


    def _open_files_dialog(self, kind: str, filter_string: str) -> list[Any]:
        return open_files_dialog(self, kind=kind, filter_string=filter_string)


    def _open_calibrate_be_dialog(self) -> None:
        from .workflows.calibration import open_calibrate_energy_dialog

        # If an energy calibration already exists, reopening calibration is a
        # destructive redo: old E-cal children must not coexist with a second
        # generation.  Ask explicitly before removing them.
        ecal_items = []
        try:
            for key, item in list(getattr(self, "_selected_by_key", {}).items()):
                meta = item.data(0, self.ROLE_META)
                is_ecal = (
                    isinstance(meta, dict)
                    and bool(meta.get("processed", False))
                    and ("energy_shift" in meta or "reference_key" in meta)
                )
                if is_ecal:
                    ecal_items.append((key, item))
        except Exception:
            ecal_items = []

        if ecal_items:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Redo energy calibration")
            box.setText("Energy calibration has already been performed.")
            box.setInformativeText(
                "Redoing it will delete the existing E-calibrated curves and start a new calibration from the defaults."
            )
            btn_redo = box.addButton("Redo", QMessageBox.ButtonRole.AcceptRole)
            btn_cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(btn_cancel)
            box.exec()
            if box.clickedButton() is not btn_redo:
                return

            # Remove all existing E-cal children from the selected-curves tree
            # and registry before opening a fresh calibration dialog.
            for key, item in ecal_items:
                try:
                    parent = item.parent()
                    if parent is not None:
                        idx = parent.indexOfChild(item)
                        if idx >= 0:
                            parent.takeChild(idx)
                except Exception:
                    pass
                try:
                    self._selected_by_key.pop(key, None)
                except Exception:
                    pass

            try:
                self.btn_e_cal_toggle.setChecked(False)
            except Exception:
                pass
            try:
                self._update_selected_tree_visibility(show_processed=False)
                self._update_plot_from_selected()
            except Exception:
                pass

        open_calibrate_energy_dialog(self)


    def show_usage_info(self, md_filename: str = "usage_controls.md", window_title: str = "Usage — PANDA"):
        """Show the modeless Help browser with TOC, search, and font-size controls."""
        # Help is deliberately modeless: users should be able to keep it open
        # while working normally in the main window.  Keep at most one Help
        # window alive so repeated Help-menu actions do not accumulate dialogs.
        existing = getattr(self, "_help_dialog", None)
        if existing is not None:
            try:
                if getattr(self, "_help_md_filename", None) == md_filename and existing.isVisible():
                    existing.raise_()
                    existing.activateWindow()
                    return
                existing.close()
            except Exception:
                pass

        try:
            usage_html = get_usage_html(md_filename, 17)
        except Exception:
            usage_html = "<p><b>Help text could not be loaded.</b></p>"

        # Use a parentless top-level window rather than a dialog owned by the
        # main window.  On Windows, an owned dialog is kept above its owner and
        # normally lacks a standard taskbar/minimize relationship.  Help should
        # behave as an independent application window while remaining modeless.
        dlg = QDialog(None, Qt.WindowType.Window)
        dlg.setModal(False)
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self._help_dialog = dlg
        self._help_md_filename = md_filename

        def _forget_help_dialog(*_args):
            if getattr(self, "_help_dialog", None) is dlg:
                self._help_dialog = None
                self._help_md_filename = None

        dlg.destroyed.connect(_forget_help_dialog)

        help_name = "What is what?" if md_filename == "usage_controls.md" else "How to?"
        pane_subtitle = (
            "GUI elements and analysis methods"
            if md_filename == "usage_controls.md"
            else "Practical workflows and troubleshooting"
        )
        dlg.setWindowTitle(f"Help — {help_name}")
        dlg.resize(1240, 800)
        dlg.setMinimumSize(980, 680)
        dlg.setSizeGripEnabled(True)

        try:
            dlg.setWindowFlags(
                dlg.windowFlags()
                | Qt.WindowType.WindowMinimizeButtonHint
                | Qt.WindowType.WindowMaximizeButtonHint
                | Qt.WindowType.WindowCloseButtonHint
            )
        except Exception:
            pass

        layout = QVBoxLayout(dlg)
        apply_dialog_metrics(layout, compact=True)

        header = QWidget(dlg)
        header.setObjectName("helpHeader")
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        header.setMaximumHeight(44)
        header.setStyleSheet(
            "QWidget#helpHeader { background: palette(alternate-base); border: 1px solid palette(mid); }"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 5, 8, 5)
        header_layout.setSpacing(8)

        pane_title = QLabel(pane_subtitle)
        pane_title.setObjectName("helpPaneTitle")
        pane_title.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        pane_title.setStyleSheet(
            "QLabel#helpPaneTitle { font-weight: 700; font-style: italic; "
            "color: palette(link); padding: 0; }"
        )
        header_layout.addWidget(pane_title)
        header_layout.addStretch(1)

        header_layout.addWidget(QLabel("Font size:"))
        font_spin = QSpinBox()
        font_spin.setRange(8, 28)
        font_spin.setSingleStep(1)
        font_spin.setValue(17)
        font_spin.setToolTip("Set the base Help text size. Headings and navigation scale with it.")
        header_layout.addWidget(font_spin)

        header_layout.addSpacing(10)
        header_layout.addWidget(QLabel("Find:"))
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("Search help...")
        try:
            search_edit.setClearButtonEnabled(True)
        except Exception:
            pass
        search_edit.setToolTip("Press Enter for next, Shift+Enter for previous.")
        search_edit.setMinimumWidth(220)
        header_layout.addWidget(search_edit)

        prev_btn = QPushButton("Prev")
        prev_btn.setToolTip("Find the previous match.")
        header_layout.addWidget(prev_btn)
        next_btn = QPushButton("Next")
        next_btn.setToolTip("Find the next match.")
        header_layout.addWidget(next_btn)
        layout.addWidget(header, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, dlg)

        toc_panel = QWidget()
        toc_layout = QVBoxLayout(toc_panel)
        toc_layout.setContentsMargins(0, 0, 0, 0)
        toc_layout.setSpacing(5)
        toc_title = QLabel("Table of Contents")
        toc_title.setObjectName("tocTitle")
        toc_title.setStyleSheet(
            "QLabel#tocTitle { font-weight: 700; color: palette(link); "
            "background: palette(button); border: 1px solid palette(mid); padding: 5px 7px; }"
        )
        toc_layout.addWidget(toc_title)

        toc = QTreeWidget()
        toc.setHeaderHidden(True)
        toc.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toc.setMinimumWidth(255)
        toc_layout.addWidget(toc, 1)

        def _set_toc_style(px: int):
            """Apply proportional navigation typography from the base Help size."""
            try:
                base = int(px)
            except Exception:
                base = 17
            sizes = {
                1: min(20, max(12, round(base * 0.84))),
                2: min(18, max(11, round(base * 0.76))),
                3: min(16, max(10, round(base * 0.68))),
            }
            toc_title_font = QFont(toc_title.font())
            toc_title_font.setPointSize(sizes[1])
            toc_title_font.setBold(True)
            toc_title.setFont(toc_title_font)
            pane_title_font = QFont(pane_title.font())
            pane_title_font.setPointSize(sizes[1])
            pane_title_font.setBold(True)
            pane_title_font.setItalic(True)
            pane_title.setFont(pane_title_font)
            try:
                toc.setStyleSheet(
                    "QTreeWidget { border: 1px solid palette(mid); padding: 3px; }"
                    "QTreeWidget::item { padding: 3px 4px; }"
                    "QTreeWidget::item:selected {"
                    " background: palette(highlight); color: palette(highlighted-text);"
                    " border-left: 4px solid palette(link);"
                    " }"
                    "QTreeWidget::branch { margin-right: 2px; }"
                )
                root = toc.invisibleRootItem()
                stack = [root.child(i) for i in range(root.childCount())]
                while stack:
                    item = stack.pop()
                    level = int(item.data(0, Qt.ItemDataRole.UserRole + 1) or 3)
                    font = QFont(toc.font())
                    font.setPointSize(sizes.get(level, sizes[3]))
                    font.setBold(level == 1)
                    font.setWeight(QFont.Weight.DemiBold if level == 2 else (QFont.Weight.Bold if level == 1 else QFont.Weight.Normal))
                    item.setFont(0, font)
                    if level == 1:
                        item.setSizeHint(0, item.sizeHint(0).expandedTo(item.sizeHint(0)))
                    stack.extend(item.child(i) for i in range(item.childCount()))
            except Exception:
                pass

        _set_toc_style(font_spin.value())

        browser = HelpBrowser()
        browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        browser.setStyleSheet("font-size: 17px;")
        browser.setMinimumWidth(380)
        browser.setHtml(usage_html)

        def _do_help_search(backward: bool = False):
            text = (search_edit.text() or "").strip()
            if not text:
                return
            flags = (
                QTextDocument.FindFlag.FindBackward
                if backward
                else QTextDocument.FindFlag(0)
            )
            try:
                found = browser.find(text, flags)
            except Exception:
                found = False
            if not found:
                try:
                    cursor = browser.textCursor()
                    cursor.movePosition(cursor.End if backward else cursor.Start)
                    browser.setTextCursor(cursor)
                    found = browser.find(text, flags)
                except Exception:
                    found = False
            if not found:
                try:
                    QMessageBox.information(dlg, "Search", f'No matches for "{text}".')
                except Exception:
                    pass

        try:
            next_btn.clicked.connect(lambda: _do_help_search(False))
            prev_btn.clicked.connect(lambda: _do_help_search(True))
            search_edit.returnPressed.connect(lambda: _do_help_search(False))
        except Exception:
            pass

        try:
            sc_find = QShortcut(QKeySequence.StandardKey.Find, dlg)
            sc_find.activated.connect(lambda: (search_edit.setFocus(), search_edit.selectAll()))
            sc_next = QShortcut(QKeySequence("F3"), dlg)
            sc_next.activated.connect(lambda: _do_help_search(False))
            sc_prev = QShortcut(QKeySequence("Shift+F3"), dlg)
            sc_prev.activated.connect(lambda: _do_help_search(True))
            sc_prev_enter = QShortcut(QKeySequence("Shift+Return"), dlg)
            sc_prev_enter.activated.connect(lambda: _do_help_search(True))
        except Exception:
            pass

        try:
            toc.clear()
            current_h1 = None
            current_h2 = None
            for level, title, anchor in getattr(browser, "_help_anchors", []) or []:
                item = QTreeWidgetItem([title])
                item.setData(0, Qt.ItemDataRole.UserRole, anchor)
                item.setData(0, Qt.ItemDataRole.UserRole + 1, level)
                if level == 1:
                    toc.addTopLevelItem(item)
                    current_h1 = item
                    current_h2 = None
                elif level == 2:
                    if current_h1 is None:
                        toc.addTopLevelItem(item)
                    else:
                        current_h1.addChild(item)
                    current_h2 = item
                else:
                    parent = current_h2 or current_h1
                    if parent is None:
                        toc.addTopLevelItem(item)
                    else:
                        parent.addChild(item)
            # Keep the major application map visible while avoiding a fully
            # expanded, visually flat contents list.
            toc.collapseAll()
            if toc.topLevelItemCount():
                toc.topLevelItem(0).setExpanded(True)
            _set_toc_style(font_spin.value())

            _expansion_guard = {"active": False}

            def _keep_one_major_branch(item):
                if _expansion_guard["active"] or item.parent() is not None:
                    return
                _expansion_guard["active"] = True
                try:
                    for idx in range(toc.topLevelItemCount()):
                        other = toc.topLevelItem(idx)
                        if other is not item:
                            other.setExpanded(False)
                finally:
                    _expansion_guard["active"] = False

            toc.itemExpanded.connect(_keep_one_major_branch)

            def _jump_to_section(item, _col=0):
                anchor = item.data(0, Qt.ItemDataRole.UserRole)
                if anchor:
                    browser.scrollToAnchor(str(anchor))
            toc.itemClicked.connect(_jump_to_section)
        except Exception:
            pass

        splitter.addWidget(toc_panel)
        splitter.addWidget(browser)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        splitter.setSizes([390, 830])
        layout.addWidget(splitter, 1)

        def _apply_help_font(px: int):
            try:
                px = int(px)
            except Exception:
                px = 14
            try:
                browser.setStyleSheet(f"font-size: {px}px;")
                browser.setHtml(get_usage_html(md_filename, px))
            except Exception:
                pass
            try:
                _set_toc_style(px)
            except Exception:
                pass

        font_spin.valueChanged.connect(_apply_help_font)
        apply_control_metrics(dlg)
        dlg.show()
        try:
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            pass


    def _show_not_implemented_dialog(self, title: str):
        QMessageBox.information(self, title, "Not implemented yet")


    def show_settings(self):
        """Open the lightweight application settings dialog."""
        dlg = SettingsDialog(current_ui_configuration(), self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        apply_ui_configuration_live(dlg.configuration())


    def _get_about_version(self) -> str:
        return __version__


    def show_about_info(self):
        info_text = (
            "PANDA: Photoemission Analysis, Normalization and Data Assessment\n\n"
            f"Software Version: {self._get_about_version()}\n"
            f"Date: {__date__}\n\n"
            "Created by: Alexei Preobrajenski (MAX IV Laboratory)\n"
            "License: MIT\n\n"
            "PANDA is a Python software package with an interactive graphical interface for "
            "loading, visualization, processing, analysis, and fitting of photoelectron "
            "spectroscopy (PES/XPS) data. It was developed at the FlexPES beamline at "
            "MAX IV Laboratory."
        )
        msg = QMessageBox(self)
        msg.setWindowTitle("About PANDA")
        msg.setText(info_text)
        logo = application_icon().pixmap(96, 96)
        if not logo.isNull():
            msg.setIconPixmap(logo)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

