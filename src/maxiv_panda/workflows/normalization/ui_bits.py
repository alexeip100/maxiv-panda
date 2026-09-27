from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QCheckBox, QDoubleSpinBox, QLabel, QGroupBox


def build_normalization_control(
    parent: QWidget,
) -> tuple[QWidget, QCheckBox, QDoubleSpinBox, QDoubleSpinBox, QLabel]:
    """Create the compact Processed-tab normalization controls."""

    w = QGroupBox("Normalization", parent)
    w.setObjectName("NormalizationGroup")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(8, 8, 8, 6)
    lay.setSpacing(6)

    cb = QCheckBox("Norm E:", w)
    cb.setToolTip(
        "Normalize each plotted curve to the mean intensity over the selected energy span."
    )

    sb_energy = QDoubleSpinBox(w)
    sb_energy.setDecimals(3)
    sb_energy.setRange(-1e6, 1e6)
    sb_energy.setSingleStep(0.1)
    sb_energy.setMinimumWidth(92)
    sb_energy.setSuffix(" eV")
    sb_energy.setToolTip("Centre energy of the normalization interval.")

    span_label = QLabel("E span:", w)
    span_label.setToolTip("Averaging width as a percentage of each spectrum's full energy span.")

    sb_span = QDoubleSpinBox(w)
    sb_span.setDecimals(1)
    sb_span.setRange(0.1, 20.0)
    sb_span.setSingleStep(0.1)
    sb_span.setValue(1.0)
    sb_span.setMinimumWidth(70)
    sb_span.setSuffix(" %")
    sb_span.setToolTip(
        "Width of the averaging interval. Near an edge, the interval shifts inward "
        "and keeps the same width."
    )

    span_ev = QLabel("", w)
    span_ev.setMinimumWidth(66)
    span_ev.setToolTip("Approximate averaging width in eV for the selected spectra.")

    lay.addWidget(cb)
    lay.addWidget(sb_energy)
    lay.addWidget(span_label)
    lay.addWidget(sb_span)
    lay.addWidget(span_ev)

    w.setStyleSheet(
        """
        QGroupBox#NormalizationGroup {
            border: 1px solid palette(mid);
            border-radius: 5px;
            margin-top: 7px;
            padding-top: 2px;
        }
        QGroupBox#NormalizationGroup::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 8px;
            padding: 0 3px;
            color: palette(window-text);
            font-weight: 600;
        }
        """
    )

    return w, cb, sb_energy, sb_span, span_ev
