"""Deployment Tab — polar-coordinate device placement tool.

Usage flow:
  1. Select target device (follows canvas selection automatically)
  2. Select anchor device (independent, does not affect canvas selection)
  3. Adjust distance (Slider + SpinBox + arrow keys) keeping angle fixed
  4. Adjust angle   (Slider + SpinBox + arrow keys) keeping distance fixed
  5. Summary section shows live distance / angle / RSSI between the pair
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
    QLineEdit,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from models.device import DeviceModel


def _dist(a: DeviceModel, b: DeviceModel) -> float:
    return math.hypot(a.x_m - b.x_m, a.y_m - b.y_m)


def _angle_deg(anchor: DeviceModel, target: DeviceModel) -> float:
    """Angle from anchor to target: 0°=East, CCW positive, range [0, 360)."""
    dx = target.x_m - anchor.x_m
    dy = target.y_m - anchor.y_m
    deg = math.degrees(math.atan2(dy, dx))
    return deg % 360.0


def _polar_to_xy(anchor: DeviceModel, dist_m: float, angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg)
    return anchor.x_m + dist_m * math.cos(rad), anchor.y_m + dist_m * math.sin(rad)


class _SliderSpinRow(QWidget):
    """A paired horizontal QSlider + QDoubleSpinBox that stay in sync."""

    value_changed = Signal(float)   # emitted only on user interaction

    def __init__(
        self,
        min_val: float,
        max_val: float,
        decimals: int,
        suffix: str,
        step: float,
        page_step: float,
    ) -> None:
        super().__init__()
        self._min = min_val
        self._max = max_val
        self._decimals = decimals
        self._scale = 10 ** decimals   # integer ticks per unit

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(round(min_val * self._scale))
        self._slider.setMaximum(round(max_val * self._scale))
        self._slider.setSingleStep(round(step * self._scale))
        self._slider.setPageStep(round(page_step * self._scale))
        layout.addWidget(self._slider, stretch=1)

        self._spin = QDoubleSpinBox()
        self._spin.setMinimum(min_val)
        self._spin.setMaximum(max_val)
        self._spin.setDecimals(decimals)
        self._spin.setSuffix(suffix)
        self._spin.setSingleStep(step)
        self._spin.setFixedWidth(90)
        layout.addWidget(self._spin)

        # Wire: slider ↔ spin (both ways, guard against recursion)
        self._updating = False
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spin.valueChanged.connect(self._on_spin_changed)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_range(self, min_val: float, max_val: float) -> None:
        self._min = min_val
        self._max = max_val
        self._slider.setMinimum(round(min_val * self._scale))
        self._slider.setMaximum(round(max_val * self._scale))
        self._spin.setMinimum(min_val)
        self._spin.setMaximum(max_val)

    def set_value(self, value: float) -> None:
        """Set value without emitting value_changed."""
        self._updating = True
        clamped = max(self._min, min(self._max, value))
        self._spin.setValue(clamped)
        self._slider.setValue(round(clamped * self._scale))
        self._updating = False

    def value(self) -> float:
        return self._spin.value()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_slider_changed(self, tick: int) -> None:
        if self._updating:
            return
        val = tick / self._scale
        self._updating = True
        self._spin.setValue(val)
        self._updating = False
        self.value_changed.emit(val)

    def _on_spin_changed(self, val: float) -> None:
        if self._updating:
            return
        self._updating = True
        self._slider.setValue(round(val * self._scale))
        self._updating = False
        self.value_changed.emit(val)


class DeploymentTab(QWidget):
    """Polar-coordinate deployment tool (left-panel tab)."""

    # Emitted when the user wants to move the target device
    move_requested = Signal(str, float, float)   # device_id, x_m, y_m

    def __init__(self) -> None:
        super().__init__()
        self._devices: list[DeviceModel] = []
        self._target_id: str | None = None
        self._anchor_id: str | None = None
        self._applying = False          # guard against feedback loops

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # ── Device selection ──────────────────────────────────────────────
        sel_group = QGroupBox("裝置選擇")
        sel_form = QFormLayout(sel_group)
        sel_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._target_combo = QComboBox()
        self._target_combo.addItem("-- 未選取 --", None)
        sel_form.addRow("目標裝置", self._target_combo)

        self._anchor_combo = QComboBox()
        self._anchor_combo.addItem("-- 未選取 --", None)
        sel_form.addRow("錨點裝置", self._anchor_combo)

        layout.addWidget(sel_group)

        # ── Polar adjustment ──────────────────────────────────────────────
        adj_group = QGroupBox("極座標調整")
        adj_layout = QVBoxLayout(adj_group)
        adj_layout.setSpacing(6)

        adj_form = QFormLayout()
        adj_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)

        self._dist_row = _SliderSpinRow(
            min_val=0.0, max_val=300.0,
            decimals=1, suffix=" m",
            step=1.0, page_step=10.0,
        )
        adj_form.addRow("距離", self._dist_row)

        self._angle_row = _SliderSpinRow(
            min_val=0.0, max_val=359.9,
            decimals=1, suffix=" °",
            step=1.0, page_step=15.0,
        )
        adj_form.addRow("角度", self._angle_row)

        adj_layout.addLayout(adj_form)
        layout.addWidget(adj_group)

        # ── Summary ───────────────────────────────────────────────────────
        sum_group = QGroupBox("即時摘要")
        sum_form = QFormLayout(sum_group)

        self._sum_dist  = QLineEdit("--")
        self._sum_dist.setReadOnly(True)
        self._sum_angle = QLineEdit("--")
        self._sum_angle.setReadOnly(True)
        self._sum_target_xy = QLineEdit("--")
        self._sum_target_xy.setReadOnly(True)

        sum_form.addRow("距離", self._sum_dist)
        sum_form.addRow("角度", self._sum_angle)
        sum_form.addRow("目標座標", self._sum_target_xy)

        layout.addWidget(sum_group)
        layout.addStretch()

        # ── Wire signals ──────────────────────────────────────────────────
        self._target_combo.currentIndexChanged.connect(self._on_combo_changed)
        self._anchor_combo.currentIndexChanged.connect(self._on_combo_changed)
        self._dist_row.value_changed.connect(self._on_dist_changed)
        self._angle_row.value_changed.connect(self._on_angle_changed)

    # =========================================================================
    # Public API
    # =========================================================================

    def refresh_devices(self, devices: list[DeviceModel]) -> None:
        """Rebuild combo lists. Preserve current selections if still valid."""
        self._devices = list(devices)
        prev_target = self._target_id
        prev_anchor = self._anchor_id

        self._target_combo.blockSignals(True)
        self._anchor_combo.blockSignals(True)

        self._target_combo.clear()
        self._anchor_combo.clear()
        self._target_combo.addItem("-- 未選取 --", None)
        self._anchor_combo.addItem("-- 未選取 --", None)

        for d in devices:
            self._target_combo.addItem(d.name, d.id)
            self._anchor_combo.addItem(d.name, d.id)

        # Restore or reset
        self._target_id = prev_target if self._find_device(prev_target) else None
        self._anchor_id = prev_anchor if self._find_device(prev_anchor) else None

        self._select_combo(self._target_combo, self._target_id)
        self._select_combo(self._anchor_combo, self._anchor_id)

        self._target_combo.blockSignals(False)
        self._anchor_combo.blockSignals(False)

        self._sync_controls()

    def set_selected_device(self, device_id: str | None) -> None:
        """Called when canvas selection changes — update target combo only."""
        if device_id == self._target_id:
            return
        # Re-click same target → deselect
        self._target_id = device_id
        self._target_combo.blockSignals(True)
        self._select_combo(self._target_combo, device_id)
        self._target_combo.blockSignals(False)
        self._sync_controls()

    def on_device_updated(self, device: DeviceModel) -> None:
        """Called when any device moves — refresh summary & controls if relevant."""
        # Update name in combos if changed
        for combo in (self._target_combo, self._anchor_combo):
            for i in range(combo.count()):
                if combo.itemData(i) == device.id:
                    combo.setItemText(i, device.name)
                    break

        if device.id in (self._target_id, self._anchor_id):
            self._sync_controls()

    def set_scene_diagonal(self, diagonal_m: float) -> None:
        """Update distance slider max to scene diagonal."""
        self._dist_row.set_range(0.0, max(diagonal_m, 1.0))

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _find_device(self, device_id: str | None) -> DeviceModel | None:
        if device_id is None:
            return None
        return next((d for d in self._devices if d.id == device_id), None)

    def _select_combo(self, combo: QComboBox, device_id: str | None) -> None:
        idx = combo.findData(device_id)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _sync_controls(self) -> None:
        """Read current target/anchor positions and update sliders + summary."""
        target = self._find_device(self._target_id)
        anchor = self._find_device(self._anchor_id)

        enabled = target is not None and anchor is not None and target.id != anchor.id
        self._dist_row.setEnabled(enabled)
        self._angle_row.setEnabled(enabled)

        if not enabled:
            self._sum_dist.setText("--")
            self._sum_angle.setText("--")
            self._sum_target_xy.setText("--")
            return

        dist  = _dist(anchor, target)
        angle = _angle_deg(anchor, target)

        self._applying = True
        self._dist_row.set_value(dist)
        self._angle_row.set_value(angle)
        self._applying = False

        self._update_summary(target, anchor, dist, angle)

    def _update_summary(
        self,
        target: DeviceModel,
        anchor: DeviceModel,
        dist: float,
        angle: float,
    ) -> None:
        self._sum_dist.setText(f"{dist:.2f} m")
        self._sum_angle.setText(f"{angle:.2f} °")
        self._sum_target_xy.setText(f"({target.x_m:.2f}, {target.y_m:.2f})")

    def _on_combo_changed(self) -> None:
        self._target_id = self._target_combo.currentData()
        self._anchor_id = self._anchor_combo.currentData()
        self._sync_controls()

    def _on_dist_changed(self, dist_m: float) -> None:
        if self._applying:
            return
        target = self._find_device(self._target_id)
        anchor = self._find_device(self._anchor_id)
        if target is None or anchor is None or target.id == anchor.id:
            return
        angle = _angle_deg(anchor, target)
        x, y = _polar_to_xy(anchor, dist_m, angle)
        self.move_requested.emit(target.id, x, y)

    def _on_angle_changed(self, angle_deg: float) -> None:
        if self._applying:
            return
        target = self._find_device(self._target_id)
        anchor = self._find_device(self._anchor_id)
        if target is None or anchor is None or target.id == anchor.id:
            return
        dist = _dist(anchor, target)
        x, y = _polar_to_xy(anchor, dist, angle_deg)
        self.move_requested.emit(target.id, x, y)
