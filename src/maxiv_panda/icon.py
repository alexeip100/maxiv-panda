from __future__ import annotations

"""Application icon and native desktop integration helpers."""

import atexit
import ctypes
import sys
from contextlib import contextmanager
from importlib import resources
from typing import Iterator

from PyQt6 import QtCore  # type: ignore
from PyQt6.QtGui import QIcon  # type: ignore


_ICON_PACKAGE = "maxiv_panda.data"
_ICON_NAME_WINDOWS = "panda_app_icon.ico"
_ICON_NAME_PORTABLE = "panda_app_icon.png"
_APP_USER_MODEL_ID = "MAXIV.FlexPES.PANDA"

# HICONs loaded with LR_LOADFROMFILE remain valid for the lifetime of the
# process.  Keep explicit references and release them on normal interpreter
# shutdown rather than repeatedly loading/destroying handles around WM_SETICON.
_WINDOWS_NATIVE_ICONS: list[int] = []


@contextmanager
def _icon_resource_path(prefer_windows_ico: bool = False) -> Iterator[str | None]:
    """Yield a filesystem path for the bundled application icon.

    ``importlib.resources.as_file`` also works when package resources are not
    ordinary files on disk.  The icon is consumed while the context is active.
    """
    names = (
        (_ICON_NAME_WINDOWS, _ICON_NAME_PORTABLE)
        if prefer_windows_ico
        else (_ICON_NAME_PORTABLE, _ICON_NAME_WINDOWS)
    )
    for name in names:
        try:
            target = resources.files(_ICON_PACKAGE).joinpath(name)
            if not target.is_file():
                continue
            with resources.as_file(target) as path:
                yield str(path)
                return
        except Exception:
            continue
    yield None


def application_icon() -> QIcon:
    """Return the bundled PANDA application icon.

    Windows prefers the multi-resolution ICO.  Other platforms prefer the PNG,
    while still falling back to the ICO if necessary.
    """
    with _icon_resource_path(prefer_windows_ico=sys.platform.startswith("win")) as path:
        if path:
            try:
                icon = QIcon(path)
                if not icon.isNull():
                    return icon
            except Exception:
                pass
    return QIcon()


def prepare_native_app_identity() -> None:
    """Set platform application identity before QApplication is constructed.

    On Windows, a Python-launched Qt process otherwise tends to inherit the
    generic Python taskbar identity/icon.  Giving the process its own explicit
    AppUserModelID before QApplication is created lets Explorer treat it as the
    FlexPES application instead of as ``python.exe``.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        shell32 = ctypes.windll.shell32
        func = shell32.SetCurrentProcessExplicitAppUserModelID
        func.argtypes = [ctypes.c_wchar_p]
        func.restype = ctypes.c_long
        func(_APP_USER_MODEL_ID)
    except Exception:
        # This is desktop integration only; never prevent application startup.
        pass


def configure_qt_application_identity(app) -> None:
    """Apply cross-platform Qt metadata and the bundled application icon."""
    for setter_name, value in (
        ("setApplicationName", "PANDA"),
        ("setApplicationDisplayName", "PANDA"),
        ("setOrganizationName", "MAX IV"),
        ("setOrganizationDomain", "maxiv.lu.se"),
    ):
        try:
            setter = getattr(app, setter_name)
            setter(value)
        except Exception:
            pass

    icon = application_icon()
    if not icon.isNull():
        try:
            app.setWindowIcon(icon)
        except Exception:
            pass


def apply_window_icon(window) -> None:
    """Apply the Qt icon and, on Windows, the native HWND icons as well.

    Qt's ``setWindowIcon`` is sufficient on most Linux desktops and provides
    the normal cross-platform fallback.  Windows Explorer may instead query the
    native window handle of a process launched as ``python -m ...``; therefore
    both WM_SETICON sizes are explicitly installed after the window exists.
    """
    icon = application_icon()
    if not icon.isNull():
        try:
            window.setWindowIcon(icon)
        except Exception:
            pass

    if sys.platform.startswith("win"):
        _apply_windows_native_window_icons(window)


def schedule_native_window_icon_refresh(window) -> None:
    """Repeat native icon application after Qt has completed window creation.

    A zero-delay refresh plus a short delayed refresh handles Windows/Qt cases
    where the HWND or its non-client resources are recreated during ``show``.
    """
    try:
        QtCore.QTimer.singleShot(0, lambda: apply_window_icon(window))
        QtCore.QTimer.singleShot(250, lambda: apply_window_icon(window))
    except Exception:
        pass


def _apply_windows_native_window_icons(window) -> None:
    try:
        hwnd = int(window.winId())
    except Exception:
        return
    if not hwnd:
        return

    with _icon_resource_path(prefer_windows_ico=True) as icon_path:
        if not icon_path:
            return
        try:
            user32 = ctypes.windll.user32

            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1
            SM_CXICON = 11
            SM_CYICON = 12
            SM_CXSMICON = 49
            SM_CYSMICON = 50

            load_image = user32.LoadImageW
            load_image.argtypes = [
                ctypes.c_void_p,
                ctypes.c_wchar_p,
                ctypes.c_uint,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_uint,
            ]
            load_image.restype = ctypes.c_void_p

            send_message = user32.SendMessageW
            send_message.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_ssize_t,
            ]
            send_message.restype = ctypes.c_ssize_t

            get_metric = user32.GetSystemMetrics
            get_metric.argtypes = [ctypes.c_int]
            get_metric.restype = ctypes.c_int

            big = load_image(
                None,
                icon_path,
                IMAGE_ICON,
                get_metric(SM_CXICON),
                get_metric(SM_CYICON),
                LR_LOADFROMFILE,
            )
            small = load_image(
                None,
                icon_path,
                IMAGE_ICON,
                get_metric(SM_CXSMICON),
                get_metric(SM_CYSMICON),
                LR_LOADFROMFILE,
            )

            if big:
                send_message(ctypes.c_void_p(hwnd), WM_SETICON, ICON_BIG, int(big))
                _WINDOWS_NATIVE_ICONS.append(int(big))
            if small:
                send_message(ctypes.c_void_p(hwnd), WM_SETICON, ICON_SMALL, int(small))
                _WINDOWS_NATIVE_ICONS.append(int(small))
        except Exception:
            pass


def _destroy_windows_native_icons() -> None:
    if not sys.platform.startswith("win") or not _WINDOWS_NATIVE_ICONS:
        return
    try:
        destroy_icon = ctypes.windll.user32.DestroyIcon
        destroy_icon.argtypes = [ctypes.c_void_p]
        destroy_icon.restype = ctypes.c_int
        seen: set[int] = set()
        for handle in _WINDOWS_NATIVE_ICONS:
            if handle and handle not in seen:
                seen.add(handle)
                try:
                    destroy_icon(ctypes.c_void_p(handle))
                except Exception:
                    pass
    finally:
        _WINDOWS_NATIVE_ICONS.clear()


atexit.register(_destroy_windows_native_icons)
