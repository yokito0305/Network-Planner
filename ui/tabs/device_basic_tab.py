from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFormLayout, QLineEdit, QWidget

from models.device import DeviceModel


class DeviceBasicTab(QWidget):
    name_changed = Signal(str)
    position_changed = Signal(float, float)

    def __init__(self) -> None:
        super().__init__()
        self._device_id: str | None = None

        layout = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.type_edit = QLineEdit()
        self.type_edit.setReadOnly(True)
        self.x_edit = QLineEdit()
        self.y_edit = QLineEdit()

        layout.addRow("Name", self.name_edit)
        layout.addRow("Type", self.type_edit)
        layout.addRow("X (m)", self.x_edit)
        layout.addRow("Y (m)", self.y_edit)

        self.name_edit.editingFinished.connect(self._emit_name_changed)
        self.x_edit.editingFinished.connect(self._emit_position_changed)
        self.y_edit.editingFinished.connect(self._emit_position_changed)

    def set_device(self, device: DeviceModel | None) -> None:
        # Block editingFinished to prevent cascading signals during
        # programmatic updates (avoids crash when focus shifts away from
        # a QLineEdit right before a node-list click rebuilds items).
        for widget in (self.name_edit, self.x_edit, self.y_edit):
            widget.blockSignals(True)
        try:
            self._device_id = None if device is None else device.id
            enabled = device is not None
            for widget in (self.name_edit, self.x_edit, self.y_edit):
                widget.setEnabled(enabled)
            if device is None:
                self.name_edit.setText("")
                self.type_edit.setText("")
                self.x_edit.setText("")
                self.y_edit.setText("")
                return
            self.name_edit.setText(device.name)
            self.type_edit.setText(device.device_type.value)
            self.x_edit.setText(f"{device.x_m:.2f}")
            self.y_edit.setText(f"{device.y_m:.2f}")
        finally:
            for widget in (self.name_edit, self.x_edit, self.y_edit):
                widget.blockSignals(False)

    def _emit_name_changed(self) -> None:
        if self._device_id is None:
            return
        self.name_changed.emit(self.name_edit.text())

    def _emit_position_changed(self) -> None:
        if self._device_id is None:
            return
        try:
            x_m = float(self.x_edit.text())
            y_m = float(self.y_edit.text())
        except ValueError:
            return
        self.position_changed.emit(x_m, y_m)
