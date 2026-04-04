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

A coordinate-distance helper at the top can pipe a distance value into the
main calculator.  「從場景匯入環境參數」fills propagation constants from the
current EnvironmentModel.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
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
from models.enums import BandId
from services.propagation_calculator import PropagationCalculator

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


# ─────────────────────────────────────────────────────────────────────────────
class CalculatorTab(QWidget):
    """Bidirectional RF link calculator with six Solve-For modes."""

    def __init__(self) -> None:
        super().__init__()
        self._calc = PropagationCalculator()
        self._env: EnvironmentModel | None = None
        self._updating = False  # re-entrancy guard

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
        coord_form = QFormLayout(coord_grp)
        coord_form.setSpacing(4)

        self._cx1 = _mk_spin(-1e5, 1e5, 0.0, suffix=" m")
        self._cy1 = _mk_spin(-1e5, 1e5, 0.0, suffix=" m")
        self._cx2 = _mk_spin(-1e5, 1e5, 100.0, suffix=" m")
        self._cy2 = _mk_spin(-1e5, 1e5, 0.0, suffix=" m")

        coord_form.addRow("Point A  X:", self._cx1)
        coord_form.addRow("Point A  Y:", self._cy1)
        coord_form.addRow("Point B  X:", self._cx2)
        coord_form.addRow("Point B  Y:", self._cy2)

        self._coord_dist_lbl = QLabel("—")
        self._coord_dist_lbl.setStyleSheet(_S_DIST)
        coord_form.addRow("Distance:", self._coord_dist_lbl)

        btn_pipe = QPushButton("↓  帶入下方 Distance 欄位")
        btn_pipe.setMaximumHeight(24)
        btn_pipe.setToolTip("Copy this distance into the main calculator's Distance field")
        btn_pipe.clicked.connect(self._pipe_coord_distance)
        coord_form.addRow("", btn_pipe)

        root.addWidget(coord_grp)

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
            self._band_combo.addItem(lbl, band)
        self._band_combo.setCurrentIndex(1)   # default 5 GHz
        band_row.addWidget(self._band_combo, stretch=1)
        env_layout.addLayout(band_row)

        self._env_hint = QLabel("（尚未連接場景）")
        self._env_hint.setStyleSheet("color:#64748B; font-size:10px;")
        self._env_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        env_layout.addWidget(self._env_hint)

        btn_import = QPushButton("匯入  ref_dist / ref_loss / n / noise_floor")
        btn_import.setMaximumHeight(26)
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

        self._solve_combo.currentIndexChanged.connect(self._on_mode_changed)

        # Initial render
        self._recalc_coord()
        self._on_mode_changed(0)   # triggers _apply_mode + _recalc

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

    # ──────────────────────────────────────────────────────────────────────────
    # Mode management
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
            # RF params → RSSI; SNR derivation uses NF; disable SNR input
            self._v_rssi.set_as_output(style=_S_RSSI)
            self._v_snr.set_as_input(False)

        elif mode == _M_DIST_FROM_RSSI:
            # RSSI + RF params → Distance; SNR derivation uses NF; disable SNR input
            self._v_dist.set_as_output(style=_S_DIST)
            self._v_snr.set_as_input(False)

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
            # RSSI + distance + params → TX Power; disable SNR input
            self._v_txp.set_as_output(style=_S_TXP)
            self._v_snr.set_as_input(False)

    # ──────────────────────────────────────────────────────────────────────────
    # Calculations
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
                self._show_derived(pl, rssi(), _snr)

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
                self._show_derived(pl, rssi(), _snr)

        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            self._show_error(str(exc))

    def _show_derived(
        self,
        pl: float | None,
        rssi: float | None,
        snr: float | None,
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
        elif mode == _M_DIST_FROM_RSSI:
            pass   # shown in the variable row itself; main result repeats PL
            self._r_main.setText(f"Path Loss = {pl:.2f} dB" if pl is not None else "—")
            self._r_main.setStyleSheet(_S_PL)
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
        d = self._calc.compute_distance_m(
            self._cx1.value(), self._cy1.value(),
            self._cx2.value(), self._cy2.value(),
        )
        self._coord_dist_lbl.setText(f"{d:.3f} m")

    def _pipe_coord_distance(self) -> None:
        """Copy the coordinate distance into the main Distance variable."""
        d = self._calc.compute_distance_m(
            self._cx1.value(), self._cy1.value(),
            self._cx2.value(), self._cy2.value(),
        )
        self._v_dist.set_value(d)
        # If dist is currently an input, recalc picks it up automatically.
        # If it's the output (mode 1), changing it doesn't matter, but recalc anyway.
        self._recalc()

    # ──────────────────────────────────────────────────────────────────────────
    # Import from scene
    # ──────────────────────────────────────────────────────────────────────────

    def _import_from_env(self) -> None:
        if self._env is None:
            return

        selected_band: BandId = self._band_combo.currentData()
        bp = next(
            (b for b in self._env.band_profiles if b.band == selected_band), None
        )

        targets = [self._v_d0.spin, self._v_n.spin,
                   self._v_nf.spin, self._v_pl0.spin]
        for sp in targets:
            sp.blockSignals(True)

        self._v_d0.set_value(self._env.reference_distance_m)
        self._v_n.set_value(self._env.path_loss_exponent)

        noise = (
            bp.noise_floor_dbm
            if bp is not None and bp.noise_floor_dbm is not None
            else self._env.default_noise_floor_dbm
        )
        self._v_nf.set_value(noise)

        if bp is not None:
            self._v_pl0.set_value(bp.reference_loss_db)

        for sp in targets:
            sp.blockSignals(False)

        self._recalc()
