import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLineEdit,
    QSizePolicy,
    QStackedWidget,
    QWidget,
)

from models.device import DeviceModel
from models.enums import DeviceType


def _ap_name_to_bss_id(name: str) -> str | None:
    """'AP-3' -> 'BSS3', custom names -> None."""
    m = re.fullmatch(r"AP-(\d+)", name, re.IGNORECASE)
    return f"BSS{m.group(1)}" if m else None


class _CompactStack(QStackedWidget):
    """QStackedWidget that sizes itself to the current page only."""

    def sizeHint(self):
        w = self.currentWidget()
        return w.sizeHint() if w else super().sizeHint()

    def minimumSizeHint(self):
        w = self.currentWidget()
        return w.minimumSizeHint() if w else super().minimumSizeHint()


class DeviceBasicTab(QWidget):
    name_changed = Signal(str)
    position_changed = Signal(float, float)
    bss_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._device_id: str | None = None
        self._device_type: DeviceType | None = None
        self._current_bss_id: str | None = None

        layout = QFormLayout(self)

        # ── Type ──────────────────────────────────────────────────────────────
        self.type_edit = QLineEdit()
        self.type_edit.setReadOnly(True)
        layout.addRow("Type", self.type_edit)

        # ── Name stack ────────────────────────────────────────────────────────
        # Page 0 (STA): combo listing STA-1, STA-2, ...
        self._sta_name_combo = QComboBox()

        # Page 1 (AP): combo listing AP-1, AP-2, ...
        self._ap_name_combo = QComboBox()

        self._name_stack = _CompactStack()
        self._name_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._name_stack.addWidget(self._sta_name_combo)   # index 0 = STA
        self._name_stack.addWidget(self._ap_name_combo)    # index 1 = AP
        layout.addRow("Name", self._name_stack)

        # ── Position ──────────────────────────────────────────────────────────
        self.x_edit = QLineEdit()
        self.y_edit = QLineEdit()
        layout.addRow("X (m)", self.x_edit)
        layout.addRow("Y (m)", self.y_edit)

        # ── BSS stack ─────────────────────────────────────────────────────────
        # Page 0 (STA): QComboBox to pick BSS
        self.bss_combo = QComboBox()

        # Page 1 (AP): read-only display of own BSS ID
        self.bss_readonly = QLineEdit()
        self.bss_readonly.setReadOnly(True)
        self.bss_readonly.setEnabled(False)

        self._bss_stack = _CompactStack()
        self._bss_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._bss_stack.addWidget(self.bss_combo)          # index 0 = STA
        self._bss_stack.addWidget(self.bss_readonly)       # index 1 = AP
        layout.addRow("BSS", self._bss_stack)

        # ── Signal connections ────────────────────────────────────────────────
        self._sta_name_combo.currentIndexChanged.connect(self._emit_sta_name_changed)
        self._ap_name_combo.currentIndexChanged.connect(self._emit_ap_name_changed)
        self.x_edit.editingFinished.connect(self._emit_position_changed)
        self.y_edit.editingFinished.connect(self._emit_position_changed)
        self.bss_combo.currentIndexChanged.connect(self._emit_bss_changed)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def set_ap_list(self, aps: list[DeviceModel]) -> None:
        """Update AP name combo and BSS combo. Called on any scene change."""
        # ── AP name combo ────────────────────────────────────────────────────
        current_ap_name = self._ap_name_combo.currentData()
        self._ap_name_combo.blockSignals(True)
        self._ap_name_combo.clear()
        for ap in aps:
            self._ap_name_combo.addItem(ap.name, ap.name)
        idx = self._ap_name_combo.findData(current_ap_name)
        self._ap_name_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._ap_name_combo.blockSignals(False)

        # ── BSS combo ────────────────────────────────────────────────────────
        current_bss = self.bss_combo.currentData()
        self.bss_combo.blockSignals(True)
        self.bss_combo.clear()
        self.bss_combo.addItem("-- not assigned --", "")
        for ap in aps:
            bss_id = _ap_name_to_bss_id(ap.name)
            if bss_id:
                self.bss_combo.addItem(bss_id, bss_id)
        target = current_bss if current_bss else (self._current_bss_id or "")
        idx = self.bss_combo.findData(target)
        self.bss_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.bss_combo.blockSignals(False)

    def set_sta_list(self, stas: list[DeviceModel]) -> None:
        """Update STA name combo. Called on any scene change."""
        current_sta_name = self._sta_name_combo.currentData()
        self._sta_name_combo.blockSignals(True)
        self._sta_name_combo.clear()
        for sta in stas:
            self._sta_name_combo.addItem(sta.name, sta.name)
        idx = self._sta_name_combo.findData(current_sta_name)
        self._sta_name_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._sta_name_combo.blockSignals(False)

    def set_device(self, device: DeviceModel | None) -> None:
        for widget in (self.x_edit, self.y_edit):
            widget.blockSignals(True)
        self._sta_name_combo.blockSignals(True)
        self._ap_name_combo.blockSignals(True)
        self.bss_combo.blockSignals(True)
        try:
            self._device_id = None if device is None else device.id
            self._device_type = None if device is None else device.device_type
            self._current_bss_id = None if device is None else device.bss_id

            enabled = device is not None
            for widget in (self.x_edit, self.y_edit):
                widget.setEnabled(enabled)

            if device is None:
                self.type_edit.setText("")
                self.x_edit.setText("")
                self.y_edit.setText("")
                self._name_stack.setCurrentIndex(0)
                self._bss_stack.setCurrentIndex(0)
                self.bss_combo.setEnabled(False)
                self.bss_readonly.setText("")
                return

            self.type_edit.setText(device.device_type.value)
            self.x_edit.setText(f"{device.x_m:.2f}")
            self.y_edit.setText(f"{device.y_m:.2f}")

            if device.device_type == DeviceType.AP:
                idx = self._ap_name_combo.findData(device.name)
                self._ap_name_combo.setCurrentIndex(idx if idx >= 0 else 0)
                self._name_stack.setCurrentIndex(1)        # AP page
                bss_id = _ap_name_to_bss_id(device.name)
                self.bss_readonly.setText(bss_id or "--")
                self.bss_readonly.setEnabled(True)
                self._bss_stack.setCurrentIndex(1)         # AP readonly
            else:
                idx = self._sta_name_combo.findData(device.name)
                self._sta_name_combo.setCurrentIndex(idx if idx >= 0 else 0)
                self._name_stack.setCurrentIndex(0)        # STA page
                self.bss_combo.setEnabled(True)
                self._bss_stack.setCurrentIndex(0)         # STA BSS combo
                idx = self.bss_combo.findData(device.bss_id or "")
                self.bss_combo.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            for widget in (self.x_edit, self.y_edit):
                widget.blockSignals(False)
            self._sta_name_combo.blockSignals(False)
            self._ap_name_combo.blockSignals(False)
            self.bss_combo.blockSignals(False)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _emit_sta_name_changed(self) -> None:
        if self._device_id is None or self._device_type != DeviceType.STA:
            return
        name = self._sta_name_combo.currentData()
        if name:
            self.name_changed.emit(name)

    def _emit_ap_name_changed(self) -> None:
        if self._device_id is None or self._device_type != DeviceType.AP:
            return
        name = self._ap_name_combo.currentData()
        if name:
            self.name_changed.emit(name)

    def _emit_position_changed(self) -> None:
        if self._device_id is None:
            return
        try:
            x_m = float(self.x_edit.text())
            y_m = float(self.y_edit.text())
        except ValueError:
            return
        self.position_changed.emit(x_m, y_m)

    def _emit_bss_changed(self) -> None:
        if self._device_id is None or self._device_type != DeviceType.STA:
            return
        bss_id = self.bss_combo.currentData() or ""
        self._current_bss_id = bss_id or None
        self.bss_changed.emit(bss_id)
