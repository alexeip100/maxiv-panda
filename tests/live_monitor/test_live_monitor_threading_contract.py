from pathlib import Path


def test_controller_owns_dedicated_qthread_and_moves_worker_to_it():
    source = Path('src/maxiv_panda/live_monitor/controller.py').read_text(encoding='utf-8')
    assert 'QThread(self)' in source
    assert '.moveToThread(self._thread)' in source
    assert 'BlockingQueuedConnection' in source
    assert 'self._thread.quit()' in source
    assert 'self._thread.wait(' in source


def test_worker_never_imports_or_touches_gui_widgets():
    source = Path('src/maxiv_panda/live_monitor/worker.py').read_text(encoding='utf-8')
    assert 'QtWidgets' not in source
    assert 'QWidget' not in source
    assert 'QMessageBox' not in source
    assert 'QTimer' in source
