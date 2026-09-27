from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "maxiv_panda"


def test_close_and_clear_all_return_to_raw_data_without_clearing_plotted_data():
    text = (SRC / "ui_actions_mixin.py").read_text(encoding="utf-8")
    assert "def _return_to_raw_data" in text
    assert "self.tabs.setCurrentWidget(self.raw_data_tab)" in text
    close_body = text.split("def close_all", 1)[1].split("def clear_all", 1)[0]
    clear_body = text.split("def clear_all", 1)[1].split("def _load_file", 1)[0]
    assert "self._return_to_raw_data()" in close_body
    assert "self._return_to_raw_data()" in clear_body
    assert "plotted_data_panel.clear" not in close_body
    assert "plotted_data_panel.clear" not in clear_body


def test_raw_tab_has_stable_widget_reference():
    text = (SRC / "ui_raw_data_mixin.py").read_text(encoding="utf-8")
    assert "self.raw_data_tab = raw_tab" in text


def test_message_boxes_use_non_native_silent_wrapper_before_ui_import():
    wrapper = (SRC / "silent_message_box.py").read_text(encoding="utf-8")
    app = (SRC / "app.py").read_text(encoding="utf-8")
    assert "DontUseNativeDialog" in wrapper
    assert "QtWidgets.QMessageBox = SilentMessageBox" in wrapper
    assert "install_silent_message_boxes(QtWidgets)" in app
    assert "from .ui import MainWindow" in app
    assert app.index("install_silent_message_boxes(QtWidgets)") < app.index("from .ui import MainWindow")
