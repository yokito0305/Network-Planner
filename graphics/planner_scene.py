import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
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

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        scene_rect = self.sceneRect()
        painter.fillRect(scene_rect, QColor("#F8FAFC"))
        scenario = self.scenario_service.scenario

        # Adaptive grid: choose spacing based on current pixels-per-metre scale
        scale = painter.transform().m11()
        grid_m = self._grid_spacing_m(scale)

        # Lighter, semi-transparent grid lines (alpha=90/255 ≈ 35%)
        grid_color = QColor(200, 212, 228, 90)
        grid_pen = QPen(grid_color)
        grid_pen.setCosmetic(True)     # always exactly 1 screen-pixel wide
        axis_pen = QPen(QColor("#94A3B8"), 0.7)

        # Clip drawing region to visible area intersected with scene bounds
        clip = scene_rect.intersected(rect)
        x0, x1 = clip.left(), clip.right()
        y0, y1 = clip.top(), clip.bottom()

        painter.setPen(grid_pen)

        # Vertical lines — only those visible in current viewport
        vx = math.floor(x0 / grid_m) * grid_m
        while vx <= x1 + 1e-9:
            if 0.0 <= vx <= scenario.width_m:
                painter.drawLine(QPointF(vx, 0.0), QPointF(vx, scenario.height_m))
            vx += grid_m

        # Horizontal lines — only those visible in current viewport
        vy = math.floor(y0 / grid_m) * grid_m
        while vy <= y1 + 1e-9:
            if 0.0 <= vy <= scenario.height_m:
                painter.drawLine(QPointF(0.0, vy), QPointF(scenario.width_m, vy))
            vy += grid_m

        # Border rect — cosmetic so it stays 1 px regardless of zoom
        border_pen = QPen(QColor("#94A3B8"))
        border_pen.setCosmetic(True)
        painter.setPen(border_pen)
        painter.drawRect(scene_rect)

        # ── Axis labels & arrows in device (screen-pixel) coordinates ─────
        # Map the four scene corners to screen pixels, then reset transform
        # so text and arrows stay a fixed size regardless of zoom.
        xf = painter.transform()
        bl = xf.map(QPointF(scene_rect.left(),  scene_rect.bottom()))  # (0,0) origin
        br = xf.map(QPointF(scene_rect.right(), scene_rect.bottom()))  # +X corner
        tl = xf.map(QPointF(scene_rect.left(),  scene_rect.top()))     # +Y corner

        painter.save()
        painter.resetTransform()

        label_pen = QPen(QColor("#64748B"))
        label_pen.setCosmetic(True)
        painter.setPen(label_pen)

        inset = 5
        lh = 13   # label height in pixels

        # (0,0) — bottom-left
        painter.drawText(
            QRectF(bl.x() + inset, bl.y() - lh - inset, 52, lh),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "(0,0)",
        )

        # X label + right-pointing arrow — bottom-right
        arrow_len = 18
        ax = br.x() - inset
        ay = br.y() - lh / 2 - inset
        painter.drawLine(QPointF(ax - arrow_len, ay), QPointF(ax, ay))
        painter.drawPolygon(QPolygonF([
            QPointF(ax,       ay),
            QPointF(ax - 6,   ay - 3),
            QPointF(ax - 6,   ay + 3),
        ]))
        painter.drawText(
            QRectF(br.x() - 60, br.y() - lh - inset, 38, lh),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"X  {scenario.width_m:.0f} m",
        )

        # Y label + up-pointing arrow — top-left
        ay2 = tl.y() + inset
        ax2 = tl.x() + inset + lh / 2
        painter.drawLine(QPointF(ax2, ay2 + arrow_len), QPointF(ax2, ay2))
        painter.drawPolygon(QPolygonF([
            QPointF(ax2,     ay2),
            QPointF(ax2 - 3, ay2 + 6),
            QPointF(ax2 + 3, ay2 + 6),
        ]))
        painter.drawText(
            QRectF(tl.x() + inset, tl.y() + arrow_len + inset + 2, 72, lh),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"Y  {scenario.height_m:.0f} m",
        )

        painter.restore()

    @staticmethod
    def _grid_spacing_m(scale: float) -> float:
        """Choose grid spacing in metres based on pixels-per-metre scale.

        Finer steps than Phase A to give a denser, more readable grid:
          scale > 200 px/m → 0.5 m
          scale > 100       → 1 m
          scale > 40        → 2 m
          scale > 15        → 5 m
          scale >  5        → 10 m
          scale >  2        → 25 m
          else              → 50 m
        """
        if scale > 200:
            return 0.5
        if scale > 100:
            return 1.0
        if scale > 40:
            return 2.0
        if scale > 15:
            return 5.0
        if scale > 5:
            return 10.0
        if scale > 2:
            return 25.0
        return 50.0

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
