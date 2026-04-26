"""FSR Dictionary Dialog — full FSR vs SNR lookup table for EHT MCS 0–13.

Opened from Tools → FSR 字典.  Lets the user pick band/width and displays
a plain-text table of SNR → FSR% for every MCS (0.1 dB resolution).

The table shows one row per 0.5 dB SNR step; the user can switch to 0.1 dB
resolution via a checkbox.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from models.enums import BandId
from services.fsr_lookup import available_keys, fsr_curve

# ── MCS metadata (modulation label, PHY rate per width) ───────────────────────
_MCS_MOD = [
    "BPSK 1/2",
    "QPSK 1/2",
    "QPSK 3/4",
    "16QAM 1/2",
    "16QAM 3/4",
    "64QAM 2/3",
    "64QAM 3/4",
    "64QAM 5/6",
    "256QAM 3/4",
    "256QAM 5/6",
    "1024QAM 3/4",
    "1024QAM 5/6",
    "4096QAM 3/4",
    "4096QAM 5/6",
]

# rate_Mbps[mcs][width_key] where width_key ∈ {20,40,80,160}
_PHY_RATE: dict[int, dict[int, float]] = {
    0:  {20: 8.6,   40: 17.2,  80: 36.0,  160: 72.1},
    1:  {20: 17.2,  40: 34.4,  80: 72.1,  160: 144.1},
    2:  {20: 25.8,  40: 51.6,  80: 108.1, 160: 216.2},
    3:  {20: 34.4,  40: 68.8,  80: 144.1, 160: 288.2},
    4:  {20: 51.6,  40: 103.2, 80: 216.2, 160: 432.4},
    5:  {20: 68.8,  40: 137.6, 80: 288.2, 160: 576.5},
    6:  {20: 77.4,  40: 154.9, 80: 324.3, 160: 648.5},
    7:  {20: 86.0,  40: 172.1, 80: 360.3, 160: 720.6},
    8:  {20: 103.2, 40: 206.5, 80: 432.4, 160: 864.7},
    9:  {20: 114.7, 40: 229.4, 80: 480.4, 160: 960.8},
    10: {20: 129.0, 40: 258.1, 80: 540.4, 160: 1080.9},
    11: {20: 143.4, 40: 286.8, 80: 600.5, 160: 1201.0},
    12: {20: 154.9, 40: 309.7, 80: 648.5, 160: 1297.1},
    13: {20: 172.1, 40: 344.1, 80: 720.6, 160: 1441.2},
}

_BAND_LABEL: dict[BandId, str] = {
    BandId.BAND_2G4: "2.4 GHz",
    BandId.BAND_5G:  "5 GHz",
    BandId.BAND_6G:  "6 GHz",
}

_SNR_STYLE_GOOD   = "color:#34D399;"
_SNR_STYLE_WARN   = "color:#FCD34D;"
_SNR_STYLE_BAD    = "color:#F87171;"


def _fsr_color(fsr: float) -> str:
    if fsr >= 0.99:
        return _SNR_STYLE_GOOD
    if fsr >= 0.50:
        return _SNR_STYLE_WARN
    return _SNR_STYLE_BAD


class FsrDictDialog(QDialog):
    """Full FSR lookup table dialog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("FSR 字典 — EHT MCS Frame Success Rate")
        self.setMinimumSize(1050, 620)
        self.resize(1200, 680)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        # ── Controls bar ──────────────────────────────────────────────────
        ctrl_row = QHBoxLayout()
        ctrl_row.addWidget(QLabel("Band / Width:"))

        self._band_combo = QComboBox()
        for band, width in sorted(available_keys(), key=lambda k: (k[0].value, k[1])):
            label = f"{_BAND_LABEL.get(band, str(band))}  {width} MHz"
            self._band_combo.addItem(label, (band, width))
        # Default to 6G 160
        for i in range(self._band_combo.count()):
            b, w = self._band_combo.itemData(i)
            if b == BandId.BAND_6G and w == 160:
                self._band_combo.setCurrentIndex(i)
                break
        ctrl_row.addWidget(self._band_combo)
        ctrl_row.addSpacing(20)

        self._fine_cb = QCheckBox("0.1 dB 解析度（預設 0.5 dB）")
        ctrl_row.addWidget(self._fine_cb)
        ctrl_row.addStretch(1)

        # ── Table ─────────────────────────────────────────────────────────
        # Columns: SNR | MCS0 | MCS1 | … | MCS13
        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # ── Layout ────────────────────────────────────────────────────────
        layout = QVBoxLayout(self)
        layout.addLayout(ctrl_row)
        layout.addWidget(self._table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # ── Wire ──────────────────────────────────────────────────────────
        self._band_combo.currentIndexChanged.connect(self._rebuild)
        self._fine_cb.stateChanged.connect(self._rebuild)

        self._rebuild()

    # ──────────────────────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        band, width = self._band_combo.currentData()
        step = 1 if self._fine_cb.isChecked() else 5   # index step (0.1 dB unit)

        # Build per-MCS curves: list of (snr_db, fsr) at full 0.1 dB resolution
        curves: list[list[tuple[float, float]]] = []
        for mcs in range(14):
            curves.append(fsr_curve(band, width, mcs))

        if not curves[0]:
            self._table.setRowCount(0)
            return

        # Subsample by step
        full_len = len(curves[0])
        indices = range(0, full_len, step)

        # Build header: SNR + per-MCS (mod label + rate)
        headers = ["SNR (dB)"]
        for mcs in range(14):
            rate = _PHY_RATE.get(mcs, {}).get(width, 0.0)
            mod  = _MCS_MOD[mcs] if mcs < len(_MCS_MOD) else ""
            headers.append(f"MCS{mcs}\n{mod}\n{rate} Mbps")

        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setRowCount(len(indices))

        for row_idx, pt_idx in enumerate(indices):
            snr_db = curves[0][pt_idx][0]
            snr_item = QTableWidgetItem(f"{snr_db:.1f}")
            snr_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row_idx, 0, snr_item)

            for mcs in range(14):
                fsr = curves[mcs][pt_idx][1]
                pct = fsr * 100.0
                text = f"{pct:.1f}%"
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setForeground(
                    _qt_color(_fsr_color(fsr))
                )
                self._table.setItem(row_idx, mcs + 1, item)

        self._table.resizeColumnsToContents()

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def set_band_width(self, band: BandId, width_mhz: int) -> None:
        """Pre-select a band/width (called from Calculator tab)."""
        for i in range(self._band_combo.count()):
            b, w = self._band_combo.itemData(i)
            if b == band and w == width_mhz:
                self._band_combo.setCurrentIndex(i)
                return


def _qt_color(css: str):
    """Parse a 'color:#RRGGBB;' string into a QColor."""
    from PySide6.QtGui import QColor
    hex_part = css.split("#")[-1].rstrip(";").strip()
    return QColor(f"#{hex_part}")
