"""Calculator Tab — Bidirectional RF Link Calculator.

Supports six "Solve For" modes — any one variable can be the unknown:

  Mode 0  RSSI       ← distance + radio params   (forward path loss)
  Mode 1  Distance   ← RSSI + radio params        (inverse path loss)
  Mode 2  SNR        ← RSSI + noise floor         (forward SNR)
  Mode 3  RSSI       ← SNR  + noise floor         (inverse SNR)
  Mode 4  Noise Floor← RSSI + SNR                 (inverse SNR, solve NF)
  Mode 5  TX Power   ← RSSI + distance            (inverse path loss, solve TxP)

All ten variables share a single QFormLayout.  Each variable row wraps a
QStackedWidget that shows either a QDoubleSpinBox (input) or a coloured
QLabel (result) depending on the active mode.

A coordinate-distance helper at the top supports two sub-modes:
  • 兩點 → 距離    : give P_A and P_B, get the Euclidean distance.
  • 原點+角度/距離 → 目標座標 : give P_A, an angle (deg) and a distance,
                              get the target coordinate (ns-3 polar layout).

「從場景匯入環境參數」fills propagation constants from the current EnvironmentModel.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from models.environment import EnvironmentModel
from models.enums import BandId, DeviceType
from services.propagation_calculator import PropagationCalculator

# Sentinel — indicates no import has been performed yet
_NOT_IMPORTED = object()

# ── Band display map ──────────────────────────────────────────────────────────
_BAND_LABELS: dict[BandId, str] = {
    BandId.BAND_2G4: "2.4 GHz",
    BandId.BAND_5G: "5 GHz",
    BandId.BAND_6G: "6 GHz",
}

# ── Solve-For mode constants ──────────────────────────────────────────────────
_M_RSSI_FROM_DIST = 0
_M_DIST_FROM_RSSI = 1
_M_SNR            = 2
_M_RSSI_FROM_SNR  = 3
_M_NF             = 4
_M_TXP            = 5

_SOLVE_LABELS = [
    "RSSI   ←  距離 + 無線參數",
    "Distance  ←  RSSI + 無線參數",
    "SNR   ←  RSSI + Noise Floor",
    "RSSI   ←  SNR + Noise Floor",
    "Noise Floor  ←  RSSI + SNR",
    "TX Power  ←  RSSI + 距離",
]

# ── Coord-helper sub-mode constants ──────────────────────────────────────────
_CM_TWO_POINTS = 0   # P_A + P_B  → distance
_CM_POLAR      = 1   # P_A + angle + distance → target coords

# ── Colour styles for result labels ──────────────────────────────────────────
_S_DIST  = "color:#38BDF8; font-weight:bold; font-size:13px; padding:2px;"
_S_PL    = "color:#FB923C; font-weight:bold; font-size:12px; padding:2px;"
_S_RSSI  = "color:#34D399; font-weight:bold; font-size:13px; padding:2px;"
_S_SNR_G = "color:#34D399; font-weight:bold; font-size:13px; padding:2px;"
_S_SNR_Y = "color:#FCD34D; font-weight:bold; font-size:13px; padding:2px;"
_S_SNR_R = "color:#F87171; font-weight:bold; font-size:13px; padding:2px;"
_S_NF    = "color:#C084FC; font-weight:bold; font-size:13px; padding:2px;"
_S_TXP   = "color:#60A5FA; font-weight:bold; font-size:13px; padding:2px;"
_S_ERR   = "color:#F87171; font-weight:bold; font-size:12px; padding:2px;"
_S_COORD = "color:#38BDF8; font-weight:bold; font-size:13px; padding:2px;"


def _snr_style(snr: float) -> str:
    if snr >= 20.0:
        return _S_SNR_G
    if snr >= 10.0:
        return _S_SNR_Y
    return _S_SNR_R


# ── Helper: build a QDoubleSpinBox ────────────────────────────────────────────
def _mk_spin(
    lo: float,
    hi: float,
    val: float,
    dec: int = 2,
    suffix: str = "",
    step: float | None = None,
) -> QDoubleSpinBox:
    sp = QDoubleSpinBox()
    sp.setRange(lo, hi)
    sp.setDecimals(dec)
    sp.setValue(val)
    if suffix:
        sp.setSuffix(suffix)
    if step is not None:
        sp.setSingleStep(step)
    else:
        sp.setStepType(QDoubleSpinBox.StepType.AdaptiveDecimalStepType)
    sp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return sp


# ── Per-variable widget: switches between input SpinBox and output Label ──────
class _VarWidget(QWidget):
    """Stacked widget: page 0 = QDoubleSpinBox (input), page 1 = QLabel (output)."""

    def __init__(self, spin: QDoubleSpinBox) -> None:
        super().__init__()
        self._spin = spin
        self._label = QLabel("—")
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._label.setMinimumHeight(spin.sizeHint().height())

        self._stack = QStackedWidget()
        self._stack.addWidget(spin)         # index 0
        self._stack.addWidget(self._label)  # index 1

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._stack)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    # ── Public API ────────────────────────────────────────────────────────

    def set_as_input(self, enabled: bool = True) -> None:
        """Show the SpinBox; grey it out if enabled=False (irrelevant param)."""
        self._stack.setCurrentIndex(0)
        self._spin.setEnabled(enabled)

    def set_as_output(self, text: str = "…", style: str = _S_RSSI) -> None:
        """Show the result Label."""
        self._label.setText(text)
        self._label.setStyleSheet(style)
        self._stack.setCurrentIndex(1)

    def update_output(self, text: str, style: str) -> None:
        """Update the label text/style (only valid while in output mode)."""
        self._label.setText(text)
        self._label.setStyleSheet(style)

    def value(self) -> float:
        """Read the SpinBox value (meaningful only when in input mode)."""
        return self._spin.value()

    def set_value(self, v: float) -> None:
        """Set the SpinBox value without emitting valueChanged."""
        self._spin.blockSignals(True)
        self._spin.setValue(v)
        self._spin.blockSignals(False)

    @property
    def spin(self) -> QDoubleSpinBox:
        return self._spin


# ── Add-node coord source indices ────────────────────────────────────────────
# These map to the _add_coord_combo items (rebuilt on coord-mode change).
_AC_POINT_A  = 0
_AC_POINT_B  = 1   # two-point mode only
_AC_TARGET   = 1   # polar mode only  (same index, different label)


# ─────────────────────────────────────────────────────────────────────────────
class CalculatorTab(QWidget):
    """Bidirectional RF link calculator with six Solve-For modes."""

    # Emitted when the user clicks "新增為 AP/STA".
    # Payload: (DeviceType, x_m: float, y_m: float, band: BandId | None, channel_width_mhz: int | None)
    # band / channel_width_mhz are None when the user has not yet clicked "匯入".
    add_node_requested = Signal(object, float, float, object, object)

    def __init__(self) -> None:
        super().__init__()
        self._calc = PropagationCalculator()
        self._env: EnvironmentModel | None = None
        self._updating = False  # re-entrancy guard

        # Set by _import_from_env(); None until the user clicks "匯入".
        self._imported_band: BandId | None = None
        self._imported_width_mhz: int | None = None

        # ── outer scroll area ─────────────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(10)

        # ── Section 1: Coordinate Distance helper ─────────────────────────
        coord_grp = QGroupBox("📐  Distance（座標換算）")
        coord_vbox = QVBoxLayout(coord_grp)
        coord_vbox.setSpacing(6)
        coord_vbox.setContentsMargins(6, 8, 6, 8)

        # ── coord sub-mode selector ───────────────────────────────────────
        coord_mode_row = QHBoxLayout()
        coord_mode_row.addWidget(QLabel("模式:"))
        self._coord_mode_combo = QComboBox()
        self._coord_mode_combo.addItem("兩點  →  距離")
        self._coord_mode_combo.addItem("原點 + 角度/距離  →  目標座標")
        coord_mode_row.addWidget(self._coord_mode_combo, stretch=1)
        coord_vbox.addLayout(coord_mode_row)

        # ── shared coord form ─────────────────────────────────────────────
        coord_form = QFormLayout()
        coord_form.setSpacing(4)
        coord_vbox.addLayout(coord_form)
        self._coord_form = coord_form  # save ref for setRowVisible

        # Row 0/1: Point A — always visible
        self._cx1 = _mk_spin(-1e5, 1e5, 0.0, suffix=" m")
        self._cy1 = _mk_spin(-1e5, 1e5, 0.0, suffix=" m")
        coord_form.addRow("Point A  X:", self._cx1)   # row 0
        coord_form.addRow("Point A  Y:", self._cy1)   # row 1

        # ── Mode 0 rows: Point B ──────────────────────────────────────────
        self._cx2 = _mk_spin(-1e5, 1e5, 100.0, suffix=" m")
        self._cy2 = _mk_spin(-1e5, 1e5, 0.0, suffix=" m")
        coord_form.addRow("Point B  X:", self._cx2)   # row 2
        coord_form.addRow("Point B  Y:", self._cy2)   # row 3

        # Row 4 (mode 0): distance result
        self._coord_dist_lbl = QLabel("—")
        self._coord_dist_lbl.setStyleSheet(_S_DIST)
        coord_form.addRow("Distance:", self._coord_dist_lbl)  # row 4

        # ── Mode 1 rows: Angle + polar distance ───────────────────────────
        self._c_angle = _mk_spin(0.0, 360.0, 0.0, dec=1, suffix=" °", step=1.0)
        self._c_polar_dist = _mk_spin(0.0, 1e6, 100.0, suffix=" m")
        coord_form.addRow("角度 (°):", self._c_angle)          # row 5
        coord_form.addRow("距離 (d):", self._c_polar_dist)     # row 6

        # Row 7/8 (mode 1): computed target coordinates
        self._c_target_x_lbl = QLabel("—")
        self._c_target_x_lbl.setStyleSheet(_S_COORD)
        self._c_target_y_lbl = QLabel("—")
        self._c_target_y_lbl.setStyleSheet(_S_COORD)
        coord_form.addRow("目標 X:", self._c_target_x_lbl)    # row 7
        coord_form.addRow("目標 Y:", self._c_target_y_lbl)    # row 8

        # ── Buttons (always visible) ──────────────────────────────────────
        btn_row = QHBoxLayout()

        btn_pipe = QPushButton("↓  帶入下方 Distance 欄位")
        btn_pipe.setMaximumHeight(24)
        btn_pipe.setToolTip(
            "Mode 0：將兩點距離帶入主計算器 Distance 欄位\n"
            "Mode 1：將極座標距離帶入主計算器 Distance 欄位"
        )
        btn_pipe.clicked.connect(self._pipe_coord_distance)
        btn_row.addWidget(btn_pipe)

        self._btn_set_origin = QPushButton("↖  設為起點 A")
        self._btn_set_origin.setMaximumHeight(24)
        self._btn_set_origin.setToolTip("將目標座標填回 Point A，方便連續計算")
        self._btn_set_origin.clicked.connect(self._set_target_as_origin)
        btn_row.addWidget(self._btn_set_origin)

        coord_form.addRow("", _make_layout_widget(btn_row))   # row 9

        root.addWidget(coord_grp)

        # ── Section 1b: Add node from coord ──────────────────────────────
        add_grp = QGroupBox("➕  新增為節點")
        add_vbox = QVBoxLayout(add_grp)
        add_vbox.setSpacing(5)
        add_vbox.setContentsMargins(6, 8, 6, 8)

        # Coord source selector (options vary by coord mode)
        add_src_row = QHBoxLayout()
        add_src_row.addWidget(QLabel("座標來源:"))
        self._add_coord_combo = QComboBox()
        add_src_row.addWidget(self._add_coord_combo, stretch=1)
        add_vbox.addLayout(add_src_row)

        # Preview label — shows the currently selected coordinate value
        self._add_coord_preview = QLabel("( —, — )")
        self._add_coord_preview.setStyleSheet(_S_COORD)
        self._add_coord_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        add_vbox.addWidget(self._add_coord_preview)

        # AP / STA buttons
        add_btn_row = QHBoxLayout()
        btn_add_ap = QPushButton("🔵  新增為 AP")
        btn_add_ap.setMinimumHeight(26)
        btn_add_ap.setToolTip("以所選座標位置新增一個 AP 節點至場景")
        btn_add_ap.clicked.connect(lambda: self._add_node(DeviceType.AP))
        btn_add_sta = QPushButton("🟢  新增為 STA")
        btn_add_sta.setMinimumHeight(26)
        btn_add_sta.setToolTip("以所選座標位置新增一個 STA 節點至場景")
        btn_add_sta.clicked.connect(lambda: self._add_node(DeviceType.STA))
        add_btn_row.addWidget(btn_add_ap)
        add_btn_row.addWidget(btn_add_sta)
        add_vbox.addLayout(add_btn_row)

        self._add_node_grp = add_grp   # visibility toggled by coord mode
        root.addWidget(add_grp)

        # ── Section 2: Solve-For mode selector ───────────────────────────
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("🔧  Solve For:"))
        self._solve_combo = QComboBox()
        for lbl in _SOLVE_LABELS:
            self._solve_combo.addItem(lbl)
        mode_row.addWidget(self._solve_combo, stretch=1)
        root.addLayout(mode_row)

        # ── Section 3: Unified variable form ─────────────────────────────
        calc_grp = QGroupBox("參數")
        calc_form = QFormLayout(calc_grp)
        calc_form.setSpacing(4)

        # Build all variable widgets
        self._v_dist = _VarWidget(_mk_spin(0.0, 1e6, 100.0, suffix=" m"))
        self._v_txp  = _VarWidget(_mk_spin(-10.0, 40.0,   16.02, suffix=" dBm", step=0.5))
        self._v_txg  = _VarWidget(_mk_spin(-10.0, 30.0,    0.00, suffix=" dBi", step=0.5))
        self._v_rxg  = _VarWidget(_mk_spin(-10.0, 30.0,    0.00, suffix=" dBi", step=0.5))
        self._v_d0   = _VarWidget(_mk_spin(0.01, 1000.0,   1.00, suffix=" m"))
        self._v_pl0  = _VarWidget(_mk_spin(0.0,  150.0,   46.68, suffix=" dB",  step=0.5))
        self._v_n    = _VarWidget(_mk_spin(1.0,    6.0,    3.00, step=0.1))
        self._v_rssi = _VarWidget(_mk_spin(-130.0,  0.0,  -60.00, suffix=" dBm", step=0.5))
        self._v_nf   = _VarWidget(_mk_spin(-130.0, -20.0, -93.97, suffix=" dBm", step=0.5))
        self._v_snr  = _VarWidget(_mk_spin(-50.0, 100.0,   33.97, suffix=" dB",  step=0.5))

        calc_form.addRow("Distance (d):",      self._v_dist)
        calc_form.addRow("TX Power:",          self._v_txp)
        calc_form.addRow("TX Gain:",           self._v_txg)
        calc_form.addRow("RX Gain:",           self._v_rxg)
        calc_form.addRow("Ref. Distance (d₀):", self._v_d0)
        calc_form.addRow("Ref. Loss (PL₀):",   self._v_pl0)
        calc_form.addRow("Path Loss Exp. (n):", self._v_n)
        calc_form.addRow("RSSI:",              self._v_rssi)
        calc_form.addRow("Noise Floor:",       self._v_nf)
        calc_form.addRow("SNR:",               self._v_snr)

        root.addWidget(calc_grp)

        # ── Section 4: Derived results (always shown) ─────────────────────
        result_grp = QGroupBox("結果")
        result_form = QFormLayout(result_grp)
        result_form.setSpacing(4)

        self._r_pl   = QLabel("—")
        self._r_pl.setStyleSheet(_S_PL)
        self._r_main = QLabel("—")   # highlighted result for the solved variable
        self._r_main.setStyleSheet(_S_RSSI)

        result_form.addRow("Path Loss:", self._r_pl)
        result_form.addRow("主要結果:",   self._r_main)

        root.addWidget(result_grp)

        # ── Section 5: Import from Scene ──────────────────────────────────
        env_grp = QGroupBox("⚙  從場景匯入環境參數")
        env_layout = QVBoxLayout(env_grp)
        env_layout.setSpacing(6)

        band_row = QHBoxLayout()
        band_row.addWidget(QLabel("Band:"))
        self._band_combo = QComboBox()
        for band, lbl in _BAND_LABELS.items():
            self._band_combo.addItem(lbl, band.name)
        self._band_combo.setCurrentIndex(1)   # default 5 GHz
        band_row.addWidget(self._band_combo, stretch=1)
        env_layout.addLayout(band_row)

        width_row = QHBoxLayout()
        width_row.addWidget(QLabel("Configured Width:"))
        self._width_combo = QComboBox()
        width_row.addWidget(self._width_combo, stretch=1)
        env_layout.addLayout(width_row)

        self._width_hint = QLabel("Effective Measurement Width: —")
        self._width_hint.setStyleSheet("color:#64748B; font-size:10px;")
        self._width_hint.setToolTip(
            "First-pass ns-3 alignment: effective measurement width currently equals "
            "configured width. HE-specific fallback rules are not modeled yet."
        )
        env_layout.addWidget(self._width_hint)

        self._noise_source_hint = QLabel("Noise Source: —")
        self._noise_source_hint.setStyleSheet("color:#64748B; font-size:10px;")
        env_layout.addWidget(self._noise_source_hint)

        self._env_hint = QLabel("（尚未連接場景）")
        self._env_hint.setStyleSheet("color:#64748B; font-size:10px;")
        self._env_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        env_layout.addWidget(self._env_hint)

        btn_import = QPushButton("匯入  ref_dist / ref_loss / n / resolved_noise_floor")
        btn_import.setMaximumHeight(26)
        btn_import.setToolTip(
            "從目前場景的環境設定匯入：\n"
            "  • Ref. Distance (d₀)\n"
            "  • Ref. Loss (PL₀)  ← 依選擇的 Band\n"
            "  • Path Loss Exp. (n)\n"
            "  • Resolved Noise Floor  ← Band override / global override / NF+width\n\n"
            "注意：TX Power 為 per-device 參數（各裝置獨立設定），\n"
            "不屬於環境參數，故不在匯入範圍內。"
        )
        btn_import.clicked.connect(self._import_from_env)
        env_layout.addWidget(btn_import)

        root.addWidget(env_grp)
        root.addStretch(1)

        scroll.setWidget(container)
        outer.addWidget(scroll)

        # ── All variable widgets for iteration ────────────────────────────
        self._rf_vars  = [self._v_dist, self._v_txp, self._v_txg, self._v_rxg,
                          self._v_d0, self._v_pl0, self._v_n]
        self._snr_vars = [self._v_rssi, self._v_nf, self._v_snr]
        self._all_vars = self._rf_vars + self._snr_vars

        # ── Wire signals ──────────────────────────────────────────────────
        for vw in self._all_vars:
            vw.spin.valueChanged.connect(self._recalc)

        for sp in (self._cx1, self._cy1, self._cx2, self._cy2):
            sp.valueChanged.connect(self._recalc_coord)

        for sp in (self._c_angle, self._c_polar_dist):
            sp.valueChanged.connect(self._recalc_coord)

        self._solve_combo.currentIndexChanged.connect(self._on_mode_changed)
        self._coord_mode_combo.currentIndexChanged.connect(self._on_coord_mode_changed)
        self._add_coord_combo.currentIndexChanged.connect(self._update_add_coord_preview)
        self._band_combo.currentIndexChanged.connect(self._on_band_changed)
        self._width_combo.currentIndexChanged.connect(self._on_width_changed)

        # Initial render
        self._on_coord_mode_changed(0)   # sets row visibility + recalcs coord + rebuilds add-combo
        self._sync_band_width_controls()
        self._on_mode_changed(0)         # triggers _apply_mode + _recalc

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_environment(self, env: EnvironmentModel | None) -> None:
        """Store environment; updates hint label."""
        self._env = env
        if env is not None:
            self._env_hint.setText("場景環境已就緒，點擊按鈕匯入")
            self._env_hint.setStyleSheet("color:#34D399; font-size:10px;")
        else:
            self._env_hint.setText("（尚未連接場景）")
            self._env_hint.setStyleSheet("color:#64748B; font-size:10px;")
        self._sync_band_width_controls()
        self._refresh_noise_preview()

    # ──────────────────────────────────────────────────────────────────────────
    # Coord sub-mode management
    # ──────────────────────────────────────────────────────────────────────────

    def _on_coord_mode_changed(self, mode: int) -> None:
        """Toggle visible rows in the coord helper section."""
        cf = self._coord_form
        is_two_pts = (mode == _CM_TWO_POINTS)

        # Mode 0 rows: Point B (2,3) + Distance result (4)
        for row in (2, 3, 4):
            cf.setRowVisible(row, is_two_pts)

        # Mode 1 rows: angle (5), polar dist (6), target X (7), target Y (8)
        for row in (5, 6, 7, 8):
            cf.setRowVisible(row, not is_two_pts)

        # "設為起點" button only makes sense in polar mode
        self._btn_set_origin.setVisible(not is_two_pts)

        # "新增為節點" group only shows in polar mode
        self._add_node_grp.setVisible(not is_two_pts)

        # Rebuild the coord-source options in the add-node group
        self._add_coord_combo.blockSignals(True)
        self._add_coord_combo.clear()
        self._add_coord_combo.addItem("Point A  (原點)")
        if is_two_pts:
            self._add_coord_combo.addItem("Point B  (目標點)")
        else:
            self._add_coord_combo.addItem("目標座標  (計算結果)")
        self._add_coord_combo.blockSignals(False)

        self._recalc_coord()

    # ──────────────────────────────────────────────────────────────────────────
    # RF mode management
    # ──────────────────────────────────────────────────────────────────────────

    def _on_mode_changed(self, mode: int) -> None:
        self._apply_mode(mode)
        self._recalc()

    def _apply_mode(self, mode: int) -> None:
        """Configure which variables are inputs vs. outputs for *mode*."""
        # Reset everything to enabled input first
        for vw in self._all_vars:
            vw.set_as_input(True)

        if mode == _M_RSSI_FROM_DIST:
            # RF params → RSSI; SNR is derived from RSSI − NF (output only)
            self._v_rssi.set_as_output(style=_S_RSSI)
            self._v_snr.set_as_output(style=_S_SNR_Y)

        elif mode == _M_DIST_FROM_RSSI:
            # RSSI + RF params → Distance; SNR is derived from RSSI − NF (output only)
            self._v_dist.set_as_output(style=_S_DIST)
            self._v_snr.set_as_output(style=_S_SNR_Y)

        elif mode == _M_SNR:
            # RSSI + NF → SNR; RF params irrelevant
            self._v_snr.set_as_output(style=_S_SNR_Y)
            for vw in self._rf_vars:
                vw.set_as_input(False)

        elif mode == _M_RSSI_FROM_SNR:
            # SNR + NF → RSSI; RF params irrelevant
            self._v_rssi.set_as_output(style=_S_RSSI)
            for vw in self._rf_vars:
                vw.set_as_input(False)

        elif mode == _M_NF:
            # RSSI + SNR → Noise Floor; RF params irrelevant
            self._v_nf.set_as_output(style=_S_NF)
            for vw in self._rf_vars:
                vw.set_as_input(False)

        elif mode == _M_TXP:
            # RSSI + distance + params → TX Power; SNR is derived (output only)
            self._v_txp.set_as_output(style=_S_TXP)
            self._v_snr.set_as_output(style=_S_SNR_Y)

    # ──────────────────────────────────────────────────────────────────────────
    # RF Calculations
    # ──────────────────────────────────────────────────────────────────────────

    def _recalc(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            self._do_recalc(self._solve_combo.currentIndex())
        finally:
            self._updating = False

    def _do_recalc(self, mode: int) -> None:
        c = self._calc

        # Helper lambdas for reading inputs
        def d()   -> float: return self._v_dist.value()
        def txp() -> float: return self._v_txp.value()
        def txg() -> float: return self._v_txg.value()
        def rxg() -> float: return self._v_rxg.value()
        def d0()  -> float: return self._v_d0.value()
        def pl0() -> float: return self._v_pl0.value()
        def n()   -> float: return self._v_n.value()
        def rssi()-> float: return self._v_rssi.value()
        def nf()  -> float: return self._v_nf.value()
        def snr() -> float: return self._v_snr.value()

        try:
            if mode == _M_RSSI_FROM_DIST:
                pl   = c.compute_path_loss_db(d(), d0(), pl0(), n())
                _rssi = c.compute_rssi_dbm(txp(), pl, txg(), rxg())
                _snr = c.compute_snr_db(_rssi, nf())
                self._v_rssi.update_output(f"{_rssi:.2f} dBm", _S_RSSI)
                self._v_snr.update_output(f"{_snr:.2f} dB", _snr_style(_snr))
                self._show_derived(pl, _rssi, _snr)

            elif mode == _M_DIST_FROM_RSSI:
                if n() <= 0:
                    raise ValueError("Path Loss Exp. (n) 必須 > 0")
                effective_pl = txp() + txg() + rxg() - rssi()
                exponent_val = (effective_pl - pl0()) / (10.0 * n())
                dist_m = d0() * (10.0 ** exponent_val)
                pl = effective_pl
                _snr = c.compute_snr_db(rssi(), nf())
                self._v_dist.update_output(f"{dist_m:.3f} m", _S_DIST)
                self._v_snr.update_output(f"{_snr:.2f} dB", _snr_style(_snr))
                self._show_derived(pl, rssi(), _snr, dist_m=dist_m)

            elif mode == _M_SNR:
                _snr = c.compute_snr_db(rssi(), nf())
                self._v_snr.update_output(f"{_snr:.2f} dB", _snr_style(_snr))
                self._show_derived(None, rssi(), _snr)

            elif mode == _M_RSSI_FROM_SNR:
                _rssi = snr() + nf()
                self._v_rssi.update_output(f"{_rssi:.2f} dBm", _S_RSSI)
                self._show_derived(None, _rssi, snr())

            elif mode == _M_NF:
                _nf = rssi() - snr()
                self._v_nf.update_output(f"{_nf:.2f} dBm", _S_NF)
                self._show_derived(None, rssi(), snr())

            elif mode == _M_TXP:
                pl   = c.compute_path_loss_db(d(), d0(), pl0(), n())
                _txp = rssi() + pl - txg() - rxg()
                _snr = c.compute_snr_db(rssi(), nf())
                self._v_txp.update_output(f"{_txp:.2f} dBm", _S_TXP)
                self._v_snr.update_output(f"{_snr:.2f} dB", _snr_style(_snr))
                self._show_derived(pl, rssi(), _snr)

        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            self._show_error(str(exc))

    def _show_derived(
        self,
        pl: float | None,
        rssi: float | None,
        snr: float | None,
        dist_m: float | None = None,
    ) -> None:
        """Update the always-visible Path Loss and main-result labels."""
        mode = self._solve_combo.currentIndex()

        if pl is not None:
            self._r_pl.setText(f"{pl:.2f} dB")
            self._r_pl.setStyleSheet(_S_PL)
        else:
            self._r_pl.setText("—  (此模式不計算)")
            self._r_pl.setStyleSheet("color:#475569; font-size:12px;")

        # Main result label mirrors the solved variable with its colour
        if mode == _M_RSSI_FROM_DIST and rssi is not None:
            self._r_main.setText(f"RSSI = {rssi:.2f} dBm")
            self._r_main.setStyleSheet(_S_RSSI)
        elif mode == _M_DIST_FROM_RSSI and dist_m is not None:
            self._r_main.setText(f"Distance = {dist_m:.3f} m")
            self._r_main.setStyleSheet(_S_DIST)
        elif mode in (_M_SNR, _M_RSSI_FROM_SNR, _M_NF) and snr is not None:
            self._r_main.setText(f"SNR = {snr:.2f} dB")
            self._r_main.setStyleSheet(_snr_style(snr))
        elif mode == _M_TXP and rssi is not None:
            self._r_main.setText(f"RSSI = {rssi:.2f} dBm   SNR = {snr:.2f} dB"
                                  if snr is not None else f"RSSI = {rssi:.2f} dBm")
            self._r_main.setStyleSheet(_S_RSSI)
        else:
            self._r_main.setText("—")

    def _show_error(self, msg: str) -> None:
        short = msg[:60] + ("…" if len(msg) > 60 else "")
        self._r_main.setText(f"⚠ {short}")
        self._r_main.setStyleSheet(_S_ERR)

    # ──────────────────────────────────────────────────────────────────────────
    # Coordinate helper
    # ──────────────────────────────────────────────────────────────────────────

    def _recalc_coord(self) -> None:
        """Recompute coord section based on the active sub-mode."""
        mode = self._coord_mode_combo.currentIndex()

        if mode == _CM_TWO_POINTS:
            # Euclidean distance between P_A and P_B
            d = self._calc.compute_distance_m(
                self._cx1.value(), self._cy1.value(),
                self._cx2.value(), self._cy2.value(),
            )
            self._coord_dist_lbl.setText(f"{d:.3f} m")

        else:  # _CM_POLAR
            # Polar → Cartesian  (same formula as ns-3 BuildStaPositionsForBss)
            #   tx = x1 + dist * cos(angle_rad)
            #   ty = y1 + dist * sin(angle_rad)
            x1   = self._cx1.value()
            y1   = self._cy1.value()
            dist = self._c_polar_dist.value()
            rad  = math.radians(self._c_angle.value())
            tx   = x1 + dist * math.cos(rad)
            ty   = y1 + dist * math.sin(rad)
            self._c_target_x_lbl.setText(f"{tx:.3f} m")
            self._c_target_y_lbl.setText(f"{ty:.3f} m")

        # Keep the add-node preview up to date
        self._update_add_coord_preview()

    def _pipe_coord_distance(self) -> None:
        """Copy a distance value into the main Distance variable.

        Mode 0 (two-point): pipes the computed Euclidean distance.
        Mode 1 (polar):     pipes the polar distance input directly.
        """
        mode = self._coord_mode_combo.currentIndex()

        if mode == _CM_TWO_POINTS:
            d = self._calc.compute_distance_m(
                self._cx1.value(), self._cy1.value(),
                self._cx2.value(), self._cy2.value(),
            )
        else:
            d = self._c_polar_dist.value()

        self._v_dist.set_value(d)
        self._recalc()

    def _get_selected_coord(self) -> tuple[float, float]:
        """Return (x_m, y_m) for whichever coord source is chosen in the add-node combo."""
        coord_mode = self._coord_mode_combo.currentIndex()
        src_idx    = self._add_coord_combo.currentIndex()

        if src_idx == _AC_POINT_A:
            return self._cx1.value(), self._cy1.value()

        # src_idx == 1: Point B (two-point mode) or computed Target (polar mode)
        if coord_mode == _CM_TWO_POINTS:
            return self._cx2.value(), self._cy2.value()
        else:
            # Recompute target to ensure consistency
            x1   = self._cx1.value()
            y1   = self._cy1.value()
            dist = self._c_polar_dist.value()
            rad  = math.radians(self._c_angle.value())
            return x1 + dist * math.cos(rad), y1 + dist * math.sin(rad)

    def _update_add_coord_preview(self, _index: int = 0) -> None:
        """Refresh the coordinate preview label in the add-node group."""
        try:
            x, y = self._get_selected_coord()
            self._add_coord_preview.setText(f"( {x:.3f} m,  {y:.3f} m )")
        except Exception:
            self._add_coord_preview.setText("( —, — )")

    def _add_node(self, device_type: DeviceType) -> None:
        """Emit add_node_requested with the currently previewed coordinate.

        band and channel_width_mhz are None when the user has not yet clicked
        "匯入" — the receiver should fall back to its own defaults in that case.
        """
        x, y = self._get_selected_coord()
        self.add_node_requested.emit(
            device_type, x, y,
            self._imported_band,
            self._imported_width_mhz,
        )

    def _set_target_as_origin(self) -> None:
        """（極座標模式）將目標座標填回 Point A，方便連續計算下一段路徑。"""
        x1   = self._cx1.value()
        y1   = self._cy1.value()
        dist = self._c_polar_dist.value()
        rad  = math.radians(self._c_angle.value())
        tx   = x1 + dist * math.cos(rad)
        ty   = y1 + dist * math.sin(rad)

        for sp in (self._cx1, self._cy1):
            sp.blockSignals(True)
        self._cx1.setValue(tx)
        self._cy1.setValue(ty)
        for sp in (self._cx1, self._cy1):
            sp.blockSignals(False)

        self._recalc_coord()

    # ──────────────────────────────────────────────────────────────────────────
    # Import from scene
    # ──────────────────────────────────────────────────────────────────────────

    def _import_from_env(self) -> None:
        if self._env is None:
            return

        selected_band = BandId[self._band_combo.currentData()]
        configured_width_mhz = self._width_combo.currentData()
        bp = next(
            (b for b in self._env.band_profiles if b.band == selected_band), None
        )

        targets = [self._v_d0.spin, self._v_n.spin,
                   self._v_nf.spin, self._v_pl0.spin]
        for sp in targets:
            sp.blockSignals(True)

        self._v_d0.set_value(self._env.reference_distance_m)
        self._v_n.set_value(self._env.path_loss_exponent)

        effective_width_mhz = self._calc.resolve_effective_measurement_width_mhz(
            configured_width_mhz
        )
        noise, noise_source = self._calc.resolve_noise_floor_dbm(
            bp.manual_noise_floor_dbm if bp is not None else None,
            self._env.manual_global_noise_floor_dbm,
            effective_width_mhz,
            self._env.rx_noise_figure_db,
        )
        self._v_nf.set_value(noise)

        if bp is not None:
            self._v_pl0.set_value(bp.reference_loss_db)

        for sp in targets:
            sp.blockSignals(False)

        # Remember which band/width was imported — used when adding nodes.
        self._imported_band = selected_band
        self._imported_width_mhz = effective_width_mhz

        self._width_hint.setText(
            f"Effective Measurement Width: {effective_width_mhz} MHz"
        )
        self._noise_source_hint.setText(f"Noise Source: {noise_source}")
        self._recalc()

    def _on_band_changed(self, _index: int) -> None:
        self._sync_band_width_controls()
        self._refresh_noise_preview()

    def _on_width_changed(self, _index: int) -> None:
        self._refresh_noise_preview()

    def _sync_band_width_controls(self) -> None:
        band = BandId[self._band_combo.currentData()]
        allowed = self._calc.allowed_channel_widths_for_band(band)
        current = self._width_combo.currentData()
        normalized = self._calc.normalize_channel_width_for_band(current, band)
        self._width_combo.blockSignals(True)
        self._width_combo.clear()
        for width_mhz in allowed:
            self._width_combo.addItem(f"{width_mhz} MHz", width_mhz)
        idx = self._width_combo.findData(normalized)
        self._width_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._width_combo.blockSignals(False)

    def _refresh_noise_preview(self) -> None:
        band = BandId[self._band_combo.currentData()]
        configured_width_mhz = self._width_combo.currentData()
        if configured_width_mhz is None:
            self._width_hint.setText("Effective Measurement Width: —")
            self._noise_source_hint.setText("Noise Source: —")
            return
        effective_width_mhz = self._calc.resolve_effective_measurement_width_mhz(
            configured_width_mhz
        )
        self._width_hint.setText(
            f"Effective Measurement Width: {effective_width_mhz} MHz"
        )
        if self._env is None:
            self._noise_source_hint.setText("Noise Source: —")
            return
        bp = next((b for b in self._env.band_profiles if b.band == band), None)
        _, noise_source = self._calc.resolve_noise_floor_dbm(
            bp.manual_noise_floor_dbm if bp is not None else None,
            self._env.manual_global_noise_floor_dbm,
            effective_width_mhz,
            self._env.rx_noise_figure_db,
        )
        self._noise_source_hint.setText(f"Noise Source: {noise_source}")


# ── Module-level helper ───────────────────────────────────────────────────────
def _make_layout_widget(layout: QHBoxLayout) -> QWidget:
    """Wrap a QHBoxLayout in a plain QWidget so it can be passed to addRow."""
    w = QWidget()
    w.setLayout(layout)
    w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return w
