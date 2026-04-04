"""Environment tab — Phase B upgrade.

Combines the read-only scene-summary section from Phase A with newly
editable propagation-model parameters (path-loss exponent, reference
distance, noise floor) and band-profile rows.

Backward-compatible API:
  set_summary(width_m, height_m, ap_count, sta_count)   ← unchanged
  set_environment(environment: EnvironmentModel)          ← new

Emitted signals (forwarded by MainWindow to ScenarioService):
  path_loss_exponent_changed(float)
  reference_distance_changed(float)
  noise_floor_changed(float)
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from models.environment import EnvironmentModel


class EnvironmentSummaryTab(QWidget):
    """Environment / propagation panel shown in the property panel."""

    path_loss_exponent_changed = Signal(float)
    reference_distance_changed = Signal(float)
    noise_floor_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

        # ── Scene summary (read-only) ──────────────────────────────────────
        scene_group = QGroupBox("Scene Summary")
        scene_form = QFormLayout(scene_group)
        self.scene_size = QLabel("-")
        self.ap_count = QLabel("0")
        self.sta_count = QLabel("0")
        self.total_count = QLabel("0")
        scene_form.addRow("Scene Size", self.scene_size)
        scene_form.addRow("AP Count", self.ap_count)
        scene_form.addRow("STA Count", self.sta_count)
        scene_form.addRow("Total", self.total_count)
        root.addWidget(scene_group)

        # ── Propagation model (read-only label) ───────────────────────────
        model_group = QGroupBox("Propagation Model")
        model_form = QFormLayout(model_group)
        self._model_label = QLabel("Log-Distance (fixed)")
        model_form.addRow("Model:", self._model_label)
        root.addWidget(model_group)

        # ── Editable parameters ───────────────────────────────────────────
        params_group = QGroupBox("Parameters")
        params_form = QFormLayout(params_group)

        self._ple_spin = QDoubleSpinBox()
        self._ple_spin.setRange(1.0, 6.0)
        self._ple_spin.setDecimals(2)
        self._ple_spin.setSingleStep(0.1)
        self._ple_spin.setToolTip("Path-loss exponent (n). Typical: 2 free-space, 3–4 indoors.")
        params_form.addRow("Path-Loss Exp. (n):", self._ple_spin)

        self._ref_spin = QDoubleSpinBox()
        self._ref_spin.setRange(0.1, 100.0)
        self._ref_spin.setDecimals(2)
        self._ref_spin.setSuffix(" m")
        self._ref_spin.setToolTip("Reference distance d₀ (m) for log-distance model.")
        params_form.addRow("Reference Dist. (d₀):", self._ref_spin)

        self._nf_spin = QDoubleSpinBox()
        self._nf_spin.setRange(-120.0, -50.0)
        self._nf_spin.setDecimals(2)
        self._nf_spin.setSuffix(" dBm")
        self._nf_spin.setToolTip("Default noise floor used for SNR calculation.")
        params_form.addRow("Noise Floor:", self._nf_spin)

        root.addWidget(params_group)

        # ── Band profiles (editable) ──────────────────────────────────────
        band_group = QGroupBox("Band Profiles")
        band_form = QFormLayout(band_group)

        # 2.4 GHz
        self._freq_2g_spin = _make_freq_spin(2000.0, 2500.0, "2.4 GHz band centre frequency (MHz)")
        self._rl_2g_spin = _make_rl_spin("Free-space reference loss at d₀ for 2.4 GHz band (dB)")
        band_form.addRow("2.4 GHz Freq (MHz):", self._freq_2g_spin)
        band_form.addRow("2.4 GHz Ref Loss (dB):", self._rl_2g_spin)

        # 5 GHz
        self._freq_5g_spin = _make_freq_spin(5000.0, 5900.0, "5 GHz band centre frequency (MHz)")
        self._rl_5g_spin = _make_rl_spin("Free-space reference loss at d₀ for 5 GHz band (dB)")
        band_form.addRow("5 GHz Freq (MHz):", self._freq_5g_spin)
        band_form.addRow("5 GHz Ref Loss (dB):", self._rl_5g_spin)

        # 6 GHz
        self._freq_6g_spin = _make_freq_spin(5925.0, 7125.0, "6 GHz band centre frequency (MHz)")
        self._rl_6g_spin = _make_rl_spin("Free-space reference loss at d₀ for 6 GHz band (dB)")
        band_form.addRow("6 GHz Freq (MHz):", self._freq_6g_spin)
        band_form.addRow("6 GHz Ref Loss (dB):", self._rl_6g_spin)

        root.addWidget(band_group)
        root.addStretch(1)

        # Wire internal signals
        self._blocked = False
        self._ple_spin.editingFinished.connect(
            lambda: self._emit_if_unblocked(self.path_loss_exponent_changed, self._ple_spin.value())
        )
        self._ref_spin.editingFinished.connect(
            lambda: self._emit_if_unblocked(self.reference_distance_changed, self._ref_spin.value())
        )
        self._nf_spin.editingFinished.connect(
            lambda: self._emit_if_unblocked(self.noise_floor_changed, self._nf_spin.value())
        )
        # Band edits are not wired here — MainWindow can connect them separately if needed.
        # (They are visible but emit nothing in Phase B; future Phase C can add signals.)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def set_summary(self, width_m: float, height_m: float, ap_count: int, sta_count: int) -> None:
        """Update read-only scene summary section (Phase A API, preserved)."""
        self.scene_size.setText(f"{width_m:.1f} m × {height_m:.1f} m")
        self.ap_count.setText(str(ap_count))
        self.sta_count.setText(str(sta_count))
        self.total_count.setText(str(ap_count + sta_count))

    def set_environment(self, env: EnvironmentModel) -> None:
        """Populate editable fields from *env* without emitting change signals."""
        self._blocked = True
        try:
            self._ple_spin.setValue(env.path_loss_exponent)
            self._ref_spin.setValue(env.reference_distance_m)
            self._nf_spin.setValue(env.default_noise_floor_dbm)

            from models.enums import BandId
            for profile in env.band_profiles:
                if profile.band == BandId.BAND_2G4:
                    self._freq_2g_spin.setValue(profile.frequency_mhz)
                    self._rl_2g_spin.setValue(profile.reference_loss_db)
                elif profile.band == BandId.BAND_5G:
                    self._freq_5g_spin.setValue(profile.frequency_mhz)
                    self._rl_5g_spin.setValue(profile.reference_loss_db)
                elif profile.band == BandId.BAND_6G:
                    self._freq_6g_spin.setValue(profile.frequency_mhz)
                    self._rl_6g_spin.setValue(profile.reference_loss_db)
        finally:
            self._blocked = False

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _emit_if_unblocked(self, signal: Signal, value: float) -> None:
        if not self._blocked:
            signal.emit(value)


# ── Factory helpers ────────────────────────────────────────────────────────────

def _make_freq_spin(lo: float, hi: float, tip: str) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(lo, hi)
    spin.setDecimals(1)
    spin.setSuffix(" MHz")
    spin.setToolTip(tip)
    return spin


def _make_rl_spin(tip: str) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(0.0, 120.0)
    spin.setDecimals(4)
    spin.setSuffix(" dB")
    spin.setToolTip(tip)
    return spin
