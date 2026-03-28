from PySide6.QtCore import QPointF, QRectF, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from models.device import DeviceModel
from models.enums import DeviceType


class DeviceItem(QGraphicsObject):
    moved = Signal(str, float, float)
    selected = Signal(str)

    def __init__(self, device: DeviceModel, radius: float = 3.0) -> None:
        super().__init__()
        self.device_id = device.id
        self._radius = radius
        self._name = device.name
        self._device_type = device.device_type
        self._label_mode = "selected_only"
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
        )
        self.setZValue(10)
        self._update_tooltip()

    def boundingRect(self) -> QRectF:
        return QRectF(-14.0, -20.0, 92.0, 40.0)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        marker_radius = self._radius + 1.5
        path.addEllipse(QPointF(0.0, 0.0), marker_radius, marker_radius)
        return path

    def contains(self, point: QPointF) -> bool:
        return self.shape().contains(point)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        del option, widget
        fill = QColor("#3B82F6") if self._device_type == DeviceType.AP else QColor("#10B981")
        pen = QPen(QColor("#111827") if self.isSelected() else QColor("#374151"), 0.8)
        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        painter.drawEllipse(QPointF(0.0, 0.0), self._radius, self._radius)
        if self._should_show_label():
            font = painter.font()
            font.setPointSizeF(max(font.pointSizeF() - 1.0, 8.0))
            painter.setFont(font)
            painter.setPen(QPen(QColor("#334155")))
            painter.drawText(QRectF(4.0, -16.0, 72.0, 16.0), self._name)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged and bool(value):
            self.selected.emit(self.device_id)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            position = value if isinstance(value, QPointF) else self.pos()
            self.moved.emit(self.device_id, position.x(), position.y())
        return super().itemChange(change, value)

    def sync_from_device(self, device: DeviceModel) -> None:
        self._name = device.name
        self._device_type = device.device_type
        self._update_tooltip()
        self.update()

    def set_label_mode(self, mode: str) -> None:
        self._label_mode = mode
        self.update()

    def _should_show_label(self) -> bool:
        if self._label_mode == "all":
            return True
        if self._label_mode == "hidden":
            return False
        return self.isSelected()

    def _update_tooltip(self) -> None:
        self.setToolTip(f"{self._name}\nType: {self._device_type.value}")
        self.update()
