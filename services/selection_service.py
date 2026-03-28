from PySide6.QtCore import QObject, Signal


class SelectionService(QObject):
    selection_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._selected_device_id: str | None = None

    @property
    def selected_device_id(self) -> str | None:
        return self._selected_device_id

    def set_selected_device_id(self, device_id: str | None) -> None:
        if self._selected_device_id == device_id:
            return
        self._selected_device_id = device_id
        self.selection_changed.emit(device_id)
