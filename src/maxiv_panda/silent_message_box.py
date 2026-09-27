from __future__ import annotations

"""Silent QMessageBox wrapper.

PANDA uses Qt's widget-based QMessageBox implementation instead of the native
platform message dialog.  On Windows the native message dialog can emit the
system notification sound for warning/information/question boxes; the Qt
widget implementation does not request that native sound.
"""

from PyQt6.QtWidgets import QMessageBox as _QtMessageBox


class SilentMessageBox(_QtMessageBox):
    """QMessageBox variant that avoids native platform message-dialog sounds."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._disable_native_dialog()

    def _disable_native_dialog(self) -> None:
        try:
            option = _QtMessageBox.Option.DontUseNativeDialog
        except AttributeError:
            return
        try:
            self.setOption(option, True)
        except Exception:
            pass

    @classmethod
    def _run_static(
        cls,
        icon,
        parent,
        title,
        text,
        buttons,
        default_button,
    ):
        box = cls(parent)
        # The native-dialog option is set in __init__, before these properties,
        # as required by Qt 6.6+.
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        if default_button != _QtMessageBox.StandardButton.NoButton:
            box.setDefaultButton(default_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is None:
            return _QtMessageBox.StandardButton.NoButton
        return box.standardButton(clicked)

    @classmethod
    def information(
        cls,
        parent,
        title,
        text,
        buttons=_QtMessageBox.StandardButton.Ok,
        defaultButton=_QtMessageBox.StandardButton.NoButton,
    ):
        return cls._run_static(
            _QtMessageBox.Icon.Information,
            parent,
            title,
            text,
            buttons,
            defaultButton,
        )

    @classmethod
    def warning(
        cls,
        parent,
        title,
        text,
        buttons=_QtMessageBox.StandardButton.Ok,
        defaultButton=_QtMessageBox.StandardButton.NoButton,
    ):
        return cls._run_static(
            _QtMessageBox.Icon.Warning,
            parent,
            title,
            text,
            buttons,
            defaultButton,
        )

    @classmethod
    def critical(
        cls,
        parent,
        title,
        text,
        buttons=_QtMessageBox.StandardButton.Ok,
        defaultButton=_QtMessageBox.StandardButton.NoButton,
    ):
        return cls._run_static(
            _QtMessageBox.Icon.Critical,
            parent,
            title,
            text,
            buttons,
            defaultButton,
        )

    @classmethod
    def question(
        cls,
        parent,
        title,
        text,
        buttons=(
            _QtMessageBox.StandardButton.Yes
            | _QtMessageBox.StandardButton.No
        ),
        defaultButton=_QtMessageBox.StandardButton.NoButton,
    ):
        return cls._run_static(
            _QtMessageBox.Icon.Question,
            parent,
            title,
            text,
            buttons,
            defaultButton,
        )


def install_silent_message_boxes(QtWidgets) -> None:
    """Make subsequent ``from PyQt6.QtWidgets import QMessageBox`` imports silent."""
    QtWidgets.QMessageBox = SilentMessageBox
