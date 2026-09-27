from __future__ import annotations

"""Read-only viewer for metadata attached to Raw Data tree items."""

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QHeaderView,
)


_MAX_INLINE_SEQUENCE_VALUES = 12
_MAX_INLINE_TEXT = 260


def _sequence_summary(value: Any) -> str:
    """Keep long Scienta axis/point lists readable in the metadata viewer."""
    text = str(value if value is not None else "").strip()
    if not text:
        return ""
    parts = text.split()
    if len(parts) > _MAX_INLINE_SEQUENCE_VALUES:
        first = " ".join(parts[:3])
        last = " ".join(parts[-3:])
        return f"{len(parts)} values: {first} ... {last}"
    if len(text) > _MAX_INLINE_TEXT:
        return text[: _MAX_INLINE_TEXT - 3].rstrip() + "..."
    return text


def _display_value(key: str, value: Any) -> str:
    key_low = str(key).lower()
    if "scale" in key_low or key_low.startswith("point "):
        return _sequence_summary(value)
    if isinstance(value, (list, tuple)):
        if len(value) > _MAX_INLINE_SEQUENCE_VALUES:
            vals = [str(v) for v in value]
            return f"{len(vals)} values: {' '.join(vals[:3])} ... {' '.join(vals[-3:])}"
        return ", ".join(str(v) for v in value)
    text = str(value if value is not None else "")
    if len(text) > _MAX_INLINE_TEXT:
        return text[: _MAX_INLINE_TEXT - 3].rstrip() + "..."
    return text


from ..ui_style import apply_dialog_metrics, apply_control_metrics, current_ui_metrics

def _nonempty_items(mapping: dict[str, Any] | None):
    for key, value in (mapping or {}).items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        yield str(key), value


def metadata_sections(metadata: dict[str, Any]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Convert stored tree metadata into compact user-facing sections."""
    scope = str(metadata.get("metadata_scope") or "curve")
    sections: list[tuple[str, list[tuple[str, str]]]] = []

    source_rows: list[tuple[str, str]] = []
    if metadata.get("file_name"):
        source_rows.append(("File", _display_value("File", metadata.get("file_name"))))
    if metadata.get("file_path"):
        source_rows.append(("Path", _display_value("Path", metadata.get("file_path"))))
    if metadata.get("region_name"):
        source_rows.append(("Region", _display_value("Region", metadata.get("region_name"))))
    if metadata.get("region_index") is not None:
        source_rows.append(("Region index", _display_value("Region index", metadata.get("region_index"))))
    if source_rows:
        sections.append(("Source", source_rows))

    file_rows = [(k, _display_value(k, v)) for k, v in _nonempty_items(metadata.get("file_info"))]
    if file_rows:
        sections.append(("File information", file_rows))

    region_meta = dict(metadata.get("region_meta") or {})
    dimension_rows: list[tuple[str, str]] = []
    other_region_rows: list[tuple[str, str]] = []
    for key, value in _nonempty_items(region_meta):
        row = (key, _display_value(key, value))
        if key.lower().startswith("dimension"):
            dimension_rows.append(row)
        else:
            other_region_rows.append(row)
    if dimension_rows:
        sections.append(("Dimensions", dimension_rows))
    if other_region_rows:
        sections.append(("Region information", other_region_rows))

    info_rows = [(k, _display_value(k, v)) for k, v in _nonempty_items(metadata.get("info_meta"))]
    if info_rows:
        sections.append(("Acquisition / instrument", info_rows))

    auxiliary = metadata.get("section_meta") or {}
    if isinstance(auxiliary, dict):
        title_map = {
            "Manipulator": "Manipulator",
            "Run Mode Information": "Run mode",
            "User Interface Information": "User interface",
        }
        for raw_name, values in auxiliary.items():
            if not isinstance(values, dict):
                continue
            rows = [(k, _display_value(k, v)) for k, v in _nonempty_items(values)]
            if rows:
                sections.append((title_map.get(str(raw_name), str(raw_name)), rows))

    if scope == "curve":
        curve_rows: list[tuple[str, str]] = []
        for key, label in (
            ("kind", "Type"),
            ("leaf_label", "Tree entry"),
            ("iteration", "Iteration"),
            ("iteration_axis_name", "Iteration axis"),
            ("iteration_axis_value", "Iteration axis value"),
            ("n_traces", "Number of traces"),
        ):
            value = metadata.get(key)
            if value is not None and str(value).strip() != "":
                curve_rows.append((label, _display_value(label, value)))
        if curve_rows:
            sections.append(("Curve", curve_rows))

        source_meta = dict(metadata.get("source_metadata") or {})
        dim_rows: list[tuple[str, str]] = []
        acquisition_rows: list[tuple[str, str]] = []
        for key, value in _nonempty_items(source_meta):
            row = (key, _display_value(key, value))
            if key.lower().startswith("dimension"):
                dim_rows.append(row)
            else:
                acquisition_rows.append(row)
        if dim_rows:
            sections.append(("Dimensions", dim_rows))
        if acquisition_rows:
            sections.append(("Acquisition / instrument", acquisition_rows))

    warnings = metadata.get("warnings") or []
    if warnings:
        sections.append(("Warnings", [("Warning", _display_value("Warning", w)) for w in warnings]))

    return sections


class MetadataDialog(QDialog):
    """Read-only two-column metadata browser with copy actions."""

    def __init__(self, metadata: dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Metadata")
        self.setModal(False)
        self.resize(760, 560)

        root = QVBoxLayout(self)
        apply_dialog_metrics(root)

        search_row = QHBoxLayout()
        search_row.setSpacing(current_ui_metrics().compact_spacing)
        search_row.addWidget(QLabel("Find:", self))
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Search metadata...")
        self.btn_prev = QPushButton("Prev", self)
        self.btn_next = QPushButton("Next", self)
        self.search_edit.setToolTip("Search parameter names and metadata values.")
        self.btn_prev.setToolTip("Select the previous matching metadata row.")
        self.btn_next.setToolTip("Select the next matching metadata row.")
        search_row.addWidget(self.search_edit, 1)
        search_row.addWidget(self.btn_prev)
        search_row.addWidget(self.btn_next)
        root.addLayout(search_row)

        self.tree = QTreeWidget(self)
        self.tree.setHeaderLabels(["Parameter", "Value"])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.tree, 1)

        for section_name, rows in metadata_sections(dict(metadata or {})):
            section = QTreeWidgetItem([section_name, ""])
            flags = section.flags()
            section.setFlags(flags & ~Qt.ItemFlag.ItemIsSelectable)
            self.tree.addTopLevelItem(section)
            for key, value in rows:
                child = QTreeWidgetItem([key, value])
                section.addChild(child)
            section.setExpanded(True)

        buttons = QHBoxLayout()
        self.btn_copy_selected = QPushButton("Copy selected", self)
        self.btn_copy_all = QPushButton("Copy all", self)
        self.btn_close = QPushButton("Close", self)
        self.btn_copy_selected.setToolTip("Copy the selected metadata rows to the clipboard.")
        self.btn_copy_all.setToolTip("Copy all displayed metadata to the clipboard.")
        buttons.addWidget(self.btn_copy_selected)
        buttons.addWidget(self.btn_copy_all)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_close)
        root.addLayout(buttons)

        self._search_matches: list[QTreeWidgetItem] = []
        self._search_index = -1
        self.btn_copy_selected.clicked.connect(self._copy_selected)
        self.btn_copy_all.clicked.connect(self._copy_all)
        self.btn_close.clicked.connect(self.close)
        self.search_edit.textChanged.connect(self._reset_search)
        self.search_edit.returnPressed.connect(self._find_next)
        self.btn_prev.clicked.connect(self._find_previous)
        self.btn_next.clicked.connect(self._find_next)
        apply_control_metrics(self)

    def _all_value_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []
        for i in range(self.tree.topLevelItemCount()):
            section = self.tree.topLevelItem(i)
            for j in range(section.childCount()):
                items.append(section.child(j))
        return items

    def _reset_search(self, *_args) -> None:
        needle = self.search_edit.text().strip().casefold()
        self._search_index = -1
        if not needle:
            self._search_matches = []
            return
        self._search_matches = [
            item for item in self._all_value_items()
            if needle in item.text(0).casefold() or needle in item.text(1).casefold()
        ]

    def _select_search_match(self, step: int) -> None:
        # Rebuild lazily as a safeguard if the caller is invoked without an
        # intervening textChanged signal (for example from a test harness).
        if self.search_edit.text().strip() and not self._search_matches:
            self._reset_search()
        if not self._search_matches:
            return
        self._search_index = (self._search_index + int(step)) % len(self._search_matches)
        item = self._search_matches[self._search_index]
        if item.parent() is not None:
            item.parent().setExpanded(True)
        self.tree.clearSelection()
        item.setSelected(True)
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

    def _find_next(self) -> None:
        self._select_search_match(1)

    def _find_previous(self) -> None:
        # From the initial state, Prev should select the last match.
        if self._search_index < 0 and self._search_matches:
            self._search_index = 0
        self._select_search_match(-1)

    def _rows_as_text(self, items: list[QTreeWidgetItem]) -> str:
        rows: list[str] = []
        for item in items:
            if item.parent() is None:
                continue
            rows.append(f"{item.text(0)}\t{item.text(1)}")
        return "\n".join(rows)

    def _copy_selected(self) -> None:
        text = self._rows_as_text(self.tree.selectedItems())
        if text:
            QApplication.clipboard().setText(text)

    def _copy_all(self) -> None:
        items: list[QTreeWidgetItem] = []
        for i in range(self.tree.topLevelItemCount()):
            section = self.tree.topLevelItem(i)
            for j in range(section.childCount()):
                items.append(section.child(j))
        text = self._rows_as_text(items)
        if text:
            QApplication.clipboard().setText(text)
