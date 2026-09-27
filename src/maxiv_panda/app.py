from __future__ import annotations

"""Application entry point for the PANDA GUI."""

import sys

from PyQt6 import QtCore, QtWidgets  # type: ignore

from .icon import (
    apply_window_icon,
    configure_qt_application_identity,
    prepare_native_app_identity,
    schedule_native_window_icon_refresh,
)
from .log_utils import configure_console_logging
from .ui_style import apply_application_style
from .silent_message_box import install_silent_message_boxes


def _qt_message_handler(message_type, context, message: str) -> None:
    """Filter one noisy Windows/Qt DPI warning while preserving other Qt messages."""
    text = str(message or "")
    if "monitorData: Unable to obtain handle for monitor" in text:
        return

    # Keep non-filtered Qt messages visible in the console.
    try:
        prefix = {
            QtCore.QtMsgType.QtDebugMsg: "Qt debug",
            QtCore.QtMsgType.QtInfoMsg: "Qt info",
            QtCore.QtMsgType.QtWarningMsg: "Qt warning",
            QtCore.QtMsgType.QtCriticalMsg: "Qt critical",
            QtCore.QtMsgType.QtFatalMsg: "Qt fatal",
        }.get(message_type, "Qt message")
    except Exception:
        prefix = "Qt message"
    try:
        sys.stderr.write(f"{prefix}: {text}\n")
    except Exception:
        pass


def _prepare_qt_environment() -> None:
    """Set Qt attributes/message filtering before QApplication is constructed."""
    try:
        QtCore.qInstallMessageHandler(_qt_message_handler)
    except Exception:
        pass
    for attr in (
        getattr(QtCore.Qt, "AA_EnableHighDpiScaling", None),
        getattr(QtCore.Qt, "AA_UseHighDpiPixmaps", None),
    ):
        if attr is None:
            continue
        try:
            QtWidgets.QApplication.setAttribute(attr, True)
        except Exception:
            pass


def main() -> None:
    """Console entry point for the `panda` and `maxiv-panda` launchers."""
    configure_console_logging()
    prepare_native_app_identity()
    _prepare_qt_environment()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    install_silent_message_boxes(QtWidgets)
    configure_qt_application_identity(app)

    # Import the UI only after installing the silent QMessageBox wrapper so
    # every module-level QMessageBox import receives the wrapper.
    from .ui import MainWindow

    # Centralised UI configuration: the existing FlexPES font remains the
    # default, with optional conservative density and accessibility scaling.
    apply_application_style(app)

    win = MainWindow()
    win.show()
    apply_window_icon(win)
    schedule_native_window_icon_refresh(win)
    raise SystemExit(app.exec())
