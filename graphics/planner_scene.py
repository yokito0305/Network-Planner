from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene

from graphics.device_item import DeviceItem
from models.device import DeviceModel
from models.enums import DeviceType
from services.scenario_service import ScenarioService
from services.scene_transform import SceneTransform
from services.selection_service import SelectionService


class PlannerScene(QGraphicsScene):
    mouse_world_changed = Signal(float, float)

    def __init__(
        self,
        scenario_service: ScenarioService,
        selection_service: SelectionService,
        transform: SceneTransform,
    ) -> None:
        super().__init__()
        self.scenario_service = scenario_service
        self.selection_service = selection_service
        self.transform = transform
        self._items_by_id: dict[str, DeviceItem] = {}
        self._label_mode = "selected_only"

        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.setSceneRect(self.transform.scene_rect(self.scenario_service.scenario))

        self.scenario_service.device_added.connect(self._on_device_added)
        self.scenario_service.device_updated.connect(self._on_device_updated)
        self.scenario_service.device_removed.connect(self._on_device_removed)
        self.scenario_service.scenario_replaced.connect(self._rebuild_from_scenario)
        self.selection_service.selection_changed.connect(self._on_selection_changed)
        self.selectionChanged.connect(self._sync_selection_from_scene)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasText():
            super().dropEvent(event)
            return
        try:
            device_type = DeviceType(event.mimeData().text())
        except ValueError:
            event.ignore()
            return
        x_m, y_m = self.transform.scene_to_world(self.scenario_service.scenario, event.scenePos())
        self.scenario_service.add_device(device_type, x_m, y_m)
        event.acceptProposedAction()

    def mouseMoveEvent(self, event) -> None:
        x_m, y_m = self.transform.scene_to_world(self.scenario_service.scenario, event.scenePos())
        self.mouse_world_changed.emit(x_m, y_m)
        super().mouseMoveEvent(event)

    def drawBackground(self, painter: QPainter, rect) -> None:
        del rect
        scene_rect = self.sceneRect()
        painter.fillRect(scene_rect, QColor("#F8FAFC"))
        scenario = self.scenario_service.scenario
        grid_pen = QPen(QColor("#E2E8F0"))
        axis_pen = QPen(QColor("#94A3B8"), 0.7)

        painter.setPen(grid_pen)
        for x in range(0, int(scenario.width_m) + 1, 10):
            painter.drawLine(x, 0, x, scenario.height_m)
        for y in range(0, int(scenario.height_m) + 1, 10):
            painter.drawLine(0, y, scenario.width_m, y)

        painter.setPen(axis_pen)
        painter.drawRect(scene_rect)

        inset = 4.0
        painter.drawText(
            QRectF(inset, scene_rect.bottom() - 18.0, 48.0, 14.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "(0,0)",
        )
        painter.drawText(
            QRectF(scene_rect.right() - 52.0, scene_rect.bottom() - 18.0, 48.0, 14.0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"X:{scenario.width_m:.0f}",
        )
        painter.drawText(
            QRectF(inset, inset, 52.0, 14.0),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"Y:{scenario.height_m:.0f}",
        )

    def _create_item(self, device: DeviceModel) -> DeviceItem:
        item = DeviceItem(device)
        item.setPos(self.transform.world_to_scene(self.scenario_service.scenario, device.x_m, device.y_m))
        item.moved.connect(self._on_item_moved)
        item.selected.connect(self.selection_service.set_selected_device_id)
        return item

    def _on_device_added(self, device: DeviceModel) -> None:
        item = self._create_item(device)
        item.set_label_mode(self._label_mode)
        self._items_by_id[device.id] = item
        self.addItem(item)
        if self.selection_service.selected_device_id == device.id:
            item.setSelected(True)

    def _on_device_updated(self, device: DeviceModel) -> None:
        item = self._items_by_id.get(device.id)
        if item is None:
            return
        item.blockSignals(True)
        item.setPos(self.transform.world_to_scene(self.scenario_service.scenario, device.x_m, device.y_m))
        item.blockSignals(False)
        item.sync_from_device(device)

    def _on_device_removed(self, device_id: str) -> None:
        item = self._items_by_id.pop(device_id, None)
        if item is None:
            return
        self.removeItem(item)

    def _on_selection_changed(self, device_id: str | None) -> None:
        for current_id, item in self._items_by_id.items():
            item.setSelected(current_id == device_id)
            item.set_label_mode(self._label_mode)

    def _on_item_moved(self, device_id: str, scene_x: float, scene_y: float) -> None:
        x_m, y_m = self.transform.scene_to_world(
            self.scenario_service.scenario,
            QPointF(scene_x, scene_y),
        )
        self.scenario_service.move_device(device_id, x_m, y_m)

    def _rebuild_from_scenario(self) -> None:
        self.clear()
        self._items_by_id.clear()
        self.setSceneRect(self.transform.scene_rect(self.scenario_service.scenario))
        for device in self.scenario_service.list_devices():
            self._on_device_added(device)

    def _sync_selection_from_scene(self) -> None:
        selected_items = self.selectedItems()
        if not selected_items:
            self.selection_service.set_selected_device_id(None)
            return
        first = selected_items[0]
        if isinstance(first, DeviceItem):
            self.selection_service.set_selected_device_id(first.device_id)

    def set_label_mode(self, mode: str) -> None:
        self._label_mode = mode
        for item in self._items_by_id.values():
            item.set_label_mode(mode)
