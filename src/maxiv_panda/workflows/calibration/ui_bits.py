from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QSizePolicy


def build_calibrate_control(parent: QWidget, on_open, on_toggle):
    """Create the welded 'Calibrate Energy' + power toggle control.

    Returns (container_widget, btn_calibrate, btn_power).
    """
    w = QWidget(parent)
    w.setObjectName("WCalibrateControl")
    w.setProperty("ecal_on", False)

    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)

    btn_cal = QPushButton("Calibrate Energy", w)
    btn_cal.setObjectName("BtnCalibrateEnergy")
    btn_cal.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    btn_cal.clicked.connect(on_open)
    row.addWidget(btn_cal)

    btn_pow = QPushButton(w)
    btn_pow.setObjectName("BtnECalPower")
    btn_pow.setCheckable(True)
    btn_pow.setChecked(False)
    btn_pow.setText("⏻")
    btn_pow.setToolTip(
        "Toggle E-calibrated view on the Processed tab (has effect only after calibration)."
    )
    btn_pow.toggled.connect(on_toggle)
    btn_pow.setFixedWidth(44)
    row.addWidget(btn_pow)

    w.setStyleSheet(
        """
        QWidget#WCalibrateControl {
          /* no border here; borders drawn by the two welded children */
        }

        QPushButton#BtnCalibrateEnergy {
          border: 1px solid #C9CDD3;
          border-right: 0px;
          border-top-left-radius: 6px;
          border-bottom-left-radius: 6px;
          padding: 4px 12px;
          margin: 0px;
        }
        QPushButton#BtnCalibrateEnergy:hover { background: #F3F4F6; }
        QPushButton#BtnCalibrateEnergy:pressed { background: #E5E7EB; }

        QPushButton#BtnECalPower {
          border: 1px solid #C9CDD3;
          border-top-right-radius: 6px;
          border-bottom-right-radius: 6px;
          padding: 4px 0px;
          margin: 0px;
          color: #5A2525; /* dark red text on pale off-state fill */
          background: #FEE2E2; /* Off state: red-ish */
          font-weight: 600;
        }
        QPushButton#BtnECalPower:hover { background: #FECACA; }
        QPushButton#BtnECalPower:pressed { background: #FCA5A5; }

        /* Latched ON state: more intense green + unified border around the whole welded control */
        QWidget#WCalibrateControl[ecal_on="true"] QPushButton#BtnCalibrateEnergy {
          border-color: #00A83C;
        }
        QWidget#WCalibrateControl[ecal_on="true"] QPushButton#BtnECalPower {
          border-color: #00A83C;
        }
        QPushButton#BtnECalPower:checked {
          color: #176B36;      /* dark green text on pale latched fill */
          background: #D1FAE5; /* latched */
          border-color: #00A83C;
        }
        """
    )
    return w, btn_cal, btn_pow
