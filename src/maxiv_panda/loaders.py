from __future__ import annotations

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QFileDialog, QDialog

from .ibw_parser import parse_ibw
from .txt_parser import parse_structured_txt
from .specs_xy_adapter import parse_and_adapt_specs_xy


def filter_for_kind(kind: str) -> str:
    if kind == 'TXT':
        return 'Text files (*.txt *.dat *.csv);;All files (*.*)'
    if kind == 'IBW':
        return 'Igor Binary Wave (*.ibw);;All files (*.*)'
    if kind == 'XY':
        return 'SPECS Prodigy XY (*.xy);;All files (*.*)'
    return 'All files (*.*)'


def open_files_dialog(parent: Any, *, kind: str, filter_string: str) -> list[Path]:
    """Open-file dialog sized like the one used in flexpes_nexafs."""
    dlg = QFileDialog(parent)
    dlg.setWindowTitle(f'Load {kind} file')
    dlg.setFileMode(QFileDialog.FileMode.ExistingFiles)
    try:
        dlg.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    except Exception:
        pass
    try:
        dlg.setOption(QFileDialog.Option.DontUseCustomDirectoryIcons, True)
    except Exception:
        pass
    try:
        dlg.setViewMode(QFileDialog.ViewMode.Detail)
    except Exception:
        pass

    filters = [f.strip() for f in filter_string.split(';;') if f.strip()]
    if filters:
        try:
            dlg.setNameFilters(filters)
        except Exception:
            try:
                dlg.setNameFilter(filters[0])
            except Exception:
                pass

    try:
        screen = parent.screen()
        if screen is not None:
            ag = screen.availableGeometry()
            w = int(ag.width() * 0.6)
            h = int(ag.height() * 0.6)
            dlg.resize(max(900, w), max(600, h))
            dlg.move(ag.center() - QPoint(dlg.width() // 2, dlg.height() // 2))
    except Exception:
        pass

    if dlg.exec() != QDialog.DialogCode.Accepted:
        return []
    return [Path(p) for p in dlg.selectedFiles()]


def parse_file(path: Path, *, kind: str) -> Any:
    if kind == 'TXT':
        return parse_structured_txt(path)
    if kind == 'IBW':
        return parse_ibw(path)
    if kind == 'XY':
        return parse_and_adapt_specs_xy(path)
    raise ValueError(f'Unsupported kind: {kind}')
