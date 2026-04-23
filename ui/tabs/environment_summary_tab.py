"""Environment tab — Phase B upgrade.

Combines the read-only scene-summary section from Phase A with newly
editable propagation-model parameters (path-loss exponent, reference
distance, manual noise override, and receiver noise figure).

Backward-compatible API:
  set_summary(width_m, height_m, ap_count, sta_count)   ← unchanged
  set_environment(environment: EnvironmentModel)        ← new
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from models.environment import EnvironmentModel, LEGACY_DEFAULT_NOISE_FLOOR_DBM


class EnvironmentSummaryTab(QWidget):
    """Environment / propagation panel shown in the property panel."""

    path_loss_exponent_changed = Signal(float)
    reference_distance_changed = Signal(float)
    manual_noise_floor_override_changed = Signal(object)
    rx_noise_figure_changed = Signal(float)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(8)

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

        model_group = QGroupBox("Propagation Model")
        model_form = QFormLayout(model_group)
        self._model_label = QLabel("Log-Distance (fixed)")
        model_form.addRow("Model:", self._model_label)
        root.addWidget(model_group)

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
        self._ref_spin.setToolTip("Reference distance d0 (m) for log-distance model.")
        params_form.addRow("Reference Dist. (d0):", self._ref_spin)

        self._manual_nf_enabled = QCheckBox("Enable manual global override")
        params_form.addRow("Manual Global Override:", self._manual_nf_enabled)

        self._nf_spin = QDoubleSpinBox()
        self._nf_spin.setRange(-120.0, -50.0)
        self._nf_spin.setDecimals(2)
        self._nf_spin.setSuffix(" dBm")
        self._nf_spin.setToolTip("Manual global noise floor override. When disabled, NF + width is used.")
        params_form.addRow("Override Value:", self._nf_spin)

        self._rx_nf_spin = QDoubleSpinBox()
        self._rx_nf_spin.setRange(0.0, 20.0)
        self._rx_nf_spin.setDecimals(2)
        self._rx_nf_spin.setSingleStep(0.1)
        self._rx_nf_spin.setSuffix(" dB")
        self._rx_nf_spin.setToolTip("Receiver noise figure used when no manual override is set.")
        params_form.addRow("Rx Noise Figure:", self._rx_nf_spin)

        root.addWidget(params_group)

        band_group = QGroupBox("Band Profiles")
        band_form = QFormLayout(band_group)

        self._freq_2g_spin = _make_freq_spin(2000.0, 2500.0, "2.4 GHz band centre frequency (MHz)")
        self._rl_2g_spin = _make_rl_spin("Free-space reference loss at d0 for 2.4 GHz band (dB)")
        self._nf_2g_label = QLabel("Auto")
        band_form.addRow("2.4 GHz Freq (MHz):", self._freq_2g_spin)
        band_form.addRow("2.4 GHz Ref Loss (dB):", self._rl_2g_spin)
        band_form.addRow("2.4 GHz Manual NF:", self._nf_2g_label)

        self._freq_5g_spin = _make_freq_spin(5000.0, 5900.0, "5 GHz band centre frequency (MHz)")
        self._rl_5g_spin = _make_rl_spin("Free-space reference loss at d0 for 5 GHz band (dB)")
        self._nf_5g_label = QLabel("Auto")
        band_form.addRow("5 GHz Freq (MHz):", self._freq_5g_spin)
        band_form.addRow("5 GHz Ref Loss (dB):", self._rl_5g_spin)
        band_form.addRow("5 GHz Manual NF:", self._nf_5g_label)

        self._freq_6g_spin = _make_freq_spin(5925.0, 7125.0, "6 GHz band centre frequency (MHz)")
        self._rl_6g_spin = _make_rl_spin("Free-space reference loss at d0 for 6 GHz band (dB)")
        self._nf_6g_label = QLabel("Auto")
        band_form.addRow("6 GHz Freq (MHz):", self._freq_6g_spin)
        band_form.addRow("6 GHz Ref Loss (dB):", self._rl_6g_spin)
        band_form.addRow("6 GHz Manual NF:", self._nf_6g_label)

        root.addWidget(band_group)
        root.addStretch(1)

        self._blocked = False
        self._ple_spin.editingFinished.connect(
            lambda: self._emit_if_unblocked(self.path_loss_exponent_changed, self._ple_spin.value())
        )
        self._ref_spin.editingFinished.connect(
            lambda: self._emit_if_unblocked(self.reference_distance_changed, self._ref_spin.value())
        )
        self._manual_nf_enabled.toggled.connect(self._on_manual_noise_toggle)
        self._nf_spin.editingFinished.connect(self._on_manual_noise_value_changed)
        self._rx_nf_spin.editingFinished.connect(
            lambda: self._emit_if_unblocked(self.rx_noise_figure_changed, self._rx_nf_spin.value())
        )

    def set_summary(self, width_m: float, height_m: float, ap_count: int, sta_count: int) -> None:
        self.scene_size.setText(f"{width_m:.1f} m x {height_m:.1f} m")
        self.ap_count.setText(str(ap_count))
        self.sta_count.setText(str(sta_count))
        self.total_count.setText(str(ap_count + sta_count))

    def set_environment(self, env: EnvironmentModel) -> None:
        self._blocked = True
        try:
            self._ple_spin.setValue(env.path_loss_exponent)
            self._ref_spin.setValue(env.reference_distance_m)
            has_override = env.manual_global_noise_floor_dbm is not None
            self._manual_nf_enabled.setChecked(has_override)
            self._nf_spin.setEnabled(has_override)
            self._nf_spin.setValue(
                env.manual_global_noise_floor_dbm
                if env.manual_global_noise_floor_dbm is not None
                else LEGACY_DEFAULT_NOISE_FLOOR_DBM
            )
            self._rx_nf_spin.setValue(env.rx_noise_figure_db)

            from models.enums import BandId

            for profile in env.band_profiles:
                manual_nf_text = (
                    f"{profile.manual_noise_floor_dbm:.2f} dBm"
                    if profile.manual_noise_floor_dbm is not None
                    else "Auto"
                )
                if profile.band == BandId.BAND_2G4:
                    self._freq_2g_spin.setValue(profile.frequency_mhz)
                    self._rl_2g_spin.setValue(profile.reference_loss_db)
                    self._nf_2g_label.setText(manual_nf_text)
                elif profile.band == BandId.BAND_5G:
                    self._freq_5g_spin.setValue(profile.frequency_mhz)
                    self._rl_5g_spin.setValue(profile.reference_loss_db)
                    self._nf_5g_label.setText(manual_nf_text)
                elif profile.band == BandId.BAND_6G:
                    self._freq_6g_spin.setValue(profile.frequency_mhz)
                    self._rl_6g_spin.setValue(profile.reference_loss_db)
                    self._nf_6g_label.setText(manual_nf_text)
        finally:
            self._blocked = False

    def _emit_if_unblocked(self, signal: Signal, value: float) -> None:
        if not self._blocked:
            signal.emit(value)

    def _on_manual_noise_toggle(self, checked: bool) -> None:
        self._nf_spin.setEnabled(checked)
        if not self._blocked:
            self.manual_noise_floor_override_changed.emit(
                self._nf_spin.value() if checked else None
            )

    def _on_manual_noise_value_changed(self) -> None:
        if not self._blocked and self._manual_nf_enabled.isChecked():
            self.manual_noise_floor_override_changed.emit(self._nf_spin.value())


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
