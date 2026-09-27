from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def energy_axis() -> np.ndarray:
    return np.linspace(0.0, 20.0, 2001)


@pytest.fixture
def synthetic_peak(energy_axis: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = energy_axis
    y = 0.15 + 0.004 * x + 3.0 * np.exp(-0.5 * ((x - 8.2) / 0.22) ** 2)
    return x, y

@pytest.fixture(scope="session")
def qapp():
    pytest.importorskip("PyQt6")
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    return app
